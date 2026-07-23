from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from zbatch_modules import classify_rules  # noqa: E402


V1_CONTRACT = ROOT / "config/contracts/classify_rules_v1.json"
V1_2_CONTRACT = ROOT / "config/contracts/classify_rules_v1.2.json"
V1_DECISIONS = ROOT / "work/zbatch_decisions/Z00s_X01_ch1_20_main_control_decisions_v1.json"
V1_2_DECISIONS = ROOT / "work/zbatch_decisions/Z00w2_X01_ch1_20_main_control_decisions_v1.2.json"
EVENT_DIR = ROOT / "runs/Z00r_X01_第14章单次重采样续跑_20章_v1.0_20260718/01_extract/events"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ClassifyRulesV12Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.v1_contract = classify_rules.load_contract(V1_CONTRACT, project_root=ROOT)
        cls.contract = classify_rules.load_contract(V1_2_CONTRACT, project_root=ROOT)
        cls.v1 = json.loads(V1_DECISIONS.read_text(encoding="utf-8"))
        cls.data = json.loads(V1_2_DECISIONS.read_text(encoding="utf-8"))
        cls.documents = [
            json.loads((EVENT_DIR / f"ch{chapter:04d}.json").read_text(encoding="utf-8"))
            for chapter in range(1, 21)
        ]
        cls.event_ids = set(classify_rules.index_events(cls.documents)[0])

    def reasons(self, data: dict) -> list[str]:
        return classify_rules.decision_reasons(
            data,
            run_id=data["run_id"],
            event_ids=self.event_ids,
            contract=self.contract,
        )

    def test_v1_history_stays_byte_frozen_and_valid_under_v1_contract(self):
        self.assertEqual(sha(V1_DECISIONS), "f35ef1ac4d3ba6d546e95ff96a15ea39eb71dce25dd89e5433ea30106d2cf565")
        self.assertEqual(
            classify_rules.decision_reasons(
                self.v1,
                run_id=self.v1["run_id"],
                event_ids=self.event_ids,
                contract=self.v1_contract,
            ),
            [],
        )

    def test_v1_2_full_decision_set_covers_all_263_events(self):
        self.assertEqual(len(self.event_ids), 263)
        self.assertEqual(len(self.data["decisions"]), 263)
        self.assertEqual(self.reasons(self.data), [])

    def test_fallback_audit_requires_all_four_types_and_mc08(self):
        data = copy.deepcopy(self.data)
        row = next(item for item in data["decisions"] if item["disposition"] == "discarded")
        del row["type_audit"]["C"]
        self.assertIn(f"{row['event_id']}四类兜底审计不完整", self.reasons(data))

        data = copy.deepcopy(self.data)
        row = next(item for item in data["decisions"] if item["disposition"] == "discarded")
        row["rule_ids"].remove("MC-08")
        self.assertIn(f"{row['event_id']}缺四类兜底审计规则MC-08", self.reasons(data))

    def test_d02_only_excludes_d_and_needs_final_disposition_rule(self):
        data = copy.deepcopy(self.data)
        row = next(
            item
            for item in data["decisions"]
            if item["disposition"] == "unclassified" and "D-02" in item["rule_ids"]
        )
        row["rule_ids"].remove("EVIDENCE-BOUNDARY")
        self.assertTrue(any("D-02只准排除D" in reason for reason in self.reasons(data)))

    def test_classified_d_with_d02_must_name_the_excluded_fragment(self):
        data = copy.deepcopy(self.data)
        row = next(
            item
            for item in data["decisions"]
            if item["disposition"] == "classified"
            and item["primary_type"] == "D"
            and "D-02" in item["rule_ids"]
        )
        row["conflict_reason"] = ""
        self.assertTrue(any("D类同时带D-02" in reason for reason in self.reasons(data)))

    def test_source_and_probability_are_separate_from_assertion(self):
        rows = {row["event_id"]: row for row in self.data["decisions"]}
        delayed = rows["EV-C0013-15"]
        self.assertEqual(delayed["assertion"], "明")
        self.assertEqual(delayed["source_level"], "述")
        self.assertEqual(delayed["scope_mode"], "probabilistic")
        chanis = rows["EV-C0019-05"]
        self.assertEqual(chanis["primary_type"], "A")
        self.assertEqual(chanis["source_level"], "述")
        self.assertIn("D-02", chanis["rule_ids"])

    def test_target_extensions_keep_one_primary_type_per_event(self):
        rows = {row["event_id"]: row for row in self.data["decisions"]}
        self.assertEqual(rows["EV-C0004-05"]["primary_type"], "B")
        self.assertEqual(rows["EV-C0013-14"]["primary_type"], "C")
        self.assertEqual(rows["EV-C0013-15"]["primary_type"], "D")
        self.assertEqual(rows["EV-C0019-05"]["primary_type"], "A")

    def test_current_event_mapping_regressions_are_not_only_historical_reference_checks(self):
        self.assertEqual(
            classify_rules.current_regression_reasons(self.data, contract=self.contract),
            [],
        )
        data = copy.deepcopy(self.data)
        row = next(item for item in data["decisions"] if item["event_id"] == "EV-C0006-03")
        row["disposition"] = "discarded"
        reasons = classify_rules.current_regression_reasons(data, contract=self.contract)
        self.assertTrue(any("current_return_mechanism_vs_offer" in reason for reason in reasons))

    def test_compiler_emits_source_and_scope_metadata(self):
        compilation = classify_rules.compile_records(
            self.documents,
            self.data,
            contract=self.contract,
        )
        records = {row["_source_event_id"]: row for row in compilation["records"]}
        delayed = records["EV-C0013-15"]
        self.assertEqual(delayed["source_level"], "述")
        self.assertEqual(delayed["scope_mode"], "probabilistic")
        self.assertEqual(records["EV-C0019-05"]["source_level"], "述")


if __name__ == "__main__":
    unittest.main()
