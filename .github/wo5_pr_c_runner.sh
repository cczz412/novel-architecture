#!/usr/bin/env bash
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN is required}"
: "${BRANCH_NAME:?BRANCH_NAME is required}"

cd repo

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git fetch origin main:refs/remotes/origin/main
git fetch origin \
  codex/module-runtime-foundation-20260819-r01:refs/remotes/origin/wo5-source

test "$(git rev-parse origin/main)" = \
  "7eca07a64b31078d51eb7dd6f7b509ede967a704"
test "$(git rev-parse refs/remotes/origin/wo5-source)" = \
  "cc793c4719fb6470946c70e744f463147989547b"

python -m py_compile .github/wo5_pr_c_apply.py
python .github/wo5_pr_c_apply.py
python -m json.tool novel-mvp/design/design_registry.json >/dev/null
test -f novel-mvp/CURRENT_VS_TARGET_R01.md
grep -Fq '页面身份：产品目标图，不是完成图' novel-mvp/ARCHITECTURE.md

SOURCE=cc793c4719fb6470946c70e744f463147989547b
for path in \
  novel-mvp/ARCHITECTURE.md \
  novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md \
  novel-mvp/design/STOP_POINT_REGISTRY_R03.md \
  novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md \
  novel-mvp/contracts/C1_CHAPTER_DOC.md \
  novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md \
  novel-mvp/contracts/validate_c11_chapter_revision_ledger.py
do
  test "$(git hash-object "$path")" = "$(git rev-parse "$SOURCE:$path")"
  echo "BYTE_IDENTICAL $path"
done

test "$(git hash-object novel-mvp/design/INDEX.md)" != \
  "$(git rev-parse "$SOURCE:novel-mvp/design/INDEX.md")"
grep -Fq 'R14 currentness 登记 R02' novel-mvp/design/INDEX.md
grep -Fq 'SYNTHESIZED_POST_WO4' novel-mvp/design/INDEX.md
echo 'INDEX_SYNTHESIS_BOUNDARY=PASS'

python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path('.')
registry = json.loads(
    (root / 'novel-mvp/design/design_registry.json').read_text(encoding='utf-8')
)
by_path = {row['path']: row for row in registry['documents']}
assert registry['inventory'] == {
    'document_count': 58,
    'status_counts': {
        'CURRENT': 20,
        'HISTORICAL': 5,
        'SUPERSEDED': 26,
        'WAITING_REWRITE': 7,
    },
    'default_route_count': 20,
}
assert by_path['novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md']['status'] == 'CURRENT'
assert by_path['novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md']['default_route'] is True
assert by_path['novel-mvp/design/STOP_POINT_REGISTRY_R03.md']['status'] == 'CURRENT'
assert by_path['novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md']['status'] == 'SUPERSEDED'
assert by_path['novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md']['default_route'] is False
for path in (
    'novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md',
    'novel-mvp/design/STOP_POINT_REGISTRY_R03.md',
    'novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md',
):
    assert by_path[path]['body_sha256'] == hashlib.sha256((root / path).read_bytes()).hexdigest()
changes = registry['expected_work_order_5_pr_c_changes']['changes']
assert len(changes) == 4
assert all(item['status'] == 'APPLIED_IN_CANDIDATE_PR' for item in changes)
print('PASS_PR_C_REGISTRY total=58 current=20 historical=5 superseded=26 waiting=7 defaults=20')
PY

python - <<'PY'
import subprocess
from pathlib import Path

path = Path('tests/test_design_currentness.py')
current = path.read_text(encoding='utf-8')
base = subprocess.check_output(
    ['git', 'show', 'origin/main:tests/test_design_currentness.py'],
    text=True,
)
old = '''    assert report["summary"]["document_count"] == 57
    assert report["summary"]["status_counts"] == {
        "CURRENT": 19,
        "HISTORICAL": 5,
        "SUPERSEDED": 26,
        "WAITING_REWRITE": 7,
    }
'''
new = '''    assert report["summary"]["document_count"] == REGISTRY["inventory"]["document_count"]
    assert report["summary"]["status_counts"] == REGISTRY["inventory"]["status_counts"]
'''
if base.count(old) != 1:
    raise SystemExit('main test does not contain the expected fixed WO4 totals exactly once')
if current != base.replace(old, new, 1):
    raise SystemExit('tests/test_design_currentness.py changed beyond the one direct-consumer function')
print('PASS_NARROW_TEST_CLOSURE function=test_repository_design_currentness_passes')
PY

python -m pip install --disable-pip-version-check uv

uv run --locked python tools/check_design_currentness.py --check
uv run --locked python tools/check_current_freshness.py --check
uv run --locked pytest -q -p no:cacheprovider \
  tests/test_design_currentness.py \
  tests/test_current_freshness.py \
  tests/test_traceability.py

python - <<'PY' >/tmp/wo5_contract_tests.txt
from pathlib import Path

needles = (
    'C1_CHAPTER_DOC',
    'WORK_DRAFT_HANDOVER_ACTION',
    'validate_c11_chapter_revision_ledger',
)
for path in sorted(Path('tests').rglob('test*.py')):
    text = path.read_text(encoding='utf-8', errors='ignore')
    if any(needle in text for needle in needles):
        print(path.as_posix())
PY

