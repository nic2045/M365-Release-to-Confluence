"""Render the per-quarter overview/dashboard page (Confluence storage format)."""

from __future__ import annotations

import html

from m365_confluence.confluence_macros import decision_badge, slip_badge
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


def _short(text: str, limit: int = 200) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return _esc(text)


def _title_cell(state: ItemState) -> str:
    if state.has_page and state.confluence_title:
        return _page_link(state.confluence_title)
    return f"<strong>{_esc(state.title)}</strong>"


def build_dashboard_body(
    quarter: str,
    items: list[ItemState],
    moved_out: list[ItemState] | None = None,
) -> str:
    ordered = sorted(items, key=lambda s: (not s.slipped, s.title.lower()))
    rows = []
    for state in ordered:
        if state.slipped and state.previous_quarter:
            slip = slip_badge(f"verschoben aus {state.previous_quarter}")
        elif state.slipped:
            slip = slip_badge()
        else:
            slip = ""
        rows.append(
            "<tr>"
            f"<td>{_title_cell(state)}</td>"
            f"<td>{_esc(', '.join(state.products))}</td>"
            f"<td>{_esc(state.status)}</td>"
            f"<td>{decision_badge(state.decision)}</td>"
            f"<td>{slip}</td>"
            f"<td>{_short(state.summary)}</td>"
            "</tr>"
        )

    header = (
        "<tr><th>Feature</th><th>Produkte</th><th>Status</th>"
        "<th>Entscheidung</th><th>Verzug</th><th>Beschreibung</th></tr>"
    )
    label = quarter or UNSCHEDULED
    body = (
        f"<p>{len(ordered)} Feature(s) für <strong>{_esc(label)}</strong>. "
        "Automatisch generiert – nicht manuell bearbeiten.</p>"
        f"<table><tbody>{header}{''.join(rows)}</tbody></table>"
    )

    if moved_out:
        moved_rows = "".join(
            "<tr>"
            f"<td>{_title_cell(state)}</td>"
            f"<td>{slip_badge('verschoben nach ' + (state.target_quarter or UNSCHEDULED))}</td>"
            "</tr>"
            for state in sorted(moved_out, key=lambda s: s.title.lower())
        )
        body += (
            "<h3>Aus diesem Quartal verschoben</h3>"
            "<table><tbody>"
            "<tr><th>Feature</th><th>Verschoben</th></tr>"
            f"{moved_rows}</tbody></table>"
        )
    return body


def quarter_dashboards(states: list[ItemState]) -> list[tuple[str, str]]:
    """Build (quarter_label, storage_body) for every quarter, incl. moved-out notes."""
    current: dict[str, list[ItemState]] = {}
    moved: dict[str, list[ItemState]] = {}
    for state in states:
        cur = state.target_quarter or UNSCHEDULED
        current.setdefault(cur, []).append(state)
        for past in state.quarter_history:
            if past and past != cur:
                moved.setdefault(past, []).append(state)

    labels = set(current) | set(moved)
    ordered = sorted(labels, key=quarter_key)
    return [
        (label, build_dashboard_body(label, current.get(label, []), moved.get(label, [])))
        for label in ordered
    ]


def group_by_quarter(items: list[ItemState]) -> dict[str, list[ItemState]]:
    groups: dict[str, list[ItemState]] = {}
    for state in items:
        key = state.target_quarter or UNSCHEDULED
        groups.setdefault(key, []).append(state)
    return dict(sorted(groups.items(), key=lambda kv: quarter_key(kv[0])))
