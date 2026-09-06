"""CLI: synthetic chapter → existing authority store → existing human card HTML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .vertical_wire import (
        DEFAULT_PROJECT_SCOPE_ID,
        STATUS_WIRED,
        dumps_result,
        load_synthetic_chapter,
        wire_synthetic_chapter_to_card,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from vertical_wire import (  # type: ignore[no-redef]
        DEFAULT_PROJECT_SCOPE_ID,
        STATUS_WIRED,
        dumps_result,
        load_synthetic_chapter,
        wire_synthetic_chapter_to_card,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Wire one frozen synthetic chapter into the existing human card."
    )
    parser.add_argument(
        "--chapter-file",
        type=Path,
        default=None,
        help="UTF-8 synthetic chapter. Default: this package's synthetic_chapter.txt.",
    )
    parser.add_argument(
        "--chapter-text",
        default=None,
        help="Inline chapter text. Overrides --chapter-file when set.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="CandidateAuthorityStore root. Omit to fail closed with a gap page.",
    )
    parser.add_argument(
        "--project-scope-id",
        default=DEFAULT_PROJECT_SCOPE_ID,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the existing-card HTML here.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
    )
    args = parser.parse_args(argv)
    if args.chapter_text is not None:
        chapter_text = args.chapter_text
    else:
        chapter_text = load_synthetic_chapter(args.chapter_file)
    result = wire_synthetic_chapter_to_card(
        chapter_text=chapter_text,
        store_root=args.store,
        project_scope_id=args.project_scope_id,
    )
    if args.out is not None:
        args.out.write_text(result["html"], encoding="utf-8")
    if not args.json_only:
        sys.stdout.write(result["markdown"] + "\n\n")
    sys.stdout.write(dumps_result(result))
    return 0 if result["status"] == STATUS_WIRED else 2


if __name__ == "__main__":
    raise SystemExit(main())
