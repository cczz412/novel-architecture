from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCORE_BUNDLE_SCHEMA = "v02-r2-offline-score-bundle.v2"
SCORE_RECEIPT_SCHEMA = "v02-r2-offline-route-score.v2"
ROUTE_OUTPUT_SCHEMA = "v02-r2-route-output.v1"
ROUTE_MANIFEST_SCHEMA = "v02-r2-dev-route-manifest.v2"


class OfflineScorerError(ValueError):
    """R2 隔离离线评分入口拒收错误。"""


def canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def _require_hash(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise OfflineScorerError(f"HASH_INVALID:{field}")
    return value


def _verify_embedded_payload_hash(
    value: Mapping[str, Any],
    *,
    field: str,
    error_prefix: str,
) -> None:
    actual = _require_hash(value.get(field), field=field)
    payload = dict(value)
    payload.pop(field)
    if sha256_bytes(canonical_bytes(payload)) != actual:
        raise OfflineScorerError(f"{error_prefix}_PAYLOAD_SHA_MISMATCH")


def _load_catalogs(catalog_dir: Path) -> list[dict[str, Any]]:
    paths = sorted(catalog_dir.glob("*.json"))
    if not paths:
        raise OfflineScorerError("SOURCE_CATALOGS_REQUIRED")
    catalogs: list[dict[str, Any]] = []
    source_ids: set[str] = set()
    paragraph_ids: set[str] = set()
    for path in paths:
        catalog = json.loads(path.read_text(encoding="utf-8"))
        source_id = catalog.get("source_id")
        if not isinstance(source_id, str) or not source_id:
            raise OfflineScorerError(f"SOURCE_CATALOG_ID_INVALID:{path.name}")
        if source_id in source_ids:
            raise OfflineScorerError(f"SOURCE_CATALOG_ID_DUPLICATED:{source_id}")
        source_ids.add(source_id)
        source_text = catalog.get("source_text")
        if not isinstance(source_text, str):
            raise OfflineScorerError(f"SOURCE_TEXT_INVALID:{source_id}")
        if sha256_bytes(source_text.encode("utf-8")) != catalog.get(
            "source_body_sha256"
        ):
            raise OfflineScorerError(f"SOURCE_BODY_SHA_MISMATCH:{source_id}")
        payload = dict(catalog)
        actual_payload_sha256 = payload.pop("catalog_payload_sha256", None)
        if sha256_bytes(canonical_bytes(payload)) != actual_payload_sha256:
            raise OfflineScorerError(f"SOURCE_CATALOG_PAYLOAD_SHA_MISMATCH:{source_id}")
        rebuilt = "".join(row["original_text"] for row in catalog["paragraphs"])
        if rebuilt != source_text:
            raise OfflineScorerError(f"SOURCE_PARAGRAPH_REBUILD_MISMATCH:{source_id}")
        for row in catalog["paragraphs"]:
            paragraph_id = row.get("paragraph_id")
            if not isinstance(paragraph_id, str) or not paragraph_id:
                raise OfflineScorerError(f"PARAGRAPH_ID_INVALID:{source_id}")
            if paragraph_id in paragraph_ids:
                raise OfflineScorerError(f"PARAGRAPH_ID_DUPLICATED:{paragraph_id}")
            paragraph_ids.add(paragraph_id)
        catalogs.append(catalog)
    return catalogs


def source_to_paragraph(
    catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for catalog in catalogs:
        for row in catalog["sentences"]:
            for source_id in [
                row["sentence_id"],
                *row.get("accepted_legacy_source_ids", []),
            ]:
                previous = mapping.setdefault(source_id, row["paragraph_id"])
                if previous != row["paragraph_id"]:
                    raise OfflineScorerError(
                        f"SOURCE_TO_PARAGRAPH_AMBIGUOUS:{source_id}"
                    )
    return mapping


def _paragraph_index(
    catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for catalog in catalogs:
        for row in catalog["paragraphs"]:
            result[row["paragraph_id"]] = {
                "case_id": catalog["source_id"],
                "char_count": len(row["original_text"]),
                "original_text_sha256": sha256_bytes(
                    row["original_text"].encode("utf-8")
                ),
            }
    return result


def _verify_sparse_index(
    *,
    index_path: Path,
    catalogs: Sequence[Mapping[str, Any]],
) -> dict[str, str]:
    from . import route_runner

    if not index_path.is_file() or index_path.is_symlink():
        raise OfflineScorerError("SPARSE_INDEX_FILE_MISSING")
    try:
        index = json.loads(index_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OfflineScorerError("SPARSE_INDEX_JSON_INVALID") from exc
    if not isinstance(index, Mapping):
        raise OfflineScorerError("SPARSE_INDEX_NOT_OBJECT")
    actual_payload_sha256 = _require_hash(
        index.get("index_payload_sha256"),
        field="index_payload_sha256",
    )
    payload = dict(index)
    payload.pop("index_payload_sha256")
    if sha256_bytes(canonical_bytes(payload)) != actual_payload_sha256:
        raise OfflineScorerError("SPARSE_INDEX_PAYLOAD_SHA_MISMATCH")
    rebuilt = route_runner.build_sparse_index(catalogs)
    if canonical_bytes(rebuilt) != canonical_bytes(index):
        raise OfflineScorerError("SPARSE_INDEX_REBUILD_MISMATCH")
    return {
        "path": index_path.relative_to(index_path.parent.parent).as_posix(),
        "file_sha256": sha256_file(index_path),
        "index_payload_sha256": actual_payload_sha256,
    }


def _head_complete(
    *,
    retrieved_paragraphs: set[str],
    source_id_groups: Sequence[Sequence[str]],
    source_paragraph_map: Mapping[str, str],
) -> bool:
    if not source_id_groups:
        raise OfflineScorerError("SOURCE_ID_GROUPS_REQUIRED")
    group_results: list[bool] = []
    for group in source_id_groups:
        if not group:
            raise OfflineScorerError("SOURCE_ID_GROUP_EMPTY")
        paragraphs = {
            source_paragraph_map[source_id]
            for source_id in group
            if source_id in source_paragraph_map
        }
        group_results.append(bool(paragraphs & retrieved_paragraphs))
    return all(group_results)


def _output_collection_records(
    *,
    sealed_outputs_dir: Path,
    route_receipt: Mapping[str, Any],
) -> list[dict[str, Any]]:
    records = route_receipt.get("outputs")
    if not isinstance(records, list) or not records:
        raise OfflineScorerError("ROUTE_RECEIPT_OUTPUTS_REQUIRED")
    normalized: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    seen_cells: set[tuple[str, int]] = set()
    for index, record in enumerate(records):
        if not isinstance(record, Mapping) or set(record) != {
            "route_id",
            "budget_chars",
            "path",
            "sha256",
        }:
            raise OfflineScorerError(f"ROUTE_RECEIPT_OUTPUT_RECORD_INVALID:{index}")
        route_id = record["route_id"]
        budget = record["budget_chars"]
        relative = record["path"]
        if not isinstance(route_id, str) or not route_id:
            raise OfflineScorerError(f"ROUTE_ID_INVALID:{index}")
        if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
            raise OfflineScorerError(f"ROUTE_BUDGET_INVALID:{index}")
        if not isinstance(relative, str) or not relative:
            raise OfflineScorerError(f"ROUTE_OUTPUT_PATH_INVALID:{index}")
        expected_relative = f"sealed_outputs/{route_id}/{budget}.json"
        if relative != expected_relative:
            raise OfflineScorerError(f"ROUTE_OUTPUT_PATH_BINDING_MISMATCH:{relative}")
        _require_hash(record["sha256"], field=f"outputs[{index}].sha256")
        if relative in seen_paths or (route_id, budget) in seen_cells:
            raise OfflineScorerError(f"ROUTE_OUTPUT_RECORD_DUPLICATED:{relative}")
        seen_paths.add(relative)
        seen_cells.add((route_id, budget))
        path = sealed_outputs_dir.parent / relative
        if not path.is_file():
            raise OfflineScorerError(f"SEALED_OUTPUT_MISSING:{relative}")
        if sha256_file(path) != record["sha256"]:
            raise OfflineScorerError(f"SEALED_OUTPUT_SHA_MISMATCH:{relative}")
        normalized.append(dict(record))
    actual_paths = {
        path.relative_to(sealed_outputs_dir.parent).as_posix()
        for path in sealed_outputs_dir.glob("*/*.json")
    }
    if actual_paths != seen_paths:
        raise OfflineScorerError("SEALED_OUTPUT_FILE_SET_MISMATCH")
    return sorted(normalized, key=lambda row: row["path"])


def _route_manifest_records(
    route_manifests_dir: Path,
    *,
    output_records: Sequence[Mapping[str, Any]],
    expected_index_payload_sha256: str,
) -> list[dict[str, Any]]:
    from . import route_runner

    records: list[dict[str, Any]] = []
    route_ids: set[str] = set()
    for path in sorted(route_manifests_dir.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("schema_version") != ROUTE_MANIFEST_SCHEMA:
            raise OfflineScorerError(f"ROUTE_MANIFEST_SCHEMA_INVALID:{path.name}")
        expected_fields = {
            "schema_version",
            "route_id",
            "parent_route_id",
            "single_change",
            "budgets",
            "question_projection_sha256",
            "source_bindings_sha256",
            "workspace_manifest_sha256",
            "index_payload_sha256",
            "runner_sha256",
            "index_builder_sha256",
            "hardening_sha256",
            "obligation_plan_sha256",
            "query_map_sha256",
            "source_candidate_frames_sha256",
            "planner_visible_source_sha256",
            "selection_projection_records",
            "planner_runner_sha256",
            "opened_input_paths",
            "hidden_root_mounted",
            "executor_kind",
            "sealed_output_collection_sha256",
            "model_api_calls",
            "network_calls",
            "manifest_payload_sha256",
        }
        if set(value) != expected_fields:
            raise OfflineScorerError(f"ROUTE_MANIFEST_FIELDS_INVALID:{path.name}")
        _verify_embedded_payload_hash(
            value,
            field="manifest_payload_sha256",
            error_prefix="ROUTE_MANIFEST",
        )
        route_id = value.get("route_id")
        if not isinstance(route_id, str) or not route_id:
            raise OfflineScorerError(f"ROUTE_MANIFEST_ID_INVALID:{path.name}")
        if route_id in route_ids or path.stem != route_id:
            raise OfflineScorerError(f"ROUTE_MANIFEST_ID_BINDING_MISMATCH:{path.name}")
        route_ids.add(route_id)
        for field in (
            "question_projection_sha256",
            "source_bindings_sha256",
            "workspace_manifest_sha256",
            "runner_sha256",
            "index_builder_sha256",
            "hardening_sha256",
            "obligation_plan_sha256",
            "query_map_sha256",
            "source_candidate_frames_sha256",
            "planner_visible_source_sha256",
            "planner_runner_sha256",
            "sealed_output_collection_sha256",
        ):
            _require_hash(value.get(field), field=f"route_manifest.{field}")
        if value["runner_sha256"] != sha256_file(Path(route_runner.__file__)):
            raise OfflineScorerError(f"ROUTE_MANIFEST_RUNNER_SHA_MISMATCH:{route_id}")
        if value["hardening_sha256"] != sha256_file(
            Path(route_runner.hardening.__file__)
        ):
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_HARDENING_SHA_MISMATCH:{route_id}"
            )
        import inspect

        actual_index_builder_sha256 = sha256_bytes(
            inspect.getsource(route_runner.build_sparse_index).encode("utf-8")
        )
        if value["index_builder_sha256"] != actual_index_builder_sha256:
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_INDEX_BUILDER_SHA_MISMATCH:{route_id}"
            )
        if value["executor_kind"] != "ZERO_API_PYTHON":
            raise OfflineScorerError(f"ROUTE_MANIFEST_EXECUTOR_INVALID:{route_id}")
        if value["model_api_calls"] != 0 or value["network_calls"] != 0:
            raise OfflineScorerError(f"ROUTE_MANIFEST_ZERO_API_BROKEN:{route_id}")
        route_outputs = sorted(
            [dict(row) for row in output_records if row["route_id"] == route_id],
            key=lambda row: row["budget_chars"],
        )
        if value["sealed_output_collection_sha256"] != sha256_bytes(
            canonical_bytes(route_outputs)
        ):
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_OUTPUT_COLLECTION_MISMATCH:{route_id}"
            )
        if value["index_payload_sha256"] != expected_index_payload_sha256:
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_INDEX_PAYLOAD_MISMATCH:{route_id}"
            )
        if value["hidden_root_mounted"] is not False:
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_HIDDEN_ROOT_MOUNTED:{route_id}"
            )
        if value["opened_input_paths"] != [
            "question_set.json",
            *[
                f"source_catalog_v2/{case_id}.json"
                for case_id in route_runner.CASE_IDS
            ],
        ]:
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_OPENED_INPUT_PATHS_INVALID:{route_id}"
            )
        if value["planner_runner_sha256"] != value["runner_sha256"]:
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_PLANNER_RUNNER_MISMATCH:{route_id}"
            )
        for field, relative in (
            (
                "obligation_plan_sha256",
                f"route_assets/obligation_plans/{route_id}.json",
            ),
            (
                "query_map_sha256",
                f"route_assets/query_maps/{route_id}.json",
            ),
            (
                "source_candidate_frames_sha256",
                f"route_assets/source_candidate_frames_v1/{route_id}.json",
            ),
        ):
            artifact_path = route_manifests_dir.parent / relative
            if not artifact_path.is_file() or sha256_file(artifact_path) != value[field]:
                raise OfflineScorerError(
                    f"ROUTE_MANIFEST_AUDIT_ARTIFACT_MISMATCH:{route_id}:{field}"
                )
        selection_records = value["selection_projection_records"]
        if (
            not isinstance(selection_records, list)
            or [row.get("budget_chars") for row in selection_records]
            != list(route_runner.BUDGETS)
        ):
            raise OfflineScorerError(
                f"ROUTE_MANIFEST_SELECTION_PROJECTION_SET_INVALID:{route_id}"
            )
        for record in selection_records:
            expected_relative = (
                f"route_assets/selection_projections/{route_id}/"
                f"{record['budget_chars']}.json"
            )
            if record.get("path") != expected_relative:
                raise OfflineScorerError(
                    f"ROUTE_MANIFEST_SELECTION_PROJECTION_PATH_INVALID:{route_id}"
                )
            projection_path = route_manifests_dir.parent / expected_relative
            if (
                not projection_path.is_file()
                or sha256_file(projection_path) != record.get("sha256")
            ):
                raise OfflineScorerError(
                    f"ROUTE_MANIFEST_SELECTION_PROJECTION_SHA_MISMATCH:{route_id}"
                )
        output_budgets = [row["budget_chars"] for row in route_outputs]
        if value["budgets"] != list(route_runner.BUDGETS):
            raise OfflineScorerError(f"ROUTE_MANIFEST_BUDGET_CONTRACT_MISMATCH:{route_id}")
        if value["budgets"] != output_budgets:
            raise OfflineScorerError(f"ROUTE_MANIFEST_OUTPUT_BUDGET_SET_MISMATCH:{route_id}")
        records.append(
            {
                "route_id": route_id,
                "path": path.relative_to(route_manifests_dir.parent).as_posix(),
                "sha256": sha256_file(path),
            }
        )
    if not records:
        raise OfflineScorerError("ROUTE_MANIFESTS_REQUIRED")
    return records


