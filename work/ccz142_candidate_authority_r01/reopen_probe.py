"""Read one candidate-authority store from a fresh Python process."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from candidate_authority import CandidateAuthorityStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--project-scope-id", required=True)
    parser.add_argument("--pointer-key", required=True)
    args = parser.parse_args()
    store = CandidateAuthorityStore(
        Path(args.root),
        project_scope_id=args.project_scope_id,
    )
    pointer = store.read_pointer(args.pointer_key)
    candidate = store.read_candidate(pointer["current_candidate_version_ref"])
    result = {
        "candidate_id": candidate["record_id"],
        "candidate_hash": candidate["record_hash"],
        "pointer_generation": pointer["generation"],
        "merge_receipt_count": len(store.read_receipts()),
        "table_counts": store.table_counts(),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
