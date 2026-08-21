#!/usr/bin/env python3
"""Create a compact PR-D candidate report from the persisted dependency analysis."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
analysis = json.loads((ROOT / '.github/wo5_pr_d_analysis.json').read_text(encoding='utf-8'))
rows = analysis['all_runtime_files']
by_module = {row['module']: row for row in rows}

anchor_tokens = (
    'workspace', 'store', 'storage', 'safe', 'atomic', 'serialize', 'schema',
    'validat', 'intent', 'route', 'router', 'handle', 'recall', 'artifact',
    'upload_source', 'identity', 'registry', 'transaction', 'commit', 'lock',
)

def m_families(row):
    return sorted({x for x in row.get('consumer_families', []) if x.startswith('M')})

selected_modules = {
    row['module']
    for row in rows
    if any(token in row['module'].lower() for token in anchor_tokens)
    or len(m_families(row)) >= 2
}
# Direct dependency closure for selected shared candidates.
changed = True
while changed:
    changed = False
    for module in list(selected_modules):
        row = by_module.get(module)
        if not row:
            continue
        for dep in row.get('imports', []):
            if dep not in selected_modules:
                selected_modules.add(dep)
                changed = True

selected = []
for module in sorted(selected_modules):
    row = by_module.get(module)
    if row:
        selected.append({
            'path': row['path'],
            'module': module,
            'exists_on_main': row['exists_on_main'],
            'source_blob': row['source_blob'],
            'imports': row['imports'],
            'imported_by': row['imported_by'],
            'consumer_families': row['consumer_families'],
            'own_families': row['own_families'],
            'direct_tests': row['direct_tests'],
            'docstring': row['docstring'],
            'selection_reason': (
                'DIRECT_DEPENDENCY_CLOSURE'
                if not any(token in module.lower() for token in anchor_tokens)
                and len(m_families(row)) < 2
                else 'ANCHOR_OR_MULTI_MODULE'
            ),
        })

excluded_single_module = []
for row in rows:
    own = [x for x in row.get('own_families', []) if x.startswith('M') or x == 'E5']
    consumers = m_families(row)
    if len(own) == 1 and len(consumers) <= 1 and row['module'] not in selected_modules:
        excluded_single_module.append({
            'path': row['path'],
            'family': own[0],
            'consumer_families': consumers,
            'reason': 'SINGLE_MODULE_BUSINESS_SEMANTICS',
        })

out = {
    'source': analysis['source'],
    'main': analysis['main'],
    'requirements': analysis['requirements'],
    'selected_candidate_count': len(selected),
    'selected_candidates': selected,
    'excluded_single_module_count': len(excluded_single_module),
    'excluded_single_module': sorted(excluded_single_module, key=lambda x: x['path']),
}
(ROOT / '.github/wo5_pr_d_selection.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
)
print(json.dumps({
    'selected_candidate_count': len(selected),
    'selected_paths': [row['path'] for row in selected],
    'requirement_ids': [row['requirement_id'] for row in analysis['requirements']],
}, ensure_ascii=False, indent=2))