def freeze_score_bundle(
    *,
    sealed_outputs_dir: Path,
    route_receipt_path: Path,
    hidden_cells_path: Path,
    catalog_dir: Path,
    route_manifests_dir: Path,
    output_path: Path,
    scoring_executor_id: str,
) -> dict[str, Any]:
    if not scoring_executor_id:
        raise OfflineScorerError("SCORING_EXECUTOR_ID_REQUIRED")
    route_receipt = json.loads(route_receipt_path.read_text(encoding="utf-8"))
    _verify_embedded_payload_hash(
        route_receipt,
        field="receipt_payload_sha256",
        error_prefix="ROUTE_RECEIPT",
    )
    outputs = _output_collection_records(
        sealed_outputs_dir=sealed_outputs_dir,
        route_receipt=route_receipt,
    )
    catalogs = _load_catalogs(catalog_dir)
    sparse_index_binding = _verify_sparse_index(
        index_path=sealed_outputs_dir.parent / "route_assets/sparse_index.json",
        catalogs=catalogs,
    )
    manifests = _route_manifest_records(
        route_manifests_dir,
        output_records=outputs,
        expected_index_payload_sha256=sparse_index_binding["index_payload_sha256"],
    )
    if route_receipt.get("route_manifests") != manifests:
        raise OfflineScorerError("ROUTE_RECEIPT_MANIFEST_BINDINGS_MISMATCH")
    if {row["route_id"] for row in manifests} != {
        row["route_id"] for row in outputs
    }:
        raise OfflineScorerError("ROUTE_MANIFEST_OUTPUT_ROUTE_SET_MISMATCH")
    catalog_paths = {path.name: path for path in catalog_dir.glob("*.json")}
    catalog_bindings = [
        {
            "source_id": catalog["source_id"],
            "path": f"{catalog['source_id']}.json",
            "file_sha256": sha256_file(catalog_paths[f"{catalog['source_id']}.json"]),
            "source_body_sha256": catalog["source_body_sha256"],
            "catalog_payload_sha256": catalog["catalog_payload_sha256"],
        }
        for catalog in catalogs
    ]
    manifest = {
        "schema_version": SCORE_BUNDLE_SCHEMA,
        "issuer_type": "LOCAL_PREREGISTERED_CANDIDATE",
        "sealed_before_score": True,
        "scoring_executor_id": scoring_executor_id,
        "hidden_cells_sha256": sha256_file(hidden_cells_path),
        "catalog_bindings": catalog_bindings,
        "sparse_index_binding": sparse_index_binding,
        "scorer_sha256": sha256_file(Path(__file__)),
        "route_receipt_sha256": sha256_file(route_receipt_path),
        "route_manifest_bindings": manifests,
        "sealed_output_collection_sha256": sha256_bytes(canonical_bytes(outputs)),
    }
    write_json(output_path, manifest)
    return manifest


