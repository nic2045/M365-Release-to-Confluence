"""Generate a draw.io (mxGraph) timeline from tracked items.

Rows = products (swimlanes), columns = time buckets (quarters or months).
Boxes are coloured by the evergreen decision. Output is a ``.drawio`` XML string
that opens in diagrams.net / the Confluence draw.io app.
"""

from __future__ import annotations

import html
import re

from m365_confluence.quarters import UNSCHEDULED, quarter_key
from m365_confluence.services import services_for
from m365_confluence.state import ItemState

NO_PRODUCT = "Ohne Produkt"
_MONTH_ABBR = [
    "",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]

_DEC_HEX = {
    "Activate": ("#d5f5e3", "#1f7a4d"),
    "Communicate": ("#d6e4ff", "#0a5bd6"),
    "Monitor": ("#fff3cd", "#9a6b00"),
    "Deactivate": ("#fde0e0", "#b42318"),
}

_HEADER_STYLE = "rounded=0;fillColor=#0a84ff;fontColor=#ffffff;fontStyle=1;html=1;whiteSpace=wrap;"

# Layout (pixels)
_ROW_HDR_W = 180
_COL_W = 210
_TITLE_H = 30
_COL_HDR_H = 30
_ITEM_H = 46
_GAP = 8


def _esc(value: str) -> str:
    return html.escape(value or "")


def _quarter_ym(label: str) -> tuple[int, int] | None:
    m = re.match(r"Q([1-4])\s+(\d{4})", label or "")
    if not m:
        return None
    q, y = int(m.group(1)), int(m.group(2))
    return (y, (q - 1) * 3 + 1)


def _products_of(state: ItemState) -> list[str]:
    return state.products or [NO_PRODUCT]


def _rows_of(state: ItemState, rows: str) -> list[str]:
    if rows == "service":
        return services_for(state.products)
    return _products_of(state)


def _bucket(state: ItemState, axis: str) -> str:
    q = state.target_quarter or UNSCHEDULED
    if axis != "month" or q == UNSCHEDULED:
        return q
    ym = _quarter_ym(q)
    if not ym:
        return UNSCHEDULED
    return f"{_MONTH_ABBR[ym[1]]} {ym[0]}"


def _columns(states: list[ItemState], axis: str) -> list[str]:
    buckets = {_bucket(s, axis) for s in states}
    if axis != "month":
        return sorted(buckets, key=quarter_key)
    # Build a continuous monthly axis from the earliest to the latest quarter present.
    yms = []
    for s in states:
        q = s.target_quarter or UNSCHEDULED
        if q != UNSCHEDULED and (ym := _quarter_ym(q)):
            yms.append(ym)
    cols: list[str] = []
    if yms:
        (y0, m0), (y1, m1) = min(yms), max(yms)
        y, m = y0, m0
        while (y, m) <= (y1, m1):
            cols.append(f"{_MONTH_ABBR[m]} {y}")
            m += 1
            if m > 12:
                m, y = 1, y + 1
    if UNSCHEDULED in buckets:
        cols.append(UNSCHEDULED)
    return cols


