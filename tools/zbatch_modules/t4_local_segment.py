"""T4 局部段覆盖单变量轮的准备、零调用校准与五章停点判定。"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import api_transport, candidate_envelope, evidence_catalog, neutral_extract, stage_sampling


class T4PilotError(RuntimeError):
    """T4 机械准备或判定失败。"""


SYSTEM_MESSAGE = neutral_extract.SYSTEM_MESSAGE
ANCHOR_ID = re.compile(r"^E(?P<number>\d{4})$")
PLACEHOLDER = re.compile(r"\{\{([A-Z0-9_]+)\}\}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise T4PilotError(f"JSON 读取失败：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise T4PilotError(f"JSON 顶层不是对象：{path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def canonical_json_bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _path(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise T4PilotError(f"路径越出仓库：{path}") from exc
    return path


def _verify_file(root: Path, ref: dict[str, Any], label: str) -> Path:
    path = _path(root, str(ref.get("path") or ""))
    expected = str(ref.get("sha256") or ref.get("config_sha256") or "")
    actual = sha256_file(path) if path.is_file() else None
    if not expected or actual != expected:
        raise T4PilotError(f"{label} SHA 漂移：expected={expected}, actual={actual}")
    return path


def anchor_range(start_anchor_id: str, end_anchor_id: str) -> list[str]:
    start = ANCHOR_ID.fullmatch(start_anchor_id)
    end = ANCHOR_ID.fullmatch(end_anchor_id)
    if start is None or end is None:
        raise T4PilotError(f"证据 ID 范围非法：{start_anchor_id}..{end_anchor_id}")
    first = int(start.group("number"))
    last = int(end.group("number"))
    if first > last:
        raise T4PilotError(f"证据 ID 范围倒置：{start_anchor_id}..{end_anchor_id}")
    return [f"E{number:04d}" for number in range(first, last + 1)]


def permit_document(manifest: dict[str, Any], chapter: int, run_id: str) -> dict[str, Any]:
    return {
        "schema_version": "z-t4-one-time-call-permit-v1",
        "batch_id": manifest["batch_id"],
        "chapter": chapter,
        "run_id": run_id,
        "model": "deepseek-v4-flash",
        "prompt_sha256": manifest["prompt_change"]["new_sha256"],
        "baseline_gate": "live_20_of_20_equivalence_and_five_request_single_variable",
        "logical_sample_limit": 1,
        "reuse_or_resume_allowed": False,
    }


def permit_relative_path(chapter: int) -> str:
    return f"work/zbatch_t4/permits/ch{chapter:04d}.call_permit.json"


def permit_sha256(manifest: dict[str, Any], chapter: int, run_id: str) -> str:
    return sha256_bytes(canonical_json_bytes(permit_document(manifest, chapter, run_id)))


def create_call_permit(manifest: dict[str, Any], root: Path, chapter: int, run_id: str) -> Path:
    path = _path(root, permit_relative_path(chapter))
    if path.exists():
        raise T4PilotError(f"第 {chapter} 章一次性通行证已存在，拒绝覆盖")
    write_json(path, permit_document(manifest, chapter, run_id))
    expected = permit_sha256(manifest, chapter, run_id)
    if sha256_file(path) != expected:
        path.unlink(missing_ok=True)
        raise T4PilotError(f"第 {chapter} 章一次性通行证写入后 SHA 不一致")
    return path


def audit_prompt_change(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    change = manifest["prompt_change"]
    old_path = _path(root, change["old_path"])
    new_path = _path(root, change["new_path"])
    for label, path, expected in (
        ("旧 Prompt", old_path, change["old_sha256"]),
        ("新 Prompt", new_path, change["new_sha256"]),
    ):
        actual = sha256_file(path)
        if actual != expected:
            raise T4PilotError(f"{label} SHA 漂移：expected={expected}, actual={actual}")
    old_text = old_path.read_text(encoding="utf-8")
    new_text = new_path.read_text(encoding="utf-8")
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    added_line = str(change["only_added_line"])
    if new_lines.count(added_line) != 1:
        raise T4PilotError("局部段覆盖条款不是恰好一行")
    insertion_index = new_lines.index(added_line)
    without_added = new_lines[:insertion_index] + new_lines[insertion_index + 1 :]
    if without_added != old_lines:
        raise T4PilotError("新旧 Prompt 除目标新增行外还有字节级变化")
    old_placeholders = PLACEHOLDER.findall(old_text)
    new_placeholders = PLACEHOLDER.findall(new_text)
    if old_placeholders != new_placeholders:
        raise T4PilotError("新旧 Prompt 的动态占位顺序发生变化，缓存结构不同构")
    first_dynamic = new_text.find("{{")
    if first_dynamic <= 0:
        raise T4PilotError("Prompt 没有可识别的固定前缀")
    layout_isomorphic = (
        old_placeholders == new_placeholders
        and new_text[:first_dynamic].find(added_line) >= 0
        and new_text.find("冻结证据目录：") > first_dynamic
    )
    if not layout_isomorphic:
        raise T4PilotError("Prompt 固定规则与动态载荷的前后层序不满足缓存同构钢线")
    return {
        "status": "pass",
        "old_prompt_sha256": change["old_sha256"],
        "new_prompt_sha256": change["new_sha256"],
        "added_line": added_line,
        "added_line_number": insertion_index + 1,
        "other_line_changes": 0,
        "placeholder_order_unchanged": old_placeholders == new_placeholders,
        "placeholder_order": new_placeholders,
        "fixed_prefix_bytes_before_first_dynamic_value": len(new_text[:first_dynamic].encode("utf-8")),
        "cache_layout_isomorphic": layout_isomorphic,
    }


def _chapter_file(book_dir: Path, chapter: int) -> Path:
    matches = sorted((book_dir / "chapters").glob(f"{chapter:04d}_*.txt"))
    if len(matches) != 1:
        raise T4PilotError(f"第 {chapter} 章正文文件数量异常：{len(matches)}")
    return matches[0]


def _request_record(messages: list[dict[str, str]], contract_path: Path) -> dict[str, Any]:
    bundle = stage_sampling.load_contract_bundle(contract_path, profile="d_mod_cutover_v1")
    route = api_transport.TransportRoute.from_mapping(bundle.route)
    contract = bundle.stage("neutral_extract")
    body = api_transport.build_request_body(
        model=route.model,
        messages=messages,
        contract=contract,
    )
    return {
        "provider": route.provider,
        "api_base_url": route.base_url,
        "api_endpoint": route.endpoint,
        "stage": "neutral_extract",
        "case_id": "",
        "contract_status": contract.status,
        "unverified_candidate_override": False,
        "body": body,
        "_security": "no_api_key_no_authorization",
    }


def baseline_equivalence_audit(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    """用当前模块重建旧 Prompt 的 20 章请求与解析结果，不发模型调用。"""

    prompt_audit = audit_prompt_change(manifest, root)
    for name, ref in manifest["protected_current_chain"].items():
        _verify_file(root, ref, f"当前保护件 {name}")
    historical = manifest["historical_extract_reference"]
    config_path = _path(root, historical["config_path"])
    if sha256_file(config_path) != historical["config_sha256"]:
        raise T4PilotError("Z00r 历史配置 SHA 漂移")
    run_dir = _path(root, f"runs/{historical['run_id']}")
    old_prompt = manifest["prompt_change"]
    old_prompt_path = _path(root, old_prompt["old_path"])
    new_prompt_path = _path(root, old_prompt["new_path"])
    contract_path = _path(root, manifest["protected_current_chain"]["stage_contract"]["path"])
    base = read_json(_path(root, manifest["base_config"]["path"]))
    book_dir = _path(root, base["book_dir"])
    rows: list[dict[str, Any]] = []
    single_variable_rows: list[dict[str, Any]] = []
    for chapter in range(1, 21):
        chapter_path = _chapter_file(book_dir, chapter)
        text = chapter_path.read_text(encoding="utf-8")
        catalog = evidence_catalog.build_evidence_catalog(chapter, text)
        catalog_document = {
            "chapter": chapter,
            "coverage": evidence_catalog.evidence_catalog_coverage(text, catalog),
            "entries": catalog,
        }
        stored_catalog_path = run_dir / "01_extract/evidence_catalogs" / f"ch{chapter:04d}.json"
        stored_request_path = run_dir / "requests/neutral_extract" / f"ch{chapter:04d}_request.json"
        stored_raw_path = run_dir / "responses/neutral_extract" / f"ch{chapter:04d}_raw.json"
        stored_events_path = run_dir / "01_extract/events" / f"ch{chapter:04d}.json"
        built = neutral_extract.build_messages(
            prompt_path=old_prompt_path,
            expected_prompt_sha256=old_prompt["old_sha256"],
            chapter=chapter,
            chapter_filename=chapter_path.name,
            catalog=catalog,
        )
        rebuilt_request = _request_record(built["messages"], contract_path)
        rebuilt_request["case_id"] = f"ch{chapter:04d}"
        stored_request = read_json(stored_request_path)
        raw_response = read_json(stored_raw_path)
        content, finish_reason = api_transport.response_content(raw_response)
        raw_event_document = candidate_envelope.parse_json_content(content)
        materialized, audit = neutral_extract.process_model_data(
            raw_event_document,
            chapter=chapter,
            catalog=catalog,
        )
        stored_events = read_json(stored_events_path)
        checks = {
            "catalog_equal": catalog_document == read_json(stored_catalog_path),
            "request_equal": rebuilt_request == stored_request,
            "events_equal": materialized == stored_events,
            "program_audit_pass": audit.get("status") == "pass",
            "finish_reason_stop": finish_reason == "stop",
        }
        rows.append(
            {
                "chapter": chapter,
                "status": "pass" if all(checks.values()) else "fail",
                "checks": checks,
                "stored_request_sha256": sha256_file(stored_request_path),
                "stored_raw_sha256": sha256_file(stored_raw_path),
                "stored_events_sha256": sha256_file(stored_events_path),
            }
        )
        if chapter in manifest["pilot_chapters"]:
            new_built = neutral_extract.build_messages(
                prompt_path=new_prompt_path,
                expected_prompt_sha256=old_prompt["new_sha256"],
                chapter=chapter,
                chapter_filename=chapter_path.name,
                catalog=catalog,
            )
            new_request = _request_record(new_built["messages"], contract_path)
            new_request["case_id"] = f"ch{chapter:04d}"
            old_without_messages = copy.deepcopy(rebuilt_request)
            new_without_messages = copy.deepcopy(new_request)
            old_messages = old_without_messages["body"].pop("messages")
            new_messages = new_without_messages["body"].pop("messages")
            old_user_lines = str(old_messages[1]["content"]).splitlines()
            new_user_lines = str(new_messages[1]["content"]).splitlines()
            inserted = old_prompt["only_added_line"]
            inserted_index = new_user_lines.index(inserted) if new_user_lines.count(inserted) == 1 else -1
            user_only_one_line = (
                inserted_index >= 0
                and new_user_lines[:inserted_index] + new_user_lines[inserted_index + 1 :] == old_user_lines
            )
            request_checks = {
                "request_outside_messages_equal": old_without_messages == new_without_messages,
                "system_message_equal": old_messages[0] == new_messages[0],
                "user_prompt_only_added_line": user_only_one_line,
                "template_sha_changed_to_registered_candidate": new_built["template_sha256"] == old_prompt["new_sha256"],
            }
            single_variable_rows.append(
                {
                    "chapter": chapter,
                    "status": "pass" if all(request_checks.values()) else "fail",
                    "checks": request_checks,
                    "old_rendered_prompt_sha256": built["prompt_sha256"],
                    "new_rendered_prompt_sha256": new_built["prompt_sha256"],
                }
            )
    failed = [row["chapter"] for row in rows if row["status"] != "pass"]
    if failed:
        raise T4PilotError(f"当前提取路径对旧 20 章不等价：{failed}")
    single_variable_failed = [
        row["chapter"] for row in single_variable_rows if row["status"] != "pass"
    ]
    if single_variable_failed:
        raise T4PilotError(f"五章完整请求不满足单变量：{single_variable_failed}")
    return {
        "schema_version": "z-t4-baseline-equivalence-v1",
        "status": "pass",
        "model_calls": 0,
        "chapters_checked": len(rows),
        "chapters_passed": len(rows),
        "historical_run_id": historical["run_id"],
        "historical_runner_sha256": historical["historical_runner_sha256"],
        "current_runner_sha256": manifest["protected_current_chain"]["runner"]["sha256"],
        "prompt_change_audit": prompt_audit,
        "pilot_request_single_variable": {
            "status": "pass",
            "chapters_checked": len(single_variable_rows),
            "chapters": single_variable_rows,
        },
        "chapters": rows,
    }


def build_pilot_config(base: dict[str, Any], manifest: dict[str, Any], chapter: int) -> dict[str, Any]:
    if chapter not in manifest["pilot_chapters"]:
        raise T4PilotError(f"章节不在预写试点清单：{chapter}")
    result = copy.deepcopy(base)
    result["batch_id"] = manifest["batch_id"]
    result["run_id"] = (
        f"{manifest['batch_id']}_X01_局部段覆盖试点_ch{chapter:04d}_v1.0_{manifest['date']}"
    )
    result["chapter_start"] = chapter
    result["chapter_end"] = chapter
    result["expected_chapters"] = 1
    result["max_calls"] = int(manifest["transport"]["network_attempts_per_logical_sample"])
    result["stages"] = ["extract"]
    new_prompt = manifest["prompt_change"]["new_path"]
    result.setdefault("prompts", {})["neutral_extract"] = new_prompt
    result.setdefault("pinned_sha256", {})[new_prompt] = manifest["prompt_change"]["new_sha256"]
    snapshots = list(result.get("spec_snapshots") or [])
    permit_path = permit_relative_path(chapter)
    for path in (manifest["prompt_change"]["old_path"], new_prompt, permit_path):
        if path not in snapshots:
            snapshots.append(path)
    result["spec_snapshots"] = snapshots
    result["pinned_sha256"][permit_path] = permit_sha256(
        manifest,
        chapter,
        result["run_id"],
    )
    result.pop("classification_source", None)
    result.pop("classification_note", None)
    result["t4_pilot"] = {
        "manifest": "config/diagnostics/Z00z_X01_局部段覆盖试点_v1.json",
        "chapter": chapter,
        "single_model_variable": "neutral_extract Prompt 只新增局部段覆盖一行",
        "logical_sample_limit": 1,
        "network_attempt_limit": result["max_calls"],
        "hard_stop_on_any_new_failure_surface": True,
        "one_time_call_permit": permit_path,
        "one_time_call_permit_sha256": result["pinned_sha256"][permit_path],
        "cache_layout": "固定任务说明在前；章号、文件名和冻结目录按原占位顺序在后",
    }
    result["rights"] = manifest["rights"]
    result["silver_role"] = "对照银标，不作裁判"
    return result


def prepare_pilot_configs(manifest: dict[str, Any], root: Path) -> dict[str, Any]:
    base_ref = manifest["base_config"]
    base_path = _path(root, base_ref["path"])
    if sha256_file(base_path) != base_ref["sha256"]:
        raise T4PilotError("试点基础配置 SHA 漂移")
    audit_prompt_change(manifest, root)
    base = read_json(base_path)
    rows = []
    for chapter in manifest["pilot_chapters"]:
        config = build_pilot_config(base, manifest, int(chapter))
        rel_path = f"config/batches/{manifest['batch_id']}_X01_局部段覆盖试点_ch{int(chapter):04d}_v1.0.json"
        output = _path(root, rel_path)
        write_json(output, config)
        rows.append(
            {
                "chapter": chapter,
                "config_path": rel_path,
                "config_sha256": sha256_file(output),
                "run_id": config["run_id"],
            }
        )
    return {
        "schema_version": "z-t4-pilot-preparation-v1",
        "status": "prepared",
        "model_calls": 0,
        "configs": rows,
    }


def _selected_anchor_ids(document: dict[str, Any]) -> set[str]:
    return {
        str(anchor.get("anchor_id"))
        for event in document.get("events") or []
        if isinstance(event, dict)
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str)
    }


def _fragment_checks(
    fragments: list[str],
    selected_ids: set[str],
    catalog_map: dict[str, str],
) -> dict[str, bool]:
    selected_quotes = [catalog_map[anchor_id] for anchor_id in sorted(selected_ids) if anchor_id in catalog_map]
    return {fragment: any(fragment in quote for quote in selected_quotes) for fragment in fragments}


def _event_anchor_ids(event: dict[str, Any]) -> set[str]:
    return {
        str(anchor.get("anchor_id"))
        for anchor in event.get("anchors") or []
        if isinstance(anchor, dict) and isinstance(anchor.get("anchor_id"), str)
    }


def evaluate_target(
    target: dict[str, Any],
    documents: dict[int, dict[str, Any]],
    catalogs: dict[int, dict[str, str]],
) -> dict[str, Any]:
    chapter = int(target["chapter"])
    selected = _selected_anchor_ids(documents[chapter])
    expected = anchor_range(target["start_anchor_id"], target["end_anchor_id"])
    missing = [anchor_id for anchor_id in expected if anchor_id not in selected]
    quote_checks = _fragment_checks(target.get("required_quote_fragments") or [], selected, catalogs[chapter])
    linked_rows = []
    for linked in target.get("linked_events") or []:
        linked_chapter = int(linked["chapter"])
        linked_document = documents[linked_chapter]
        expected_ids = list(linked.get("expected_anchor_ids") or [])
        coherent_matches = [
            {
                "event_id": event.get("event_id"),
                "event": str(event.get("event") or ""),
                "anchor_ids": sorted(_event_anchor_ids(event)),
            }
            for event in linked_document.get("events") or []
            if isinstance(event, dict)
            and set(expected_ids).issubset(_event_anchor_ids(event))
        ]
        summary_checks = {
            fragment: any(fragment in match["event"] for match in coherent_matches)
            for fragment in linked.get("required_summary_fragments") or []
        }
        coherent_event_ids = [
            match["event_id"]
            for match in coherent_matches
            if all(fragment in match["event"] for fragment in linked.get("required_summary_fragments") or [])
        ]
        linked_rows.append(
            {
                "chapter": linked_chapter,
                "role": linked.get("role"),
                "historical_event_id": linked.get("event_id"),
                "expected_anchor_ids": expected_ids,
                "coherent_matches": coherent_matches,
                "coherent_event_ids": coherent_event_ids,
                "summary_fragment_checks": summary_checks,
                "pass": bool(coherent_event_ids),
                "id_boundary": "历史事件ID只作旧账定位；新增局部事件可能引起顺序重编号，验收要求同一条新事件完整承接全部关联锚与摘要。",
            }
        )
    related_rows = []
    for related in target.get("related_spans") or []:
        related_chapter = int(related["chapter"])
        related_selected = _selected_anchor_ids(documents[related_chapter])
        related_expected = anchor_range(related["start_anchor_id"], related["end_anchor_id"])
        related_missing = [value for value in related_expected if value not in related_selected]
        related_checks = _fragment_checks(
            related.get("required_quote_fragments") or [],
            related_selected,
            catalogs[related_chapter],
        )
        related_rows.append(
            {
                "chapter": related_chapter,
                "role": related.get("role"),
                "missing_anchor_ids": related_missing,
                "required_quote_checks": related_checks,
                "pass": not related_missing and all(related_checks.values()),
            }
        )
    passed = (
        not missing
        and all(quote_checks.values())
        and all(row["pass"] for row in linked_rows)
        and all(row["pass"] for row in related_rows)
    )
    target_events = [
        event
        for event in documents[chapter].get("events") or []
        if isinstance(event, dict) and _event_anchor_ids(event).intersection(expected)
    ]
    semantic_checks = {
        term: any(
            term in str(event.get("event") or "")
            or any(term in catalogs[chapter].get(anchor_id, "") for anchor_id in _event_anchor_ids(event))
            for event in target_events
        )
        for term in target.get("semantic_terms") or []
    }
    return {
        "id": target["id"],
        "label": target["label"],
        "chapter": chapter,
        "expected_anchor_ids": expected,
        "missing_anchor_ids": missing,
        "required_quote_checks": quote_checks,
        "semantic_term_diagnostics": semantic_checks,
        "linked_events": linked_rows,
        "related_spans": related_rows,
        "interpretation_boundary": target.get("interpretation_boundary"),
        "pass": passed,
    }


def parse_attempt_rows(path: Path, *, case_id: str, max_attempts: int) -> dict[str, Any]:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError) as exc:
        raise T4PilotError(f"调用尝试账读取失败：{path}：{exc}") from exc
    count = len(rows)
    expected_attempts = list(range(1, count + 1))
    observed_attempts = [row.get("attempt") for row in rows]
    observed_call_numbers = [row.get("call_number") for row in rows]
    request_shas = {row.get("request_sha256") for row in rows}
    checks = {
        "one_logical_sample": 1 <= count <= max_attempts and observed_attempts == expected_attempts,
        "attempt_sequence_contiguous": observed_attempts == expected_attempts,
        "call_number_sequence_contiguous": observed_call_numbers == expected_attempts,
        "same_case": all(row.get("case_id") == case_id for row in rows),
        "same_stage": all(row.get("stage") == "neutral_extract" for row in rows),
        "same_request_sha": len(request_shas) == 1 and None not in request_shas,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "count": count,
        "retries": max(0, count - 1),
        "checks": checks,
        "attempts": observed_attempts,
        "call_numbers": observed_call_numbers,
        "request_sha256": next(iter(request_shas)) if len(request_shas) == 1 else None,
    }


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve()))


def tree_fingerprint(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        raise T4PilotError(f"运行目录不存在：{path}")
    rows = []
    for file in sorted(item for item in path.rglob("*") if item.is_file() and item.name != ".DS_Store"):
        rows.append(
            {
                "path": str(file.relative_to(path)),
                "sha256": sha256_file(file),
                "bytes": file.stat().st_size,
            }
        )
    payload = "\n".join(f"{row['path']}\t{row['sha256']}\t{row['bytes']}" for row in rows)
    return {
        "files": len(rows),
        "bytes": sum(row["bytes"] for row in rows),
        "sha256": sha256_bytes(payload.encode("utf-8")),
        "entries": rows,
    }


def verify_run_artifacts(
    *,
    root: Path,
    config: dict[str, Any],
    chapter: int,
    require_seal: bool = True,
) -> dict[str, Any]:
    run_dir = _path(root, f"runs/{config['run_id']}")
    run_manifest = read_json(run_dir / "run_manifest.json")
    preflight = read_json(run_dir / "preflight.json")
    request_path = run_dir / "requests/neutral_extract" / f"ch{chapter:04d}_request.json"
    raw_path = run_dir / "responses/neutral_extract" / f"ch{chapter:04d}_raw.json"
    meta_path = run_dir / "responses/neutral_extract" / f"ch{chapter:04d}_meta.json"
    output_path = run_dir / "01_extract/events" / f"ch{chapter:04d}.json"
    receipt_path = output_path.with_suffix(output_path.suffix + ".receipt.json")
    audit_path = run_dir / "01_extract/program_audits" / f"ch{chapter:04d}.json"
    catalog_path = run_dir / "01_extract/evidence_catalogs" / f"ch{chapter:04d}.json"
    request = read_json(request_path)
    meta = read_json(meta_path)
    document = read_json(output_path)
    receipt = read_json(receipt_path)
    audit = read_json(audit_path)
    catalog_document = read_json(catalog_path)
    messages = request.get("body", {}).get("messages") or []
    if len(messages) != 2:
        raise T4PilotError(f"第 {chapter} 章请求 messages 数量异常")
    catalog = catalog_document.get("entries") or []
    catalog_json = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    chapter_path = _chapter_file(_path(root, config["book_dir"]), chapter)
    chapter_sha = sha256_file(chapter_path)
    catalog_sha = sha256_bytes(catalog_json.encode("utf-8"))
    expected_input_sha = sha256_bytes((chapter_sha + "\n" + catalog_sha).encode("utf-8"))
    expected_prompt_sha = sha256_bytes(str(messages[1]["content"]).encode("utf-8"))
    chapter_text = chapter_path.read_text(encoding="utf-8")
    rebuilt_catalog = evidence_catalog.build_evidence_catalog(chapter, chapter_text)
    rebuilt_catalog_document = {
        "chapter": chapter,
        "coverage": evidence_catalog.evidence_catalog_coverage(chapter_text, rebuilt_catalog),
        "entries": rebuilt_catalog,
    }
    raw_response = read_json(raw_path)
    content, raw_finish_reason = api_transport.response_content(raw_response)
    raw_event_document = candidate_envelope.parse_json_content(content)
    rematerialized, rebuilt_audit = neutral_extract.process_model_data(
        raw_event_document,
        chapter=chapter,
        catalog=rebuilt_catalog,
    )
    receipt_checks = {
        "stage": receipt.get("stage") == "neutral_extract",
        "case_id": receipt.get("case_id") == f"ch{chapter:04d}",
        "output_path": receipt.get("output_path") == _relative(root, output_path),
        "request_path": receipt.get("request_path") == _relative(root, request_path),
        "raw_response_path": receipt.get("raw_response_path") == _relative(root, raw_path),
        "response_meta_path": receipt.get("response_meta_path") == _relative(root, meta_path),
        "output_sha256": receipt.get("output_sha256") == sha256_file(output_path),
        "request_sha256": receipt.get("request_sha256") == sha256_file(request_path),
        "raw_response_sha256": receipt.get("raw_response_sha256") == sha256_file(raw_path),
        "response_meta_sha256": receipt.get("response_meta_sha256") == sha256_file(meta_path),
        "input_sha256": receipt.get("input_sha256") == expected_input_sha,
        "prompt_sha256": receipt.get("prompt_sha256") == expected_prompt_sha,
        "runner_sha256": receipt.get("runner_sha256") == config.get("runner_sha256"),
        "provider_config_sha256": receipt.get("provider_config_sha256") == config.get("provider_config_sha256"),
    }
    attempts = parse_attempt_rows(
        run_dir / "call_attempts.jsonl",
        case_id=f"ch{chapter:04d}",
        max_attempts=int(config["max_calls"]),
    )
    fixed_body = copy.deepcopy(request["body"])
    fixed_body.pop("messages", None)
    preflight_checks = preflight.get("checks") if isinstance(preflight.get("checks"), list) else []
    preflight_pins = preflight.get("pinned_files") if isinstance(preflight.get("pinned_files"), list) else []
    seal_path = _path(root, f"work/zbatch_t4/seals/ch{chapter:04d}.run_seal.json")
    seal_check = True
    seal_sha = None
    if require_seal:
        seal = read_json(seal_path)
        current_tree = tree_fingerprint(run_dir)
        seal_check = (
            seal.get("schema_version") == "z-t4-run-seal-v1"
            and seal.get("chapter") == chapter
            and seal.get("run_id") == config["run_id"]
            and seal.get("config_sha256") == sha256_bytes(canonical_json_bytes(config))
            and seal.get("run_tree") == current_tree
        )
        seal_sha = sha256_file(seal_path)
    checks = {
        "run_completed": run_manifest.get("status") == "completed" and "extract" in (run_manifest.get("stages_completed") or []),
        "preflight_pass": preflight.get("preflight") == "pass"
        and preflight.get("model_calls") == 0
        and bool(preflight_checks)
        and all(item.get("ok") is True for item in preflight_checks if isinstance(item, dict))
        and bool(preflight_pins)
        and all(item.get("matches_pin") is True for item in preflight_pins if isinstance(item, dict)),
        "attempt_ledger_pass": attempts["status"] == "pass",
        "run_manifest_call_count_matches": run_manifest.get("calls_made") == attempts["count"],
        "http_200": meta.get("http_status") == 200,
        "finish_reason_stop": meta.get("finish_reason") == "stop",
        "raw_finish_reason_stop": raw_finish_reason == "stop",
        "model_exact": meta.get("requested_model") == "deepseek-v4-flash" and meta.get("response_model") == "deepseek-v4-flash",
        "sampling_exact": fixed_body == {
            "model": "deepseek-v4-flash",
            "temperature": 0.2,
            "max_tokens": 16000,
            "n": 1,
            "response_format": {"type": "json_object"},
            "reasoning_effort": "medium",
        },
        "program_contract_pass": audit.get("status") == "pass" and not audit.get("reasons"),
        "catalog_rebuild_equal": catalog_document == rebuilt_catalog_document,
        "raw_to_output_equal": rematerialized == document,
        "program_audit_rebuild_equal": rebuilt_audit == audit,
        "outside_catalog_anchor_zero": not audit.get("missing_catalog_anchor_ids"),
        "nonempty": bool(document.get("events")),
        "system_message_exact": messages[0] == {"role": "system", "content": SYSTEM_MESSAGE},
        "receipt_hashes_pass": all(receipt_checks.values()),
        "run_tree_seal_pass": seal_check,
    }
    return {
        "chapter": chapter,
        "run_id": config["run_id"],
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "receipt_checks": receipt_checks,
        "attempt_ledger": attempts,
        "network_attempts": attempts["count"],
        "retries": attempts["retries"],
        "event_count": len(document.get("events") or []),
        "anchor_reference_count": audit.get("anchor_reference_count"),
        "request_sha256": sha256_file(request_path),
        "raw_response_sha256": sha256_file(raw_path),
        "output_sha256": sha256_file(output_path),
        "catalog_sha256": sha256_file(catalog_path),
        "program_audit_sha256": sha256_file(audit_path),
        "run_manifest_sha256": sha256_file(run_dir / "run_manifest.json"),
        "preflight_sha256": sha256_file(run_dir / "preflight.json"),
        "run_seal_sha256": seal_sha,
        "messages": messages,
        "fixed_body": fixed_body,
        "document": document,
        "catalog": {str(item["anchor_id"]): str(item["quote"]) for item in catalog},
    }


def create_run_seal(
    *,
    root: Path,
    config_path: Path,
    chapter: int,
) -> dict[str, Any]:
    config = read_json(config_path)
    verified = verify_run_artifacts(
        root=root,
        config=config,
        chapter=chapter,
        require_seal=False,
    )
    if verified["status"] != "pass":
        raise T4PilotError(f"第 {chapter} 章基础工件未过验，拒绝盖运行树封条")
    run_dir = _path(root, f"runs/{config['run_id']}")
    seal = {
        "schema_version": "z-t4-run-seal-v1",
        "chapter": chapter,
        "run_id": config["run_id"],
        "config_path": _relative(root, config_path),
        "config_sha256": sha256_file(config_path),
        "run_tree": tree_fingerprint(run_dir),
        "model": "deepseek-v4-flash",
        "logical_sample_limit": 1,
    }
    seal_path = _path(root, f"work/zbatch_t4/seals/ch{chapter:04d}.run_seal.json")
    if seal_path.exists():
        raise T4PilotError(f"第 {chapter} 章运行树封条已存在，拒绝覆盖")
    write_json(seal_path, seal)
    return seal


def evaluate_pilot(manifest: dict[str, Any], preparation: dict[str, Any], root: Path) -> dict[str, Any]:
    prompt_audit = audit_prompt_change(manifest, root)
    for name, ref in manifest["protected_current_chain"].items():
        _verify_file(root, ref, f"当前保护件 {name}")
    for name, ref in manifest["t4_gate_code"].items():
        _verify_file(root, ref, f"T4 专属闸代码 {name}")
    validate_preparation(manifest, preparation, root)
    target_ref = manifest["coverage_targets"]
    target_path = _path(root, target_ref["path"])
    if sha256_file(target_path) != target_ref["sha256"]:
        raise T4PilotError("覆盖靶配置 SHA 漂移")
    targets = read_json(target_path)["targets"]
    documents: dict[int, dict[str, Any]] = {}
    catalogs: dict[int, dict[str, str]] = {}
    run_rows = []
    user_prompts: list[str] = []
    fixed_bodies: list[dict[str, Any]] = []
    system_messages: list[dict[str, str]] = []
    total_attempts = 0
    retry_total = 0
    for row in preparation["configs"]:
        chapter = int(row["chapter"])
        config_path = _path(root, row["config_path"])
        if sha256_file(config_path) != row["config_sha256"]:
            raise T4PilotError(f"第 {chapter} 章试点配置 SHA 漂移")
        config = read_json(config_path)
        run_dir = _path(root, f"runs/{config['run_id']}")
        verified = verify_run_artifacts(root=root, config=config, chapter=chapter)
        documents[chapter] = verified.pop("document")
        catalogs[chapter] = verified.pop("catalog")
        messages = verified.pop("messages")
        fixed_body = verified.pop("fixed_body")
        user_prompts.append(str(messages[1].get("content") or ""))
        system_messages.append(messages[0])
        fixed_bodies.append(fixed_body)
        total_attempts += int(verified["network_attempts"])
        retry_total += int(verified["retries"])
        run_rows.append(verified)
    template = _path(root, manifest["prompt_change"]["new_path"]).read_text(encoding="utf-8")
    static_prefix = template[: template.find("{{")]
    cache_checks = {
        "template_placeholder_order_unchanged": prompt_audit["placeholder_order_unchanged"],
        "system_message_identical": bool(system_messages)
        and all(message == system_messages[0] for message in system_messages)
        and system_messages[0] == {"role": "system", "content": SYSTEM_MESSAGE},
        "fixed_prefix_identical": all(prompt.startswith(static_prefix) for prompt in user_prompts),
        "sampling_body_identical": all(body == fixed_bodies[0] for body in fixed_bodies),
        "task_instructions_before_dynamic_payload": template.find("{{") > template.find("局部段覆盖"),
    }
    target_rows = [evaluate_target(target, documents, catalogs) for target in targets]
    run_gate = all(row["status"] == "pass" for row in run_rows)
    target_gate = all(row["pass"] for row in target_rows)
    cache_gate = all(cache_checks.values())
    passed = run_gate and target_gate and cache_gate
    return {
        "schema_version": "z-t4-local-segment-pilot-evaluation-v1",
        "status": "pass" if passed else "fail",
        "pilot_pass": passed,
        "model": "deepseek-v4-flash",
        "logical_samples": len(run_rows),
        "network_attempts": total_attempts,
        "retries": retry_total,
        "prompt_change_audit": prompt_audit,
        "run_gate_pass": run_gate,
        "target_gate_pass": target_gate,
        "cache_gate_pass": cache_gate,
        "cache_isomorphism": cache_checks,
        "runs": run_rows,
        "targets": target_rows,
        "next_action": "expand_ch1_20" if passed else "hard_stop_no_patch",
        "boundary": "试点数据只判局部段覆盖候选；不升默认、不铺X02至X04、不写outbox。",
    }


def validate_preparation(
    manifest: dict[str, Any],
    preparation: dict[str, Any],
    root: Path,
) -> dict[int, dict[str, Any]]:
    base_ref = manifest["base_config"]
    base_path = _path(root, base_ref["path"])
    if sha256_file(base_path) != base_ref["sha256"]:
        raise T4PilotError("试点基础配置 SHA 漂移")
    base = read_json(base_path)
    rows = preparation.get("configs")
    if not isinstance(rows, list):
        raise T4PilotError("试点准备单缺 configs")
    by_chapter = {int(row.get("chapter")): row for row in rows if isinstance(row, dict)}
    expected_chapters = [int(chapter) for chapter in manifest["pilot_chapters"]]
    if list(by_chapter) != expected_chapters or len(rows) != len(expected_chapters):
        raise T4PilotError("试点准备单章节或顺序漂移")
    for chapter in expected_chapters:
        row = by_chapter[chapter]
        config_path = _path(root, str(row.get("config_path") or ""))
        expected_config = build_pilot_config(base, manifest, chapter)
        actual_config = read_json(config_path)
        if actual_config != expected_config:
            raise T4PilotError(f"第 {chapter} 章配置不是当前生成函数的精确结果")
        actual_sha = sha256_file(config_path)
        if row.get("config_sha256") != actual_sha:
            raise T4PilotError(f"第 {chapter} 章准备单配置 SHA 漂移")
        if row.get("run_id") != expected_config["run_id"]:
            raise T4PilotError(f"第 {chapter} 章准备单 run_id 漂移")
    return by_chapter


def validate_saved_baseline(
    manifest: dict[str, Any],
    saved_path: Path,
    root: Path,
) -> dict[str, Any]:
    saved = read_json(saved_path)
    live = baseline_equivalence_audit(manifest, root)
    if saved != live:
        raise T4PilotError("保存的基线等价证据与现场零调用重算不一致")
    if (
        live.get("status") != "pass"
        or live.get("model_calls") != 0
        or live.get("chapters_passed") != 20
        or live.get("pilot_request_single_variable", {}).get("status") != "pass"
    ):
        raise T4PilotError("基线等价证据没有满足 T4 调用前钢线")
    return live


def _target_dependencies(target: dict[str, Any]) -> set[int]:
    chapters = {int(target["chapter"])}
    chapters.update(int(row["chapter"]) for row in target.get("linked_events") or [])
    chapters.update(int(row["chapter"]) for row in target.get("related_spans") or [])
    return chapters


def chapter_stop_evaluation(
    manifest: dict[str, Any],
    preparation: dict[str, Any],
    root: Path,
    completed_chapters: list[int],
) -> dict[str, Any]:
    by_chapter = validate_preparation(manifest, preparation, root)
    completed = set(completed_chapters)
    expected_prefix = [int(chapter) for chapter in manifest["pilot_chapters"]][
        : len(completed_chapters)
    ]
    if completed_chapters != expected_prefix:
        raise T4PilotError("单章停点不是预写试点顺序的连续前缀")
    documents: dict[int, dict[str, Any]] = {}
    catalogs: dict[int, dict[str, str]] = {}
    run_rows = []
    for chapter in completed_chapters:
        config = read_json(_path(root, by_chapter[chapter]["config_path"]))
        verified = verify_run_artifacts(root=root, config=config, chapter=chapter)
        documents[chapter] = verified.pop("document")
        catalogs[chapter] = verified.pop("catalog")
        verified.pop("messages")
        verified.pop("fixed_body")
        run_rows.append(verified)
    target_ref = manifest["coverage_targets"]
    target_path = _path(root, target_ref["path"])
    if sha256_file(target_path) != target_ref["sha256"]:
        raise T4PilotError("覆盖靶配置 SHA 漂移")
    targets = read_json(target_path)["targets"]
    available = [target for target in targets if _target_dependencies(target).issubset(completed)]
    target_rows = [evaluate_target(target, documents, catalogs) for target in available]
    newest = completed_chapters[-1]
    newly_due = [
        row
        for target, row in zip(available, target_rows)
        if newest in _target_dependencies(target)
        and not _target_dependencies(target).issubset(set(completed_chapters[:-1]))
    ]
    checks = {
        "all_completed_runs_valid": bool(run_rows) and all(row["status"] == "pass" for row in run_rows),
        "newest_chapter_has_due_target": bool(newly_due),
        "all_available_targets_pass": bool(target_rows) and all(row["pass"] for row in target_rows),
    }
    passed = all(checks.values())
    return {
        "schema_version": "z-t4-chapter-stop-v1",
        "status": "pass" if passed else "fail",
        "chapter": newest,
        "completed_chapters": completed_chapters,
        "checks": checks,
        "runs": run_rows,
        "targets": target_rows,
        "newly_due_target_ids": [row["id"] for row in newly_due],
        "next_action": "allow_next_pilot_chapter" if passed else "hard_stop_no_more_calls",
    }


def validate_call_gate(
    manifest: dict[str, Any],
    preparation: dict[str, Any],
    root: Path,
    *,
    chapter: int,
    saved_baseline_path: Path,
) -> dict[str, Any]:
    for name, ref in manifest["protected_current_chain"].items():
        _verify_file(root, ref, f"当前保护件 {name}")
    for name, ref in manifest["t4_gate_code"].items():
        _verify_file(root, ref, f"T4 专属闸代码 {name}")
    validate_saved_baseline(manifest, saved_baseline_path, root)
    by_chapter = validate_preparation(manifest, preparation, root)
    order = [int(value) for value in manifest["pilot_chapters"]]
    if chapter not in order:
        raise T4PilotError(f"章节不在 T4 预写顺序：{chapter}")
    index = order.index(chapter)
    prior = order[:index]
    current_config = read_json(_path(root, by_chapter[chapter]["config_path"]))
    current_run_dir = _path(root, f"runs/{current_config['run_id']}")
    current_permit = _path(root, permit_relative_path(chapter))
    if current_permit.exists():
        raise T4PilotError(f"第 {chapter} 章一次性通行证在调用闸前已存在，拒绝沿用")
    if current_run_dir.exists():
        raise T4PilotError(
            f"第 {chapter} 章运行目录已经存在，禁止 resume 或再次采样：{current_run_dir.name}"
        )
    for later in order[index + 1 :]:
        later_config = read_json(_path(root, by_chapter[later]["config_path"]))
        later_run_dir = _path(root, f"runs/{later_config['run_id']}")
        if later_run_dir.exists():
            raise T4PilotError(f"发现越序试点运行：第 {later} 章")
    if prior:
        prior_gate = chapter_stop_evaluation(manifest, preparation, root, prior)
        if prior_gate["status"] != "pass":
            raise T4PilotError(f"前序试点停点未过，禁止调用第 {chapter} 章")
    else:
        for later in order[1:]:
            later_config = read_json(_path(root, by_chapter[later]["config_path"]))
            if _path(root, f"runs/{later_config['run_id']}").exists():
                raise T4PilotError("首章调用前已出现后续章运行目录")
    return {
        "status": "pass",
        "chapter": chapter,
        "config_path": by_chapter[chapter]["config_path"],
        "config_sha256": by_chapter[chapter]["config_sha256"],
        "run_id": current_config["run_id"],
        "prior_chapters": prior,
        "existing_run_reuse_allowed": False,
        "model": "deepseek-v4-flash",
        "logical_sample_limit": 1,
        "network_attempt_limit": current_config["max_calls"],
    }


def result_exit_code(command: str, result: dict[str, Any]) -> int:
    if command == "evaluate" and result.get("pilot_pass") is not True:
        return 2
    if command == "run-chapter" and result.get("status") != "pass":
        return 2
    return 0
