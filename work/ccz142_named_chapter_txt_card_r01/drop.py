"""CLI: named book+chapter TXT → existing human card HTML."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .named_chapter import (
        STATUS_DROPPED,
        drop_named_chapter,
        dumps_result,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from named_chapter import (  # type: ignore[no-redef]
        STATUS_DROPPED,
        drop_named_chapter,
        dumps_result,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Drop one named, rights-released chapter TXT into the existing human card."
        )
    )
    parser.add_argument(
        "--book",
        required=True,
        help="Book title or allowlist book_id. Example: 北塔夹具",
    )
    parser.add_argument(
        "--chapter",
        type=int,
        required=True,
        help="Chapter number. Example: 1",
    )
    parser.add_argument(
        "--txt",
        type=Path,
        default=None,
        help="UTF-8 chapter TXT. Default: the allowlisted in-repo fixture.",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="CandidateAuthorityStore root. Omit to fail closed with a gap page.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write the existing-card HTML (with drop banner) here.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
    )
    args = parser.parse_args(argv)
    result = drop_named_chapter(
        book=args.book,
        chapter_no=args.chapter,
        txt_path=args.txt,
        store_root=args.store,
    )
    if args.out is not None:
        args.out.write_text(result["html"], encoding="utf-8")
    if not args.json_only:
        sys.stdout.write(result["markdown"] + "\n\n")
    sys.stdout.write(dumps_result(result))
    return 0 if result["status"] == STATUS_DROPPED else 2


if __name__ == "__main__":
    raise SystemExit(main())
