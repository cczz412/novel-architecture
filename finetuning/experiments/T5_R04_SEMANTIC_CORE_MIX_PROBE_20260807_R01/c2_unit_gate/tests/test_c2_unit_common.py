import importlib.util
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
from c2_unit_common import atomize_question, parse_question, render_c2_user


SYSTEM = "system"
CARD = '{"sample_id":"S1","publication":{"book_title":"书","author":"作者"}}'


def test_positive_parse_and_reconstruct():
    raw = "左文。目标第一句。\n目标第二句很长，但是仍然应该可重建。"
    user = (
        "【小说背景卡｜只辅助理解，不代替证据】\n" + CARD
        + "\n\n【短段身份】\n- segment_id：S1:W1\n- sample_id：S1\n- split：train"
        + "\n\n【责任边界｜用于判断归属，不是额外证据】\n- 左侧重叠字符数：3"
        + "\n\n【连续短段原文｜evidence 只能从这里逐字复制】\n" + raw
    )
    question = parse_question(SYSTEM, user)
    assert question["bridge_text"] == "左文。"[:3]
    unit_map = atomize_question(question, max_chars=12)
    assert "".join(unit["text"] for unit in unit_map["all_units"]) == raw
    assert all(unit["local_id"].startswith("T") for unit in unit_map["all_units"] if unit["region"] == "target")


def test_special_parse_render_readonly_unnumbered():
    left = "更早上文。\n紧邻上文。"
    target = "负责区第一句。\n负责区第二句。"
    user = (
        "【小说背景卡｜只辅助理解，不代替证据】\n" + CARD
        + "\n\n【短段身份】\n- segment_id：S1:W2\n- sample_id：S1\n- split：train_candidate"
        + "\n\n【只读左重叠区｜只帮助理解，不重复抽取】\n" + left
        + "\n\n【本段负责区｜只抽证据结束位置落在这里的事实】\n" + target
    )
    question = parse_question(SYSTEM, user)
    assert question["source_text"] == left + target
    unit_map = atomize_question(question, max_chars=8, visible_bridge_units=1)
    rendered = render_c2_user(question, unit_map)
    assert "【只读上文｜仅辅助理解，不可作为证据编号】" in rendered
    assert "[T01]" in rendered
    assert "".join(unit["text"] for unit in unit_map["all_units"]) == left + target


def test_deterministic_atomization():
    raw = "咚！\n咚！\n咚！\n随后人物离开了房间。"
    user = (
        "【小说背景卡｜只辅助理解，不代替证据】\n" + CARD
        + "\n\n【短段身份】\n- segment_id：S1:W3\n- sample_id：S1\n- split：train"
        + "\n\n【责任边界｜用于判断归属，不是额外证据】\n- 左侧重叠字符数：0"
        + "\n\n【连续短段原文｜evidence 只能从这里逐字复制】\n" + raw
    )
    question = parse_question(SYSTEM, user)
    assert atomize_question(question) == atomize_question(question)
    unit_map = atomize_question(question)
    assert "".join(unit["text"] for unit in unit_map["all_units"]) == raw
