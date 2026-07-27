from __future__ import annotations

import pytest

from experiments.extraction_redesign_v02_overnight_20260725.V02_R1_route_comparison_r02_20260726 import (
    v02_r1_route_finalize_r04 as r04,
)


@pytest.mark.parametrize(
    ("before", "category", "after"),
    [
        ("ACTUAL", "KEY_CAUSAL_TRIGGER", "CONFIRMED"),
        ("ESTABLISHED", "WORLD_RULE_ABILITY_LIMIT_COST", "CONFIRMED"),
        ("HAPPENED", "CHAPTER_EXIT_STATE", "CONFIRMED"),
        ("OCCURRED", "CHARACTER_STATE_CHANGE", "CONFIRMED"),
        ("OBSERVED", "CHARACTER_STATE_CHANGE", "CONFIRMED"),
        (
            "OBSERVED",
            r04.UNRESOLVED_CATEGORY,
            "UNRESOLVED",
        ),
        ("ONGOING", "KNOWLEDGE_OR_BELIEF_CHANGE", "CONFIRMED"),
        ("ONGOING", r04.UNRESOLVED_CATEGORY, "UNRESOLVED"),
        ("FORESHADOWED", r04.UNRESOLVED_CATEGORY, "UNRESOLVED"),
        ("PENDING", r04.UNRESOLVED_CATEGORY, "UNRESOLVED"),
        ("RISK", r04.UNRESOLVED_CATEGORY, "UNRESOLVED"),
        ("UNKNOWN", r04.UNRESOLVED_CATEGORY, "UNRESOLVED"),
        ("PLANNED", "GOAL_PLAN_PROMISE_THREAT", "PLANNED"),
    ],
)
def test_exact_actuality_normalization(
    before: str,
    category: str,
    after: str,
) -> None:
    assert r04.normalize_actuality(before, category) == after


def test_unresolved_alias_cannot_cross_category() -> None:
    with pytest.raises(ValueError, match="仅允许"):
        r04.normalize_actuality("RISK", "CHARACTER_STATE_CHANGE")


def test_unknown_alias_is_rejected() -> None:
    with pytest.raises(ValueError, match="未登记"):
        r04.normalize_actuality("MAYBE", r04.UNRESOLVED_CATEGORY)
