import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "verify_p4_two_runs", ROOT / "tools" / "verify_p4_two_runs.py"
)
verify = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verify)


def test_expected_member_contract_is_narrow():
    assert verify.EXPECTED_MEMBERS == ["TOY_SPLITTER_BUILD.json"]


def test_sha256_is_raw_byte_based(tmp_path):
    path = tmp_path / "x"
    path.write_bytes(b"a\r\n")
    assert verify.sha256(path) != verify.sha256(_write(tmp_path / "y", b"a\n"))


def _write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path
