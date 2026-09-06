"""Open the existing card via the original proof / HTML read path."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

MODULE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
STORE_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_identity_store_r01"
NAMED_ROOT = REPOSITORY_ROOT / "work" / "ccz142_named_chapter_txt_card_r01"
PROOF_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_proof_r01"
DISPLAY_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_display_r01"
PREVIEW_ROOT = REPOSITORY_ROOT / "work" / "ccz142_current_candidate_read_preview_r01"
for candidate in (
    REPOSITORY_ROOT,
    MODULE_ROOT,
    STORE_ROOT,
    NAMED_ROOT,
    PROOF_ROOT,
    DISPLAY_ROOT,
    PREVIEW_ROOT,
):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from current_read_proof import prove_current_read  # noqa: E402
from html_render import show_current_html  # noqa: E402
from named_chapter import DEFAULT_PROJECT_SCOPE_ID  # noqa: E402

DOCUMENT_IDENTITY = "CCZ142-NAMED-IDENTITY-READ-R01"
GITHUB_ISSUE = 303
BASE_MAIN_SHA = "e2559ca23ccbe586416dd3bced3fae8a2fdaeb82"


def open_original_store_card(
    *,
    store_root: Path,
    project_scope_id: str = DEFAULT_PROJECT_SCOPE_ID,
) -> dict[str, Any]:
    """Open with prove/show. Sidecar is applied inside prove_current_read."""

    shown = show_current_html(
        store_root=Path(store_root),
        project_scope_id=project_scope_id,
    )
    proof = shown["proof"]
    scope = proof.get("result_scope") if isinstance(proof, dict) else {}
    title = scope.get("book_title") if isinstance(scope, dict) else None
    return {
        "document_identity": DOCUMENT_IDENTITY,
        "github_issue": GITHUB_ISSUE,
        "base_main_sha": BASE_MAIN_SHA,
        "status": proof.get("status") if isinstance(proof, dict) else None,
        "product_adopted": False,
        "pointer_namespace": "FIXTURE_ONLY",
        "identity_from_sidecar": title not in (None, "未提供"),
        "html": shown["html"],
        "markdown": shown["markdown"],
        "proof": proof,
        "prove": prove_current_read(
            store_root=Path(store_root),
            project_scope_id=project_scope_id,
        ),
    }


def dumps_result(result: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in result.items()
        if key not in {"html", "markdown"}
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