def verify_score_bundle(
    *,
    score_bundle_manifest_path: Path,
    expected_score_bundle_manifest_sha256: str,
    sealed_outputs_dir: Path,
    route_receipt_path: Path,
    hidden_cells_path: Path,
    catalog_dir: Path,
    route_manifests_dir: Path,
) -> dict[str, Any]:
    _require_hash(
        expected_score_bundle_manifest_sha256,
        field="expected_score_bundle_manifest_sha256",
    )
    if sha256_file(score_bundle_manifest_path) != expected_score_bundle_manifest_sha256:
        raise OfflineScorerError("SCORE_BUNDLE_MANIFEST_SHA_MISMATCH")
    manifest = json.loads(score_bundle_manifest_path.read_text(encoding="utf-8"))
    expected_fields = {
        "schema_version",
        "issuer_type",
        "sealed_before_score",
        "scoring_executor_id",
        "hidden_cells_sha256",
        "catalog_bindings",
        "sparse_index_binding",
        "scorer_sha256",
        "route_receipt_sha256",
        "route_manifest_bindings",
        "sealed_output_collection_sha256",
    }
    if set(manifest) != expected_fields:
        raise OfflineScorerError("SCORE_BUNDLE_FIELDS_INVALID")
    if manifest["schema_version"] != SCORE_BUNDLE_SCHEMA:
        raise OfflineScorerError("SCORE_BUNDLE_SCHEMA_INVALID")
    if manifest["issuer_type"] not in {
        "LOCAL_PREREGISTERED_CANDIDATE",
        "EXTERNAL_PREREGISTERED",
    }:
        raise OfflineScorerError("SCORE_BUNDLE_ISSUER_INVALID")
    if manifest["sealed_before_score"] is not True:
        raise OfflineScorerError("SCORE_BUNDLE_NOT_PRESEALED")
    if not isinstance(manifest["scoring_executor_id"], str) or not manifest[
        "scoring_executor_id"
    ]:
        raise OfflineScorerError("SCORING_EXECUTOR_ID_REQUIRED")
    bindings = {
        "hidden_cells_sha256": sha256_file(hidden_cells_path),
        "scorer_sha256": sha256_file(Path(__file__)),
        "route_receipt_sha256": sha256_file(route_receipt_path),
    }
    for field, actual in bindings.items():
        if manifest[field] != actual:
            raise OfflineScorerError(f"SCORE_BUNDLE_BINDING_MISMATCH:{field}")
    route_receipt = json.loads(route_receipt_path.read_text(encoding="utf-8"))
    _verify_embedded_payload_hash(
        route_receipt,
        field="receipt_payload_sha256",
        error_prefix="ROUTE_RECEIPT",
    )
    output_records = _output_collection_records(
        sealed_outputs_dir=sealed_outputs_dir,
        route_receipt=route_receipt,
    )
    if manifest["sealed_output_collection_sha256"] != sha256_bytes(
        canonical_bytes(output_records)
    ):
        raise OfflineScorerError("SEALED_OUTPUT_COLLECTION_SHA_MISMATCH")
    catalogs = _load_catalogs(catalog_dir)
    sparse_index_binding = _verify_sparse_index(
        index_path=sealed_outputs_dir.parent / "route_assets/sparse_index.json",
        catalogs=catalogs,
    )
    if manifest["sparse_index_binding"] != sparse_index_binding:
        raise OfflineScorerError("SPARSE_INDEX_BINDING_MISMATCH")
    manifest_records = _route_manifest_records(
        route_manifests_dir,
        output_records=output_records,
        expected_index_payload_sha256=sparse_index_binding["index_payload_sha256"],
    )
    if route_receipt.get("route_manifests") != manifest_records:
        raise OfflineScorerError("ROUTE_RECEIPT_MANIFEST_BINDINGS_MISMATCH")
    if manifest["route_manifest_bindings"] != manifest_records:
        raise OfflineScorerError("ROUTE_MANIFEST_BINDINGS_MISMATCH")
    catalog_paths = {path.name: path for path in catalog_dir.glob("*.json")}
    actual_catalog_bindings = [
        {
            "source_id": catalog["source_id"],
            "path": f"{catalog['source_id']}.json",
            "file_sha256": sha256_file(catalog_paths[f"{catalog['source_id']}.json"]),
            "source_body_sha256": catalog["source_body_sha256"],
            "catalog_payload_sha256": catalog["catalog_payload_sha256"],
        }
        for catalog in catalogs
    ]
    if manifest["catalog_bindings"] != actual_catalog_bindings:
        raise OfflineScorerError("SOURCE_CATALOG_BINDINGS_MISMATCH")
    return {
        "status": "PASS",
        "score_bundle_manifest_sha256": expected_score_bundle_manifest_sha256,
        "sealed_output_count": len(output_records),
        "route_manifest_count": len(manifest_records),
        "catalog_count": len(catalogs),
        "scoring_executor_id": manifest["scoring_executor_id"],
    }


