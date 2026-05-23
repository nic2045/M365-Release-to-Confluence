"""FastAPI app to review/edit drafts (review.json) and publish to Confluence.

Run with: m365-to-confluence-ui --review-file review.json
Requires the 'ui' extra: pip install -e ".[ui]"

The HTML/CSS/JS now live in the shared module bundle (``view.py`` + the
``static/`` tree) so the exact same view can be embedded by the Weekly
platform. This module serves it standalone with no host chrome.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from m365_confluence.review import load_drafts, save_drafts
from m365_confluence.ui.view import STATIC_DIR, render_module_html

#: URL prefixes used standalone. The Weekly host mounts the same bundle under
#: its own prefixes (``/api/m365`` and a module asset route).
ASSET_BASE = "/m365-assets"
API_BASE = "/api"


def create_app(review_file: str) -> FastAPI:
    app = FastAPI(title="M365 Review")
    app.mount(ASSET_BASE, StaticFiles(directory=str(STATIC_DIR)), name="m365-assets")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return render_module_html(asset_base=ASSET_BASE, api_base=API_BASE)

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
