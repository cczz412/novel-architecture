import importlib.util
from pathlib import Path
import pytest


MODULE_PATH = Path(__file__).parents[1] / "tools/evaluator_r02.py"
SPEC = importlib.util.spec_from_file_location("evaluator_r02", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def fact(text: str, status: str = "已发生", speaker=None):
    return {"fact": text, "status": status, "evidence": "证据", "speaker": speaker}


def test_case_local_matching_does_not_cross_cases():
    first = MODULE.count_match([fact("甲")], [], MODULE.fact_key)
    second = MODULE.count_match([], [fact("甲")], MODULE.fact_key)
    bucket = {"tp": 0, "fp": 0, "fn": 0}
    MODULE.add_bucket(bucket, first)
    MODULE.add_bucket(bucket, second)
    assert bucket == {"tp": 0, "fp": 1, "fn": 1}


def test_container_abnormal_is_reachable_and_separate():
    invalid = MODULE.validate_output('{"facts":[', "a")
    abnormal = MODULE.validate_output('{"wrong":[]}', "a")
    assert invalid["json_valid"] is False
    assert abnormal["json_valid"] is True
    assert abnormal["top_schema_valid"] is False


def test_fact_match_and_triple_match_are_separate():
    gold = [fact("陈川出发。", speaker="陈川")]
    pred = [fact("陈川出发。", speaker="来源不明")]
    assert MODULE.count_match(gold, pred, MODULE.fact_key)["tp"] == 1
    assert MODULE.count_match(gold, pred, MODULE.triple_key)["tp"] == 0
    conditional = MODULE.conditional_field_accuracy(gold, pred)
    assert conditional["paired_exact_fact"] == 1
    assert conditional["status_correct"] == 1
    assert conditional["speaker_correct"] == 0


def test_recover_complete_objects_from_truncated_json():
    text = '{"facts":[{"fact":"甲","status":"已发生","evidence":"证据"},{"fact":"甲","status":"已发生","evidence":"证据"},{"fact":"甲","status":"已发生","evidence":"证据"},{"fact":"未完'
    recovered = MODULE.extract_complete_objects(text)
    assert len(recovered) == 3
    assert MODULE.repeated(recovered, MODULE.fact_key)
    assert MODULE.duplicate_count(recovered, MODULE.fact_key) == 2
    fragments = MODULE.repeated_fragments(recovered)
    assert any(row["kind"] == "fact" and row["count"] == 3 for row in fragments)


def test_recovered_correct_fact_does_not_promote_invalid_json():
    gold = [fact("陈川出发。")]
    checked = MODULE.validate_output('{"facts":[{"fact":"陈川出发。","status":"已发生","evidence":"证据"}', "a")
    assert checked["json_valid"] is False
    assert checked["schema_valid"] is False
    assert checked["facts"] == []
    assert MODULE.count_match(gold, checked["recovered_facts"], MODULE.fact_key)["tp"] == 1


def test_duplicate_case_id_is_hard_failure():
    raw = [{"case_id": "C1"}, {"case_id": "C1"}]
    gold = [{"case_id": "C1"}, {"case_id": "C1"}]
    with pytest.raises(ValueError, match="case_id 重复"):
        MODULE.ensure_case_alignment(raw, gold, "G")
