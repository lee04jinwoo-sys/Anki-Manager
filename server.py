import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnkiManagerWeb")

app = FastAPI(title="Anki Manager Web")

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_header(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# Import routers
from backend.routers import stats, organize, workflow, status, design, links, dashboard, cards, corpus

# Include routers
app.include_router(dashboard.router)
app.include_router(stats.router)
app.include_router(organize.router)
app.include_router(workflow.router)
app.include_router(status.router)
app.include_router(design.router)
app.include_router(links.router)
app.include_router(cards.router)
app.include_router(corpus.router)

from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent
_FRONTEND_DIR = _SERVER_DIR / "frontend"
_DIST_DIR = _FRONTEND_DIR / "dist"

# Mount assets if dist exists
if (_DIST_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST_DIR / "assets")), name="assets")

if (_FRONTEND_DIR / "css").exists():
    app.mount("/css", StaticFiles(directory=str(_FRONTEND_DIR / "css")), name="css")
if (_FRONTEND_DIR / "js").exists():
    app.mount("/js", StaticFiles(directory=str(_FRONTEND_DIR / "js")), name="js")

@app.api_route("/", methods=["GET", "HEAD"])
def read_root():
    if (_DIST_DIR / "index.html").exists():
        return FileResponse(str(_DIST_DIR / "index.html"))
    return FileResponse(str(_FRONTEND_DIR / "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8001, reload=True)
