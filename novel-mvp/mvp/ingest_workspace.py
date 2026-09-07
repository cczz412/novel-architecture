"""把 M1 纯内存结果持久化到已经绑定作者与项目的 AuthorWorkspace。

适配器不接路径、作者 ID 或项目 ID；身份、隔离、原子提交和云端替换点全部留在
workspace 句柄及其 backend。原始上传 bytes 只进入 raw_upload immutable store。
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from typing import Any

from mvp.upload_source import CLOUD_SWAP_POINT, UploadSource
from mvp.workspace import AuthorWorkspace


VISIBLE_KEYS = {"input_manifest", "module_state"}
UPLOAD_RECORD_KEYS = {
    "source_name",
    "raw_bytes",
    "source_sha256",
    "bytes",
    "declarations",
    "encoding_hint",
    "cloud_swap_point",
}
LEGACY_UPLOAD_RECORD_KEYS = UPLOAD_RECORD_KEYS - {"declarations"}
PERSISTED_UPLOAD_RECORD_KEYS = {
    "source_name",
    "source_sha256",
    "bytes",
    "declarations",
    "encoding_hint",
    "cloud_swap_point",
    "immutable_receipt",
}
IMMUTABLE_RECEIPT_KEYS = {
    "blob_id",
    "kind",
    "content_sha256",
    "size",
    "metadata_sha256",
}
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class IngestWorkspaceError(ValueError):
    """M1 结果尚未满足工作区持久化前置条件。"""


def _validated_upload_records(m1_result: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = m1_result.get("upload_objects")
    if not isinstance(records, list) or not records:
        raise IngestWorkspaceError("M1_UPLOAD_OBJECTS_REQUIRED")
    format_receipt = m1_result.get("format_receipt")
    if (
        not isinstance(format_receipt, dict)
        or format_receipt.get("status") != "READY"
        or format_receipt.get("upload_objects") != records
    ):
        raise IngestWorkspaceError("M1_FORMAT_RECEIPT_MISMATCH")
    validated: list[dict[str, Any]] = []
    names: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise IngestWorkspaceError("M1_UPLOAD_RECORD_INVALID")
        record_keys = frozenset(record)
        if record_keys not in {
            frozenset(UPLOAD_RECORD_KEYS),
            frozenset(LEGACY_UPLOAD_RECORD_KEYS),
        }:
            raise IngestWorkspaceError("M1_UPLOAD_RECORD_INVALID")
        normalized = copy.deepcopy(record)
        normalized.setdefault("declarations", None)
        source = UploadSource(
            source_name=normalized["source_name"],
            raw_bytes=normalized["raw_bytes"],
            declarations=normalized["declarations"],
            encoding_hint=normalized["encoding_hint"],
        )
        if (
            normalized["source_sha256"] != source.sha256
            or normalized["bytes"] != len(source.raw_bytes)
            or normalized["declarations"] != source.declarations
            or normalized["cloud_swap_point"] != CLOUD_SWAP_POINT
        ):
            raise IngestWorkspaceError("M1_UPLOAD_RECORD_INTEGRITY_MISMATCH")
        if source.source_name in names:
            raise IngestWorkspaceError("M1_UPLOAD_SOURCE_NAME_DUPLICATE")
        names.add(source.source_name)
        validated.append(normalized)
    return validated


def _persistable_result(
    m1_result: Mapping[str, Any],
    manifest_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = copy.deepcopy(dict(m1_result))
    candidate["upload_objects"] = copy.deepcopy(manifest_entries)
    candidate["format_receipt"]["upload_objects"] = copy.deepcopy(
        manifest_entries
    )
    sources = candidate.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if isinstance(source, dict):
                source.pop("original_bytes_base64", None)
    return candidate


def _json_preflight(m1_result: Mapping[str, Any], records: list[dict[str, Any]]) -> None:
    placeholders = [
        {
            "source_name": record["source_name"],
            "source_sha256": record["source_sha256"],
            "bytes": record["bytes"],
            "declarations": copy.deepcopy(record["declarations"]),
            "encoding_hint": record["encoding_hint"],
            "cloud_swap_point": record["cloud_swap_point"],
        }
        for record in records
    ]
    candidate = _persistable_result(m1_result, placeholders)
    try:
        json.dumps(candidate, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise IngestWorkspaceError("M1_RESULT_NOT_JSON_SERIALIZABLE") from exc


def persist_m1_result(
    workspace: AuthorWorkspace,
    operation_id: str,
    m1_result: Mapping[str, Any],
    expected_versions: Mapping[str, Any],
) -> dict[str, Any]:
    """保存 raw uploads，再原子提交 input_manifest 与当前 M1 结构化结果。"""
    if not isinstance(workspace, AuthorWorkspace):
        raise IngestWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    if not isinstance(m1_result, Mapping):
        raise IngestWorkspaceError("M1_RESULT_MAPPING_REQUIRED")
    if not isinstance(expected_versions, Mapping) or set(expected_versions) != VISIBLE_KEYS:
        raise IngestWorkspaceError("M1_EXPECTED_VERSION_KEYS_MISMATCH")
    records = _validated_upload_records(m1_result)
    _json_preflight(m1_result, records)

    manifest_entries = []
    for record in records:
        immutable_receipt = workspace.store_immutable(
            "raw_upload",
            record["raw_bytes"],
            {
                "source_name": record["source_name"],
                "source_sha256": record["source_sha256"],
                "bytes": record["bytes"],
                "declarations": copy.deepcopy(record["declarations"]),
                "encoding_hint": record["encoding_hint"],
                "cloud_swap_point": record["cloud_swap_point"],
            },
        )
        if (
            immutable_receipt["content_sha256"] != record["source_sha256"]
            or immutable_receipt["size"] != record["bytes"]
        ):
            raise IngestWorkspaceError("RAW_UPLOAD_IMMUTABLE_RECEIPT_MISMATCH")
        manifest_entries.append(
            {
                "source_name": record["source_name"],
                "source_sha256": record["source_sha256"],
                "bytes": record["bytes"],
                "declarations": copy.deepcopy(record["declarations"]),
                "encoding_hint": record["encoding_hint"],
                "cloud_swap_point": record["cloud_swap_point"],
                "immutable_receipt": immutable_receipt,
            }
        )

    persisted_result = _persistable_result(m1_result, manifest_entries)
    mutations = {
        "input_manifest": {"uploads": manifest_entries},
        "module_state": persisted_result,
    }
    commit_receipt = workspace.commit(
        operation_id,
        mutations,
        expected_versions,
    )
    return {
        "status": commit_receipt["status"],
        "operation_id": operation_id,
        "replayed": commit_receipt["replayed"],
        "generation_id": commit_receipt["generation_id"],
        "versions": commit_receipt["versions"],
        "payload_sha256": commit_receipt["payload_sha256"],
        "immutable_receipts": [
            entry["immutable_receipt"] for entry in manifest_entries
        ],
    }


def _stable_visible_pair(
    workspace: AuthorWorkspace,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    first_manifest = workspace.read("input_manifest")
    first_state = workspace.read("module_state")
    second_manifest = workspace.read("input_manifest")
    second_state = workspace.read("module_state")
    if first_manifest != second_manifest or first_state != second_state:
        raise IngestWorkspaceError("M1_READ_WATERMARK_CHANGED")
    return first_manifest, first_state


def _validated_persisted_uploads(
    workspace: AuthorWorkspace,
    manifest: object,
    module_state: object,
) -> list[dict[str, Any]]:
    if not isinstance(manifest, dict) or set(manifest) != {"uploads"}:
        raise IngestWorkspaceError("M1_INPUT_MANIFEST_INVALID")
    uploads = manifest["uploads"]
    if not isinstance(uploads, list) or not uploads:
        raise IngestWorkspaceError("M1_PERSISTED_UPLOADS_REQUIRED")
    if not isinstance(module_state, dict):
        raise IngestWorkspaceError("M1_MODULE_STATE_INVALID")
    state_uploads = module_state.get("upload_objects")
    format_receipt = module_state.get("format_receipt")
    if (
        not isinstance(state_uploads, list)
        or not isinstance(format_receipt, dict)
        or format_receipt.get("status") != "READY"
        or not isinstance(format_receipt.get("upload_objects"), list)
        or uploads != state_uploads
        or uploads != format_receipt["upload_objects"]
    ):
        raise IngestWorkspaceError("M1_PERSISTED_UPLOAD_LISTS_DIVERGED")

    validated: list[dict[str, Any]] = []
    names: set[str] = set()
    for index, record in enumerate(uploads):
        if not isinstance(record, dict) or set(record) != PERSISTED_UPLOAD_RECORD_KEYS:
            raise IngestWorkspaceError(f"M1_PERSISTED_UPLOAD_INVALID:{index}")
        source_name = record["source_name"]
        source_sha = record["source_sha256"]
        byte_count = record["bytes"]
        declarations = record["declarations"]
        encoding_hint = record["encoding_hint"]
        try:
            safe_source = UploadSource(
                source_name=source_name,
                raw_bytes=b"",
                declarations=declarations,
                encoding_hint=encoding_hint,
            )
        except (TypeError, ValueError) as exc:
            raise IngestWorkspaceError(
                f"M1_PERSISTED_UPLOAD_INVALID:{index}"
            ) from exc
        if (
            safe_source.source_name in names
            or not isinstance(source_sha, str)
            or SHA256_RE.fullmatch(source_sha) is None
            or isinstance(byte_count, bool)
            or not isinstance(byte_count, int)
            or byte_count < 0
            or declarations != safe_source.declarations
            or record["cloud_swap_point"] != CLOUD_SWAP_POINT
        ):
            raise IngestWorkspaceError(f"M1_PERSISTED_UPLOAD_INVALID:{index}")
        names.add(safe_source.source_name)

        receipt = record["immutable_receipt"]
        if not isinstance(receipt, dict) or set(receipt) != IMMUTABLE_RECEIPT_KEYS:
            raise IngestWorkspaceError(f"M1_IMMUTABLE_RECEIPT_INVALID:{index}")
        expected_blob_id = (
            f"i_{workspace.author_id[2:]}_raw_upload_{source_sha}"
        )
        if (
            receipt["blob_id"] != expected_blob_id
            or receipt["kind"] != "raw_upload"
            or receipt["content_sha256"] != source_sha
            or receipt["size"] != byte_count
            or not isinstance(receipt["metadata_sha256"], str)
            or SHA256_RE.fullmatch(receipt["metadata_sha256"]) is None
        ):
            raise IngestWorkspaceError(
                f"M1_IMMUTABLE_RECEIPT_MISMATCH:{index}"
            )
        validated.append(copy.deepcopy(record))
    return validated


def _safe_summary(module_state: dict[str, Any]) -> dict[str, Any]:
    count = module_state.get("count")
    total_chars = module_state.get("total_chars")
    warnings = module_state.get("warnings")
    format_receipt = module_state["format_receipt"]
    terminal_source_count = format_receipt.get("terminal_source_count")
    if (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < 0
        or isinstance(total_chars, bool)
        or not isinstance(total_chars, int)
        or total_chars < 0
        or not isinstance(warnings, list)
        or any(not isinstance(item, str) for item in warnings)
        or isinstance(terminal_source_count, bool)
        or not isinstance(terminal_source_count, int)
        or terminal_source_count < 0
    ):
        raise IngestWorkspaceError("M1_MODULE_STATE_SUMMARY_INVALID")
    return {
        "count": count,
        "total_chars": total_chars,
        "warning_count": len(warnings),
        "terminal_source_count": terminal_source_count,
    }


def _validated_visible_state(
    workspace: AuthorWorkspace,
) -> dict[str, Any] | None:
    manifest_state, module_state_record = _stable_visible_pair(workspace)
    if manifest_state is None and module_state_record is None:
        return None
    if manifest_state is None or module_state_record is None:
        raise IngestWorkspaceError("M1_VISIBLE_STATE_INCOMPLETE")
    if manifest_state["version"] != module_state_record["version"]:
        raise IngestWorkspaceError("M1_VISIBLE_STATE_VERSION_DIVERGED")
    uploads = _validated_persisted_uploads(
        workspace,
        manifest_state["payload"],
        module_state_record["payload"],
    )
    return {
        "state_identity": {
            "input_manifest": {
                "version": manifest_state["version"],
                "sha256": manifest_state["sha256"],
            },
            "module_state": {
                "version": module_state_record["version"],
                "sha256": module_state_record["sha256"],
            },
        },
        "uploads": uploads,
        "module_state": copy.deepcopy(module_state_record["payload"]),
    }


def _safe_upload_records(uploads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """安全摘要不返回作者声明正文；完整声明只供内部再装载。"""
    return [
        {
            key: copy.deepcopy(value)
            for key, value in record.items()
            if key != "declarations"
        }
        for record in uploads
    ]


def read_persisted_m1_state(workspace: AuthorWorkspace) -> dict[str, Any]:
    """稳定读回 M1 安全摘要；不返回原始 bytes、解码正文或章节正文。"""
    if not isinstance(workspace, AuthorWorkspace):
        raise IngestWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    visible = _validated_visible_state(workspace)
    if visible is None:
        return {
            "status": "EMPTY",
            "state_identity": None,
            "uploads": [],
            "summary": None,
        }
    return {
        "status": "READY",
        "state_identity": visible["state_identity"],
        "uploads": _safe_upload_records(visible["uploads"]),
        "summary": _safe_summary(visible["module_state"]),
    }


def load_persisted_upload_sources(
    workspace: AuthorWorkspace,
) -> list[UploadSource]:
    """只从当前项目已验证 manifest 再装载原始上传对象。"""
    if not isinstance(workspace, AuthorWorkspace):
        raise IngestWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    visible = _validated_visible_state(workspace)
    if visible is None:
        return []

    loaded_sources: list[UploadSource] = []
    for index, record in enumerate(visible["uploads"]):
        loaded = workspace.read_immutable(record["immutable_receipt"])
        expected_metadata = {
            "source_name": record["source_name"],
            "source_sha256": record["source_sha256"],
            "bytes": record["bytes"],
            "declarations": copy.deepcopy(record["declarations"]),
            "encoding_hint": record["encoding_hint"],
            "cloud_swap_point": record["cloud_swap_point"],
        }
        if loaded["metadata"] != expected_metadata:
            raise IngestWorkspaceError(
                f"M1_IMMUTABLE_METADATA_MISMATCH:{index}"
            )
        raw_bytes = loaded["raw_bytes"]
        source = UploadSource(
            source_name=record["source_name"],
            raw_bytes=raw_bytes,
            declarations=record["declarations"],
            encoding_hint=record["encoding_hint"],
        )
        if source.sha256 != record["source_sha256"] or len(raw_bytes) != record["bytes"]:
            raise IngestWorkspaceError(
                f"M1_REHYDRATED_UPLOAD_INTEGRITY_MISMATCH:{index}"
            )
        loaded_sources.append(source)

    after_state = _validated_visible_state(workspace)
    if (
        after_state is None
        or after_state["state_identity"] != visible["state_identity"]
        or after_state["uploads"] != visible["uploads"]
    ):
        raise IngestWorkspaceError("M1_REHYDRATE_WATERMARK_CHANGED")
    return loaded_sources


def load_persisted_m1_snapshot(workspace: AuthorWorkspace) -> dict[str, Any]:
    """内部接纳用：同一 M1 版本的材料身份、上传回执和已复验的原始对象。

    返回值含正文，只交给已绑定的业务入口，不是作者项目列表的安全摘要。
    消费者写入时仍必须用 state_identity 作为原子提交的只读前置水位。
    """
    if not isinstance(workspace, AuthorWorkspace):
        raise IngestWorkspaceError("AUTHOR_WORKSPACE_HANDLE_REQUIRED")
    before = _validated_visible_state(workspace)
    if before is None:
        raise IngestWorkspaceError("M1_PERSISTED_STATE_REQUIRED")
    uploads = load_persisted_upload_sources(workspace)
    after = _validated_visible_state(workspace)
    if before != after:
        raise IngestWorkspaceError("M1_REHYDRATE_WATERMARK_CHANGED")
    return {**before, "upload_sources": uploads}
