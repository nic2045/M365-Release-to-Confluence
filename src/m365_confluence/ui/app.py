"""FastAPI app to review/edit drafts (review.json) and publish to Confluence.

Run with: m365-to-confluence-ui --review-file review.json
Requires the 'ui' extra: pip install -e ".[ui]"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from m365_confluence.review import load_drafts, save_drafts

INDEX_HTML = """<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>M365 Review</title>
<style>
 :root{--blue:#0a84ff;--ink:#1d2433;--muted:#6b7688;--line:#e6e8ec;--bg:#f5f7fa}
 *{box-sizing:border-box}
 body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--ink);line-height:1.45}
 header{position:sticky;top:0;z-index:10;background:var(--blue);color:#fff;padding:14px 24px;display:flex;align-items:center;gap:14px;box-shadow:0 2px 8px rgba(0,0,0,.12)}
 header h1{font-size:17px;margin:0;font-weight:650}
 header .grow{flex:1}
 button{background:#fff;color:var(--blue);border:0;border-radius:8px;padding:9px 16px;font-weight:600;cursor:pointer;font-size:14px}
 button.ghost{background:rgba(255,255,255,.18);color:#fff}
 button:hover{opacity:.92}
 .toggle{color:#fff;font-weight:500;font-size:13px;display:flex;align-items:center;gap:6px;cursor:pointer}
 .steps{max-width:980px;margin:18px auto 4px;padding:0 24px;color:var(--muted);font-size:13px;display:flex;gap:18px;flex-wrap:wrap}
 .steps b{color:var(--ink)}
 main{padding:12px 24px 60px;max-width:980px;margin:0 auto}
 .card{background:#fff;border:1px solid var(--line);border-left:5px solid var(--blue);border-radius:12px;padding:0;margin:18px 0;box-shadow:0 1px 3px rgba(16,24,40,.06);overflow:hidden;transition:opacity .15s}
 .card.ignored{opacity:.5;border-left-color:#b0b7c3}
 .chead{display:flex;align-items:center;gap:10px;padding:12px 18px;background:#fafbfc;border-bottom:1px solid var(--line)}
 .num{flex:none;width:26px;height:26px;border-radius:50%;background:var(--blue);color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center}
 .card.ignored .num{background:#b0b7c3}
 .ctitle{flex:1;min-width:0}
 .ctitle input{width:100%;border:0;background:transparent;font-size:16px;font-weight:650;color:var(--ink);padding:2px 0}
 .ctitle input:focus{outline:0;border-bottom:2px solid var(--blue)}
 .src{font-size:11px;color:var(--muted);margin-top:2px}
 .cbody{padding:16px 18px}
 .chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
 .chip{background:#eef1f5;color:#4a5568;border-radius:20px;padding:2px 10px;font-size:11px;font-weight:600}
 .chip.stage{background:#e7f0ff;color:#0a5bd6}
 .chip.rel{background:#fff3e0;color:#b25e00}
 .chip.chan{background:#ece9fb;color:#5b3fc4}
 .chip.new{background:#e3fcef;color:#1f7a4d}
 .chip.upd{background:#fff8e1;color:#9a6b00}
 .chip.area{background:#e8eefc;color:#3b50b0}
 .chip.svc{background:#e0f2f1;color:#00695c;font-weight:700}
 .genbar{max-width:980px;margin:10px auto 0;padding:12px 16px;display:flex;gap:12px;flex-wrap:wrap;align-items:center;background:#fff;border:1px solid var(--line);border-radius:12px}
 .genbar select,.genbar input[type=text],.genbar input[type=number]{padding:6px 8px;border:1px solid var(--line);border-radius:8px;font:inherit}
 .gopt,.gchk{font-size:12px;color:var(--ink);display:inline-flex;align-items:center;gap:6px}
 .pbox{display:flex;gap:6px;flex-wrap:wrap;align-items:center;max-height:120px;overflow:auto;width:100%}
 .filters{max-width:980px;margin:6px auto 0;padding:10px 24px;display:flex;gap:18px;flex-wrap:wrap;align-items:center}
 .fgroup{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
 .flabel{font-size:11px;font-weight:700;text-transform:uppercase;color:var(--muted)}
 .fchk{font-size:12px;color:var(--ink);display:inline-flex;align-items:center;gap:4px;background:#fff;border:1px solid var(--line);border-radius:16px;padding:3px 10px;cursor:pointer}
 .row{display:flex;gap:16px;flex-wrap:wrap}
 .row>div{flex:1;min-width:200px}
 label{display:block;font-size:11px;font-weight:700;letter-spacing:.02em;text-transform:uppercase;color:var(--muted);margin:10px 0 3px}
 input[type=text],select,textarea{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}
 input[type=text]:focus,select:focus,textarea:focus{outline:0;border-color:var(--blue);box-shadow:0 0 0 3px rgba(10,132,255,.12)}
 textarea{min-height:62px;resize:vertical}
 .check{display:flex;align-items:center;gap:7px;font-size:13px;font-weight:500;color:var(--ink);margin-top:26px;text-transform:none;letter-spacing:0}
 .dec{display:inline-block;padding:3px 10px;border-radius:6px;font-size:12px;font-weight:700;color:#fff}
 .Activate{background:#1f9d55}.Communicate{background:#0a84ff}.Monitor{background:#d9a400}.Deactivate{background:#d64545}
 #status{font-size:13px;color:#fff;opacity:.95}
 .empty{text-align:center;color:var(--muted);margin-top:80px}
 .ignbtn{background:#eef1f5;color:#4a5568;border-radius:8px;padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer;border:0}
 .card.ignored .ignbtn{background:var(--blue);color:#fff}
</style></head>
<body>
<header>
  <h1>M365 Review &amp; Edit</h1>
  <span id="status"></span>
  <span class="grow"></span>
  <label class="toggle"><input type="checkbox" id="hideign" onchange="render()"> Ignorierte ausblenden</label>
  <label class="toggle"><input type="checkbox" id="dry"> Dry-run</label>
  <button class="ghost" onclick="save()">Speichern</button>
  <button onclick="publish()">Veröffentlichen</button>
</header>
<div class="steps">
  <span><b>1.</b> Durchgehen</span>
  <span><b>2.</b> Bearbeiten oder <b>Ignorieren</b></span>
  <span><b>3.</b> Speichern</span>
  <span><b>4.</b> Veröffentlichen (ignorierte werden ausgelassen)</span>
</div>
<div class="genbar">
  <span class="flabel">Entwürfe erzeugen:</span>
  <select id="g_source"><option value="roadmap">Roadmap</option><option value="message-center">Message Center</option><option value="both">Beide</option></select>
  <label class="gopt">Limit <input type="number" id="g_limit" min="1" style="width:64px" value="20"></label>
  <label class="gopt">Quartal <select id="g_quarter"></select></label>
  <label class="gchk"><input type="checkbox" id="g_ww" checked> Worldwide</label>
  <label class="gchk"><input type="checkbox" id="g_new" checked> nur neue Rollouts</label>
  <label class="gchk"><input type="checkbox" id="g_major"> nur Major</label>
  <label class="gchk"><input type="checkbox" id="g_action"> Action req.</label>
  <label class="gchk"><input type="checkbox" id="g_force"> Force</label>
  <button onclick="generate()">Erzeugen (KI)</button>
  <button class="ghost" style="color:#0a5bd6;background:#eef1f5" onclick="loadProducts()">Produkte laden</button>
  <button class="ghost" style="color:#0a5bd6;background:#eef1f5" onclick="saveSettings(true)">Einstellungen speichern</button>
  <div style="flex-basis:100%;height:0"></div>
  <span class="flabel">Produkte:</span>
  <div id="g_products_box" class="pbox"></div>
</div>
<div id="filters" class="filters"></div>
<main id="list"></main>
<script>
const DECISIONS=["Activate","Communicate","Monitor","Deactivate"];
const AREAS=["End User","Admin / IT","Security","Compliance"];
const CAT={planForChange:'Plan for Change',preventOrFixIssue:'Prevent/Fix Issue',stayInformed:'Stay Informed'};
let drafts=[];
let activeQ=null, activeChan=null, activeProd=null, activeArea=null, activeSvc=null;
function setStatus(t){document.getElementById('status').textContent=t;}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}
function uniq(vals){return [...new Set(vals)].sort();}
function quartersOf(){return uniq(drafts.map(d=>d.edit.target_quarter||'—'));}
function channelsOf(){const c=[];drafts.forEach(d=>(d.source.release_phases||[]).forEach(p=>c.push(p)));return uniq(c);}
function productsOf(){const c=[];drafts.forEach(d=>(d.source.products||[]).forEach(p=>c.push(p)));return uniq(c);}
function servicesOf(){const c=[];drafts.forEach(d=>(d.source.services||[]).forEach(s=>c.push(s)));return uniq(c);}
function prodServiceMap(){const m={};drafts.forEach(d=>Object.assign(m,d.source.product_services||{}));return m;}
// Level 2: only products whose service (level 1) is currently active.
function productsForActiveServices(){
  const m=prodServiceMap();
  return productsOf().filter(p=>!activeSvc||activeSvc.has(m[p]||'Allgemein / M365 Admin'));
}
function relevance(s){
  const parts=[];
  if(s.category&&CAT[s.category])parts.push(CAT[s.category]); else if(s.category&&s.category!=='roadmap')parts.push(s.category);
  if(s.severity)parts.push(s.severity);
  if((s.tags||[]).includes('MajorChange'))parts.push('Major');
  return parts.join(' · ');
}
function chk(set,val,fn){return `<label class="fchk"><input type="checkbox" ${set.has(val)?'checked':''} onchange="${fn}('${val.replace(/'/g,"")}')"> ${esc(val)}</label>`;}
function renderFilters(){
  const qs=quartersOf(), chs=channelsOf(), svcs=servicesOf();
  if(activeSvc===null)activeSvc=new Set(svcs);
  if(activeQ===null)activeQ=new Set(qs);
  if(activeChan===null)activeChan=new Set(chs);
  if(activeArea===null)activeArea=new Set(AREAS);
  const prs=productsForActiveServices();           // level 2 depends on level 1
  if(activeProd===null)activeProd=new Set(productsOf());
  const qhtml=qs.map(q=>chk(activeQ,q,"toggleQ")).join('');
  const ahtml=AREAS.map(a=>chk(activeArea,a,"toggleA")).join('');
  const shtml=svcs.length?('<span class="flabel">Service (1):</span>'+svcs.map(s=>chk(activeSvc,s,"toggleS")).join('')):'';
  const phtml=prs.length?('<span class="flabel">Produkt (2):</span>'+prs.map(p=>chk(activeProd,p,"toggleP")).join('')):'';
  const chtml=chs.length?('<span class="flabel">Channel:</span>'+chs.map(c=>chk(activeChan,c,"toggleC")).join('')):'';
  document.getElementById('filters').innerHTML=
    `<div class="fgroup"><span class="flabel">Quartal:</span>${qhtml}</div>`
    +`<div class="fgroup"><span class="flabel">Bereich:</span>${ahtml}</div>`
    +`<div class="fgroup">${shtml}</div><div class="fgroup">${phtml}</div>`
    +`<div class="fgroup">${chtml}</div>`;
}
function flip(set,val){set.has(val)?set.delete(val):set.add(val);render();}
function toggleQ(v){flip(activeQ,v);}
function toggleC(v){flip(activeChan,v);}
function toggleP(v){flip(activeProd,v);}
function toggleA(v){flip(activeArea,v);}
function toggleS(v){
  activeSvc.has(v)?activeSvc.delete(v):activeSvc.add(v);
  // keep product selection in sync: drop products whose service is now inactive
  const m=prodServiceMap();
  productsOf().forEach(p=>{ if(!activeSvc.has(m[p]||'Allgemein / M365 Admin')) activeProd.delete(p); else activeProd.add(p); });
  renderFilters();render();
}
async function load(){
  populateQuarters('');
  try{const sr=await fetch('/api/settings');applySettings(await sr.json());}catch(e){}
  renderProductChecks([]);
  const r=await fetch('/api/drafts');const d=await r.json();drafts=d.items||[];
  activeQ=null;activeChan=null;activeProd=null;activeArea=null;activeSvc=null;renderFilters();render();
  setStatus(drafts.length+' Einträge');
}
function field(label,val,onin,ml){
  if(ml)return `<label>${label}</label><textarea oninput="${onin}">${esc(val)}</textarea>`;
  return `<label>${label}</label><input type="text" value="${esc(val)}" oninput="${onin}">`;
}
function passesFilters(it){
  if(activeQ && !activeQ.has(it.edit.target_quarter||'—'))return false;
  const svcs=it.source.services||[];
  if(activeSvc && svcs.length && !svcs.some(s=>activeSvc.has(s)))return false;  // level 1
  const prods=it.source.products||[];
  if(activeProd && prods.length && !prods.some(p=>activeProd.has(p)))return false;  // level 2
  const phases=it.source.release_phases||[];
  if(activeChan && phases.length && !phases.some(p=>activeChan.has(p)))return false;
  const areas=it.edit.areas||[];
  if(activeArea && areas.length && !areas.some(a=>activeArea.has(a)))return false;
  return true;
}
function render(){
  const hide=document.getElementById('hideign').checked;
  const el=document.getElementById('list');
  const visible=drafts.map((it,i)=>[it,i]).filter(([it])=>!(hide&&it.ignored)&&passesFilters(it));
  if(!visible.length){el.innerHTML='<div class="empty">Keine Einträge (Filter prüfen). Sonst erst Entwürfe erzeugen:<br><code>make review</code></div>';return;}
  el.innerHTML=visible.map(([it,i])=>{
    const e=it.edit, s=it.source;
    const opts=DECISIONS.map(o=>`<option ${o===e.decision?'selected':''}>${o}</option>`).join('');
    const ct=s.change_type||'';
    const rel=relevance(s);
    const chips=
       (s.services||[]).map(v=>`<span class="chip svc">${esc(v)}</span>`).join('')
      +(e.areas||[]).map(a=>`<span class="chip area">${esc(a)}</span>`).join('')
      +(s.status?`<span class="chip stage">Stufe: ${esc(s.status)}</span>`:'')
      +(ct?`<span class="chip ${ct==='Neu'?'new':'upd'}">${esc(ct)}</span>`:'')
      +(rel?`<span class="chip rel">Relevanz: ${esc(rel)}</span>`:'')
      +(s.release_phases||[]).map(p=>`<span class="chip chan">${esc(p)}</span>`).join('')
      +(s.products||[]).map(p=>`<span class="chip">${esc(p)}</span>`).join('')
      +(e.target_quarter?`<span class="chip">${esc(e.target_quarter)}</span>`:'')
      +(e.cab_required?'<span class="chip" style="background:#fde8e8;color:#b42318">CAB</span>':'');
    const areaChecks=AREAS.map(a=>`<label class="check" style="margin-top:0"><input type="checkbox" ${(e.areas||[]).includes(a)?'checked':''} onchange="toggleItemArea(${i},'${a}')"> ${a}</label>`).join('');
    const ASSESS=[['data_protection_impact','Datenschutz'],['it_landscape_impact','IT-Landschaft'],['config_change_required','Konfig anpassen'],['kbv_change_required','KBV/Anlage']];
    const assessChecks=ASSESS.map(([k,lbl])=>`<label class="check" style="margin-top:0"><input type="checkbox" ${e[k]?'checked':''} onchange="upd(${i},'${k}',this.checked)"> ${lbl}</label>`).join('');
    return `<div class="card ${it.ignored?'ignored':''}" id="card${i}">
      <div class="chead">
        <span class="num">${i+1}</span>
        <div class="ctitle">
          <input type="text" value="${esc(e.confluence_title)}" oninput="upd(${i},'confluence_title',this.value)">
          <div class="src">${esc(s.source)} · ${esc(s.id)}</div>
        </div>
        <span class="dec ${e.decision}">${esc(e.decision)}</span>
        <button class="ignbtn" onclick="toggleIgnore(${i})">${it.ignored?'Ignoriert ✓':'Ignorieren'}</button>
      </div>
      <div class="cbody">
        <div class="chips">${chips}</div>
        <label>Bereich</label>
        <div class="row" style="gap:18px">${areaChecks}</div>
        <label>Bewertung</label>
        <div class="row" style="gap:18px">${assessChecks}</div>
        <div class="row">
          <div>${field('Ziel-Quartal',e.target_quarter,`upd(${i},'target_quarter',this.value)`)}</div>
          <div><label>Entscheidung</label><select onchange="upd(${i},'decision',this.value);render()">${opts}</select></div>
          <div><label class="check"><input type="checkbox" ${e.cab_required?'checked':''} onchange="upd(${i},'cab_required',this.checked);render()"> CAB erforderlich</label></div>
          <div><label class="check"><input type="checkbox" ${it.make_page?'checked':''} onchange="updTop(${i},'make_page',this.checked)"> Eigene Seite anlegen</label></div>
        </div>
        ${field('CAB-Empfehlung',e.cab_recommendation,`upd(${i},'cab_recommendation',this.value)`)}
        ${field('Zusammenfassung',e.summary,`upd(${i},'summary',this.value)`,true)}
        ${field('Impact',e.impact,`upd(${i},'impact',this.value)`,true)}
        ${field('Empfohlene Aktion',e.recommended_action,`upd(${i},'recommended_action',this.value)`)}
      </div>
    </div>`;
  }).join('');
}
function upd(i,k,v){drafts[i].edit[k]=v;}
function updTop(i,k,v){drafts[i][k]=v;}
function toggleItemArea(i,a){const e=drafts[i].edit;e.areas=e.areas||[];const x=e.areas.indexOf(a);x>=0?e.areas.splice(x,1):e.areas.push(a);render();}
function toggleIgnore(i){drafts[i].ignored=!drafts[i].ignored;render();}
let genProducts=new Set();
function populateQuarters(selected){
  const now=new Date();
  let y=now.getFullYear(), q=Math.floor(now.getMonth()/3)+1;
  q-=1; if(q<1){q=4;y-=1;}  // start one quarter back
  const opts=['<option value="">— Alle —</option>'];
  const seen=new Set();
  for(let i=0;i<7;i++){
    const label='Q'+q+' '+y; seen.add(label);
    opts.push(`<option value="${label}">${label}</option>`);
    q+=1; if(q>4){q=1;y+=1;}
  }
  if(selected && !seen.has(selected))opts.splice(1,0,`<option value="${selected}">${selected}</option>`);
  const sel=document.getElementById('g_quarter');
  sel.innerHTML=opts.join('');
  sel.value=selected||'';
}
function renderProductChecks(all){
  const names=[...new Set([...genProducts, ...(all||[])])].sort();
  const box=document.getElementById('g_products_box');
  box.innerHTML = names.length
    ? names.map(n=>`<label class="fchk"><input type="checkbox" ${genProducts.has(n)?'checked':''} onchange="toggleGenProduct('${n.replace(/'/g,"")}')"> ${esc(n)}</label>`).join('')
    : '<span class="meta">— „Produkte laden" klicken, um zu wählen —</span>';
}
function toggleGenProduct(n){genProducts.has(n)?genProducts.delete(n):genProducts.add(n);}
function gatherSettings(){
  return {
    source:document.getElementById('g_source').value,
    limit:parseInt(document.getElementById('g_limit').value)||null,
    quarter:document.getElementById('g_quarter').value.trim(),
    products:[...genProducts],
    worldwide_only:document.getElementById('g_ww').checked,
    new_rollouts_only:document.getElementById('g_new').checked,
    major_only:document.getElementById('g_major').checked,
    action_required:document.getElementById('g_action').checked,
    force:document.getElementById('g_force').checked,
  };
}
function applySettings(s){
  if(!s||!Object.keys(s).length)return;
  if(s.source)document.getElementById('g_source').value=s.source;
  if(s.limit)document.getElementById('g_limit').value=s.limit;
  if(s.quarter!=null)populateQuarters(s.quarter);
  if(typeof s.worldwide_only==='boolean')document.getElementById('g_ww').checked=s.worldwide_only;
  if(typeof s.new_rollouts_only==='boolean')document.getElementById('g_new').checked=s.new_rollouts_only;
  if(typeof s.major_only==='boolean')document.getElementById('g_major').checked=s.major_only;
  if(typeof s.action_required==='boolean')document.getElementById('g_action').checked=s.action_required;
  if(typeof s.force==='boolean')document.getElementById('g_force').checked=s.force;
  genProducts=new Set(s.products||[]);
}
async function saveSettings(notify){
  await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(gatherSettings())});
  if(notify)setStatus('Einstellungen gespeichert.');
}
async function generate(){
  const body=gatherSettings();
  await saveSettings(false);
  setStatus('Erzeuge Entwürfe via KI… (kann etwas dauern)');
  const r=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.error){setStatus('Fehler: '+d.error);return;}
  drafts=d.items||[];activeQ=null;activeChan=null;activeProd=null;activeArea=null;activeSvc=null;renderFilters();render();
  setStatus(d.count+' Entwürfe erzeugt.');
}
async function loadProducts(){
  const source=document.getElementById('g_source').value;
  setStatus('Lade Produkte…');
  const r=await fetch('/api/products?source='+encodeURIComponent(source));
  const d=await r.json();
  if(d.error){setStatus('Fehler: '+d.error);return;}
  renderProductChecks((d.products||[]).map(p=>p.name));
  setStatus((d.products||[]).length+' Produkte geladen.');
}
async function save(){
  setStatus('Speichere…');
  await fetch('/api/drafts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:drafts})});
  const ign=drafts.filter(d=>d.ignored).length;
  setStatus('Gespeichert ('+(drafts.length-ign)+' aktiv, '+ign+' ignoriert).');
}
async function publish(){
  await save();
  const dry=document.getElementById('dry').checked;
  setStatus('Veröffentliche…');
  const r=await fetch('/api/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({dry_run:dry})});
  const d=await r.json();
  if(d.error){setStatus('Fehler: '+d.error);return;}
  setStatus(`Fertig: ${d.published} Seite(n), ${d.dashboards} Dashboard(s)${dry?' (dry-run)':''}.`);
}
load();
</script>
</body></html>
"""


def create_app(review_file: str) -> FastAPI:
    app = FastAPI(title="M365 Review")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return INDEX_HTML

    settings_file = str(Path(review_file).with_name("ui_settings.json"))

    @app.get("/api/settings")
    def get_settings() -> dict:
        p = Path(settings_file)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return {}
        return {}

    @app.post("/api/settings")
    async def post_settings(request: Request) -> dict:
        data = await request.json()
        Path(settings_file).write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return {"saved": True}

    @app.get("/api/drafts")
    def get_drafts() -> dict:
        items = load_drafts(review_file) if Path(review_file).exists() else []
        return {"items": items, "review_file": review_file}

    @app.post("/api/drafts")
    async def post_drafts(request: Request) -> dict:
        data = await request.json()
        items = data.get("items", [])
        save_drafts(review_file, items)
        return {"saved": len(items)}

    @app.post("/api/generate")
    async def generate(request: Request):
        from m365_confluence.config import Config, ConfigError
        from m365_confluence.pipeline import run

        body = await request.json()
        source = body.get("source", "roadmap")
        use_mc = source in {"both", "message-center"}
        use_rm = source in {"both", "roadmap"}
        try:
            config = Config.load(
                use_message_center=use_mc,
                use_roadmap=use_rm,
                require_confluence=False,
            )
            run(
                config,
                since_days=body.get("since_days"),
                limit=body.get("limit"),
                quarter=body.get("quarter") or None,
                major_only=bool(body.get("major_only")),
                action_required=bool(body.get("action_required")),
                products=body.get("products") or None,
                categories=body.get("categories") or None,
                worldwide_only=bool(body.get("worldwide_only", True)),
                new_rollouts_only=bool(body.get("new_rollouts_only", True)),
                force=bool(body.get("force")),
                review_out=review_file,
            )
        except (ConfigError, FileNotFoundError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:  # surface upstream/LLM errors to the UI
            return JSONResponse({"error": str(exc)}, status_code=500)
        items = load_drafts(review_file) if Path(review_file).exists() else []
        return {"items": items, "count": len(items)}

    @app.get("/api/products")
    def products(source: str = "roadmap"):
        from m365_confluence.config import Config, ConfigError
        from m365_confluence.pipeline import collect_products

        use_mc = source in {"both", "message-center"}
        use_rm = source in {"both", "roadmap"}
        try:
            config = Config.load(
                use_message_center=use_mc,
                use_roadmap=use_rm,
                require_confluence=False,
            )
            return {"products": [{"name": n, "count": c} for n, c in collect_products(config)]}
        except ConfigError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.post("/api/publish")
    async def publish(request: Request):
        from m365_confluence.config import Config, ConfigError
        from m365_confluence.pipeline import run_from_review

        body = await request.json()
        dry = bool(body.get("dry_run", False))
        try:
            config = Config.load(
                use_message_center=False,
                use_roadmap=False,
                require_confluence=not dry,
            )
            result = run_from_review(config, review_file, dry_run=dry)
        except (ConfigError, FileNotFoundError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return {
            "published": result.published,
            "dashboards": result.dashboards,
            "processed": result.processed,
        }

    return app


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="m365-to-confluence-ui")
    parser.add_argument("--review-file", default="review.json")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    import uvicorn

    print(f"Review UI on http://{args.host}:{args.port}  (file: {args.review_file})")
    uvicorn.run(create_app(args.review_file), host=args.host, port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
