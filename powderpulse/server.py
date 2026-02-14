"""PowderPulse standalone server — static files + Liftie CORS proxy.

Replaces `npx serve -s dist` so PowderPulse can run independently
from the main CareAssist portal on its own port (3003).
"""
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import httpx
import uvicorn

app = FastAPI(title="PowderPulse")

DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")


# ── Liftie API proxy (CORS bypass) ──────────────────────────────
@app.get("/api/liftie/{resort_id}")
async def proxy_liftie(resort_id: str):
    """Proxy requests to Liftie API to bypass CORS restrictions."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://liftie.info/api/resort/{resort_id}",
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
            return {"error": f"Liftie API returned {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# ── Health check ─────────────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok", "service": "powderpulse"}


# ── Static assets (JS, CSS, images) ─────────────────────────────
assets_dir = os.path.join(DIST_DIR, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# ── SPA catch-all ────────────────────────────────────────────────
@app.get("/{path:path}")
async def serve_spa(path: str = ""):
    # Serve actual files (snowflake.svg, etc.)
    file_path = os.path.join(DIST_DIR, path)
    if path and os.path.isfile(file_path):
        return FileResponse(file_path)
    # Everything else → index.html (SPA routing)
    return FileResponse(os.path.join(DIST_DIR, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3003)
