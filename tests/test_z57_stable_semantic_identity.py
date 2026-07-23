from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from zbatch_modules import classify_rules  # noqa: E402


OLD_CONTRACT = ROOT / "config/contracts/classify_rules_v1.2.json"
NEW_CONTRACT = ROOT / "config/contracts/classify_rules_v1.2_semantic_identity_v1.json"
EVENT_DIR = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719/01_extract/events"
CATALOG_DIR = ROOT / "runs/Z56b_X01_端到端全链体检_提取20章_v1.0_20260719/01_extract/evidence_catalogs"
DRAFT_DECISIONS = ROOT / "work/zbatch_decisions/Z56c_X01_ch1_20_main_control_decisions_v1.2.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Z57StableSemanticIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = classify_rules.load_contract(NEW_CONTRACT, project_root=ROOT)
        cls.documents = [
            json.loads((EVENT_DIR / f"ch{chapter:04d}.json").read_text(encoding="utf-8"))
            for chapter in range(1, 21)
        ]
        cls.catalogs = {}
        for chapter in range(1, 21):
            document = json.loads(
                (CATALOG_DIR / f"ch{chapter:04d}.json").read_text(encoding="utf-8")
            )
            cls.catalogs[chapter] = {
                row["anchor_id"]: row["quote"] for row in document["entries"]
            }
        cls.decisions = json.loads(DRAFT_DECISIONS.read_text(encoding="utf-8"))

    def test_old_contract_is_byte_frozen_and_semantic_rules_are_unchanged(self) -> None:
        self.assertEqual(
            sha256(OLD_CONTRACT),
            "ad2ccc3b13e8b138a32a46b8566e928a3c4e35a60cf31c5494c7b9ba3dd021de",
        )
        self.assertEqual(
            self.contract.rules_sha256,
            "514eb54735b2fe6de83824c10e63ec1134fcdbbe5b92fd6cd8c496ee9e78e433",
        )

    def test_z56_pool_resolves_by_source_semantics_not_same_sequential_id(self) -> None:
        audit = classify_rules.resolve_current_regression_cases(
            self.documents,
            contract=self.contract,
            evidence_catalogs=self.catalogs,
        )
        rows = {
            row["semantic_id"]: row
            for case in audit["cases"]
            for row in case["identities"]
        }
        self.assertEqual(rows["chapter6.return_offer.on_formal_request"]["resolved_event_id"], "EV-C0006-05")
        self.assertEqual(rows["chapter7.regular_meeting.proposal"]["resolved_event_id"], "EV-C0007-06")
        self.assertEqual(rows["chapter7.regular_meeting.specific_schedule"]["resolved_event_id"], "EV-C0007-09")
        self.assertEqual(rows["chapter7.grey_fog.time_flow_one_to_one"]["resolved_event_id"], "EV-C0007-23")
        self.assertEqual(rows["chapter6.return_mechanism.cut_connection"]["status"], "not_observed")
        self.assertEqual(rows["chapter19.chanis_gate.local_taboo"]["status"], "not_observed")
        self.assertNotEqual(rows["chapter19.chanis_gate.local_taboo"]["resolved_event_id"], "EV-C0019-05")
        self.assertEqual(audit["resolution_reasons"], [])

    def test_four_old_semantics_are_explicitly_not_observed(self) -> None:
        audit = classify_rules.resolve_current_regression_cases(
            self.documents, contract=self.contract, evidence_catalogs=self.catalogs
        )
        missing = [
            row["semantic_id"]
            for case in audit["cases"]
            for row in case["identities"]
            if row["status"] == "not_observed"
        ]
        self.assertEqual(
            missing,
            [
                "chapter6.return_mechanism.cut_connection",
                "chapter13.personal_risk.theoretical_only",
                "chapter13.world_rule.probabilistic_recurrence",
                "chapter19.chanis_gate.local_taboo",
            ],
        )

    def test_renumbering_does_not_change_semantic_resolution(self) -> None:
        documents = copy.deepcopy(self.documents)
        for document in documents:
            for index, event in enumerate(reversed(document["events"]), 1):
                event["event_id"] = f"EV-C{document['chapter']:04d}-{index:02d}"
        audit = classify_rules.resolve_current_regression_cases(
            documents, contract=self.contract, evidence_catalogs=self.catalogs
        )
        rows = {
            row["semantic_id"]: row
            for case in audit["cases"]
            for row in case["identities"]
        }
        self.assertEqual(rows["chapter7.regular_meeting.specific_schedule"]["status"], "resolved")
        self.assertNotEqual(rows["chapter7.regular_meeting.specific_schedule"]["resolved_event_id"], "EV-C0007-09")
        self.assertEqual(rows["chapter19.chanis_gate.local_taboo"]["status"], "not_observed")

    def test_ambiguous_semantic_match_hard_fails(self) -> None:
        documents = copy.deepcopy(self.documents)
        source = next(row for row in documents[6]["events"] if row["event_id"] == "EV-C0007-09")
        duplicate = copy.deepcopy(source)
        duplicate["event_id"] = "EV-C0007-99"
        documents[6]["events"].append(duplicate)
        audit = classify_rules.resolve_current_regression_cases(
            documents, contract=self.contract, evidence_catalogs=self.catalogs
        )
        self.assertTrue(any("命中多事件" in reason for reason in audit["resolution_reasons"]))

    def test_frozen_quote_drift_hard_fails(self) -> None:
        documents = copy.deepcopy(self.documents)
        event = next(row for row in documents[3]["events"] if row["event_id"] == "EV-C0004-05")
        anchor = next(row for row in event["anchors"] if row["anchor_id"] == "E0212")
        anchor["quote"] += "漂移"
        audit = classify_rules.resolve_current_regression_cases(
            documents, contract=self.contract, evidence_catalogs=self.catalogs
        )
        self.assertTrue(any("冻结原句锚指纹漂移" in reason for reason in audit["resolution_reasons"]))

    def test_missing_or_changed_frozen_catalog_anchor_hard_fails(self) -> None:
        catalogs = copy.deepcopy(self.catalogs)
        del catalogs[4]["E0212"]
        audit = classify_rules.resolve_current_regression_cases(
            self.documents, contract=self.contract, evidence_catalogs=catalogs
        )
        self.assertTrue(any("冻结证据目录缺锚" in reason for reason in audit["resolution_reasons"]))

        catalogs = copy.deepcopy(self.catalogs)
        catalogs[4]["E0212"] += "漂移"
        audit = classify_rules.resolve_current_regression_cases(
            self.documents, contract=self.contract, evidence_catalogs=catalogs
        )
        self.assertTrue(any("冻结证据目录原句指纹漂移" in reason for reason in audit["resolution_reasons"]))

    def test_current_gate_skips_missing_semantics_but_checks_resolved_cases(self) -> None:
        data = copy.deepcopy(self.decisions)
        rows = {row["event_id"]: row for row in data["decisions"]}
        for event_id in ("EV-C0007-06", "EV-C0007-09", "EV-C0009-06"):
            rows[event_id]["duplicate_group"] = "DUP-C0007-REGULAR-MEETING"
        rows["EV-C0007-06"]["disposition"] = "discarded"
        rows["EV-C0007-09"]["disposition"] = "classified"
        rows["EV-C0007-09"]["primary_type"] = "B"
        rows["EV-C0009-06"]["disposition"] = "discarded"
        rows["EV-C0009-06"]["primary_type"] = None
        self.assertEqual(
            classify_rules.current_regression_reasons(
                data,
                contract=self.contract,
                event_documents=self.documents,
                evidence_catalogs=self.catalogs,
            ),
            [],
        )
        rows["EV-C0007-09"]["disposition"] = "discarded"
        self.assertTrue(
            any(
                "current_regular_meeting_vs_specific_schedule" in reason
                for reason in classify_rules.current_regression_reasons(
                    data,
                    contract=self.contract,
                    event_documents=self.documents,
                    evidence_catalogs=self.catalogs,
                )
            )
        )

    def test_stable_gate_refuses_to_run_without_event_documents(self) -> None:
        self.assertEqual(
            classify_rules.current_regression_reasons(self.decisions, contract=self.contract),
            ["当前决定回归缺稳定语义身份所需的中性事件文档"],
        )

    def test_duplicate_semantic_id_is_rejected_at_contract_load(self) -> None:
        raw = json.loads(NEW_CONTRACT.read_text(encoding="utf-8"))
        raw["current_regression_cases"][1]["identities"][0]["semantic_id"] = (
            raw["current_regression_cases"][0]["identities"][0]["semantic_id"]
        )
        temporary = NEW_CONTRACT.with_name(".test_duplicate_semantic_id.json")
        try:
            temporary.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "semantic_id为空或重复"):
                classify_rules.load_contract(temporary, project_root=ROOT)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
