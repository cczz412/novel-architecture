import importlib.util
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "tools" / "render_from_explicit_positions.py"
spec = importlib.util.spec_from_file_location("position_renderer", MODULE)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def test_span_mapping_uses_coordinates():
    units = [
        {"char_start": 0, "char_end": 4, "local_id": "T01"},
        {"char_start": 4, "char_end": 8, "local_id": "T02"},
    ]
    assert renderer.map_span(units, 5, 7)["evidence_ids"] == ["T02"]


def test_cross_unit_span_is_preserved():
    units = [
        {"char_start": 0, "char_end": 4, "local_id": "T01"},
        {"char_start": 4, "char_end": 8, "local_id": "T02"},
    ]
    mapped = renderer.map_span(units, 3, 6)
    assert mapped["evidence_ids"] == ["T01", "T02"]
    assert mapped["cross_unit"] is True
