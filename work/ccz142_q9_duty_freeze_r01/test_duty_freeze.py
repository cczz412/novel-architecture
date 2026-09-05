from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from self_check import FROZEN_LABELS, run_self_check  # noqa: E402

REPO = ROOT.parents[1]


def test_self_check_passes() -> None:
    result = run_self_check()
    assert result["result"] == "PASS"
    assert result["frozen_duties"] == list(FROZEN_LABELS)
    assert result["on_demand_modules"] == ["B03", "B04", "B05", "B09"]


def test_json_does_not_claim_b02_numbers_or_best_model() -> None:
    payload = json.loads((ROOT / "DUTY_FREEZE.json").read_text(encoding="utf-8"))
    assert "wire_b02_coverage_numbers" in payload["explicitly_deferred"]
    assert "declare_best_model" in payload["explicitly_deferred"]
    assert payload["status"] == "SIGNPOST_ONLY"


def test_side_path_readmes_keep_original_titles() -> None:
    mapping = {
        "work/ccz57_m3_b03_bound_evidence_read_r03_5": "B-03",
        "work/ccz57_m3_b04_patch_atomic_group_r03_5": "B-04",
        "work/ccz57_m3_b05_patch_route_r03_5": "B-05",
        "work/ccz57_m3_b09_current_causal_hint_view_r01": "B-09",
    }
    for rel, needle in mapping.items():
        first = (REPO / rel / "README.md").read_text(encoding="utf-8").splitlines()[0]
        assert needle in first
        assert first.startswith("# ")