def _cell(cid: str, value: str, style: str, x: int, y: int, w: int, h: int) -> str:
    return (
        f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def _edge(cid: str, source: str, target: str, style: str) -> str:
    return (
        f'<mxCell id="{cid}" style="{style}" edge="1" parent="1" '
        f'source="{source}" target="{target}"><mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def _wrap(body: str) -> str:
    return (
        '<mxfile><diagram name="Roadmap">'
        '<mxGraphModel dx="1200" dy="800" grid="0" gridSize="10" guides="1" '
        'tooltips="1" connect="0" arrows="0" fold="0" page="1" pageScale="1" '
        'math="0" shadow="0"><root>'
        '<mxCell id="0"/><mxCell id="1" parent="0"/>'
        f"{body}"
        "</root></mxGraphModel></diagram></mxfile>"
    )


def build_timeline(
    states: list[ItemState], axis: str = "quarter", rows: str = "service", style: str = "grid"
) -> str:
    if style == "fishbone":
        return _build_fishbone(states, axis, rows)
    products = sorted(
        {p for s in states for p in _rows_of(s, rows)},
        key=lambda p: (p in (NO_PRODUCT, "Sonstiges"), p.lower()),
    )
    columns = _columns(states, axis)

    # Index items by (row, column).
    grid: dict[tuple[str, str], list[ItemState]] = {}
    for s in states:
        col = _bucket(s, axis)
        for p in _rows_of(s, rows):
            grid.setdefault((p, col), []).append(s)

    # Row heights from the busiest cell in each row.
    row_h: dict[str, int] = {}
    for p in products:
        busiest = max((len(grid.get((p, c), [])) for c in columns), default=0)
        row_h[p] = max(1, busiest) * (_ITEM_H + _GAP) + _GAP

    cells: list[str] = []
    header = "rounded=0;fillColor=#0a84ff;fontColor=#ffffff;fontStyle=1;html=1;whiteSpace=wrap;"
    rowhdr = "rounded=0;fillColor=#f0f3f7;fontStyle=1;html=1;whiteSpace=wrap;align=left;"
    grid_style = "rounded=0;fillColor=none;strokeColor=#d0d5dd;html=1;"

    # Column headers
    for ci, col in enumerate(columns):
        x = _ROW_HDR_W + ci * _COL_W
        cells.append(_cell(f"col{ci}", _esc(col), header, x, _TITLE_H, _COL_W, _COL_HDR_H))

    # Rows: left header + per-cell grid background + item boxes
    y = _TITLE_H + _COL_HDR_H
    for ri, product in enumerate(products):
        h = row_h[product]
        cells.append(_cell(f"row{ri}", _esc(product), rowhdr, 0, y, _ROW_HDR_W, h))
        for ci, col in enumerate(columns):
            x = _ROW_HDR_W + ci * _COL_W
            cells.append(_cell(f"bg{ri}_{ci}", "", grid_style, x, y, _COL_W, h))
            items = grid.get((product, col), [])
            for k, s in enumerate(items):
                fill, stroke = _DEC_HEX.get(s.decision, ("#eeeeee", "#888888"))
                style = (
                    f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                    "align=left;verticalAlign=top;spacing=4;"
                )
                title = s.title if len(s.title) <= 70 else s.title[:69] + "…"
                slip = " ⚠" if s.slipped else ""
                # Label markup must be escaped inside the XML attribute value.
                value = f"{_esc(title)}{slip}&#10;&lt;i&gt;{_esc(s.decision)}&lt;/i&gt;"
                bx = x + _GAP
                by = y + _GAP + k * (_ITEM_H + _GAP)
                cells.append(
                    _cell(f"it{ri}_{ci}_{k}", value, style, bx, by, _COL_W - 2 * _GAP, _ITEM_H)
                )
        y += h

    cells.append(_cell("title", "M365 Roadmap Timeline", header, 0, 0, _ROW_HDR_W, _TITLE_H))
    body = "".join(cells)
    return _wrap(body)


def _build_fishbone(states: list[ItemState], axis: str, rows: str) -> str:
    """Fishbone/Ishikawa layout.

    A horizontal time spine (arrow head = future, right). Each quarter is a
    diagonal main bone, alternating above/below the spine, with the quarter label
    at its tip; the quarter's features hang off the bone as a diagonal chain of
    twig boxes, coloured by decision.
    """
    columns = list(_columns(states, axis))
    grid: dict[str, list[ItemState]] = {}
    for s in states:
        grid.setdefault(_bucket(s, axis), []).append(s)

    w, h = 180, 42
    span = 300  # horizontal distance between quarter bones
    first = 70  # offset of the quarter label from the spine
    step_y = h + 16  # vertical distance between stacked twig boxes
    dx = 26  # horizontal slant per step (gives the diagonal bone look)
    x0 = 60

    # Vertical room needed on the busier side determines the spine's y.
    up_max = max((len(grid.get(c, [])) for i, c in enumerate(columns) if i % 2 == 0), default=0)
    mid_y = 70 + first + (up_max + 1) * step_y

    cells: list[str] = []
    spine_style = "endArrow=classic;html=1;strokeColor=#0a84ff;strokeWidth=3;"
    bone_style = "endArrow=none;html=1;strokeColor=#9aa4b2;"
    qlabel_style = "rounded=1;html=1;fontStyle=1;fillColor=#0a84ff;fontColor=#ffffff;"
    invisible = "fillColor=none;strokeColor=none;html=1;"

    n = len(columns)
    spine_end_x = x0 + (n + 1) * span
    cells.append(_cell("sp_l", "", invisible, x0, mid_y, 1, 1))
    cells.append(_cell("head", "M365 Roadmap →", _HEADER_STYLE, spine_end_x, mid_y - 26, 160, 52))
    cells.append(_edge("spine", "sp_l", "head", spine_style))

    for qi, col in enumerate(columns):
        qx = x0 + (qi + 1) * span
        up = qi % 2 == 0
        # Anchor on the spine where this bone meets it.
        anchor = f"sp{qi}"
        cells.append(_cell(anchor, "", invisible, qx, mid_y, 1, 1))

        # level 0 = quarter label, levels 1..n = feature twigs (chained outward).
        entries: list[tuple[str, str, str]] = [(f"q{qi}", _esc(col), qlabel_style)]
        for k, s in enumerate(grid.get(col, [])):
            fill, stroke = _DEC_HEX.get(s.decision, ("#eeeeee", "#888888"))
            style = (
                f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                "align=left;verticalAlign=top;spacing=4;"
            )
            title = s.title if len(s.title) <= 58 else s.title[:57] + "…"
            slip = " ⚠" if s.slipped else ""
            svc = services_for(s.products)
            sub = svc[0] if svc else ""
            value = f"{_esc(title)}{slip}&#10;&lt;i&gt;{_esc(sub)}&lt;/i&gt;"
            entries.append((f"f{qi}_{k}", value, style))

        prev = anchor
        for level, (cid, value, style) in enumerate(entries):
            bx = qx - 70 - level * dx
            by = mid_y - first - level * step_y - h if up else mid_y + first + level * step_y
            cells.append(_cell(cid, value, style, bx, by, w, h))
            cells.append(_edge(f"e_{cid}", prev, cid, bone_style))
            prev = cid

    cells.append(_cell("title", "M365 Roadmap (Fischgräten)", _HEADER_STYLE, x0, 16, 320, 30))
    return _wrap("".join(cells))
