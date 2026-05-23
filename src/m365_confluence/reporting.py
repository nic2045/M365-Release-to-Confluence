"""Render the per-quarter overview/dashboard page (Confluence storage format)."""

from __future__ import annotations

import html

from m365_confluence.confluence_macros import (
    area_badges,
    cab_badge,
    decision_badge,
    service_badges,
    slip_badge,
    status_macro,
)
from m365_confluence.quarters import UNSCHEDULED, quarter_key
from m365_confluence.services import services_for
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


NO_PRODUCT = "Ohne Produkt"

_HEADER = (
    "<tr><th>Feature</th><th>Service</th><th>Bereich</th><th>Status</th><th>Entscheidung</th>"
    "<th>CAB-Empfehlung</th><th>Bewertung</th><th>Verzug</th><th>Beschreibung</th></tr>"
)


def _products_of(state: ItemState) -> list[str]:
    return state.products or [NO_PRODUCT]


def _assessment_cell(state: ItemState) -> str:
    tags = []
    if state.data_protection_impact:
        tags.append("Datenschutz")
    if state.it_landscape_impact:
        tags.append("IT-Landschaft")
    if state.config_change_required:
        tags.append("Konfig")
    if state.kbv_change_required:
        tags.append("KBV")
    if "Security" in state.areas:
        tags.append("Risikobewertung")
    return "".join(status_macro("Yellow", t) for t in tags)


def _feature_row(state: ItemState) -> str:
    if state.slipped and state.previous_quarter:
        slip = slip_badge(f"verschoben aus {state.previous_quarter}")
    elif state.slipped:
        slip = slip_badge()
    else:
        slip = ""
    cab_rec = f" {_short(state.cab_recommendation, 140)}" if state.cab_recommendation else ""
    cab_cell = f"{cab_badge(state.cab_required)}{cab_rec}"
    return (
        "<tr>"
        f"<td>{_title_cell(state)}</td>"
        f"<td>{service_badges(services_for(state.products))}</td>"
        f"<td>{area_badges(state.areas)}</td>"
        f"<td>{_esc(state.status)}</td>"
        f"<td>{decision_badge(state.decision)}</td>"
        f"<td>{cab_cell}</td>"
        f"<td>{_assessment_cell(state)}</td>"
        f"<td>{slip}</td>"
        f"<td>{_short(state.summary)}</td>"
        "</tr>"
    )


def build_dashboard_body(
    quarter: str,
    items: list[ItemState],
    moved_out: list[ItemState] | None = None,
) -> str:
    by_product: dict[str, list[ItemState]] = {}
    for state in items:
        for product in _products_of(state):
            by_product.setdefault(product, []).append(state)

    label = quarter or UNSCHEDULED
    body = (
        f"<p>{len(items)} Feature(s) für <strong>{_esc(label)}</strong>, nach Produkt gegliedert. "
        "Automatisch generiert – nicht manuell bearbeiten.</p>"
    )
    for product in sorted(by_product, key=lambda p: (p == NO_PRODUCT, p.lower())):
        group = sorted(by_product[product], key=lambda s: (not s.slipped, s.title.lower()))
        rows = "".join(_feature_row(s) for s in group)
        body += f"<h3>{_esc(product)}</h3><table><tbody>{_HEADER}{rows}</tbody></table>"

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
