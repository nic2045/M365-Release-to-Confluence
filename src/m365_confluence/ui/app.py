"""FastAPI app to review/edit drafts (review.json) and publish to Confluence.

Run with: m365-to-confluence-ui --review-file review.json
Requires the 'ui' extra: pip install -e ".[ui]"
"""

from __future__ import annotations

import argparse
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
<main id="list"></main>
<script>
const DECISIONS=["Activate","Communicate","Monitor","Deactivate"];
let drafts=[];
function setStatus(t){document.getElementById('status').textContent=t;}
function esc(s){return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}
async function load(){
  const r=await fetch('/api/drafts');const d=await r.json();drafts=d.items||[];render();
  setStatus(drafts.length+' Einträge');
}
function field(label,val,onin,ml){
  if(ml)return `<label>${label}</label><textarea oninput="${onin}">${esc(val)}</textarea>`;
  return `<label>${label}</label><input type="text" value="${esc(val)}" oninput="${onin}">`;
}
function render(){
  const hide=document.getElementById('hideign').checked;
  const el=document.getElementById('list');
  const visible=drafts.map((it,i)=>[it,i]).filter(([it])=>!(hide&&it.ignored));
  if(!visible.length){el.innerHTML='<div class="empty">Keine Einträge. Erst Entwürfe erzeugen:<br><code>make review</code></div>';return;}
  el.innerHTML=visible.map(([it,i])=>{
    const e=it.edit, s=it.source;
    const opts=DECISIONS.map(o=>`<option ${o===e.decision?'selected':''}>${o}</option>`).join('');
    const chips=(s.products||[]).map(p=>`<span class="chip">${esc(p)}</span>`).join('')
      +(e.target_quarter?`<span class="chip">${esc(e.target_quarter)}</span>`:'')
      +(e.cab_required?'<span class="chip" style="background:#fde8e8;color:#b42318">CAB</span>':'');
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
function toggleIgnore(i){drafts[i].ignored=!drafts[i].ignored;render();}
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
