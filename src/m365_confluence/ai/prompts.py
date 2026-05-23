"""Prompt construction and response parsing for change processing.

The system prompt encodes *your standards* for how a change should be
written up. Adjust ``STANDARDS`` to match your house style — it is the single
place that defines tone, structure and required fields.
"""

from __future__ import annotations

import html
import json

from m365_confluence.confluence_macros import area_badges, cab_badge, decision_badge
from m365_confluence.models import ChangeItem, ProcessedItem

STANDARDS = """\
You are a Microsoft 365 change manager. You turn raw M365 Message Center posts
and roadmap entries into clear, consistent internal change notes.

House standards for every change note:
- Write in {language}. Use a neutral, professional tone.
- Be concise and factual. Never invent details that are not in the source.
- Always state who is affected and what (if anything) admins or users must do.
- Prefer concrete dates over vague phrasing when the source provides them.

This feeds an evergreen process that decides whether a feature must be
activated, deactivated, or communicated. Provide a clear recommendation:
- "Activate":    a feature/setting should be deliberately turned on.
- "Deactivate":  a feature/setting should be turned off or blocked.
- "Communicate": no toggle needed, but users/admins must be informed.
- "Monitor":     no action yet; keep watching (use when unclear).

Also determine the target quarter the change is expected to roll out in,
formatted as "Qn YYYY" (e.g. "Q3 2026"). A hint may be provided; correct it
if the source text clearly states another timeframe. Use "" if unknown.

Return ONLY a single, valid JSON object (no markdown fences, no commentary)
with exactly these keys:
  "title":              string  - a short, descriptive note title
  "summary":            string  - 2-4 sentence plain-language summary
  "impact":             string  - who/what is affected and how
  "audience":           string  - one of: "Admins", "End users", "Both"
  "recommended_action": string  - what the reader should do; "" if nothing
  "action_items":       string[] - concrete, actionable steps (may be empty)
  "target_quarter":     string  - "Qn YYYY" or "" if unknown
  "decision":           string  - one of: "Activate", "Deactivate", "Communicate", "Monitor"
  "decision_rationale": string  - one sentence explaining the decision
  "cab_required":       boolean - true if the Change Advisory Board (CAB) should review this
  "cab_recommendation": string  - one sentence for the CAB: what to advise; "" if not relevant
  "areas":              string[] - one or more affected areas, each EXACTLY one of:
                                   "End User", "Admin / IT", "Security", "Compliance"
  "data_protection_impact": boolean - true if it affects data/information protection (privacy)
  "it_landscape_impact":    boolean - true if it affects the general IT landscape
  "config_change_required": boolean - true if a platform configuration change is needed
  "kbv_change_required":    boolean - true if the works agreement (KBV) or an annex must change

JSON rules (strict):
- Output must parse as JSON (RFC 8259). Escape every double quote inside a
  string value as \\". Do not use single quotes for JSON.
- Do not put raw line breaks inside string values; keep each value on one line.
- No trailing commas. No text before the opening {{ or after the closing }}.

Example shape (values are illustrative only):
{{"title":"...","summary":"...","impact":"...","audience":"Admins",\
"recommended_action":"...","action_items":["...","..."],\
"target_quarter":"Q3 2026","decision":"Communicate","decision_rationale":"...",\
"cab_required":false,"cab_recommendation":"...","areas":["Admin / IT","Security"],\
"data_protection_impact":false,"it_landscape_impact":true,\
"config_change_required":false,"kbv_change_required":false}}
"""

_USER_TEMPLATE = """\
Process the following M365 change into an internal change note.

Source: {source}
Reference ID: {id}
Status: {status}
Category: {category}
Products: {products}
Tags: {tags}
Last modified: {last_modified}
Act by: {act_by}
Detected target quarter (hint): {quarter_hint}
Source URL: {url}

--- RAW CONTENT START ---
{body}
--- RAW CONTENT END ---
"""


def build_system_prompt(language: str, org_context: str = "") -> str:
    prompt = STANDARDS.format(language=language)
    if org_context:
        prompt += (
            "\nOrganisation context (use it to tailor the decision and impact "
            "to this environment):\n" + org_context + "\n"
        )
    return prompt


def build_user_prompt(item: ChangeItem, quarter_hint: str = "") -> str:
    return _USER_TEMPLATE.format(
        source=item.source,
        id=item.id,
        status=item.status or "n/a",
        category=item.category or "n/a",
        products=", ".join(item.products) or "n/a",
        tags=", ".join(item.tags) or "n/a",
        last_modified=item.last_modified.isoformat() if item.last_modified else "n/a",
        act_by=item.act_by.isoformat() if item.act_by else "n/a",
        quarter_hint=quarter_hint or "unknown",
        url=item.url or "n/a",
        body=item.body[:12000],
    )


DECISIONS = ("Activate", "Deactivate", "Communicate", "Monitor")


def _normalize_decision(value: str) -> str:
    cleaned = (value or "").strip().lower()
    for option in DECISIONS:
        if cleaned == option.lower():
            return option
    return "Monitor"


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "1", "ja"}


AREAS = ("End User", "Admin / IT", "Security", "Compliance")
_AREA_SYNONYMS = {
    "end user": "End User",
    "enduser": "End User",
    "endbenutzer": "End User",
    "user": "End User",
    "users": "End User",
    "admin": "Admin / IT",
    "admin / it": "Admin / IT",
    "admin/it": "Admin / IT",
    "it": "Admin / IT",
    "administration": "Admin / IT",
    "security": "Security",
    "sicherheit": "Security",
    "compliance": "Compliance",
    "governance": "Compliance",
}


