from __future__ import annotations

import hashlib
import re
from pathlib import Path

from isolation import run_git


ROOT = Path(__file__).resolve().parents[1]
NAVIGATION_DOCS = (
    "README.md",
    "governance/README.md",
    "governance/INDEX.md",
    "tools/README.md",
    "tests/README.md",
    "experiments/README.md",
    "references/README.md",
    "intake/README.md",
    "work/README.md",
    "side-tracks/README.md",
    "side-tracks/BOARD.md",
    "side-tracks/INGEST.md",
)
LOCAL_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_root_readme_is_a_durable_one_hop_map() -> None:
    text = _read("README.md")
    assert "[治理索引](governance/INDEX.md)" in text
    assert "[技术兼容快照](governance/CURRENT_STATE.json)" in text
    assert "https://linear.app/ccz/document/4ddff334d4f0" in text
    for path in (
        "governance/",
        "foundation/",
        "intake/",
        "config/",
        "experiments/",
        "tools/",
        "tests/",
        "references/",
        "work/",
        "side-tracks/",
        "runs/",
        "reports/",
        "TEMP/",
        "corpus-downloads",
    ):
        assert f"`{path}`" in text
    assert "Z00u" not in text
    assert "固定运输路径只接受" not in text


def test_test_readme_uses_the_fixed_full_chain_command() -> None:
    expected = (
        'cd "$(git rev-parse --show-toplevel)" && '
        "uv run --locked pytest -q"
    )
    text = _read("tests/README.md")
    assert expected in text
    assert "/Users/" not in text
    assert ".venv/bin/python -m pytest -q" not in text
    assert "uv run pytest" not in text


def test_active_navigation_docs_do_not_route_back_to_retired_current_page() -> None:
    for relative in (
        "references/README.md",
        "side-tracks/README.md",
        "side-tracks/BOARD.md",
        "side-tracks/INGEST.md",
    ):
        assert "](../current.md)" not in _read(relative), relative


def test_experiment_readme_does_not_treat_unregistered_as_garbage() -> None:
    text = _read("experiments/README.md")
    assert "未登记" in text
    assert "不代表垃圾" in text
    assert "experiment.json" in text
    assert "[治理索引](../governance/INDEX.md)" in text


def test_archived_stub_rules_are_visible_before_side_track_instructions() -> None:
    readme = _read("side-tracks/README.md")
    ingest = _read("side-tracks/INGEST.md")
    assert "ARCHIVED.md" in readme
    assert "不能直接接收新文件" in readme
    assert "不能把新回包直接丢进旧 `returns/`" in ingest
    assert "禁止往 stub 里续写" in ingest
    assert "`TEMP/dr_*/returns/`" not in readme
    assert "进 ST-002 returns" not in ingest


def test_tool_readme_routes_to_unified_top_level_and_catalog_help() -> None:
    text = _read("tools/README.md")
    assert "python3 tools/novel_pipeline.py --help" in text
    assert "python3 tools/novel_pipeline.py catalog --help" in text
    assert "不要假设每个命名空间的顶层 `--help` 都可用" not in text


def test_navigation_markdown_local_links_resolve() -> None:
    broken: list[str] = []
    for relative in NAVIGATION_DOCS:
        source = ROOT / relative
        for raw_target in LOCAL_LINK.findall(source.read_text(encoding="utf-8")):
            target = raw_target.strip().split("#", 1)[0]
            if (
                not target
                or "://" in target
                or target.startswith(("mailto:", "file-upload://"))
            ):
                continue
            resolved = (source.parent / target).resolve()
            if not resolved.exists():
                try:
                    repository_relative = resolved.relative_to(ROOT.resolve())
                except ValueError:
                    repository_relative = None
                if (
                    repository_relative is not None
                    and repository_relative.parts
                    and repository_relative.parts[0]
                    in {"TEMP", "runs", "reports", "outbox"}
                ):
                    continue
                broken.append(f"{relative} -> {target}")
    assert broken == []


def test_corpus_pointer_is_machine_local_and_documented() -> None:
    pointer = ROOT / "corpus-downloads"
    assert pointer.is_symlink()
    assert pointer.readlink() == Path(".local/corpus-downloads")
    assert "/Users/" not in pointer.readlink().as_posix()
    ignored = run_git(
        "check-ignore",
        "-q",
        ".local/corpus-downloads",
        cwd=ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    documentation = _read("references/corpus-pointers.md")
    assert ".local/corpus-downloads" in documentation
    assert "干净克隆后正文仍不会自动出现" in documentation
    local_target = ROOT / ".local/corpus-downloads"
    if local_target.exists():
        assert local_target.is_dir()


def test_v02_transport_tool_does_not_pin_a_user_home_directory() -> None:
    source = _read("tools/v02_c4_transport_probe.py")
    assert 'Path("/Users/' not in source
    assert "CODEX_ATTACHMENTS_DIR" in source
    assert "Path.home()" in source


def test_z88_package_is_self_contained_and_current_sha_matches() -> None:
    package = (
        ROOT
        / "references/survey-inbox/packages/Z88_pro_returns_candidate_20260722"
    )
    assert package.is_dir()
    assert not package.is_symlink()
    sums = package / "SHA256SUMS.current.txt"
    checked: list[str] = []
    for line in sums.read_text(encoding="utf-8").splitlines():
        expected, separator, relative = line.partition("  ")
        assert separator
        path = package / relative
        assert path.is_file()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        checked.append(relative)
    assert checked == [
        "inventory.json",
        "returns/pack_A_short_quote_validation_return.md",
        "returns/pack_B_scoring_methods_return.md",
        "returns/pack_C_longform_extraction_arch_return.md",
        "returns/pack_D_reproducible_pipeline_return.md",
        "第88道回包收件汇报.md",
    ]
    alias = package / "Z88_return_receipt.md"
    assert alias.is_symlink()
    assert alias.readlink() == Path("第88道回包收件汇报.md")
