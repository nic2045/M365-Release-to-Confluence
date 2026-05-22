"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from m365_confluence.config import Config, ConfigError
from m365_confluence.pipeline import run


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m365-to-confluence",
        description=(
            "Read M365 changes/rollouts (Message Center + roadmap), summarise them "
            "with an LLM, and publish them to Confluence."
        ),
    )
    parser.add_argument(
        "--source",
        choices=["both", "message-center", "roadmap"],
        default="both",
        help="Which source(s) to read (default: both).",
    )
    parser.add_argument(
        "--since-days",
        type=int,
        default=None,
        help="Only include items modified within the last N days.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to process.",
    )
    parser.add_argument(
        "--title-prefix",
        default="[M365] ",
        help="Prefix for generated Confluence page titles.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process items but do not write to Confluence.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    use_message_center = args.source in {"both", "message-center"}
    use_roadmap = args.source in {"both", "roadmap"}

    try:
        config = Config.load(
            use_message_center=use_message_center,
            use_roadmap=use_roadmap,
        )
        result = run(
            config,
            since_days=args.since_days,
            limit=args.limit,
            dry_run=args.dry_run,
            title_prefix=args.title_prefix,
        )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    mode = "dry-run (nothing published)" if args.dry_run else f"published {result.published}"
    print(
        f"Done. fetched={result.fetched} processed={result.processed} "
        f"skipped={result.skipped} ({mode}).",
        file=sys.stderr,
    )
    for title in result.titles:
        print(f"  - {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
