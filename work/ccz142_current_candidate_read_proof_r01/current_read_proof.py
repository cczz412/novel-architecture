"""Read current candidate from the existing authority store and project a human card.

This package does not write pointers, candidates, or a second store. It only
calls the existing B06/CandidateAuthorityStore read APIs, or reports a typed gap.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
B06_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b06_commit_core_r01"
for candidate in (REPOSITORY_ROOT, MODULE_ROOT, AUTHORITY_ROOT, B01_ROOT, B06_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from b06_contracts import B06ContractError  # noqa: E402
from candidate_authority import CandidateAuthorityError, CandidateAuthorityStore  # noqa: E402

DOCUMENT_IDENTITY = "CCZ142-CURRENT-CANDIDATE-READ-PROOF-R01"
GITHUB_ISSUE = 264
BASE_MAIN_SHA = "e01bb638fdbb9cf509aa22e588522840cea799e5"
DEFAULT_PROJECT_SCOPE_ID = "fixture-project-001"
DATABASE_FILENAME = "b06-commit-core.sqlite3"
FIXTURE_POINTER_NAMESPACE = "FIXTURE_ONLY"
FIXTURE_ACCESS = "POLICY_FIXTURE_READ_ONLY"
PRODUCT_CANDIDATE_NAMESPACE = "PRODUCT" + "_CANDIDATE_AUTHORITY"

STATUS_READ_OK = "READ_OK"
STATUS_GAP = "GAP"

GAP_NO_LIVE_STORE = "GAP_NO_LIVE_STORE"
GAP_STORE_MISSING = "GAP_STORE_MISSING"
GAP_POINTER_MISSING = "GAP_POINTER_MISSING"
GAP_POINTER_AMBIGUOUS = "GAP_POINTER_AMBIGUOUS"
GAP_CANDIDATE_MISSING = "GAP_CANDIDATE_MISSING"
GAP_NOT_PRODUCT_IDENTITY = "GAP_NOT_PRODUCT_IDENTITY"
GAP_NO_HUMAN_ITEMS = "GAP_NO_HUMAN_ITEMS"
GAP_REAL_NOVEL_NOT_IN_SCOPE = "GAP_REAL_NOVEL_NOT_IN_SCOPE"

STANDING_BOUNDARIES = (GAP_REAL_NOVEL_NOT_IN_SCOPE,)


SCOPE_UNPROVIDED = "未提供"

NAMED_CARD_IDENTITY_FILENAME = "named-card-identity.json"


def load_named_card_identity(store_root: Path) -> dict[str, Any] | None:
    """Read optional sidecar beside sqlite. Bad files are ignored."""

    target = Path(store_root) / NAMED_CARD_IDENTITY_FILENAME
    if not target.is_file():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    title = payload.get("book_title")
    chapter_no = payload.get("chapter_no")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(chapter_no, int) or isinstance(chapter_no, bool):
        return None
    return payload


def apply_named_card_identity(
    scope: dict[str, Any],
    store_root: Path,
) -> dict[str, Any]:
    payload = load_named_card_identity(store_root)
    if payload is None:
        return scope
    scope["book_title"] = str(payload["book_title"]).strip()
    scope["chapter_id"] = str(payload["chapter_no"])
    return scope




def empty_coverage_view() -> dict[str, Any]:
    """No candidate set yet. Do not write zero as if coverage was measured."""

    return {
        "wired": False,
        "b02_originals": False,
        "chapter_claim": "不足以判断全部覆盖",
        "density_line": None,
        "segment_counts": [],
        "bindings": [],
        "unobserved_note": (
            "尚无 B02 穷尽观察。不能把没列到的来源说成没有漏抽。"
        ),
    }


def project_coverage_view(card: dict[str, Any] | None) -> dict[str, Any]:
    """Derive count distribution from current items. Not a B02 original."""

    view = empty_coverage_view()
    if not isinstance(card, dict):
        return view
    items = card.get("items")
    if not isinstance(items, list) or not items:
        return view
    seg_counts: dict[int, int] = {}
    evidence_counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence = item.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            key = evidence.strip()
            evidence_counts[key] = evidence_counts.get(key, 0) + 1
        locations = item.get("match_locations")
        segs: set[int] = set()
        if isinstance(locations, list):
            for loc in locations:
                if not isinstance(loc, dict):
                    continue
                seg = loc.get("seg")
                if isinstance(seg, int) and not isinstance(seg, bool):
                    segs.add(seg)
        for seg in segs:
            seg_counts[seg] = seg_counts.get(seg, 0) + 1
    if not evidence_counts:
        return view
    parts = [
        f"责任段 {seg} 有 {seg_counts[seg]} 条" for seg in sorted(seg_counts)
    ]
    if not parts:
        total = sum(evidence_counts.values())
        parts = [f"本次已返回 {total} 条"]
    view["wired"] = True
    view["density_line"] = (
        "密度（仅说明本次已返回的候选）："
        + "；".join(parts)
        + "。这是条数分布，不是抽全评分，也不能按条数比漏抽。"
    )
    view["segment_counts"] = [
        {"seg": seg, "candidate_count": seg_counts[seg]}
        for seg in sorted(seg_counts)
    ]
    view["bindings"] = [
        {
            "source_evidence": source,
            "candidate_count": count,
            "status": "BOUND",
        }
        for source, count in sorted(evidence_counts.items())
    ]
    return view


def empty_result_scope() -> dict[str, Any]:
    """Honest unknowns. Never invent a book title or whole-chapter claim."""

    return {
        "book_title": SCOPE_UNPROVIDED,
        "project_scope_id": SCOPE_UNPROVIDED,
        "chapter_id": SCOPE_UNPROVIDED,
        "revision_no": SCOPE_UNPROVIDED,
        "revision_text_sha256": SCOPE_UNPROVIDED,
        "responsibility_segment": SCOPE_UNPROVIDED,
        "display_range": "当前指针指向的这一份候选。不是已确认的整章汇总。",
        "chapter_completeness": "未确认",
        "density": "尚未提供，不编数字",
    }


def project_result_scope(
    *,
    pointer: dict[str, Any] | None = None,
    candidate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scope = empty_result_scope()
    pointer = pointer if isinstance(pointer, dict) else {}
    candidate = candidate if isinstance(candidate, dict) else {}
    ref = pointer.get("chapter_revision_ref")
    payload = candidate.get("payload")
    if not isinstance(ref, dict) and isinstance(payload, dict):
        ref = payload.get("chapter_revision_ref")
    if isinstance(ref, dict):
        chapter_id = ref.get("chapter_id")
        if isinstance(chapter_id, str) and chapter_id:
            scope["chapter_id"] = chapter_id
        revision_no = ref.get("revision_no")
        if isinstance(revision_no, int) and not isinstance(revision_no, bool):
            scope["revision_no"] = revision_no
        revision_hash = ref.get("revision_text_sha256")
        if isinstance(revision_hash, str) and revision_hash:
            scope["revision_text_sha256"] = revision_hash
    project_scope_id = pointer.get("project_scope_id")
    if isinstance(project_scope_id, str) and project_scope_id:
        scope["project_scope_id"] = project_scope_id
    seg = pointer.get("seg")
    if isinstance(seg, int) and not isinstance(seg, bool):
        scope["responsibility_segment"] = seg
        scope["display_range"] = f"当前指针的责任段 {seg}。不是已确认的整章汇总。"
    return scope


READ_PATH = {
    "store_class": (
        "work/ccz142_candidate_authority_r01/candidate_authority.py"
        "::CandidateAuthorityStore"
    ),
    "inherits": "B06CommitStore",
    "read_pointer": "B06CommitStore.read_pointer",
    "read_candidate": "B06CommitStore.read_candidate",
    "database_filename": DATABASE_FILENAME,
    "pointer_discovery": (
        "readonly SELECT logical_pointer_key FROM current_pointers; "
        "discovery probe, not a second writer"
    ),
    "human_card": "project payload.items to fact/status/evidence plus lineage_id and match_locations when present; never re-search text; no patch advice",
    "not_this_path": [
        "work/ccz57_m3_b09_current_causal_hint_view_r01",
        "GitHub pull request 235 product namespace cutover",
        "real novel API",
    ],
}

KIND_BY_STATUS = {
    "已发生": "已发生",
    "正在发生": "已发生",
    "推测": "传闻／怀疑",
    "误信": "误信",
    "计划": "未证实",
    "承诺": "未证实",
    "条件": "未证实",
    "否定": "否定",
}

STORE_ERROR_TO_GAP = {
    "B06_STORE_NOT_INITIALIZED": GAP_STORE_MISSING,
    "B06_WRITE_SET_ESCAPE": GAP_STORE_MISSING,
    "AUTHORITY_SCHEMA_NOT_INITIALIZED": GAP_STORE_MISSING,
    "AUTHORITY_SCHEMA_IDENTITY_MISSING": GAP_STORE_MISSING,
    "AUTHORITY_SCHEMA_IDENTITY_MISMATCH": GAP_STORE_MISSING,
    "AUTHORITY_SCHEMA_LAYOUT_MISMATCH": GAP_STORE_MISSING,
    "AUTHORITY_LOCK_MISSING": GAP_STORE_MISSING,
    "AUTHORITY_PROJECT_SCOPE_MISSING": GAP_STORE_MISSING,
    "PROJECT_SCOPE_INVALID": GAP_STORE_MISSING,
    "PROJECT_SCOPE_STORE_MISMATCH": GAP_STORE_MISSING,
    "B06_POINTER_NOT_FOUND": GAP_POINTER_MISSING,
    "B06_CANDIDATE_NOT_FOUND": GAP_CANDIDATE_MISSING,
    "B06_CANDIDATE_REF_MISMATCH": GAP_CANDIDATE_MISSING,
}


def _error_code(error: BaseException) -> str | None:
    code = getattr(error, "code", None)
    return code if isinstance(code, str) else None


def _base_proof() -> dict[str, Any]:
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": STATUS_GAP,
        "read_path": dict(READ_PATH),
        "identity": {
            "pointer_namespace": None,
            "candidate_access": None,
            "candidate_schema_id": None,
            "candidate_contract": None,
            "product_adopted": False,
        },
        "pointer_key": None,
        "discovered_pointer_keys": [],
        "human_card": None,
        "result_scope": empty_result_scope(),
        "coverage_view": empty_coverage_view(),
        "gaps": [],
        "limitations": [],
        "standing_boundaries": list(STANDING_BOUNDARIES),
        "store_error_code": None,
    }


def _gap_proof(
    code: str,
    *,
    extra: dict[str, Any] | None = None,
    store_error_code: str | None = None,
) -> dict[str, Any]:
    proof = _base_proof()
    proof["status"] = STATUS_GAP
    proof["gaps"] = [code]
    proof["store_error_code"] = store_error_code
    if extra:
        proof.update(extra)
    return proof


def _map_store_error(error: BaseException) -> dict[str, Any]:
    code = _error_code(error)
    gap = STORE_ERROR_TO_GAP.get(code or "", GAP_STORE_MISSING)
    return _gap_proof(gap, store_error_code=code)


def list_logical_pointer_keys(store_root: Path) -> list[str]:
    """Read-only discovery of pointer keys. Not a second writer."""

    database = store_root / DATABASE_FILENAME
    if not database.is_file():
        return []
    uri = f"file:{database.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT logical_pointer_key FROM current_pointers "
            "ORDER BY logical_pointer_key"
        ).fetchall()
    return [str(row[0]) for row in rows if isinstance(row[0], str) and row[0]]


def _item_kind(status: str) -> str:
    return KIND_BY_STATUS.get(status, "未证实")


def _is_plain_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def project_item_source(raw: dict[str, Any]) -> tuple[str, list[dict[str, int]]]:
    """Copy lineage and match locations already on the candidate. Never re-search text."""

    lineage = raw.get("lineage_id")
    if isinstance(lineage, str) and lineage.startswith("lin_") and lineage[4:]:
        stable = lineage
    else:
        stable = SCOPE_UNPROVIDED
    locations: list[dict[str, int]] = []
    binding = raw.get("evidence_binding")
    if isinstance(binding, dict):
        matches = binding.get("match_locations")
        if isinstance(matches, list):
            for loc in matches:
                if not isinstance(loc, dict):
                    continue
                seg = loc.get("seg")
                start = loc.get("start_byte")
                end = loc.get("end_byte")
                if (
                    _is_plain_int(seg)
                    and _is_plain_int(start)
                    and _is_plain_int(end)
                    and start < end
                ):
                    locations.append(
                        {"seg": int(seg), "start_byte": int(start), "end_byte": int(end)}
                    )
    return stable, locations


def format_source_locations(locations: list[dict[str, int]]) -> str:
    if not locations:
        return SCOPE_UNPROVIDED
    parts = [
        f"责任段 {loc['seg']}，字节 {loc['start_byte']}–{loc['end_byte']}"
        for loc in locations
    ]
    return "；".join(parts)


def project_human_card(
    *,
    pointer: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    payload = candidate.get("payload")
    raw_items = payload.get("items") if isinstance(payload, dict) else None
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            fact = raw.get("fact")
            status = raw.get("status")
            evidence = raw.get("evidence")
            if not isinstance(fact, str) or not fact:
                continue
            if not isinstance(status, str) or not status:
                continue
            if not isinstance(evidence, str) or not evidence:
                continue
            stable, locations = project_item_source(raw)
            item: dict[str, Any] = {
                "fact": fact,
                "status": status,
                "evidence": evidence,
                "kind": _item_kind(status),
                "stable_item_id": stable,
                "match_locations": locations,
                "source_location": format_source_locations(locations),
            }
            speaker = raw.get("speaker")
            if isinstance(speaker, str) and speaker:
                item["speaker"] = speaker
            items.append(item)
    return {
        "title": "抽出了什么（人话结果卡）",
        "identity_note": (
            "这是夹具 current，不是产品权威，也不是正式事实。"
            "没有修补建议。"
        ),
        "pointer_namespace": pointer.get("pointer_namespace"),
        "item_count": len(items),
        "items": items,
    }


def render_human_text(proof: dict[str, Any]) -> str:
    lines = [
        "A 轨只读证明：current 候选从哪读",
        f"读路：{proof['read_path']['store_class']}",
        f"状态：{proof['status']}",
    ]
    if proof["gaps"]:
        lines.append("缺口：" + "、".join(proof["gaps"]))
    if proof["limitations"]:
        lines.append("限制：" + "、".join(proof["limitations"]))
    identity = proof["identity"]
    if identity.get("pointer_namespace"):
        lines.append(
            "身份："
            f"{identity['pointer_namespace']}／"
            f"{identity['candidate_access'] or '未知 access'}；"
            "不是产品采用"
        )
    card = proof.get("human_card")
    if isinstance(card, dict) and card.get("items"):
        lines.append(card["title"])
        for item in card["items"]:
            speaker = f"（{item['speaker']}）" if "speaker" in item else ""
            lines.append(
                f"- [{item['kind']}] {item['fact']}{speaker}｜证据：{item['evidence']}"
                f"｜条目：{item.get('stable_item_id') or SCOPE_UNPROVIDED}"
                f"｜位置：{item.get('source_location') or SCOPE_UNPROVIDED}"
            )
    lines.append("真实小说 API 不在本票范围。")
    return "\n".join(lines)


def prove_current_read(
    *,
    store_root: Path | None = None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
    pointer_key: str | None = None,
) -> dict[str, Any]:
    """Open the existing authority store, read current, or return a typed gap."""

    if store_root is None:
        return _gap_proof(GAP_NO_LIVE_STORE)

    store_root = Path(store_root)
    database = store_root / DATABASE_FILENAME
    if not store_root.exists() or not database.is_file():
        return _gap_proof(GAP_STORE_MISSING)

    try:
        discovered = list_logical_pointer_keys(store_root)
        store = CandidateAuthorityStore(
            store_root,
            project_scope_id=project_scope_id,
        )
        selected_key = pointer_key
        if selected_key is None:
            if len(discovered) == 0:
                return _gap_proof(
                    GAP_POINTER_MISSING,
                    extra={"discovered_pointer_keys": discovered},
                )
            if len(discovered) > 1:
                return _gap_proof(
                    GAP_POINTER_AMBIGUOUS,
                    extra={"discovered_pointer_keys": discovered},
                )
            selected_key = discovered[0]
        pointer = store.read_pointer(selected_key)
        candidate_ref = pointer.get("current_candidate_version_ref")
        if not isinstance(candidate_ref, dict):
            return _gap_proof(
                GAP_CANDIDATE_MISSING,
                extra={
                    "pointer_key": selected_key,
                    "discovered_pointer_keys": discovered,
                },
            )
        candidate = store.read_candidate(candidate_ref)
    except (B06ContractError, CandidateAuthorityError, sqlite3.Error) as error:
        mapped = _map_store_error(error)
        mapped["pointer_key"] = pointer_key
        return mapped

    namespace = pointer.get("pointer_namespace")
    access = candidate.get("access")
    card = project_human_card(pointer=pointer, candidate=candidate)
    result_scope = project_result_scope(pointer=pointer, candidate=candidate)
    result_scope = apply_named_card_identity(result_scope, store_root)
    limitations: list[str] = []
    if namespace != PRODUCT_CANDIDATE_NAMESPACE:
        limitations.append(GAP_NOT_PRODUCT_IDENTITY)
    proof = _base_proof()
    proof["pointer_key"] = selected_key
    proof["discovered_pointer_keys"] = discovered
    proof["identity"] = {
        "pointer_namespace": namespace,
        "candidate_access": access,
        "candidate_schema_id": pointer.get("candidate_schema_id"),
        "candidate_contract": candidate.get("contract_version"),
        "product_adopted": False,
    }
    coverage_view = project_coverage_view(card)
    if coverage_view["wired"]:
        result_scope["density"] = coverage_view["density_line"]
    proof["human_card"] = card
    proof["result_scope"] = result_scope
    proof["coverage_view"] = coverage_view
    proof["limitations"] = limitations
    if card["item_count"] == 0:
        proof["status"] = STATUS_GAP
        proof["gaps"] = [GAP_NO_HUMAN_ITEMS]
        return proof
    if namespace != FIXTURE_POINTER_NAMESPACE:
        proof["status"] = STATUS_GAP
        proof["gaps"] = [GAP_NOT_PRODUCT_IDENTITY]
        return proof
    proof["status"] = STATUS_READ_OK
    proof["gaps"] = []
    return proof


def dumps_proof(proof: dict[str, Any]) -> str:
    return json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
