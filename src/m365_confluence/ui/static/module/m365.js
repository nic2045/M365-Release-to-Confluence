/* M365 catalog module logic.
 *
 * Two-stage workflow:
 *   A) Sync  — fetch all items once (no LLM), labelled deterministically.
 *   B) Enrich — run the LLM only for the items the user selects; cached.
 * Everything between is local: filter by service/product, pick, then publish.
 *
 * The only host coupling is the API base, injected by whichever host renders
 * the shell (standalone uses "/api"; the Weekly platform passes "/api/m365"). */
(function () {
  const CFG = window.__M365__ || {};
  const API = (CFG.apiBase || "/api").replace(/\/$/, "");

  const DECISIONS = ["Activate", "Communicate", "Monitor", "Deactivate"];
  const AREAS = ["End User", "Admin / IT", "Security", "Compliance"];
  const CAT = { planForChange: "Plan for Change", preventOrFixIssue: "Prevent/Fix Issue", stayInformed: "Stay Informed" };
  const DIFF = { new: "Neu", changed: "Geändert", removed: "Entfernt", unchanged: "" };
  let items = [];
  let activeQ = null, activeChan = null, activeProd = null, activeArea = null, activeSvc = null;
  const selected = new Set();

  const $ = (id) => document.getElementById(id);
  function setStatus(t) { $("status").textContent = t; }
  function esc(s) { return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  function uniq(vals) { return [...new Set(vals)].sort(); }
  function quarterOf(it) { return (it.edit && it.edit.target_quarter) || (it.source && it.source.target_quarter) || "—"; }
  function areasOf(it) { return (it.edit && it.edit.areas) || []; }
  function stripHtml(s) { return (s || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(); }

  function quartersOf() { return uniq(items.map(quarterOf)); }
  function channelsOf() { const c = []; items.forEach((d) => (d.source.release_phases || []).forEach((p) => c.push(p))); return uniq(c); }
  function productsOf() { const c = []; items.forEach((d) => (d.source.products || []).forEach((p) => c.push(p))); return uniq(c); }
  function servicesOf() { const c = []; items.forEach((d) => (d.source.services || []).forEach((s) => c.push(s))); return uniq(c); }
  function prodServiceMap() { const m = {}; items.forEach((d) => Object.assign(m, d.source.product_services || {})); return m; }
  function productsForActiveServices() {
    const m = prodServiceMap();
    return productsOf().filter((p) => !activeSvc || activeSvc.has(m[p] || "Allgemein / M365 Admin"));
  }
  function relevance(s) {
    const parts = [];
    if (s.category && CAT[s.category]) parts.push(CAT[s.category]);
    else if (s.category && s.category !== "roadmap") parts.push(s.category);
    if (s.severity) parts.push(s.severity);
    if ((s.tags || []).includes("MajorChange")) parts.push("Major");
    return parts.join(" · ");
  }
  function chk(set, val, fn) { return `<label class="fchk"><input type="checkbox" ${set.has(val) ? "checked" : ""} onchange="M365.${fn}('${val.replace(/'/g, "")}')"> ${esc(val)}</label>`; }

  function renderFilters() {
    const qs = quartersOf(), chs = channelsOf(), svcs = servicesOf();
    if (activeSvc === null) activeSvc = new Set(svcs);
    if (activeQ === null) activeQ = new Set(qs);
    if (activeChan === null) activeChan = new Set(chs);
    if (activeArea === null) activeArea = new Set(AREAS);
    const prs = productsForActiveServices();
    if (activeProd === null) activeProd = new Set(productsOf());
    const qhtml = qs.map((q) => chk(activeQ, q, "toggleQ")).join("");
    const ahtml = AREAS.map((a) => chk(activeArea, a, "toggleA")).join("");
    const shtml = svcs.length ? ('<span class="flabel">Service (1):</span>' + svcs.map((s) => chk(activeSvc, s, "toggleS")).join("")) : "";
    const m = prodServiceMap();
    let pgroups = "";
    svcs.filter((s) => activeSvc.has(s)).forEach((s) => {
      const ps = prs.filter((p) => (m[p] || "Allgemein / M365 Admin") === s);
      if (ps.length) pgroups += `<span class="flabel sub">${esc(s)}:</span>` + ps.map((p) => chk(activeProd, p, "toggleP")).join("");
    });
    const phtml = pgroups ? ('<span class="flabel">Produkt (2):</span>' + pgroups) : "";
    const chtml = chs.length ? ('<span class="flabel">Channel:</span>' + chs.map((c) => chk(activeChan, c, "toggleC")).join("")) : "";
    $("filters").innerHTML =
      `<div class="fgroup"><span class="flabel">Quartal:</span>${qhtml}</div>` +
      `<div class="fgroup"><span class="flabel">Bereich:</span>${ahtml}</div>` +
      `<div class="fgroup">${shtml}</div><div class="fgroup">${phtml}</div>` +
      `<div class="fgroup">${chtml}</div>`;
  }
  function flip(set, val) { set.has(val) ? set.delete(val) : set.add(val); render(); }
  function toggleQ(v) { flip(activeQ, v); }
  function toggleC(v) { flip(activeChan, v); }
  function toggleP(v) { flip(activeProd, v); }
  function toggleA(v) { flip(activeArea, v); }
  function toggleS(v) {
    activeSvc.has(v) ? activeSvc.delete(v) : activeSvc.add(v);
    const m = prodServiceMap();
    productsOf().forEach((p) => { if (!activeSvc.has(m[p] || "Allgemein / M365 Admin")) activeProd.delete(p); else activeProd.add(p); });
    renderFilters(); render();
  }

  function passesFilters(it) {
    if ($("f_changed").checked && !(it.change_status === "new" || it.change_status === "changed")) return false;
    if ($("f_enriched").checked && !it.enriched) return false;
    if (activeQ && !activeQ.has(quarterOf(it))) return false;
    const svcs = it.source.services || [];
    if (activeSvc && svcs.length && !svcs.some((s) => activeSvc.has(s))) return false;
    const prods = it.source.products || [];
    if (activeProd && prods.length && !prods.some((p) => activeProd.has(p))) return false;
    const phases = it.source.release_phases || [];
    if (activeChan && phases.length && !phases.some((p) => activeChan.has(p))) return false;
    const areas = areasOf(it);
    if (activeArea && areas.length && !areas.some((a) => activeArea.has(a))) return false;
    return true;
  }

  function field(label, val, onin, ml) {
    if (ml) return `<label>${label}</label><textarea oninput="${onin}">${esc(val)}</textarea>`;
    return `<label>${label}</label><input type="text" value="${esc(val)}" oninput="${onin}">`;
  }

  function visibleItems() {
    const hide = $("hideign").checked;
    return items.map((it, i) => [it, i]).filter(([it]) => !(hide && it.ignored) && passesFilters(it));
  }

  function updateSelInfo() { $("selinfo").textContent = selected.size + " ausgewählt"; }

  function render() {
    updateSelInfo();
    const el = $("list");
    const visible = visibleItems();
    if (!visible.length) {
      el.innerHTML = items.length
        ? '<div class="module-empty">Keine Einträge — Filter prüfen.</div>'
        : '<div class="module-empty">Noch keine Daten. <button class="bp" onclick="M365.sync()">Sync starten</button></div>';
      return;
    }
    el.innerHTML = visible.map(([it, i]) => renderCard(it, i)).join("");
  }

  function renderCard(it, i) {
    const e = it.edit || {}, s = it.source;
    const diff = DIFF[it.change_status] || "";
    const ct = s.change_type || "";
    const rel = relevance(s);
    const q = quarterOf(it);
    const chips =
      (s.services || []).map((v) => `<span class="chip svc">${esc(v)}</span>`).join("") +
      (areasOf(it)).map((a) => `<span class="chip area">${esc(a)}</span>`).join("") +
      (s.status ? `<span class="chip stage">Stufe: ${esc(s.status)}</span>` : "") +
      (diff ? `<span class="chip ${it.change_status === "new" ? "new" : "upd"}">${esc(diff)}</span>` : "") +
      (ct ? `<span class="chip ${ct === "Neu" ? "new" : "upd"}">${esc(ct)}</span>` : "") +
      (rel ? `<span class="chip rel">Relevanz: ${esc(rel)}</span>` : "") +
      (s.release_phases || []).map((p) => `<span class="chip chan">${esc(p)}</span>`).join("") +
      (s.products || []).map((p) => `<span class="chip">${esc(p)}</span>`).join("") +
      (q !== "—" ? `<span class="chip">${esc(q)}</span>` : "") +
      (it.published ? '<span class="chip" style="background:#e6f4ea;color:#137333;border-color:transparent">Veröffentlicht</span>' : "") +
      (e.cab_required ? '<span class="chip" style="background:#fde8e8;color:#b42318;border-color:transparent">CAB</span>' : "");

    const head = `<div class="chead">
        <label class="check" style="margin-right:6px"><input type="checkbox" ${selected.has(it.key) ? "checked" : ""} onchange="M365.toggleSelect('${it.key}')"></label>
        <span class="num">${i + 1}</span>
        <div class="ctitle">
          <input type="text" value="${esc(it.enriched ? e.confluence_title : s.title)}" ${it.enriched ? `oninput="M365.upd(${i},'confluence_title',this.value)"` : "disabled"}>
          <div class="src">${esc(s.source)} · ${esc(s.id)}${s.url ? ` · <a href="${esc(s.url)}" target="_blank" rel="noopener">MS</a>` : ""}</div>
        </div>
        ${it.enriched ? `<span class="dec ${e.decision}">${esc(e.decision)}</span>` : `<span class="chip">${it.stale ? "veraltet" : "nicht angereichert"}</span>`}
        <button class="ignbtn" onclick="M365.toggleIgnore(${i})">${it.ignored ? "Ignoriert ✓" : "Ignorieren"}</button>
      </div>`;

    let body;
    if (!it.enriched) {
      const preview = esc(stripHtml(s.body).slice(0, 400));
      body = `<div class="cbody">
          <div class="chips">${chips}</div>
          <div class="meta" style="margin:6px 0">${preview || "—"}${stripHtml(s.body).length > 400 ? "…" : ""}</div>
          <button class="bp" onclick="M365.enrichOne('${it.key}')">Diesen Eintrag anreichern (KI)</button>
        </div>`;
    } else {
      const opts = DECISIONS.map((o) => `<option ${o === e.decision ? "selected" : ""}>${o}</option>`).join("");
      const areaChecks = AREAS.map((a) => `<label class="check"><input type="checkbox" ${(e.areas || []).includes(a) ? "checked" : ""} onchange="M365.toggleItemArea(${i},'${a}')"> ${a}</label>`).join("");
      const ASSESS = [["data_protection_impact", "Datenschutz"], ["it_landscape_impact", "IT-Landschaft"], ["config_change_required", "Konfig anpassen"], ["kbv_change_required", "KBV/Anlage"]];
      const assessChecks = ASSESS.map(([k, lbl]) => `<label class="check"><input type="checkbox" ${e[k] ? "checked" : ""} onchange="M365.upd(${i},'${k}',this.checked)"> ${lbl}</label>`).join("");
      body = `<div class="cbody">
          <div class="chips">${chips}</div>
          ${it.stale ? '<div class="meta" style="color:#b42318;margin:4px 0">Quelle hat sich seit der Anreicherung geändert — ggf. neu anreichern.</div>' : ""}
          <label>Bereich</label>
          <div class="row" style="gap:18px">${areaChecks}</div>
          <label>Bewertung</label>
          <div class="row" style="gap:18px">${assessChecks}</div>
          <div class="row">
            <div>${field("Ziel-Quartal", e.target_quarter, `M365.upd(${i},'target_quarter',this.value)`)}</div>
            <div><label>Entscheidung</label><select onchange="M365.upd(${i},'decision',this.value);M365.render()">${opts}</select></div>
            <div><label class="check"><input type="checkbox" ${e.cab_required ? "checked" : ""} onchange="M365.upd(${i},'cab_required',this.checked);M365.render()"> CAB erforderlich</label></div>
            <div><label class="check"><input type="checkbox" ${it.make_page ? "checked" : ""} onchange="M365.updTop(${i},'make_page',this.checked)"> Eigene Seite anlegen</label></div>
          </div>
          ${field("CAB-Empfehlung", e.cab_recommendation, `M365.upd(${i},'cab_recommendation',this.value)`)}
          ${field("Zusammenfassung", e.summary, `M365.upd(${i},'summary',this.value)`, true)}
          ${field("Impact", e.impact, `M365.upd(${i},'impact',this.value)`, true)}
          ${field("Empfohlene Aktion", e.recommended_action, `M365.upd(${i},'recommended_action',this.value)`)}
        </div>`;
    }
    return `<div class="scard card ${it.ignored ? "ignored" : ""}" id="card${i}" style="padding:0">${head}${body}</div>`;
  }

  function upd(i, k, v) { if (items[i].edit) items[i].edit[k] = v; }
  function updTop(i, k, v) { items[i][k] = v; }
  function toggleItemArea(i, a) { const e = items[i].edit; if (!e) return; e.areas = e.areas || []; const x = e.areas.indexOf(a); x >= 0 ? e.areas.splice(x, 1) : e.areas.push(a); render(); }
  function toggleIgnore(i) { items[i].ignored = !items[i].ignored; render(); }
  function toggleSelect(key) { selected.has(key) ? selected.delete(key) : selected.add(key); updateSelInfo(); }
  function selectAllVisible(on) {
    if (!on) { selected.clear(); } else { visibleItems().forEach(([it]) => selected.add(it.key)); }
    render();
  }

  function gatherSettings() {
    return {
      source: $("g_source").value,
      since_days: parseInt($("g_since").value) || null,
      force: $("g_force").checked,
      only_changed: $("f_changed").checked,
      only_enriched: $("f_enriched").checked,
    };
  }
  function applySettings(s) {
    if (!s || !Object.keys(s).length) return;
    if (s.source) $("g_source").value = s.source;
    if (s.since_days) $("g_since").value = s.since_days;
    if (typeof s.force === "boolean") $("g_force").checked = s.force;
    if (typeof s.only_changed === "boolean") $("f_changed").checked = s.only_changed;
    if (typeof s.only_enriched === "boolean") $("f_enriched").checked = s.only_enriched;
  }
  async function saveSettings(notify) {
    await fetch(`${API}/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gatherSettings()) });
    if (notify) setStatus("Einstellungen gespeichert.");
  }

  function adopt(list) {
    items = list || [];
    // Drop selections that no longer exist.
    const keys = new Set(items.map((d) => d.key));
    [...selected].forEach((k) => { if (!keys.has(k)) selected.delete(k); });
    activeQ = activeChan = activeProd = activeArea = activeSvc = null;
    renderFilters(); render();
  }

  async function sync() {
    await saveSettings(false);
    const body = { source: $("g_source").value, since_days: parseInt($("g_since").value) || null };
    setStatus("Sync läuft… (alle Daten von Microsoft)");
    const r = await fetch(`${API}/sync`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    adopt(d.items);
    $("syncinfo").textContent = `${d.total} gesamt · ${d.new} neu · ${d.changed} geändert · ${d.removed} entfernt`;
    setStatus(`Sync fertig: ${d.total} Einträge.`);
  }

  async function enrichKeys(keys) {
    if (!keys.length) { setStatus("Nichts ausgewählt."); return; }
    setStatus(`Reichere ${keys.length} Eintrag/Einträge mit KI an… (kostet Tokens)`);
    const r = await fetch(`${API}/enrich`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keys, force: $("g_force").checked }) });
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    adopt(d.items);
    const errs = (d.errors || []).length ? `, ${d.errors.length} Fehler` : "";
    setStatus(`Angereichert: ${d.enriched} (${d.skipped} übersprungen${errs}).`);
  }
  function enrich() { enrichKeys([...selected]); }
  function enrichOne(key) { enrichKeys([key]); }

  async function save() {
    setStatus("Speichere…");
    const payload = items.map((d) => ({ key: d.key, ignored: !!d.ignored, make_page: !!d.make_page, edit: d.edit }));
    await fetch(`${API}/catalog`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: payload }) });
    const ign = items.filter((d) => d.ignored).length;
    setStatus("Gespeichert (" + (items.length - ign) + " aktiv, " + ign + " ignoriert).");
  }

  async function publish() {
    await save();
    const dry = $("dry").checked;
    setStatus("Veröffentliche angereicherte Einträge…");
    const r = await fetch(`${API}/catalog/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dry_run: dry }) });
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    setStatus(`Fertig: ${d.published} Seite(n), ${d.dashboards} Dashboard(s)${dry ? " (dry-run)" : ""}.`);
    if (!dry) { const cr = await fetch(`${API}/catalog`); adopt((await cr.json()).items); }
  }

  async function load() {
    try { const sr = await fetch(`${API}/settings`); applySettings(await sr.json()); } catch (e) { /* none yet */ }
    const r = await fetch(`${API}/catalog`);
    const d = await r.json();
    adopt(d.items);
    if (d.synced_at) $("syncinfo").textContent = "letzter Sync: " + d.synced_at.slice(0, 16).replace("T", " ");
    setStatus(items.length + " Einträge" + (items.length ? "" : " — Sync starten"));
  }

  window.M365 = {
    render, renderFilters, upd, updTop, toggleItemArea, toggleIgnore,
    toggleQ, toggleC, toggleP, toggleA, toggleS,
    toggleSelect, selectAllVisible, sync, enrich, enrichOne, saveSettings, save, publish,
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