if test -s /tmp/wo5_contract_tests.txt; then
  mapfile -t CONTRACT_TESTS </tmp/wo5_contract_tests.txt
  printf 'CONTRACT_TEST %s\n' "${CONTRACT_TESTS[@]}"
  uv run --locked pytest -q -p no:cacheprovider "${CONTRACT_TESTS[@]}"
else
  echo 'CONTRACT_TEST_DISCOVERY=NONE'
  exit 1
fi

set +e
uv run --locked pytest -q -p no:cacheprovider >/tmp/wo5_candidate_full.log 2>&1
candidate_rc=$?
set -e

git worktree add --detach /tmp/wo5-main origin/main
set +e
(
  cd /tmp/wo5-main
  uv run --locked pytest -q -p no:cacheprovider
) >/tmp/wo5_main_full.log 2>&1
main_rc=$?
set -e

python - "$candidate_rc" "$main_rc" <<'PY'
from pathlib import Path
import sys

candidate_rc = int(sys.argv[1])
main_rc = int(sys.argv[2])
candidate = Path('/tmp/wo5_candidate_full.log').read_text(encoding='utf-8', errors='replace')
main = Path('/tmp/wo5_main_full.log').read_text(encoding='utf-8', errors='replace')

if candidate_rc == 0 and main_rc == 0:
    print('FULL_SUITE=PASS_ON_MAIN_AND_CANDIDATE')
    raise SystemExit(0)

signatures = (
    'ERROR collecting tests/test_novel_mvp_m3_admission.py',
    'REGRESSION_FIXTURE_LOCK.json',
    'FileNotFoundError',
)
identical_baseline_block = (
    candidate_rc == main_rc == 2
    and all(item in candidate and item in main for item in signatures)
    and candidate.count('ERROR collecting') == 1
    and main.count('ERROR collecting') == 1
    and 'FAILED ' not in candidate
    and 'FAILED ' not in main
)
if identical_baseline_block:
    print(
        'FULL_SUITE=BASELINE_BLOCKED_IDENTICALLY '
        'test=tests/test_novel_mvp_m3_admission.py '
        'missing=TEMP/.../REGRESSION_FIXTURE_LOCK.json '
        'candidate_rc=2 main_rc=2'
    )
    raise SystemExit(0)

print('--- candidate full suite ---')
print(candidate)
print('--- main full suite ---')
print(main)
raise SystemExit(
    f'candidate full-suite result differs from main baseline: '
    f'candidate_rc={candidate_rc} main_rc={main_rc}'
)
PY

uv run --locked ruff check \
  novel-mvp/contracts/validate_c11_chapter_revision_ledger.py \
  tests/test_design_currentness.py

git rm \
  .github/wo5_pr_c_apply.py \
  .github/wo5_pr_c_runner.sh \
  .github/workflows/wo5-pr-c-visible.yml
rmdir .github/workflows .github 2>/dev/null || true

git add \
  novel-mvp/ARCHITECTURE.md \
  novel-mvp/CURRENT_VS_TARGET_R01.md \
  novel-mvp/README.md \
  novel-mvp/design/INDEX.md \
  novel-mvp/design/design_registry.json \
  novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md \
  novel-mvp/design/STOP_POINT_REGISTRY_R03.md \
  novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md \
  novel-mvp/contracts/C1_CHAPTER_DOC.md \
  novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md \
  novel-mvp/contracts/validate_c11_chapter_revision_ledger.py \
  tests/test_design_currentness.py

python - <<'PY'
import subprocess

changed = subprocess.check_output(
    ['git', 'diff', '--cached', '--name-only', 'origin/main'],
    text=True,
).splitlines()
expected = {
    'novel-mvp/ARCHITECTURE.md',
    'novel-mvp/CURRENT_VS_TARGET_R01.md',
    'novel-mvp/README.md',
    'novel-mvp/design/INDEX.md',
    'novel-mvp/design/design_registry.json',
    'novel-mvp/design/LEDGER_DIRECTORY_DESIGN_R01.md',
    'novel-mvp/design/STOP_POINT_REGISTRY_R03.md',
    'novel-mvp/design/INTAKE_SHELVES_DESIGN_R02.md',
    'novel-mvp/contracts/C1_CHAPTER_DOC.md',
    'novel-mvp/contracts/WORK_DRAFT_HANDOVER_ACTION.md',
    'novel-mvp/contracts/validate_c11_chapter_revision_ledger.py',
    'tests/test_design_currentness.py',
}
if set(changed) != expected:
    raise SystemExit(
        f'PR-C write set mismatch missing={sorted(expected-set(changed))} '
        f'unexpected={sorted(set(changed)-expected)}'
    )
forbidden_prefixes = (
    '.github/',
    'novel-mvp/mvp/',
    'work/',
    'references/cloud-supervision/',
    'governance/',
)
forbidden = [
    path for path in changed
    if path in {'README.md', 'AGENTS.md'} or path.startswith(forbidden_prefixes)
]
if forbidden:
    raise SystemExit(f'PR-C forbidden paths: {forbidden}')
print(f'PASS_PR_C_SCOPE changed_files={len(changed)}')
for path in changed:
    print(path)
PY

git diff --cached --check
git commit -m "feat(novel-mvp): admit PR-C architecture and ledger design [skip ci]"
git push origin "HEAD:${BRANCH_NAME}"
