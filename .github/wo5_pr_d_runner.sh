#!/usr/bin/env bash
set -euo pipefail

# Build on the validated PR-D compatibility runner and partition the remaining
# concurrency-sensitive tests into clean pytest processes. Every novel-mvp test
# still runs; only the explicitly authorized m3_admission debt is ignored.
cd "$(dirname "$0")/.."
STAGE2_RUNNER=".github/wo5_pr_d_runner_partitioned.sh"
python - "$STAGE2_RUNNER" <<'PY'
from __future__ import annotations

import subprocess
import sys

prior_commit = "245a9308a259cded776edbf799cff170d7c717f2"
wrapper = subprocess.check_output(
    ["git", "show", f"{prior_commit}:.github/wo5_pr_d_runner.sh"],
    text=True,
)
anchor = "source = source.replace(cleanup_marker, cleanup_replacement, 1)\n"
if wrapper.count(anchor) != 1:
    raise SystemExit("PR_D_PARTITION_INSERTION_ANCHOR_NOT_FOUND_EXACTLY_ONCE")

insertion = r'''

bulk_marker = r"""mapfile -t existing_novel_tests < <(
  find tests -maxdepth 1 -type f -name 'test_novel_mvp*.py' -print | sort
)
filtered_tests=()
for test_path in "${existing_novel_tests[@]}"; do
  if [[ "$test_path" == "tests/test_novel_mvp_m3_admission.py" ]]; then
    continue
  fi
  filtered_tests+=("$test_path")
done
printf 'PR_D_MAIN_NOVEL_TEST_FILES=%s\n' "${#filtered_tests[@]}"
printf 'PR_D_KNOWN_DEBT_IGNORED=tests/test_novel_mvp_m3_admission.py\n'
uv run --locked pytest -q -p no:cacheprovider \
  --ignore=tests/test_novel_mvp_m3_admission.py \
  "${filtered_tests[@]}"
"""
bulk_replacement = r"""mapfile -t existing_novel_tests < <(
  find tests -maxdepth 1 -type f -name 'test_novel_mvp*.py' -print | sort
)
# These files are not skipped: the shared-runtime/direct files and
# chapterization were already run above in fresh pytest processes. The M4 queue
# concurrency file is run below in its own fresh process so unrelated test
# globals cannot contaminate its thread races.
already_run_tests=(
  tests/test_novel_mvp_workspace.py
  tests/test_novel_mvp_upload_source.py
  tests/test_novel_mvp_recall_handle_workspace.py
  tests/test_novel_mvp_ledger_directory_tool.py
  tests/test_novel_mvp_ledger_directory_workspace.py
  tests/test_novel_mvp_chapterization.py
)
isolated_concurrency_tests=(
  tests/test_novel_mvp_m4_review_queue_runtime.py
)
bulk_tests=()
for test_path in "${existing_novel_tests[@]}"; do
  case "$test_path" in
    tests/test_novel_mvp_m3_admission.py|\
    tests/test_novel_mvp_workspace.py|\
    tests/test_novel_mvp_upload_source.py|\
    tests/test_novel_mvp_recall_handle_workspace.py|\
    tests/test_novel_mvp_ledger_directory_tool.py|\
    tests/test_novel_mvp_ledger_directory_workspace.py|\
    tests/test_novel_mvp_chapterization.py|\
    tests/test_novel_mvp_m4_review_queue_runtime.py)
      continue
      ;;
  esac
  bulk_tests+=("$test_path")
done
printf 'PR_D_ALREADY_RUN_TEST_FILES=%s\n' "${#already_run_tests[@]}"
printf '%s\n' "${already_run_tests[@]}"
printf 'PR_D_ISOLATED_CONCURRENCY_TEST_FILES=%s\n' \
  "${#isolated_concurrency_tests[@]}"
printf '%s\n' "${isolated_concurrency_tests[@]}"
printf 'PR_D_BULK_NOVEL_TEST_FILES=%s\n' "${#bulk_tests[@]}"
printf 'PR_D_KNOWN_DEBT_IGNORED=tests/test_novel_mvp_m3_admission.py\n'
uv run --locked pytest -q -p no:cacheprovider \
  "${isolated_concurrency_tests[@]}"
uv run --locked pytest -q -p no:cacheprovider \
  --ignore=tests/test_novel_mvp_m3_admission.py \
  "${bulk_tests[@]}"
"""
if source.count(bulk_marker) != 1:
    raise SystemExit("PR_D_BULK_TEST_BLOCK_NOT_FOUND_EXACTLY_ONCE")
source = source.replace(bulk_marker, bulk_replacement, 1)
'''
wrapper = wrapper.replace(anchor, anchor + insertion, 1)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(wrapper)
PY
chmod +x "$STAGE2_RUNNER"
exec bash "$STAGE2_RUNNER"
