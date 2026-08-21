#!/usr/bin/env bash
set -euo pipefail

# Reuse the approved PR-D runner and add only a validation-time compatibility
# materialization for main's still-tracked chapterization test. Nothing under
# TEMP/ or tests/fixtures/ is staged or delivered; permanent fixture migration
# remains PR-F.
cd "$(dirname "$0")/.."
TMP_RUNNER=".github/wo5_pr_d_runner_impl.sh"
python - "$TMP_RUNNER" <<'PY'
from __future__ import annotations

import subprocess
import sys

commit = "128fa3950aea4a2f7dd513b2dd1fee6f67add2b1"
source = subprocess.check_output(
    ["git", "show", f"{commit}:.github/wo5_pr_d_runner.sh"],
    text=True,
)

setup_marker = r'''uv run --locked pytest -q -p no:cacheprovider "${test_files[@]}"

mapfile -t existing_novel_tests < <(
'''
setup_replacement = r'''uv run --locked pytest -q -p no:cacheprovider "${test_files[@]}"

# main still contains one chapterization test wired to historical, untracked TEMP
# paths. Materialize a validation-only compatibility tree from the frozen branch's
# safe synthetic fixtures, plus one deterministic synthetic R03 double-heading
# control required by the unchanged main assertions. Delete everything before
# Ruff/staging. This is not PR-F fixture migration.
PR_D_COMPAT_FIXTURE_ROOT="tests/fixtures/novel_mvp/intake_regressions"
PR_D_COMPAT_TEMP_ROOT="TEMP/t03_parallel_r13_m1_m2_20260815_r01"
rm -rf "$PR_D_COMPAT_FIXTURE_ROOT" "$PR_D_COMPAT_TEMP_ROOT"
git archive "$SOURCE" "$PR_D_COMPAT_FIXTURE_ROOT" | tar -x
python - <<'PY_COMPAT'
from __future__ import annotations

import json
import shutil
from pathlib import Path

fixture_root = Path("tests/fixtures/novel_mvp/intake_regressions")
texts = fixture_root / "texts"
temp_root = Path("TEMP/t03_parallel_r13_m1_m2_20260815_r01")
receipt_root = temp_root / "t03_prod_02_safe_chapterization_20260817_r01"
s1a_root = temp_root / "t03_s1a_fix_20260817_r01"
r03_root = temp_root / "t03_r03_double_heading_fix_20260817_r01"
for path in (receipt_root, s1a_root / "fixtures", r03_root / "fixtures"):
    path.mkdir(parents=True, exist_ok=True)

manifest_path = fixture_root / "chapterization_manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
case = next(item for item in manifest["cases"] if item["case_id"] == "P-CH-02")
if case["kind"] != "file_text":
    raise SystemExit(f"PR_D_COMPAT_P_CH_02_KIND_CHANGED:{case['kind']}")
case["kind"] = "ordered_concatenation_of_frozen_inputs"
case["directory"] = str(texts)
case["filenames"] = [Path(case["path"]).name]
case["source_file_sha256"] = [case["sha256"]]
case["combined_chars"] = case["chars"]
case["combined_sha256"] = case["sha256"]
(receipt_root / "CHAPTERIZATION_FIXTURE_LOCK.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

s1a = {
    "cases": [
        {
            "case_id": "S1A-R01",
            "inputs": [
                {"path": str(texts / "ten_chapter_section_control.txt")}
            ],
        }
    ]
}
(s1a_root / "S1A_BEFORE_LOCK.json").write_text(
    json.dumps(s1a, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

copy_map = {
    texts / "f03_valid_bare_section_title.txt":
        s1a_root / "fixtures/F03_valid_bare_section_title.txt",
    texts / "f04_valid_section_title_with_name.txt":
        s1a_root / "fixtures/F04_valid_section_title_with_name.txt",
    texts / "f09_ambiguous_compact_section_sentence.txt":
        s1a_root / "fixtures/F09_ambiguous_compact_section_sentence.txt",
    texts / "dht02_stable_double_heading.txt":
        r03_root / "fixtures/DHT-02_stable_double_heading.txt",
    texts / "dht05_body_between_candidates.txt":
        r03_root / "fixtures/DHT-05_body_between_candidates.txt",
    texts / "dht10_isolated_ambiguous_pair.txt":
        r03_root / "fixtures/DHT-10_isolated_ambiguous_pair.txt",
}
for source_path, target_path in copy_map.items():
    if not source_path.is_file():
        raise SystemExit(f"PR_D_COMPAT_SOURCE_FIXTURE_MISSING:{source_path}")
    shutil.copyfile(source_path, target_path)

# The unchanged main test requires a real double-heading source whose first
# chapter starts at character 80 and whose collapsed titles are exact. The
# synthetic preamble deliberately makes the whole input BLOCKED, while the
# explicit chapter declaration path admits the three chapter pairs.
preamble = "前" * 79 + "\n"
r03_text = preamble + (
    "第1章 第1章 绯红\n"
    "第1章绯红\n"
    "雨落。\n"
    "第2章 第2章 情况\n"
    "第2章情况\n"
    "门开。\n"
    "第3章 第3章 梅丽莎（第一更求推荐票）\n"
    "第3章梅丽莎（第一更求推荐票）\n"
    "天亮。\n"
)
if r03_text.find("第1章") != 80:
    raise SystemExit(f"PR_D_COMPAT_R03_BAD_CHAPTER_START:{r03_text.find('第1章')}")
r03_source = r03_root / "fixtures/R03_validation_only_double_heading.txt"
r03_source.write_text(r03_text, encoding="utf-8")
(r03_root / "R03_DOUBLE_HEADING_BASELINE.json").write_text(
    json.dumps(
        {"source": {"path": str(r03_source)}},
        ensure_ascii=False,
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)

print(
    "PASS_PR_D_VALIDATION_ONLY_FIXTURES "
    "source=cc793c4_safe_synthetic_fixtures "
    "compat_temp=historical_main_test_paths "
    "r03=deterministic_double_heading_control "
    "delivery=NOT_STAGED_PR_F_REMAINS_OWNER"
)
PY_COMPAT

uv run --locked pytest -q -p no:cacheprovider tests/test_novel_mvp_chapterization.py

mapfile -t existing_novel_tests < <(
'''
if source.count(setup_marker) != 1:
    raise SystemExit("PR_D_COMPAT_SETUP_MARKER_NOT_FOUND_EXACTLY_ONCE")
