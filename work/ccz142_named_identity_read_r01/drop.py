"""CLI: reopen the existing card via original show_current_html."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__:
    from .identity_read import dumps_result, open_original_store_card
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from identity_read import dumps_result, open_original_store_card  # type: ignore[no-redef]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Open an existing human card with the original show_current_html path."
        )
    )
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args(argv)
    result = open_original_store_card(store_root=args.store)
    if args.out is not None:
        args.out.write_text(result["html"], encoding="utf-8")
    if not args.json_only:
        sys.stdout.write(result["markdown"] + "\n\n")
    sys.stdout.write(dumps_result(result))
    ok = result.get("identity_from_sidecar") is True
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
