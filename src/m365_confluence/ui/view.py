"""Shared module view contract.

This renders the M365 review workspace as a sidebar-less, responsive page that
looks like the Weekly platform (via the vendored design-system) but carries no
host chrome. Two hosts render it:

* the m365_confluence standalone app (FastAPI ``ui/app.py``), and
* the Weekly platform, which mounts the same bundle in its main-view iframe.

The host injects ``asset_base`` (where the static bundle is served) and
``api_base`` (where this module's JSON API lives), so the identical view works
in both places. Keeping the markup here — next to the module's static assets —
is what lets the module stay standalone while the host merely embeds it.
"""

from __future__ import annotations

import importlib.resources as resources
from pathlib import Path

#: Filesystem dir of the bundled static assets (design-system + module).
STATIC_DIR: Path = Path(str(resources.files("m365_confluence.ui"))) / "static"

_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>M365 Review</title>
<link rel="stylesheet" href="{asset_base}/design-system/tokens.css">
<link rel="stylesheet" href="{asset_base}/design-system/base.css">
<link rel="stylesheet" href="{asset_base}/design-system/components.css">
<link rel="stylesheet" href="{asset_base}/design-system/shell.css">
<link rel="stylesheet" href="{asset_base}/module/m365.css">
</head>
<body>
<div class="module-shell">
  <header class="module-header">
    <h1>M365 Katalog</h1>
    <span id="status" class="module-status"></span>
    <span class="grow"></span>
    <a class="bs" href="debug" target="_blank" rel="noopener">Debug</a>
    <label class="ds-check"><input type="checkbox" id="hideign" onchange="M365.render()"> Ignorierte ausblenden</label>
    <label class="ds-check"><input type="checkbox" id="dry"> Dry-run</label>
    <button class="bs" onclick="M365.save()">Speichern</button>
    <button class="bp" onclick="M365.publish()">Veröffentlichen</button>
  </header>

  <div class="m365-steps">
    <span><b>1.</b> Sync (1× alle Daten)</span>
    <span><b>2.</b> Filtern nach Service/Produkt &amp; <b>auswählen</b></span>
    <span><b>3.</b> Auswahl mit KI anreichern</span>
    <span><b>4.</b> Bearbeiten, Speichern, Veröffentlichen</span>
  </div>

  <div class="module-bar">
    <div class="genbar" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;width:100%">
      <span class="flabel">Daten:</span>
      <select id="g_source"><option value="both">Beide</option><option value="roadmap">Roadmap</option><option value="message-center">Message Center</option></select>
      <label class="gopt">Seit (Tage) <input type="number" id="g_since" min="1" style="width:64px" placeholder="alle"></label>
      <button class="bp" onclick="M365.sync()">Sync (Daten laden)</button>
      <span id="syncinfo" class="meta"></span>
      <div style="flex-basis:100%;height:0"></div>
      <span class="flabel">Auswahl:</span>
      <button class="bs" onclick="M365.selectAllVisible(true)">Sichtbare wählen</button>
      <button class="bs" onclick="M365.selectAllVisible(false)">Auswahl leeren</button>
      <span id="selinfo" class="meta">0 ausgewählt</span>
      <button class="bp" onclick="M365.enrich()">Auswahl anreichern (KI)</button>
      <label class="gchk"><input type="checkbox" id="g_force"> neu anreichern</label>
      <span class="grow"></span>
      <label class="gchk"><input type="checkbox" id="f_changed" onchange="M365.render()"> nur Veränderungen</label>
      <label class="gchk"><input type="checkbox" id="f_enriched" onchange="M365.render()"> nur angereichert</label>
      <button class="bs" onclick="M365.saveSettings(true)">Einstellungen speichern</button>
    </div>
  </div>

  <div id="filters" class="filters"></div>
  <main id="list" class="module-main"></main>
</div>