source = source.replace(setup_marker, setup_replacement, 1)

cleanup_marker = r'''uv run --locked pytest -q -p no:cacheprovider \
  --ignore=tests/test_novel_mvp_m3_admission.py \
  "${filtered_tests[@]}"

printf 'PR_D_ADAPTATION_TABLE_START\n'
'''
cleanup_replacement = r'''uv run --locked pytest -q -p no:cacheprovider \
  --ignore=tests/test_novel_mvp_m3_admission.py \
  "${filtered_tests[@]}"

rm -rf "$PR_D_COMPAT_TEMP_ROOT" "$PR_D_COMPAT_FIXTURE_ROOT"
rmdir tests/fixtures/novel_mvp tests/fixtures TEMP 2>/dev/null || true
test ! -e "$PR_D_COMPAT_TEMP_ROOT"
test ! -e "$PR_D_COMPAT_FIXTURE_ROOT"
if git status --porcelain --untracked-files=all | grep -E \
  '^(.. )?(TEMP/t03_parallel_r13_m1_m2_20260815_r01|tests/fixtures/novel_mvp/intake_regressions)' \
  >/dev/null; then
  git status --porcelain --untracked-files=all
  echo 'PR_D_VALIDATION_ONLY_FIXTURE_LEAK' >&2
  exit 1
fi
printf 'PASS_PR_D_VALIDATION_ONLY_FIXTURE_CLEANUP\n'

printf 'PR_D_ADAPTATION_TABLE_START\n'
'''
if source.count(cleanup_marker) != 1:
    raise SystemExit("PR_D_COMPAT_CLEANUP_MARKER_NOT_FOUND_EXACTLY_ONCE")
source = source.replace(cleanup_marker, cleanup_replacement, 1)

with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(source)
PY
chmod +x "$TMP_RUNNER"
exec bash "$TMP_RUNNER"