def _validate_route_output(
    *,
    route_output: Mapping[str, Any],
    hidden_cells: Sequence[Mapping[str, Any]],
    catalogs: Sequence[Mapping[str, Any]],
    expected_index_payload_sha256: str,
) -> dict[str, dict[str, Any]]:
    expected_top_fields = {
        "schema_version",
        "candidate_status",
        "route_id",
        "budget_chars",
        "question_projection_sha256",
        "index_payload_sha256",
        "alias_ledger_sha256",
        "cue_lexicon_sha256",
        "cells",
        "model_api_calls",
        "network_calls",
        "output_payload_sha256",
    }
    if set(route_output) != expected_top_fields:
        raise OfflineScorerError("ROUTE_OUTPUT_FIELDS_INVALID")
    if route_output["schema_version"] != ROUTE_OUTPUT_SCHEMA:
        raise OfflineScorerError("ROUTE_OUTPUT_SCHEMA_INVALID")
    _verify_embedded_payload_hash(
        route_output,
        field="output_payload_sha256",
        error_prefix="ROUTE_OUTPUT",
    )
    if route_output["model_api_calls"] != 0 or route_output["network_calls"] != 0:
        raise OfflineScorerError("ROUTE_OUTPUT_ZERO_API_CONTRACT_BROKEN")
    for field in (
        "question_projection_sha256",
        "index_payload_sha256",
        "alias_ledger_sha256",
        "cue_lexicon_sha256",
    ):
        _require_hash(route_output[field], field=field)
    if route_output["index_payload_sha256"] != expected_index_payload_sha256:
        raise OfflineScorerError("ROUTE_OUTPUT_INDEX_PAYLOAD_MISMATCH")
    budget = route_output["budget_chars"]
    if not isinstance(budget, int) or isinstance(budget, bool) or budget <= 0:
        raise OfflineScorerError("ROUTE_OUTPUT_BUDGET_INVALID")
    cells = route_output["cells"]
    if not isinstance(cells, list) or len(cells) != len(hidden_cells):
        raise OfflineScorerError("ROUTE_OUTPUT_CELL_COUNT_INVALID")
    hidden_by_id = {cell["cell_id"]: cell for cell in hidden_cells}
    if len(hidden_by_id) != len(hidden_cells):
        raise OfflineScorerError("HIDDEN_CELL_ID_DUPLICATED")
    paragraph_index = _paragraph_index(catalogs)
    output_cells: dict[str, dict[str, Any]] = {}
    for cell_index, cell in enumerate(cells):
        required_fields = {
            "cell_id",
            "case_id",
            "question_id",
            "request_heads",
            "query_variant_count",
            "selected_windows",
            "candidate_chars",
        }
        optional_fields = {
            "actual_match_window_count",
            "actual_match_chars",
            "fallback_window_count",
            "fallback_chars",
        }
        if not isinstance(cell, Mapping) or not required_fields <= set(cell):
            raise OfflineScorerError(f"ROUTE_OUTPUT_CELL_FIELDS_INVALID:{cell_index}")
        if set(cell) - required_fields - optional_fields:
            raise OfflineScorerError(f"ROUTE_OUTPUT_CELL_FIELDS_UNKNOWN:{cell_index}")
        cell_id = cell["cell_id"]
        if cell_id in output_cells:
            raise OfflineScorerError(f"ROUTE_OUTPUT_CELL_DUPLICATED:{cell_id}")
        if cell_id != f"{cell['case_id']}::{cell['question_id']}":
            raise OfflineScorerError(f"ROUTE_OUTPUT_CELL_BINDING_INVALID:{cell_id}")
        hidden = hidden_by_id.get(cell_id)
        if hidden is None:
            raise OfflineScorerError(f"ROUTE_OUTPUT_CELL_UNKNOWN:{cell_id}")
        if hidden["case_id"] != cell["case_id"] or hidden["question_id"] != cell[
            "question_id"
        ]:
            raise OfflineScorerError(f"ROUTE_OUTPUT_HIDDEN_BINDING_MISMATCH:{cell_id}")
        windows = cell["selected_windows"]
        if not isinstance(windows, list):
            raise OfflineScorerError(f"ROUTE_OUTPUT_WINDOWS_NOT_LIST:{cell_id}")
        seen_paragraphs: set[str] = set()
        seen_ranks: set[int] = set()
        recomputed_chars = 0
        actual_match_chars = 0
        fallback_chars = 0
        actual_match_windows = 0
        fallback_windows = 0
        for window_index, window in enumerate(windows):
            required_window_fields = {
                "paragraph_id",
                "rank",
                "score",
                "char_count",
                "selection_reason",
            }
            optional_window_fields = {
                "request_head_ids",
                "matched_query_ids",
                "matched_grams",
            }
            if (
                not isinstance(window, Mapping)
                or not required_window_fields <= set(window)
                or set(window) - required_window_fields - optional_window_fields
            ):
                raise OfflineScorerError(
                    f"ROUTE_OUTPUT_WINDOW_FIELDS_INVALID:{cell_id}:{window_index}"
                )
            paragraph_id = window["paragraph_id"]
            paragraph = paragraph_index.get(paragraph_id)
            if paragraph is None:
                raise OfflineScorerError(f"ROUTE_OUTPUT_PARAGRAPH_UNKNOWN:{paragraph_id}")
            if paragraph["case_id"] != cell["case_id"]:
                raise OfflineScorerError(f"ROUTE_OUTPUT_PARAGRAPH_CROSS_CASE:{paragraph_id}")
            if paragraph_id in seen_paragraphs:
                raise OfflineScorerError(f"ROUTE_OUTPUT_PARAGRAPH_DUPLICATED:{paragraph_id}")
            seen_paragraphs.add(paragraph_id)
            rank = window["rank"]
            if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
                raise OfflineScorerError(f"ROUTE_OUTPUT_WINDOW_RANK_INVALID:{cell_id}")
            if rank in seen_ranks:
                raise OfflineScorerError(f"ROUTE_OUTPUT_WINDOW_RANK_DUPLICATED:{cell_id}")
            seen_ranks.add(rank)
            if window["char_count"] != paragraph["char_count"]:
                raise OfflineScorerError(f"ROUTE_OUTPUT_WINDOW_CHAR_MISMATCH:{paragraph_id}")
            recomputed_chars += paragraph["char_count"]
            if window["selection_reason"] == "UNMATCHED_FALLBACK":
                fallback_windows += 1
                fallback_chars += paragraph["char_count"]
            elif window["selection_reason"] == "ACTUAL_QUERY_MATCH":
                actual_match_windows += 1
                actual_match_chars += paragraph["char_count"]
        if recomputed_chars != cell["candidate_chars"]:
            raise OfflineScorerError(f"ROUTE_OUTPUT_CANDIDATE_CHARS_MISMATCH:{cell_id}")
        if recomputed_chars > budget:
            raise OfflineScorerError(f"ROUTE_OUTPUT_BUDGET_EXCEEDED:{cell_id}")
        diagnostic_values = {
            "actual_match_window_count": actual_match_windows,
            "actual_match_chars": actual_match_chars,
            "fallback_window_count": fallback_windows,
            "fallback_chars": fallback_chars,
        }
        for field, actual in diagnostic_values.items():
            if field in cell and cell[field] != actual:
                raise OfflineScorerError(f"ROUTE_OUTPUT_DIAGNOSTIC_MISMATCH:{cell_id}:{field}")
        output_cells[cell_id] = {
            **cell,
            "recomputed_candidate_chars": recomputed_chars,
        }
    if set(output_cells) != set(hidden_by_id):
        raise OfflineScorerError("ROUTE_OUTPUT_HIDDEN_CELL_SET_MISMATCH")
    return output_cells


