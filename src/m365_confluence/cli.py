"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys

from m365_confluence.config import Config, ConfigError
from m365_confluence.pipeline import collect_products, run, run_from_review


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
        "--list-products",
        action="store_true",
        help="List the products found in the source(s) with counts, then exit "
        "(no LLM, no Confluence). Use it to pick values for --product.",
    )
    parser.add_argument(
        "--pick-products",
        action="store_true",
        help="Interactively choose products (multi-select) before running.",
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
        "--item-pages",
        choices=["none", "major", "all"],
        default="major",
        help="Create an individual page per feature: 'none', 'major' (only major "
        "changes, default), or 'all'. The quarter dashboards are always created.",
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
        "--review-out",
        metavar="PATH",
        default=None,
        help="Process items and write editable drafts to PATH (review.json); publish nothing.",
    )
    parser.add_argument(
        "--from-review",
        metavar="PATH",
        default=None,
        help="Publish edited drafts from PATH to Confluence without calling the LLM.",
    )
    parser.add_argument(
        "--title-prefix",
        default="[M365] ",
        help="Prefix for generated Confluence page titles.",
    )
    parser.add_argument(
        "--approve",
        action="store_true",
        help="Explicit human approval to write to Confluence. Without it (and without "
        "--dry-run) the tool only writes drafts (review.json) for review.",
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


def _parse_selection(raw: str, count: int) -> list[int]:
    """Parse '1,3,5', ranges '1-4', or 'all' into 0-based indices."""
    text = raw.strip().lower()
    if text in {"all", "*"}:
        return list(range(count))
    chosen: set[int] = set()
    for token in text.replace(",", " ").split():
        if "-" in token:
            start, _, end = token.partition("-")
            if start.isdigit() and end.isdigit():
                for n in range(int(start), int(end) + 1):
                    if 1 <= n <= count:
                        chosen.add(n - 1)
        elif token.isdigit() and 1 <= int(token) <= count:
            chosen.add(int(token) - 1)
    return sorted(chosen)


def _interactive_pick(products: list[tuple[str, int]]) -> list[str]:
    if not products:
        print("No products found in the selected source(s).", file=sys.stderr)
        return []
    print("Select products (multi-select):", file=sys.stderr)
    for i, (name, cnt) in enumerate(products, start=1):
        print(f"  [{i:2d}] {name}  ({cnt})", file=sys.stderr)
    print("Enter numbers (e.g. 1,3,5 or 1-4), 'all', or blank to cancel:", file=sys.stderr)
    try:
        raw = input("> ")
    except EOFError:
        raw = ""
    indices = _parse_selection(raw, len(products))
    return [products[i][0] for i in indices]


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    _configure_logging(verbose=args.verbose, debug_http=args.debug_http)

    use_message_center = args.source in {"both", "message-center"}
    use_roadmap = args.source in {"both", "roadmap"}

    if args.list_products:
        try:
            config = Config.load(
                use_message_center=use_message_center,
                use_roadmap=use_roadmap,
                require_confluence=False,
            )
            products = collect_products(config)
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2
        print(f"Found {len(products)} distinct product(s):")
        for name, count in products:
            print(f"  {count:5d}  {name}")
        return 0

    if args.from_review:
        try:
            config = Config.load(
                use_message_center=False,
                use_roadmap=False,
                require_confluence=not args.dry_run,
            )
            result = run_from_review(
                config,
                args.from_review,
                dry_run=args.dry_run,
                title_prefix=args.title_prefix,
                state_file=args.state_file,
                changelog_file=args.changelog_file,
            )
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2
        print(
            f"Published from review: pages={result.published} dashboards={result.dashboards}.",
            file=sys.stderr,
        )
        return 0

    # Safe by default: never write to Confluence without explicit human approval.
    review_out = args.review_out
    auto_review = False
    if not args.approve and not args.dry_run and review_out is None:
        review_out = "review.json"
        auto_review = True

    try:
        config = Config.load(
            use_message_center=use_message_center,
            use_roadmap=use_roadmap,
            require_confluence=not args.dry_run and review_out is None,
        )
        # CLI overrides config defaults; config (.env) fills in when a flag is absent.
        f = config.filters
        if args.pick_products:
            products = _interactive_pick(collect_products(config))
            if not products:
                print("No products selected; aborting.", file=sys.stderr)
                return 0
        elif args.product is not None:
            products = args.product
        else:
            products = f.products or None
        result = run(
            config,
            since_days=args.since_days,
            limit=args.limit,
            quarter=args.quarter if args.quarter is not None else (f.quarter or None),
            major_only=args.major_only or f.major_only,
            action_required=args.action_required or f.action_required,
            products=products,
            categories=args.category if args.category is not None else (f.categories or None),
            dry_run=args.dry_run,
            force=args.force,
            item_pages=args.item_pages,
            title_prefix=args.title_prefix,
            state_file=args.state_file,
            changelog_file=args.changelog_file,
            review_out=review_out,
        )
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        mode = "dry-run (nothing published)"
    elif review_out is not None:
        mode = f"drafts written to {review_out} (NOT published)"
    else:
        mode = f"published {result.published}"
    print(
        f"Done. fetched={result.fetched} processed={result.processed} "
        f"new={result.new} changed={result.changed} unchanged={result.unchanged} "
        f"skipped={result.skipped} slipped={result.slipped} "
        f"dashboards={result.dashboards} ({mode}).",
        file=sys.stderr,
    )
    if auto_review:
        print(
            "No --approve given: nothing was written to Confluence. Review the drafts "
            f"({review_out}) in the UI or with --from-review, then publish.",
            file=sys.stderr,
        )
    for title in result.titles:
        print(f"  - {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