<script>window.__M365__ = {{ apiBase: "{api_base}" }};</script>
<script src="{asset_base}/module/m365.js"></script>
</body>
</html>
"""


def render_module_html(*, asset_base: str = "/m365-assets", api_base: str = "/api") -> str:
    """Render the standalone-capable module page.

    Args:
        asset_base: URL prefix under which the host serves this module's static
            bundle (the dir containing ``design-system/`` and ``module/``).
        api_base: URL prefix for this module's JSON API endpoints.
    """
    return _PAGE.format(asset_base=asset_base.rstrip("/"), api_base=api_base.rstrip("/"))


def _esc(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _short(value: str | None) -> str:
    """Trim an ISO timestamp to minute precision for the debug table."""
    if not value:
        return "—"
    return _esc(value[:16].replace("T", " "))


def _yesno(flag: bool) -> str:
    return "✓" if flag else "—"


_DEBUG_PAGE = """<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>M365 Debug</title>
<style>
 body{{font:13px/1.4 system-ui,sans-serif;margin:0;padding:16px;color:#1a1a1a}}
 h1{{font-size:18px;margin:0 0 4px}}
 .meta{{color:#666;margin-bottom:12px}}
 table{{border-collapse:collapse;width:100%}}
 th,td{{border:1px solid #ddd;padding:4px 8px;text-align:left;vertical-align:top}}
 th{{background:#f4f4f6;position:sticky;top:0}}
 tr.removed{{opacity:.5}}
 tr.changed{{background:#fff7e6}}
 tr.new{{background:#eef9ee}}
 .pub{{color:#137333;font-weight:600}}
 .nopub{{color:#999}}
 code{{font-size:12px}}
 a{{color:#1a56db}}
</style>
</head>
<body>
<h1>M365 Debug — Katalog</h1>
<div class="meta">Letzter Sync: {synced_at} · {count} Einträge · <a href=".">zurück zum Review</a></div>
<table>
<thead><tr>
<th>Quelle / ID</th><th>Titel</th><th>Status</th><th>Quartal</th>
<th>Erstellt (MS)</th><th>Aktualisiert (MS)</th><th>Heruntergeladen</th><th>Letzter Sync</th>
<th>Diff</th><th>KI</th><th>Veröffentlicht</th><th>Confluence-Titel</th>
</tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>
"""


def render_debug_html(rows: list[dict], synced_at: str) -> str:
    """Server-rendered debug table: every item as delivered by MS + its lifecycle."""
    body_rows = []
    for r in rows:
        cls = "removed" if r.get("removed") else (r.get("change_status") or "")
        link = (
            f'<a href="{_esc(r["url"])}" target="_blank" rel="noopener">{_esc(r["source"])}</a>'
            if r.get("url")
            else _esc(r.get("source"))
        )
        ki = "veraltet" if r.get("stale") else _yesno(r.get("enriched"))
        if r.get("published"):
            pub = f'<span class="pub">{_short(r.get("published_at"))}</span>'
        else:
            pub = '<span class="nopub">—</span>'
        body_rows.append(
            "<tr class=\"{cls}\">"
            "<td>{src}<br><code>{id}</code></td><td>{title}</td><td>{status}</td><td>{q}</td>"
            "<td>{created}</td><td>{modified}</td><td>{first}</td><td>{last}</td>"
            "<td>{diff}</td><td>{ki}</td><td>{pub}</td><td>{ctitle}</td></tr>".format(
                cls=_esc(cls),
                src=link,
                id=_esc(r.get("id")),
                title=_esc(r.get("title")),
                status=_esc(r.get("status")) or "—",
                q=_esc(r.get("target_quarter")) or "—",
                created=_short(r.get("created")),
                modified=_short(r.get("last_modified")),
                first=_short(r.get("first_seen")),
                last=_short(r.get("last_seen")),
                diff=_esc(r.get("change_status")) or "—",
                ki=ki,
                pub=pub,
                ctitle=_esc(r.get("confluence_title")) or "—",
            )
        )
    return _DEBUG_PAGE.format(
        synced_at=_short(synced_at) if synced_at else "—",
        count=len(rows),
        rows="\n".join(body_rows) or '<tr><td colspan="12">Noch kein Sync ausgeführt.</td></tr>',
    )
