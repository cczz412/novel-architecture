"""CLI for the A-track current-candidate read proof."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .current_read_proof import (
        DEFAULT_PROJECT_SCOPE_ID,
        dumps_proof,
        prove_current_read,
        render_human_text,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from current_read_proof import (  # type: ignore[no-redef]
        DEFAULT_PROJECT_SCOPE_ID,
        dumps_proof,
        prove_current_read,
        render_human_text,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prove where current candidate is read, or report a typed gap."
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="CandidateAuthorityStore root (directory that holds the sqlite file).",
    )
    parser.add_argument(
        "--project-scope-id",
        default=DEFAULT_PROJECT_SCOPE_ID,
    )
    parser.add_argument(
        "--pointer-key",
        default=None,
        help="Logical pointer key. If omitted and exactly one pointer exists, use it.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only the machine proof JSON.",
    )
    args = parser.parse_args(argv)
    proof = prove_current_read(
        store_root=args.store,
        project_scope_id=args.project_scope_id,
        pointer_key=args.pointer_key,
    )
    if not args.json_only:
        sys.stdout.write(render_human_text(proof) + "\n\n")
    sys.stdout.write(dumps_proof(proof))
    return 0 if proof["status"] == "READ_OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