def normalize_areas(values: object) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for v in values:
        key = str(v).strip().lower()
        name = _AREA_SYNONYMS.get(key) or next((a for a in AREAS if a.lower() == key), None)
        if name and name not in out:
            out.append(name)
    return out


def parse_response(raw: str, item: ChangeItem) -> ProcessedItem:
    data = _load_json(raw)
    title = (data.get("title") or item.title).strip()
    action_items = [str(a).strip() for a in data.get("action_items", []) if str(a).strip()]
    processed = ProcessedItem(
        source_item=item,
        summary=str(data.get("summary", "")).strip(),
        impact=str(data.get("impact", "")).strip(),
        audience=str(data.get("audience", "")).strip(),
        recommended_action=str(data.get("recommended_action", "")).strip(),
        action_items=action_items,
        target_quarter=str(data.get("target_quarter", "")).strip(),
        decision=_normalize_decision(str(data.get("decision", ""))),
        decision_rationale=str(data.get("decision_rationale", "")).strip(),
        cab_required=_as_bool(data.get("cab_required")),
        cab_recommendation=str(data.get("cab_recommendation", "")).strip(),
        areas=normalize_areas(data.get("areas")),
        data_protection_impact=_as_bool(data.get("data_protection_impact")),
        it_landscape_impact=_as_bool(data.get("it_landscape_impact")),
        config_change_required=_as_bool(data.get("config_change_required")),
        kbv_change_required=_as_bool(data.get("kbv_change_required")),
        confluence_title=title,
    )
    processed.confluence_body = render_storage(processed)
    return processed


def _load_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text.removeprefix("json").strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    # strict=False tolerates literal control characters (e.g. newlines) in strings.
    return json.loads(text, strict=False)


def render_storage(item: ProcessedItem) -> str:
    """Render a Confluence storage-format (XHTML) body following house standards."""
    src = item.source_item

    def esc(value: str) -> str:
        return html.escape(value or "")

    meta_rows = "".join(
        f"<tr><th>{esc(label)}</th><td>{esc(value)}</td></tr>"
        for label, value in (
            ("Source", src.source),
            ("Reference ID", src.id),
            ("Status", src.status),
            ("Target quarter", item.target_quarter),
            ("Products", ", ".join(src.products)),
            ("Audience", item.audience),
            ("Act by", src.act_by.date().isoformat() if src.act_by else ""),
        )
        if value
    )

    slip_banner = ""
    if item.slipped:
        slip_banner = (
            '<ac:structured-macro ac:name="warning"><ac:rich-text-body><p>'
            f"Verzug erkannt: Ziel verschoben von {esc(item.previous_quarter)} "
            f"auf {esc(item.target_quarter)}."
            "</p></ac:rich-text-body></ac:structured-macro>"
        )

    decision = ""
    if item.decision:
        rationale = f" {esc(item.decision_rationale)}" if item.decision_rationale else ""
        decision = f"<h2>Decision</h2><p>{decision_badge(item.decision)}{rationale}</p>"

    rec = f" {esc(item.cab_recommendation)}" if item.cab_recommendation else ""
    cab = f"<h2>CAB-Empfehlung</h2><p>{cab_badge(item.cab_required)}{rec}</p>"

    area = f"<h2>Bereich</h2><p>{area_badges(item.areas)}</p>" if item.areas else ""

    security_relevant = "Security" in item.areas

    def _yesno(value: bool) -> str:
        return "<strong>Ja</strong>" if value else "Nein"

    assessment_rows = "".join(
        f"<li>{label}: {_yesno(value)}</li>"
        for label, value in (
            ("Auswirkung auf Daten-/Informationsschutz", item.data_protection_impact),
            ("Auswirkung auf allgemeine IT-Landschaft", item.it_landscape_impact),
            ("Konfiguration der Plattform anpassen", item.config_change_required),
            ("KBV / Anlage anpassen", item.kbv_change_required),
        )
    )
    notes = ""
    if item.data_protection_impact:
        notes += "<p>→ ISB und/oder DSB zum monatlichen Treffen einladen.</p>"
    if security_relevant:
        notes += "<p>→ Security-relevant: erneute Risikobewertung des Services notwendig.</p>"
    assessment = f"<h2>Bewertung</h2><ul>{assessment_rows}</ul>{notes}"

    actions = ""
    if item.action_items:
        lis = "".join(f"<li>{esc(a)}</li>" for a in item.action_items)
        actions = f"<h2>Action items</h2><ul>{lis}</ul>"

    recommended = ""
    if item.recommended_action:
        recommended = f"<h2>Recommended action</h2><p>{esc(item.recommended_action)}</p>"

    link = f'<p><a href="{esc(src.url)}">Original source</a></p>' if src.url else ""

    return (
        f"{slip_banner}"
        f"<table><tbody>{meta_rows}</tbody></table>"
        f"<h2>Summary</h2><p>{esc(item.summary)}</p>"
        f"<h2>Impact</h2><p>{esc(item.impact)}</p>"
        f"{area}"
        f"{decision}"
        f"{cab}"
        f"{assessment}"
        f"{recommended}"
        f"{actions}"
        f"{link}"
    )
