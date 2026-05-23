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
<html lang="de"><head><meta charset="utf-8">
<title>M365 Review</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#f4f5f7;color:#172b4d}
 header{background:#0052cc;color:#fff;padding:12px 20px;display:flex;align-items:center;gap:16px}
 header h1{font-size:18px;margin:0;flex:1}
 button{background:#0052cc;color:#fff;border:0;border-radius:4px;padding:8px 14px;cursor:pointer}
 button.secondary{background:#42526e}
 main{padding:20px;max-width:1100px;margin:0 auto}
 .card{background:#fff;border:1px solid #dfe1e6;border-radius:6px;padding:16px;margin-bottom:16px}
 .row{display:flex;gap:16px;flex-wrap:wrap}
 .row>div{flex:1;min-width:220px}
 label{display:block;font-size:12px;font-weight:600;color:#5e6c84;margin:8px 0 2px}
 input[type=text],select,textarea{width:100%;box-sizing:border-box;padding:6px;border:1px solid #dfe1e6;border-radius:4px;font:inherit}
 textarea{min-height:60px}
 .meta{font-size:12px;color:#5e6c84}
 .pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;color:#fff}
 #status{font-size:13px}
</style></head>
<body>
<header>
  <h1>M365 Review &amp; Edit</h1>
  <span id="status"></span>
  <button class="secondary" onclick="save()">Speichern</button>
  <label style="color:#fff;font-weight:400"><input type="checkbox" id="dry"> Dry-run</label>
  <button onclick="publish()">Nach Confluence veröffentlichen</button>
</header>
<main id="list"></main>
<script>
const DECISIONS=["Activate","Communicate","Monitor","Deactivate"];
let drafts=[];
function setStatus(t){document.getElementById('status').textContent=t;}
async function load(){
  const r=await fetch('/api/drafts');const d=await r.json();drafts=d.items||[];render();
  setStatus(drafts.length+' Entwürfe ('+(d.review_file||'')+')');
}
function field(label,val,onin,ml){
  const v=(val||'').replace(/"/g,'&quot;');
  if(ml)return `<label>${label}</label><textarea oninput="${onin}">${val||''}</textarea>`;
  return `<label>${label}</label><input type="text" value="${v}" oninput="${onin}">`;
}
function render(){
  const el=document.getElementById('list');
  el.innerHTML=drafts.map((it,i)=>{
    const e=it.edit, s=it.source;
    const opts=DECISIONS.map(o=>`<option ${o===e.decision?'selected':''}>${o}</option>`).join('');
    return `<div class="card">
      <div class="meta">${s.source} · ${s.id} · ${(s.products||[]).join(', ')}</div>
      ${field('Titel',e.confluence_title,`upd(${i},'confluence_title',this.value)`)}
      <div class="row">
        <div>${field('Ziel-Quartal',e.target_quarter,`upd(${i},'target_quarter',this.value)`)}</div>
        <div><label>Entscheidung</label><select onchange="upd(${i},'decision',this.value)">${opts}</select></div>
        <div><label>CAB</label><label style="font-weight:400"><input type="checkbox" ${e.cab_required?'checked':''} onchange="upd(${i},'cab_required',this.checked)"> CAB erforderlich</label></div>
        <div><label>Einzelseite</label><label style="font-weight:400"><input type="checkbox" ${it.make_page?'checked':''} onchange="updTop(${i},'make_page',this.checked)"> Seite anlegen</label></div>
      </div>
      ${field('CAB-Empfehlung',e.cab_recommendation,`upd(${i},'cab_recommendation',this.value)`)}
      ${field('Zusammenfassung',e.summary,`upd(${i},'summary',this.value)`,true)}
      ${field('Impact',e.impact,`upd(${i},'impact',this.value)`,true)}
      ${field('Empfohlene Aktion',e.recommended_action,`upd(${i},'recommended_action',this.value)`)}
    </div>`;
  }).join('');
}
function upd(i,k,v){drafts[i].edit[k]=v;}
function updTop(i,k,v){drafts[i][k]=v;}
async function save(){
  setStatus('Speichere…');
  await fetch('/api/drafts',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({items:drafts})});
  setStatus('Gespeichert.');
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
