#!/usr/bin/env bash
set -euo pipefail

SOURCE="cc793c4719fb6470946c70e744f463147989547b"
BASE="c533bbada4697bf9af2cf7f245bf4c08069e313f"
BRANCH_NAME="${BRANCH_NAME:?BRANCH_NAME is required}"

cd "$(dirname "$0")/.."
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git fetch origin main:refs/remotes/origin/main
git fetch origin codex/module-runtime-foundation-20260819-r01:refs/remotes/origin/wo5-source
test "$(git rev-parse origin/main)" = "$BASE"
test "$(git rev-parse refs/remotes/origin/wo5-source)" = "$SOURCE"

runtime_files=(
  novel-mvp/mvp/workspace.py
  novel-mvp/mvp/store.py
  novel-mvp/mvp/upload_source.py
  novel-mvp/mvp/recall_handle_workspace.py
  novel-mvp/mvp/ledger_directory_tool.py
  novel-mvp/mvp/ledger_directory_workspace.py
)

test_files=(
  tests/test_novel_mvp_workspace.py
  tests/test_novel_mvp_upload_source.py
  tests/test_novel_mvp_recall_handle_workspace.py
  tests/test_novel_mvp_ledger_directory_tool.py
  tests/test_novel_mvp_ledger_directory_workspace.py
)

all_files=("${runtime_files[@]}" "${test_files[@]}")

printf 'PR_D_BYTE_IDENTITY_TABLE_START\n'
for path in "${all_files[@]}"; do
  mkdir -p "$(dirname "$path")"
  if git cat-file -e "origin/main:$path" 2>/dev/null; then
    before="$(git rev-parse "origin/main:$path")"
  else
    before="ABSENT_ON_MAIN"
  fi
  git show "$SOURCE:$path" > "$path"
  after="$(git hash-object "$path")"
  expected="$(git rev-parse "$SOURCE:$path")"
  test "$after" = "$expected"
  if [[ "$before" == "$expected" ]]; then
    disposition="ALREADY_IDENTICAL_NO_DIFF"
  elif [[ "$before" == "ABSENT_ON_MAIN" ]]; then
    disposition="NEW_EXACT_COPY"
  else
    disposition="REPLACED_WITH_EXACT_COPY"
  fi
  printf '%s | %s | source_blob=%s | main_blob=%s\n' "$path" "$disposition" "$expected" "$before"
done
printf 'PR_D_BYTE_IDENTITY_TABLE_END\n'

python - <<'PY'
from __future__ import annotations
import ast
import json
import subprocess
from pathlib import Path

source = "cc793c4719fb6470946c70e744f463147989547b"
selected = {
    "workspace",
    "store",
    "upload_source",
    "recall_handle_workspace",
    "ledger_directory_tool",
    "ledger_directory_workspace",
}
paths = [Path("novel-mvp/mvp") / f"{name}.py" for name in sorted(selected)]

