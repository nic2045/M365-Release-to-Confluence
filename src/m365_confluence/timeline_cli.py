"""Generate a draw.io roadmap timeline from the local state, optionally publish it.

Usage:
  m365-timeline --axis quarter --out roadmap.drawio
  m365-timeline --axis month --publish
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from m365_confluence.config import Config, ConfigError
from m365_confluence.drawio import build_timeline
from m365_confluence.state import StateStore

_DIAGRAM_NAME = "m365-roadmap-timeline"


def _publish(xml: str, title_prefix: str) -> str:
    from m365_confluence.confluence.client import ConfluenceClient

    config = Config.load(use_message_center=False, use_roadmap=False)
    client = ConfluenceClient(config.confluence)
    title = f"{title_prefix}Roadmap Timeline"
    # The draw.io for Confluence app renders an attached diagram whose attachment
    # name equals the macro's diagramName (no file extension). Attach the mxfile
    # under that exact name, and also keep a downloadable .drawio copy.
    body = (
        "<p>Automatisch generiert – nicht manuell bearbeiten.</p>"
        '<ac:structured-macro ac:name="drawio">'
        f'<ac:parameter ac:name="diagramName">{_DIAGRAM_NAME}</ac:parameter>'
        "</ac:structured-macro>"
        "<p>Download: "
        f'<ac:link><ri:attachment ri:filename="{_DIAGRAM_NAME}.drawio"/></ac:link></p>'
    )
    page = client.upsert_page(title, body)
    page_id = str(page.get("id", ""))
    data = xml.encode("utf-8")
    client.attach_file(page_id, _DIAGRAM_NAME, data)  # name == diagramName (for the macro)
    client.attach_file(page_id, f"{_DIAGRAM_NAME}.drawio", data)  # downloadable copy
    return title


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="m365-timeline",
        description="Generate a draw.io roadmap timeline from the local state file.",
    )
    parser.add_argument("--state-file", default="m365_state.json")
    parser.add_argument("--axis", choices=["quarter", "month"], default="quarter")
    parser.add_argument("--rows", choices=["service", "product"], default="service")
    parser.add_argument("--style", choices=["grid", "fishbone"], default="grid")
    parser.add_argument("--out", default="roadmap.drawio", help="Output .drawio file path.")
    parser.add_argument("--publish", action="store_true", help="Also publish/embed in Confluence.")
    parser.add_argument("--title-prefix", default="[M365] ")
    args = parser.parse_args(argv)

    states = StateStore(args.state_file).load().all_items()
    if not states:
        print(f"No items in {args.state_file}. Run a fetch first.", file=sys.stderr)
        return 1

    xml = build_timeline(states, axis=args.axis, rows=args.rows, style=args.style)
    Path(args.out).write_text(xml, encoding="utf-8")
    print(
        f"Wrote {args.out} ({len(states)} items, style={args.style}, "
        f"axis={args.axis}, rows={args.rows})."
    )

    if args.publish:
        try:
            title = _publish(xml, args.title_prefix)
        except ConfigError as exc:
            print(f"Configuration error: {exc}", file=sys.stderr)
            return 2
        print(f"Published timeline to Confluence: {title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
