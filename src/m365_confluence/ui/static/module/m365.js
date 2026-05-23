/* M365 review module logic. Ported from the original inline INDEX_HTML script.
 *
 * The only host coupling is the API base + asset base, injected by whichever
 * host renders the shell (the m365_confluence standalone app uses "/api"; the
 * Weekly platform mounts the same bundle and passes "/api/m365"). Everything
 * else is host-agnostic so the view is identical standalone and embedded. */
(function () {
  const CFG = window.__M365__ || {};
  const API = (CFG.apiBase || "/api").replace(/\/$/, "");

  const DECISIONS = ["Activate", "Communicate", "Monitor", "Deactivate"];
  const AREAS = ["End User", "Admin / IT", "Security", "Compliance"];
  const CAT = { planForChange: "Plan for Change", preventOrFixIssue: "Prevent/Fix Issue", stayInformed: "Stay Informed" };
  let drafts = [];
  let activeQ = null, activeChan = null, activeProd = null, activeArea = null, activeSvc = null;
  let genProducts = new Set();

  const $ = (id) => document.getElementById(id);
  function setStatus(t) { $("status").textContent = t; }
  function esc(s) { return (s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;"); }
  function uniq(vals) { return [...new Set(vals)].sort(); }
  function quartersOf() { return uniq(drafts.map((d) => d.edit.target_quarter || "—")); }
  function channelsOf() { const c = []; drafts.forEach((d) => (d.source.release_phases || []).forEach((p) => c.push(p))); return uniq(c); }
  function productsOf() { const c = []; drafts.forEach((d) => (d.source.products || []).forEach((p) => c.push(p))); return uniq(c); }
  function servicesOf() { const c = []; drafts.forEach((d) => (d.source.services || []).forEach((s) => c.push(s))); return uniq(c); }
  function prodServiceMap() { const m = {}; drafts.forEach((d) => Object.assign(m, d.source.product_services || {})); return m; }
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
    if (activeQ && !activeQ.has(it.edit.target_quarter || "—")) return false;
    const svcs = it.source.services || [];
    if (activeSvc && svcs.length && !svcs.some((s) => activeSvc.has(s))) return false;
    const prods = it.source.products || [];
    if (activeProd && prods.length && !prods.some((p) => activeProd.has(p))) return false;
    const phases = it.source.release_phases || [];
    if (activeChan && phases.length && !phases.some((p) => activeChan.has(p))) return false;
    const areas = it.edit.areas || [];
    if (activeArea && areas.length && !areas.some((a) => activeArea.has(a))) return false;
    return true;
  }

  function field(label, val, onin, ml) {
    if (ml) return `<label>${label}</label><textarea oninput="${onin}">${esc(val)}</textarea>`;
    return `<label>${label}</label><input type="text" value="${esc(val)}" oninput="${onin}">`;
  }

  function render() {
    const hide = $("hideign").checked;
    const el = $("list");
    const visible = drafts.map((it, i) => [it, i]).filter(([it]) => !(hide && it.ignored) && passesFilters(it));
    if (!visible.length) {
      el.innerHTML = '<div class="module-empty">Keine Einträge (Filter prüfen). Sonst erst Entwürfe erzeugen: <code>make review</code></div>';
      return;
    }
    el.innerHTML = visible.map(([it, i]) => {
      const e = it.edit, s = it.source;
      const opts = DECISIONS.map((o) => `<option ${o === e.decision ? "selected" : ""}>${o}</option>`).join("");
      const ct = s.change_type || "";
      const rel = relevance(s);
      const chips =
        (s.services || []).map((v) => `<span class="chip svc">${esc(v)}</span>`).join("") +
        (e.areas || []).map((a) => `<span class="chip area">${esc(a)}</span>`).join("") +
        (s.status ? `<span class="chip stage">Stufe: ${esc(s.status)}</span>` : "") +
        (ct ? `<span class="chip ${ct === "Neu" ? "new" : "upd"}">${esc(ct)}</span>` : "") +
        (rel ? `<span class="chip rel">Relevanz: ${esc(rel)}</span>` : "") +
        (s.release_phases || []).map((p) => `<span class="chip chan">${esc(p)}</span>`).join("") +
        (s.products || []).map((p) => `<span class="chip">${esc(p)}</span>`).join("") +
        (e.target_quarter ? `<span class="chip">${esc(e.target_quarter)}</span>` : "") +
        (e.cab_required ? '<span class="chip" style="background:#fde8e8;color:#b42318;border-color:transparent">CAB</span>' : "");
      const areaChecks = AREAS.map((a) => `<label class="check"><input type="checkbox" ${(e.areas || []).includes(a) ? "checked" : ""} onchange="M365.toggleItemArea(${i},'${a}')"> ${a}</label>`).join("");
      const ASSESS = [["data_protection_impact", "Datenschutz"], ["it_landscape_impact", "IT-Landschaft"], ["config_change_required", "Konfig anpassen"], ["kbv_change_required", "KBV/Anlage"]];
      const assessChecks = ASSESS.map(([k, lbl]) => `<label class="check"><input type="checkbox" ${e[k] ? "checked" : ""} onchange="M365.upd(${i},'${k}',this.checked)"> ${lbl}</label>`).join("");
      return `<div class="scard card ${it.ignored ? "ignored" : ""}" id="card${i}" style="padding:0">
        <div class="chead">
          <span class="num">${i + 1}</span>
          <div class="ctitle">
            <input type="text" value="${esc(e.confluence_title)}" oninput="M365.upd(${i},'confluence_title',this.value)">
            <div class="src">${esc(s.source)} · ${esc(s.id)}</div>
          </div>
          <span class="dec ${e.decision}">${esc(e.decision)}</span>
          <button class="ignbtn" onclick="M365.toggleIgnore(${i})">${it.ignored ? "Ignoriert ✓" : "Ignorieren"}</button>
        </div>
        <div class="cbody">
          <div class="chips">${chips}</div>
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
        </div>
      </div>`;
    }).join("");
  }

  function upd(i, k, v) { drafts[i].edit[k] = v; }
  function updTop(i, k, v) { drafts[i][k] = v; }
  function toggleItemArea(i, a) { const e = drafts[i].edit; e.areas = e.areas || []; const x = e.areas.indexOf(a); x >= 0 ? e.areas.splice(x, 1) : e.areas.push(a); render(); }
  function toggleIgnore(i) { drafts[i].ignored = !drafts[i].ignored; render(); }

  function populateQuarters(selected) {
    const now = new Date();
    let y = now.getFullYear(), q = Math.floor(now.getMonth() / 3) + 1;
    q -= 1; if (q < 1) { q = 4; y -= 1; }
    const opts = ['<option value="">— Alle —</option>'];
    const seen = new Set();
    for (let i = 0; i < 7; i++) {
      const label = "Q" + q + " " + y; seen.add(label);
      opts.push(`<option value="${label}">${label}</option>`);
      q += 1; if (q > 4) { q = 1; y += 1; }
    }
    if (selected && !seen.has(selected)) opts.splice(1, 0, `<option value="${selected}">${selected}</option>`);
    const sel = $("g_quarter");
    sel.innerHTML = opts.join("");
    sel.value = selected || "";
  }
  function renderProductChecks(all) {
    const names = [...new Set([...genProducts, ...(all || [])])].sort();
    const box = $("g_products_box");
    box.innerHTML = names.length
      ? names.map((n) => `<label class="fchk"><input type="checkbox" ${genProducts.has(n) ? "checked" : ""} onchange="M365.toggleGenProduct('${n.replace(/'/g, "")}')"> ${esc(n)}</label>`).join("")
      : '<span class="meta">— „Produkte laden" klicken, um zu wählen —</span>';
  }
  function toggleGenProduct(n) { genProducts.has(n) ? genProducts.delete(n) : genProducts.add(n); }

  function gatherSettings() {
    return {
      source: $("g_source").value,
      limit: parseInt($("g_limit").value) || null,
      quarter: $("g_quarter").value.trim(),
      products: [...genProducts],
      worldwide_only: $("g_ww").checked,
      new_rollouts_only: $("g_new").checked,
      major_only: $("g_major").checked,
      action_required: $("g_action").checked,
      force: $("g_force").checked,
    };
  }
  function applySettings(s) {
    if (!s || !Object.keys(s).length) return;
    if (s.source) $("g_source").value = s.source;
    if (s.limit) $("g_limit").value = s.limit;
    if (s.quarter != null) populateQuarters(s.quarter);
    if (typeof s.worldwide_only === "boolean") $("g_ww").checked = s.worldwide_only;
    if (typeof s.new_rollouts_only === "boolean") $("g_new").checked = s.new_rollouts_only;
    if (typeof s.major_only === "boolean") $("g_major").checked = s.major_only;
    if (typeof s.action_required === "boolean") $("g_action").checked = s.action_required;
    if (typeof s.force === "boolean") $("g_force").checked = s.force;
    genProducts = new Set(s.products || []);
  }
  async function saveSettings(notify) {
    await fetch(`${API}/settings`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(gatherSettings()) });
    if (notify) setStatus("Einstellungen gespeichert.");
  }
  async function generate() {
    const body = gatherSettings();
    await saveSettings(false);
    setStatus("Erzeuge Entwürfe via KI… (kann etwas dauern)");
    const r = await fetch(`${API}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    drafts = d.items || []; activeQ = activeChan = activeProd = activeArea = activeSvc = null; renderFilters(); render();
    setStatus(d.count + " Entwürfe erzeugt.");
  }
  async function loadProducts() {
    const source = $("g_source").value;
    setStatus("Lade Produkte…");
    const r = await fetch(`${API}/products?source=` + encodeURIComponent(source));
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    renderProductChecks((d.products || []).map((p) => p.name));
    setStatus((d.products || []).length + " Produkte geladen.");
  }
  async function save() {
    setStatus("Speichere…");
    await fetch(`${API}/drafts`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items: drafts }) });
    const ign = drafts.filter((d) => d.ignored).length;
    setStatus("Gespeichert (" + (drafts.length - ign) + " aktiv, " + ign + " ignoriert).");
  }
  async function publish() {
    await save();
    const dry = $("dry").checked;
    setStatus("Veröffentliche…");
    const r = await fetch(`${API}/publish`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ dry_run: dry }) });
    const d = await r.json();
    if (d.error) { setStatus("Fehler: " + d.error); return; }
    setStatus(`Fertig: ${d.published} Seite(n), ${d.dashboards} Dashboard(s)${dry ? " (dry-run)" : ""}.`);
  }
  async function load() {
    populateQuarters("");
    try { const sr = await fetch(`${API}/settings`); applySettings(await sr.json()); } catch (e) { /* no saved settings yet */ }
    renderProductChecks([]);
    const r = await fetch(`${API}/drafts`);
    const d = await r.json();
    drafts = d.items || [];
    activeQ = activeChan = activeProd = activeArea = activeSvc = null;
    renderFilters(); render();
    setStatus(drafts.length + " Einträge");
  }

  // Expose the handlers referenced by inline on* attributes.
  window.M365 = { render, renderFilters, upd, updTop, toggleItemArea, toggleIgnore, toggleQ, toggleC, toggleP, toggleA, toggleS, toggleGenProduct, generate, loadProducts, saveSettings, save, publish };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", load);
  else load();
})();
