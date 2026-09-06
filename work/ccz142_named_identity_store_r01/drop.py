"""CLI: persist named identity beside the store, or reopen from store only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .store_identity import (
        STATUS_DROPPED,
        drop_named_chapter_to_store,
        dumps_result,
        open_store_card,
    )
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from store_identity import (  # type: ignore[no-redef]
        STATUS_DROPPED,
        drop_named_chapter_to_store,
        dumps_result,
        open_store_card,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Drop a named released chapter and persist 书名／章节 beside the store, "
            "or reopen the existing card from the store path only."
        )
    )
    parser.add_argument("--book", default=None)
    parser.add_argument("--chapter", type=int, default=None)
    parser.add_argument("--txt", type=Path, default=None)
    parser.add_argument("--store", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--open-only", action="store_true")
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args(argv)
    if args.open_only:
        result = open_store_card(store_root=args.store)
        ok = result.get("identity_stamped") is True
    else:
        if not args.book or args.chapter is None:
            parser.error("--book and --chapter are required unless --open-only")
        result = drop_named_chapter_to_store(
            book=args.book,
            chapter_no=args.chapter,
            txt_path=args.txt,
            store_root=args.store,
        )
        ok = result["status"] == STATUS_DROPPED
    if args.out is not None:
        args.out.write_text(result["html"], encoding="utf-8")
    if not args.json_only:
        sys.stdout.write(result["markdown"] + "\n\n")
    sys.stdout.write(dumps_result(result))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