def score_route_output(
    *,
    route_output: Mapping[str, Any],
    hidden_cells: Sequence[Mapping[str, Any]],
    catalogs: Sequence[Mapping[str, Any]],
    expected_index_payload_sha256: str,
) -> dict[str, Any]:
    output_cells = _validate_route_output(
        route_output=route_output,
        hidden_cells=hidden_cells,
        catalogs=catalogs,
        expected_index_payload_sha256=expected_index_payload_sha256,
    )
    source_paragraph_map = source_to_paragraph(catalogs)
    answerable = [
        cell for cell in hidden_cells if cell["answerability"] == "ANSWERABLE"
    ]
    full_hits = 0
    head_hits = 0
    head_total = 0
    per_case: dict[str, dict[str, int]] = {}
    for cell in answerable:
        retrieved = {
            row["paragraph_id"]
            for row in output_cells[cell["cell_id"]]["selected_windows"]
        }
        case = per_case.setdefault(
            cell["case_id"],
            {"question_hits": 0, "question_total": 0, "head_hits": 0, "head_total": 0},
        )
        case["question_total"] += 1
        cell_complete = True
        for head in cell["required_heads"]:
            head_total += 1
            case["head_total"] += 1
            complete = _head_complete(
                retrieved_paragraphs=retrieved,
                source_id_groups=head["source_id_groups"],
                source_paragraph_map=source_paragraph_map,
            )
            if complete:
                head_hits += 1
                case["head_hits"] += 1
            else:
                cell_complete = False
        if cell_complete:
            full_hits += 1
            case["question_hits"] += 1
    candidate_chars_total = sum(
        cell["recomputed_candidate_chars"] for cell in output_cells.values()
    )
    return {
        "route_id": route_output["route_id"],
        "budget_chars": route_output["budget_chars"],
        "answerable_question_count": len(answerable),
        "open_question_count": len(hidden_cells) - len(answerable),
        "full_question_recall_count": full_hits,
        "full_question_recall": round(full_hits / max(len(answerable), 1), 6),
        "required_head_count": head_total,
        "required_head_recall_count": head_hits,
        "required_head_recall": round(head_hits / max(head_total, 1), 6),
        "candidate_chars_total": candidate_chars_total,
        "candidate_chars_average_30": round(
            candidate_chars_total / max(len(output_cells), 1), 2
        ),
        "per_case": per_case,
        "interpretation_boundary": (
            "只测冻结窗口是否覆盖隐藏评分端所需证据组；不等于答案正确率，"
            "不使用语义裁判票，不允许升默认。"
        ),
    }


