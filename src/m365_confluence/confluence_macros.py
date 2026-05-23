"""Confluence storage-format macro helpers (status badges, panels)."""

from __future__ import annotations

import html

# Decision -> Confluence status macro colour (Green/Yellow/Red/Blue/Grey/Purple).
DECISION_COLOURS = {
    "Activate": "Green",
    "Communicate": "Blue",
    "Monitor": "Yellow",
    "Deactivate": "Red",
}


def status_macro(colour: str, title: str) -> str:
    safe = html.escape(title or "")
    return (
        '<ac:structured-macro ac:name="status">'
        f'<ac:parameter ac:name="colour">{colour}</ac:parameter>'
        f'<ac:parameter ac:name="title">{safe}</ac:parameter>'
        "</ac:structured-macro>"
    )


def decision_badge(decision: str) -> str:
    if not decision:
        return ""
    colour = DECISION_COLOURS.get(decision, "Grey")
    return status_macro(colour, decision)


def slip_badge(label: str = "verschoben") -> str:
    return status_macro("Red", label)


def cab_badge(required: bool) -> str:
    return status_macro("Red", "CAB: Ja") if required else status_macro("Green", "CAB: Nein")


AREA_COLOURS = {
    "End User": "Blue",
    "Admin / IT": "Purple",
    "Security": "Red",
    "Compliance": "Green",
}


def area_badges(areas: list[str]) -> str:
    return "".join(status_macro(AREA_COLOURS.get(a, "Grey"), a) for a in areas)
