"""Join one coordinated concurrent root initialization from a fresh process."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from candidate_authority import CandidateAuthorityStore, CandidateRootInitializer
from shadow_fixtures import (
    MutableRootAuthorityReader,
    authority_snapshot,
    root_request,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--project-scope-id", required=True)
    parser.add_argument("--start-file", type=Path, required=True)
    args = parser.parse_args()
    deadline = time.monotonic() + 10
    while not args.start_file.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError("CONCURRENT_START_FILE_TIMEOUT")
        time.sleep(0.01)
    request = root_request(project_scope_id=args.project_scope_id)
    store = CandidateAuthorityStore(
        args.root,
        project_scope_id=args.project_scope_id,
    )
    result = CandidateRootInitializer(
        store=store,
        authority_reader=MutableRootAuthorityReader(authority_snapshot(request)),
    ).initialize_root(request)
    print(
        json.dumps(
            {
                "candidate_version_ref": result["candidate_version_ref"],
                "reused_existing_initialization": result[
                    "reused_existing_initialization"
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
