"""CLI: named book+chapter TXT → existing human card with book/chapter fields."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .identity_card import (
        STATUS_DROPPED,
        drop_named_chapter_with_card_identity,
        dumps_result,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from identity_card import (  # type: ignore[no-redef]
        STATUS_DROPPED,
        drop_named_chapter_with_card_identity,
        dumps_result,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Drop one named released chapter TXT and stamp book/chapter "
            "onto the existing human card."
        )
    )
    parser.add_argument("--book", required=True)
    parser.add_argument("--chapter", type=int, required=True)
    parser.add_argument("--txt", type=Path, default=None)
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args(argv)
    result = drop_named_chapter_with_card_identity(
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
