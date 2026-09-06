"""Wire a frozen synthetic chapter through CCZ-142 extraction into the existing human card."""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_candidate_authority_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
B01_ROOT = REPOSITORY_ROOT / "work" / "ccz57_m3_b01_candidate_version_r03_5"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    AUTHORITY_ROOT,
    PROOF_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
    B01_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from candidate_authority import (  # noqa: E402
    CandidateAuthorityStore,
    CandidateRootInitializer,
)
from html_render import show_current_html  # noqa: E402
from shadow_fixtures import (  # noqa: E402
    MutableRootAuthorityReader,
    authority_snapshot,
    root_request,
)
from work.ccz57_m3_b01_candidate_version_r03_5.fixtures import (  # noqa: E402
    REVISION_TEXT,
)

DOCUMENT_IDENTITY = "CCZ142-HUMAN-CARD-VERTICAL-WIRE-R01"
GITHUB_ISSUE = 295
BASE_MAIN_SHA = "79a034bce97de06a08d7fee871551d6e6a938339"
DEFAULT_PROJECT_SCOPE_ID = "fixture-project-001"
DATABASE_FILENAME = "b06-commit-core.sqlite3"
OPERATION_ID = "human-card-vertical-wire-r01"
SYNTHETIC_CHAPTER = REVISION_TEXT
STATUS_WIRED = "WIRED"
STATUS_CLOSED = "CLOSED"
GAP_CHAPTER_MISMATCH = "GAP_CHAPTER_MISMATCH"
GAP_NO_STORE_ROOT = "GAP_NO_STORE_ROOT"
GAP_REAL_NOVEL_NOT_IN_SCOPE = "GAP_REAL_NOVEL_NOT_IN_SCOPE"

# Evidence quotes must already exist in the frozen synthetic chapter / B01 seg 1.
FROZEN_HANDOFF_ITEMS: list[dict[str, str]] = [
    {
        "fact": "甲进入北塔。",
        "status": "已发生",
        "evidence": "甲走进北塔。",
    },
    {
        "fact": "甲拿起铜钥匙。",
        "status": "已发生",
        "evidence": "甲拿起铜钥匙。",
        "speaker": "旁白",
    },
    {
        "fact": "甲可能还在北塔。",
        "status": "推测",
        "evidence": "甲走进北塔。",
    },
    {
        "fact": "甲以为铜钥匙已经到手。",
        "status": "误信",
        "evidence": "甲拿起铜钥匙。",
        "speaker": "旁白",
    },
    {
        "fact": "甲还要再进北塔。",
        "status": "计划",
        "evidence": "甲走进北塔。",
    },
]


def load_synthetic_chapter(path: Path | None = None) -> str:
    target = path or (MODULE_ROOT / "synthetic_chapter.txt")
    return target.read_text(encoding="utf-8").strip()


def extract_handoff_items(chapter_text: str) -> list[dict[str, str]] | None:
    """Frozen extractor. Not a model. Wrong chapter returns None and must not write."""

    if chapter_text.strip() != SYNTHETIC_CHAPTER:
        return None
    return deepcopy(FROZEN_HANDOFF_ITEMS)


def _closed(
    *,
    gaps: list[str],
    shown: dict[str, Any],
) -> dict[str, Any]:
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": STATUS_CLOSED,
        "gaps": gaps,
        "wrote": False,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "standing_boundaries": [GAP_REAL_NOVEL_NOT_IN_SCOPE],
        "shown": shown,
        "html": shown["html"],
        "markdown": shown["markdown"],
        "proof": shown["proof"],
    }


def wire_synthetic_chapter_to_card(
    *,
    chapter_text: str,
    store_root: Path | None = None,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Admit frozen extraction into the existing authority store, then open the existing card."""

    items = extract_handoff_items(chapter_text)
    if items is None:
        return _closed(gaps=[GAP_CHAPTER_MISMATCH], shown=show_current_html())
    if store_root is None:
        return _closed(gaps=[GAP_NO_STORE_ROOT], shown=show_current_html())

    store_root = Path(store_root)
    store = CandidateAuthorityStore(store_root, project_scope_id=project_scope_id)
    store.initialize_authority_schema()
    request = root_request()
    request["raw_items"] = items
    request["operation_id"] = OPERATION_ID
    published = CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(request)),
    ).initialize_root(request)
    shown = show_current_html(
        store_root=store.root,
        project_scope_id=project_scope_id,
        pointer_key=published["logical_pointer_key"],
    )
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": STATUS_WIRED,
        "gaps": [],
        "wrote": True,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "pointer_key": published["logical_pointer_key"],
        "extraction_item_count": len(items),
        "standing_boundaries": [GAP_REAL_NOVEL_NOT_IN_SCOPE],
        "shown": shown,
        "html": shown["html"],
        "markdown": shown["markdown"],
        "proof": shown["proof"],
    }


def dumps_result(result: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"shown", "html", "markdown"}
    }
    payload["proof"] = result["proof"]
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
