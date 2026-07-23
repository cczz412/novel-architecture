from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import z75_multidirection_score as score  # noqa: E402


class Z75MultidirectionScoreTests(unittest.TestCase):
    def make_adjudication(
        self,
        path: Path,
        direction_id: str,
        *,
        gold_verdicts: list[str] | None = None,
        rescue_first_partial: bool = False,
        degrade_first_preserved: bool = False,
    ) -> dict[str, object]:
        formal = score.load_formal_gold(score.DEFAULT_GOLD_POINTER)
        old34 = score.load_old34(score.DEFAULT_OLD34_BASELINE)
        part_ids = list(formal["parts"])
        verdicts = gold_verdicts or [
            "strict_hit",
            "semantic_shadow",
            "coverage_only_invalid_support",
            *(["miss"] * 20),
        ]
        self.assertEqual(len(verdicts), 23)
        gold_rows = [
            {
                "part_id": part_id,
                "verdict": verdict,
                "candidate_event_ids": [] if verdict == "miss" else [f"EV-{index:02d}"],
                "semantic_review_note": f"人工判词：{part_id}",
            }
            for index, (part_id, verdict) in enumerate(zip(part_ids, verdicts), start=1)
        ]
        current_rows = [
            {
                "record_id": record_id,
                "verdict": old_row["verdict"],
                "candidate_event_ids": [],
                "semantic_review_note": f"人工判词：{record_id}",
            }
            for record_id, old_row in old34["rows"].items()
        ]
        if rescue_first_partial:
            next(
                row for row in current_rows if row["verdict"] == "partially_preserved"
            )["verdict"] = "preserved"
        if degrade_first_preserved:
            next(row for row in current_rows if row["verdict"] == "preserved")[
                "verdict"
            ] = "partially_preserved"
        doc: dict[str, object] = {
            "schema_version": "z75-manual-adjudication-v1",
            "direction_id": direction_id,
            "gold_rows": gold_rows,
            "current_rows": current_rows,
            "overflow_rows": [
                {
                    "event_id": f"{direction_id}-OVERFLOW-01",
                    "event": "只列待判溢出，不自动评分。",
                }
            ],
        }
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return doc

    def make_usage(self, path: Path, *, omit_chapter: int | None = None) -> None:
        rows = []
        for chapter in score.TARGET_CHAPTERS:
            if chapter == omit_chapter:
                continue
            rows.append(
                {
                    "case_id": f"pilot_ch{chapter:04d}",
                    "elapsed_ms": chapter * 100,
                    "finish_reason": "stop",
                    "stage_max_tokens": 32000,
                    "usage": {
                        "prompt_tokens": 1000 + chapter,
                        "completion_tokens": 2000 + chapter,
                        "total_tokens": 3000 + chapter * 2,
                        "completion_tokens_details": {
                            "reasoning_tokens": 1500 + chapter
                        },
                    },
                }
            )
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def make_four_specs(self, root: Path) -> dict[str, tuple[Path, Path]]:
        specs: dict[str, tuple[Path, Path]] = {}
        for index, direction_id in enumerate(("JR08", "JR28", "TRIAD08", "TRIAD16")):
            adjudication = root / f"{direction_id}.json"
            usage = root / f"{direction_id}.usage.jsonl"
            self.make_adjudication(
                adjudication,
                direction_id,
                rescue_first_partial=index == 1,
                degrade_first_preserved=index == 3,
            )
            self.make_usage(usage)
            specs[direction_id] = (adjudication, usage)
        return specs

    def test_aggregates_four_manual_directions_without_semantic_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            specs = self.make_four_specs(Path(temp))
            result = score.build_scorecard(specs)

        self.assertEqual(result["status"], "candidate_silver_only")
        self.assertFalse(result["semantic_boundary"]["automatic_semantic_matching"])
        self.assertEqual(result["formal_gold"]["formal_denominator"], 23)
        self.assertEqual(result["aggregate"]["direction_count"], 4)
        self.assertEqual(result["aggregate"]["logical_samples_from_usage"], 20)
        self.assertEqual(result["aggregate"]["hard_stop_directions"], ["TRIAD16"])

        by_id = {row["direction_id"]: row for row in result["directions"]}
        jr08 = by_id["JR08"]
        self.assertEqual(jr08["gold_v1_2"]["summary"]["strict_hit"], 1)
        self.assertEqual(jr08["gold_v1_2"]["summary"]["effective_recall"], 2)
        self.assertEqual(jr08["gold_v1_2"]["summary"]["surface_coverage"], 3)
        self.assertEqual(jr08["gold_v1_2"]["summary"]["invalid_anchor_observation"], 1)
        self.assertEqual(jr08["gold_v1_2"]["summary"]["miss"], 20)
        self.assertEqual(jr08["overflow"]["count"], 1)
        self.assertTrue(jr08["old_34_gate"]["quality_gate"]["passed"])

        jr28 = by_id["JR28"]
        self.assertEqual(
            jr28["old_34_gate"]["comparison_to_z68c"]["old_partial_rescued_count"],
            1,
        )
        triad16 = by_id["TRIAD16"]
        self.assertEqual(
            triad16["old_34_gate"]["comparison_to_z68c"]["degradation_count"],
            1,
        )
        self.assertEqual(jr08["usage"]["logical_samples"], 5)
        self.assertEqual(jr08["usage"]["totals"]["prompt_tokens"], 5044)

    def test_rejects_missing_formal_gold_part(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            path = specs["JR08"][0]
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["gold_rows"].pop()
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(score.ScoreError, "金标 23 条 ID 不齐"):
                score.build_scorecard(specs)

    def test_rejects_unapproved_gold_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            path = specs["JR08"][0]
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["gold_rows"][0]["verdict"] = "looks_similar"
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(score.ScoreError, "判词无效"):
                score.build_scorecard(specs)

    def test_rejects_usage_missing_one_target_chapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            self.make_usage(specs["JR08"][1], omit_chapter=19)
            with self.assertRaisesRegex(score.ScoreError, "每个靶章恰好一条"):
                score.build_scorecard(specs)

    def test_cli_requires_same_direction_ids_for_adjudication_and_usage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            direction_args = [
                f"{direction_id}={paths[0]}" for direction_id, paths in specs.items()
            ]
            usage_args = [
                f"{direction_id}={paths[1]}" for direction_id, paths in specs.items()
            ]
            usage_args[-1] = f"OTHER={specs['TRIAD16'][1]}"
            argv: list[str] = []
            for value in direction_args:
                argv.extend(["--direction", value])
            for value in usage_args:
                argv.extend(["--usage", value])
            argv.extend(["--output", str(root / "score.json")])
            with self.assertRaisesRegex(score.ScoreError, "方向 ID 不一致"):
                score.main(argv)

    def test_manual_note_change_does_not_change_mechanical_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            before = score.build_scorecard(specs)
            path = specs["JR08"][0]
            doc = json.loads(path.read_text(encoding="utf-8"))
            changed = copy.deepcopy(doc)
            changed["gold_rows"][0]["semantic_review_note"] = "另一份人工说明"
            path.write_text(json.dumps(changed, ensure_ascii=False), encoding="utf-8")
            after = score.build_scorecard(specs)
        before_summary = before["directions"][0]["gold_v1_2"]["summary"]
        after_summary = after["directions"][0]["gold_v1_2"]["summary"]
        self.assertEqual(before_summary, after_summary)

    def test_accepts_landed_manual_aliases_and_normalizes_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            specs = self.make_four_specs(root)
            path = specs["JR28"][0]
            doc = json.loads(path.read_text(encoding="utf-8"))
            for row in doc["gold_rows"]:
                row["gold_part_id"] = row.pop("part_id")
                row["reason"] = row.pop("semantic_review_note")
            for row in doc["current_rows"]:
                row["reason"] = row.pop("semantic_review_note")
            path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            result = score.build_scorecard(specs)

        by_id = {row["direction_id"]: row for row in result["directions"]}
        normalized = by_id["JR28"]
        self.assertEqual(
            "GOLD-C0003-01-N01",
            normalized["gold_v1_2"]["rows"][0]["part_id"],
        )
        self.assertIn(
            "人工判词",
            normalized["gold_v1_2"]["rows"][0]["semantic_review_note"],
        )

    def test_allows_three_complete_directions_when_fourth_transport_hard_stops(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            specs = self.make_four_specs(Path(temp))
            specs.pop("TRIAD16")
            result = score.build_scorecard(specs, expected_direction_count=3)
        self.assertEqual(3, result["aggregate"]["direction_count"])
        self.assertEqual(15, result["aggregate"]["logical_samples_from_usage"])


if __name__ == "__main__":
    unittest.main()
