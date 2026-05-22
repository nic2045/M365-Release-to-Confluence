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
        "--quarter",
        default=None,
        help='Only items detected for this target quarter, e.g. "Q3 2026".',
    )
    parser.add_argument(
        "--major-only",
        action="store_true",
        help="Only Message Center items flagged as a major change.",
    )
    parser.add_argument(
        "--action-required",
        action="store_true",
        help="Only items with an action-required deadline.",
    )
    parser.add_argument(
        "--product",
        action="append",
        default=None,
        metavar="NAME",
        help="Only items touching this product (repeatable; substring match, e.g. Teams).",
    )
    parser.add_argument(
        "--category",
        action="append",
        default=None,
        metavar="NAME",
        help="Only items in this Message Center category (repeatable), "
        "e.g. planForChange, preventOrFixIssue, stayInformed.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess all items, even unchanged ones (ignores the state cache).",
    )
    parser.add_argument(
        "--state-file",
        default="m365_state.json",
        help="Path to the local state file used for skip/slip tracking.",
    )
    parser.add_argument(
        "--changelog-file",
        default="m365_changelog.json",
        help="Path to the local changelog file (drives the Changelog page).",
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
        help="Enable debug logging for this tool (third-party HTTP logs stay quiet).",
    )
    parser.add_argument(
        "--debug-http",
        action="store_true",
        help="Also show verbose HTTP logs from httpx/anthropic/openai/requests.",
    )
    return parser


def _configure_logging(*, verbose: bool, debug_http: bool) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)

    logging.getLogger("m365_confluence").setLevel(logging.DEBUG if verbose else logging.INFO)

    # Keep noisy HTTP client libraries quiet unless explicitly requested.
    http_level = logging.DEBUG if debug_http else logging.WARNING
    for noisy in ("httpx", "httpcore", "anthropic", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(http_level)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(verbose=args.verbose, debug_http=args.debug_http)

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
            quarter=args.quarter,
            major_only=args.major_only,
            action_required=args.action_required,
            products=args.product,
            categories=args.category,
            dry_run=args.dry_run,
            force=args.force,
            title_prefix=args.title_prefix,
            state_file=args.state_file,
            changelog_file=args.changelog_file,
        )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    mode = "dry-run (nothing published)" if args.dry_run else f"published {result.published}"
    print(
        f"Done. fetched={result.fetched} processed={result.processed} "
        f"new={result.new} changed={result.changed} unchanged={result.unchanged} "
        f"skipped={result.skipped} slipped={result.slipped} "
        f"dashboards={result.dashboards} ({mode}).",
        file=sys.stderr,
    )
    for title in result.titles:
        print(f"  - {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
