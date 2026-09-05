"""CLI: print the human Markdown card, or the gap page."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .card_render import show_current_card
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from card_render import show_current_card  # type: ignore[no-redef]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Show the current-candidate human card, or a typed gap page."
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="CandidateAuthorityStore root. Omit to show the no-live-store gap page.",
    )
    parser.add_argument(
        "--project-scope-id",
        default="fixture-project-001",
    )
    parser.add_argument(
        "--pointer-key",
        default=None,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write Markdown to this file instead of stdout.",
    )
    args = parser.parse_args(argv)
    shown = show_current_card(
        store_root=args.store,
        project_scope_id=args.project_scope_id,
        pointer_key=args.pointer_key,
    )
    markdown = shown["markdown"]
    if args.out is not None:
        args.out.write_text(markdown, encoding="utf-8")
    else:
        sys.stdout.write(markdown)
        if not markdown.endswith("\n"):
            sys.stdout.write("\n")
    proof = shown["proof"]
    return 0 if proof.get("status") == "READ_OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