def score_all(
    *,
    sealed_outputs_dir: Path,
    route_receipt_path: Path,
    hidden_cells_path: Path,
    catalog_dir: Path,
    route_manifests_dir: Path,
    score_bundle_manifest_path: Path,
    expected_score_bundle_manifest_sha256: str,
    output_path: Path,
) -> dict[str, Any]:
    bundle_receipt = verify_score_bundle(
        score_bundle_manifest_path=score_bundle_manifest_path,
        expected_score_bundle_manifest_sha256=expected_score_bundle_manifest_sha256,
        sealed_outputs_dir=sealed_outputs_dir,
        route_receipt_path=route_receipt_path,
        hidden_cells_path=hidden_cells_path,
        catalog_dir=catalog_dir,
        route_manifests_dir=route_manifests_dir,
    )
    route_receipt = json.loads(route_receipt_path.read_text(encoding="utf-8"))
    hidden = json.loads(hidden_cells_path.read_text(encoding="utf-8"))
    catalogs = _load_catalogs(catalog_dir)
    sparse_index_binding = _verify_sparse_index(
        index_path=sealed_outputs_dir.parent / "route_assets/sparse_index.json",
        catalogs=catalogs,
    )
    records = _output_collection_records(
        sealed_outputs_dir=sealed_outputs_dir,
        route_receipt=route_receipt,
    )
    rows: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda row: (row["route_id"], row["budget_chars"])):
        path = sealed_outputs_dir.parent / record["path"]
        output = json.loads(path.read_text(encoding="utf-8"))
        if output.get("route_id") != record["route_id"]:
            raise OfflineScorerError(f"ROUTE_OUTPUT_ROUTE_ID_MISMATCH:{record['path']}")
        if output.get("budget_chars") != record["budget_chars"]:
            raise OfflineScorerError(f"ROUTE_OUTPUT_BUDGET_BINDING_MISMATCH:{record['path']}")
        rows.append(
            score_route_output(
                route_output=output,
                hidden_cells=hidden["cells"],
                catalogs=catalogs,
                expected_index_payload_sha256=sparse_index_binding[
                    "index_payload_sha256"
                ],
            )
        )
    by_budget: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_budget.setdefault(str(row["budget_chars"]), []).append(row)
    winners = []
    for budget, budget_rows in sorted(by_budget.items(), key=lambda item: int(item[0])):
        ranked = sorted(
            budget_rows,
            key=lambda row: (
                -row["full_question_recall_count"],
                -row["required_head_recall_count"],
                row["candidate_chars_total"],
                row["route_id"],
            ),
        )
        winners.append(
            {
                "budget_chars": int(budget),
                "ranking": [
                    {
                        "route_id": row["route_id"],
                        "full_question_recall_count": row["full_question_recall_count"],
                        "required_head_recall_count": row["required_head_recall_count"],
                        "candidate_chars_total": row["candidate_chars_total"],
                    }
                    for row in ranked
                ],
            }
        )
    receipt: dict[str, Any] = {
        "schema_version": SCORE_RECEIPT_SCHEMA,
        "candidate_status": "candidate_silver_not_active",
        "score_source": "ISOLATED_HIDDEN_REFERENCE_OFFLINE_ONLY",
        "model_api_calls": 0,
        "network_calls": 0,
        "score_bundle_verification": bundle_receipt,
        "route_receipt_sha256": sha256_file(route_receipt_path),
        "rows": rows,
        "rankings_by_budget": winners,
        "formal_quality_score": False,
        "external_adjudicator_trust_root_attached": False,
        "next_model_stage_allowed": False,
        "blocking_reason": "ENGINEERING_REVIEW_AND_PREREGISTRATION_REQUIRED",
    }
    receipt["receipt_payload_sha256"] = sha256_bytes(canonical_bytes(receipt))
    write_json(output_path, receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("freeze", "score"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--sealed-outputs-dir", type=Path, required=True)
        sub.add_argument("--route-receipt", type=Path, required=True)
        sub.add_argument("--hidden-cells", type=Path, required=True)
        sub.add_argument("--catalog-dir", type=Path, required=True)
        sub.add_argument("--route-manifests-dir", type=Path, required=True)
        sub.add_argument("--score-bundle-manifest", type=Path, required=True)
    freeze_parser = subparsers.choices["freeze"]
    freeze_parser.add_argument("--scoring-executor-id", required=True)
    score_parser = subparsers.choices["score"]
    score_parser.add_argument("--score-bundle-manifest-sha256", required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "freeze":
        result = freeze_score_bundle(
            sealed_outputs_dir=args.sealed_outputs_dir,
            route_receipt_path=args.route_receipt,
            hidden_cells_path=args.hidden_cells,
            catalog_dir=args.catalog_dir,
            route_manifests_dir=args.route_manifests_dir,
            output_path=args.score_bundle_manifest,
            scoring_executor_id=args.scoring_executor_id,
        )
    else:
        result = score_all(
            sealed_outputs_dir=args.sealed_outputs_dir,
            route_receipt_path=args.route_receipt,
            hidden_cells_path=args.hidden_cells,
            catalog_dir=args.catalog_dir,
            route_manifests_dir=args.route_manifests_dir,
            score_bundle_manifest_path=args.score_bundle_manifest,
            expected_score_bundle_manifest_sha256=(
                args.score_bundle_manifest_sha256
            ),
            output_path=args.output,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
