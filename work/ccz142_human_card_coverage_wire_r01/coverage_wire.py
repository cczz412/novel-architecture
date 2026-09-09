"""Open the existing card; coverage/density come from prove_current_read."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    NAMED_ROOT,
    PROOF_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from html_render import show_current_html  # noqa: E402
from named_chapter import DEFAULT_PROJECT_SCOPE_ID  # noqa: E402

DOCUMENT_IDENTITY = "CCZ142-HUMAN-CARD-COVERAGE-WIRE-R01"
GITHUB_ISSUE = 305
BASE_MAIN_SHA = "ef1d3ad96867539faa8105f57be81b16401aae1b"


def open_coverage_card(
    *,
    store_root: Path,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Original show path. Coverage is projected inside prove_current_read."""

    shown = show_current_html(
        store_root=Path(store_root),
        project_scope_id=project_scope_id,
    )
    proof = shown["proof"]
    view = proof.get("coverage_view") if isinstance(proof, dict) else {}
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": proof.get("status") if isinstance(proof, dict) else None,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "coverage_wired": bool(
            isinstance(view, dict) and view.get("wired") is True
        ),
        "b02_originals": False,
        "html": shown["html"],
        "markdown": shown["markdown"],
        "proof": proof,
    }


def dumps_result(result: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"html", "markdown"}
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
