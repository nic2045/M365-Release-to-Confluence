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
    <h1>M365 Review &amp; Edit</h1>
    <span id="status" class="module-status"></span>
    <span class="grow"></span>
    <label class="ds-check"><input type="checkbox" id="hideign" onchange="M365.render()"> Ignorierte ausblenden</label>
    <label class="ds-check"><input type="checkbox" id="dry"> Dry-run</label>
    <button class="bs" onclick="M365.save()">Speichern</button>
    <button class="bp" onclick="M365.publish()">Veröffentlichen</button>
  </header>

  <div class="m365-steps">
    <span><b>1.</b> Durchgehen</span>
    <span><b>2.</b> Bearbeiten oder <b>Ignorieren</b></span>
    <span><b>3.</b> Speichern</span>
    <span><b>4.</b> Veröffentlichen (ignorierte werden ausgelassen)</span>
  </div>

  <div class="module-bar">
    <div class="genbar" style="display:flex;gap:12px;flex-wrap:wrap;align-items:center;width:100%">
      <span class="flabel">Entwürfe erzeugen:</span>
      <select id="g_source"><option value="roadmap">Roadmap</option><option value="message-center">Message Center</option><option value="both">Beide</option></select>
      <label class="gopt">Limit <input type="number" id="g_limit" min="1" style="width:64px" value="20"></label>
      <label class="gopt">Quartal <select id="g_quarter"></select></label>
      <label class="gchk"><input type="checkbox" id="g_ww" checked> Worldwide</label>
      <label class="gchk"><input type="checkbox" id="g_new" checked> nur neue Rollouts</label>
      <label class="gchk"><input type="checkbox" id="g_major"> nur Major</label>
      <label class="gchk"><input type="checkbox" id="g_action"> Action req.</label>
      <label class="gchk"><input type="checkbox" id="g_force"> Force</label>
      <button class="bp" onclick="M365.generate()">Erzeugen (KI)</button>
      <button class="bs" onclick="M365.loadProducts()">Produkte laden</button>
      <button class="bs" onclick="M365.saveSettings(true)">Einstellungen speichern</button>
      <div style="flex-basis:100%;height:0"></div>
      <span class="flabel">Produkte:</span>
      <div id="g_products_box" class="pbox"></div>
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