def internal_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 1 and module:
                result.add(module.split(".", 1)[0])
            elif module.startswith("mvp."):
                result.add(module.split(".", 2)[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("mvp."):
                    result.add(alias.name.split(".", 2)[1])
    return result

closure = {}
for path in paths:
    name = path.stem
    deps = sorted(internal_imports(path))
    closure[name] = deps
    for dep in deps:
        if dep in selected:
            continue
        dep_path = f"novel-mvp/mvp/{dep}.py"
        source_exists = subprocess.run(
            ["git", "cat-file", "-e", f"{source}:{dep_path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if not source_exists:
            continue
        main_exists = subprocess.run(
            ["git", "cat-file", "-e", f"origin/main:{dep_path}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if not main_exists:
            raise SystemExit(f"MISSING_DIRECT_DEPENDENCY:{name}->{dep_path}")
        src_blob = subprocess.check_output(
            ["git", "rev-parse", f"{source}:{dep_path}"], text=True
        ).strip()
        main_blob = subprocess.check_output(
            ["git", "rev-parse", f"origin/main:{dep_path}"], text=True
        ).strip()
        if src_blob != main_blob:
            raise SystemExit(
                f"CHANGED_DIRECT_DEPENDENCY_NOT_SELECTED:{name}->{dep_path}:"
                f"source={src_blob}:main={main_blob}"
            )
print("PASS_PR_D_DIRECT_DEPENDENCY_CLOSURE=" + json.dumps(closure, sort_keys=True))

trace = json.loads(Path("governance/capability_traceability.json").read_text(encoding="utf-8"))
owners = {"AUTHOR_WORKSPACE", "STORAGE", "ROUTER", "SHARED_SERVICE"}
ids = sorted(
    row["requirement_id"]
    for row in trace["requirements"]
    if row.get("primary_owner") in owners
)
expected = [
    "AE-AW-B01", "AE-AW-B02", "AE-AW-B03",
    "AE-AW-C01", "AE-AW-C02", "AE-AW-C03", "AE-AW-C04",
    "AE-AW-C05", "AE-AW-C06",
    "AE-AW-N01", "AE-AW-N02", "AE-AW-N03", "AE-AW-N04",
]
if ids != expected:
    raise SystemExit(f"PR_D_REQUIREMENT_SET_CHANGED:expected={expected}:actual={ids}")
print("PR_D_REQUIREMENT_IDS=" + ",".join(ids))
PY

python -m pip install --disable-pip-version-check uv
uv run --locked python tools/check_design_currentness.py --check
uv run --locked python tools/check_current_freshness.py --check

uv run --locked pytest -q -p no:cacheprovider "${test_files[@]}"

mapfile -t existing_novel_tests < <(find tests -maxdepth 1 -type f -name 'test_novel_mvp*.py' -print | sort)
filtered_tests=()
for test_path in "${existing_novel_tests[@]}"; do
  if [[ "$test_path" == "tests/test_novel_mvp_m3_admission.py" ]]; then
    continue
  fi
  filtered_tests+=("$test_path")
done
printf 'PR_D_MAIN_NOVEL_TEST_FILES=%s\n' "${#filtered_tests[@]}"
uv run --locked pytest -q -p no:cacheprovider "${filtered_tests[@]}"

uv run --locked ruff check "${runtime_files[@]}" "${test_files[@]}"

printf 'PR_D_ADAPTATION_TABLE_START\n'
printf 'NONE | all selected runtime and tests are byte-exact frozen-source copies\n'
printf 'PR_D_ADAPTATION_TABLE_END\n'

printf 'PR_D_EXCLUDED_BUSINESS_FILES_START\n'
printf 'PR-E1 | novel-mvp/mvp/input_router.py | M1 format/intake semantics\n'
printf 'PR-E1/PR-E5 | novel-mvp/mvp/external_chapter_route_tool.py | external-chapter lane gate\n'
printf 'PR-E2 | novel-mvp/mvp/factstore.py | M4/M5 fact transaction semantics\n'
printf 'PR-E2 | novel-mvp/mvp/ask_tool.py | M6 evidence-query semantics\n'
printf 'PR-E3 | novel-mvp/mvp/overview.py | M9 projection semantics\n'
printf 'PR-E4 | novel-mvp/mvp/intent_router.py | M8 future-intent semantics\n'
printf 'PR-E4 | novel-mvp/mvp/intent_router_tool.py | M8 intent transport shell\n'
printf 'PR-E4/PR-E5 | novel-mvp/mvp/planstore.py | planning and handover business state\n'
printf 'PR-E5 | chapter/work_draft/handover/revision runtime files | chapter-fact-draft vertical cut\n'
printf 'PR-F | fixture directories | full fixture migration\n'
printf 'PR_D_EXCLUDED_BUSINESS_FILES_END\n'

# Remove every temporary WO5 PR-D analysis/execution file from the final branch.
rm -f \
  .github/wo5_pr_d_analyze.py \
  .github/wo5_pr_d_analysis.json \
  .github/wo5_pr_d_select.py \
  .github/wo5_pr_d_selection.json \
  .github/wo5_pr_d_compact.json \
  .github/wo5_pr_d_runner.sh \
  .github/workflows/wo5-pr-d-analyze.yml \
  .github/workflows/wo5-pr-d-compact.yml \
  .github/workflows/wo5-pr-d-final.yml
rmdir .github/workflows .github 2>/dev/null || true

git add "${all_files[@]}"
# Stage removal of temporary tracked files.
git add -u .github 2>/dev/null || true

python - <<'PY'
from __future__ import annotations
import subprocess

allowed = {
    "novel-mvp/mvp/workspace.py",
    "novel-mvp/mvp/store.py",
    "novel-mvp/mvp/upload_source.py",
    "novel-mvp/mvp/recall_handle_workspace.py",
    "novel-mvp/mvp/ledger_directory_tool.py",
    "novel-mvp/mvp/ledger_directory_workspace.py",
    "tests/test_novel_mvp_workspace.py",
    "tests/test_novel_mvp_upload_source.py",
    "tests/test_novel_mvp_recall_handle_workspace.py",
    "tests/test_novel_mvp_ledger_directory_tool.py",
    "tests/test_novel_mvp_ledger_directory_workspace.py",
}
changed = subprocess.check_output(
    ["git", "diff", "--cached", "--name-only", "origin/main"], text=True
).splitlines()
unexpected = sorted(set(changed) - allowed)
if unexpected:
    raise SystemExit(f"PR_D_UNEXPECTED_FINAL_PATHS:{unexpected}")
required = {
    "novel-mvp/mvp/recall_handle_workspace.py",
    "novel-mvp/mvp/ledger_directory_tool.py",
    "novel-mvp/mvp/ledger_directory_workspace.py",
    "tests/test_novel_mvp_recall_handle_workspace.py",
    "tests/test_novel_mvp_ledger_directory_tool.py",
    "tests/test_novel_mvp_ledger_directory_workspace.py",
}
missing = sorted(required - set(changed))
if missing:
    raise SystemExit(f"PR_D_REQUIRED_NEW_PATHS_MISSING:{missing}")
for path in changed:
    if path.startswith(("novel-mvp/design/", "governance/", "work/", "references/cloud-supervision/", ".github/")):
        raise SystemExit(f"PR_D_FORBIDDEN_PATH:{path}")
    if path in {"AGENTS.md", "README.md"}:
        raise SystemExit(f"PR_D_FORBIDDEN_ROOT_PATH:{path}")
print(f"PASS_PR_D_FINAL_SCOPE changed_files={len(changed)}")
for path in changed:
    print(path)
PY

git diff --cached --check
git commit -m "feat(novel-mvp): admit shared runtime foundation [skip ci]"
git push origin "HEAD:${BRANCH_NAME}"
