"""Render the per-quarter overview/dashboard page (Confluence storage format)."""

from __future__ import annotations

import html

from m365_confluence.quarters import UNSCHEDULED, quarter_key
from m365_confluence.state import ItemState


def _esc(value: str) -> str:
    return html.escape(value or "")


def _page_link(title: str) -> str:
    """A Confluence storage-format link to another page by its title."""
    safe = _esc(title)
    return (
        "<ac:link>"
        f'<ri:page ri:content-title="{safe}" />'
        f"<ac:plain-text-link-body><![CDATA[{title}]]></ac:plain-text-link-body>"
        "</ac:link>"
    )


def dashboard_title(quarter: str, prefix: str) -> str:
    label = quarter or UNSCHEDULED
    return f"{prefix}Rollouts {label}"


def build_dashboard_body(quarter: str, items: list[ItemState]) -> str:
    ordered = sorted(items, key=lambda s: (not s.slipped, s.title.lower()))
    rows = []
    for state in ordered:
        title_cell = (
            _page_link(state.confluence_title) if state.confluence_title else _esc(state.title)
        )
        slip = "⚠ verschoben" if state.slipped else ""
        rows.append(
            "<tr>"
            f"<td>{title_cell}</td>"
            f"<td>{_esc(', '.join(state.products))}</td>"
            f"<td>{_esc(state.status)}</td>"
            f"<td>{_esc(state.decision)}</td>"
            f"<td>{_esc(slip)}</td>"
            "</tr>"
        )

    header = (
        "<tr><th>Feature</th><th>Produkte</th><th>Status</th>"
        "<th>Entscheidung</th><th>Verzug</th></tr>"
    )
    count = len(ordered)
    label = quarter or UNSCHEDULED
    return (
        f"<p>{count} Feature(s) für <strong>{_esc(label)}</strong>. "
        "Automatisch generiert – nicht manuell bearbeiten.</p>"
        f"<table><tbody>{header}{''.join(rows)}</tbody></table>"
    )


def group_by_quarter(items: list[ItemState]) -> dict[str, list[ItemState]]:
    groups: dict[str, list[ItemState]] = {}
    for state in items:
        key = state.target_quarter or UNSCHEDULED
        groups.setdefault(key, []).append(state)
    return dict(sorted(groups.items(), key=lambda kv: quarter_key(kv[0])))
