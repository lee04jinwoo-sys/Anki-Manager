import os
import re
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AnkiManagerWeb")

app = FastAPI(title="Anki Manager Web")

# 로컬 출처만 허용한다: Vite 개발 서버, 이 서버, Anki 데스크톱 카드 웹뷰(127.0.0.1:임의 포트).
LOCAL_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1)(:\d+)?$"
_LOCAL_ORIGIN = re.compile(LOCAL_ORIGIN_REGEX)
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@app.middleware("http")
async def reject_cross_site_writes(request, call_next):
    # CORS는 응답 읽기만 막고, 본문 없는 POST는 다른 사이트에서도 전송·실행된다.
    # 브라우저는 교차 출처 POST에 Origin을 붙이므로, 로컬이 아닌 Origin의 쓰기 요청은 거부한다.
    # Origin이 없는 요청(curl, agent_bridge 등 로컬 프로세스)은 허용한다.
    origin = request.headers.get("origin")
    if request.method not in _SAFE_METHODS and origin is not None and not _LOCAL_ORIGIN.match(origin):
        return JSONResponse(status_code=403, content={"detail": "cross-site request rejected"})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_ORIGIN_REGEX,
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
from backend.routers import stats, organize, workflow, status, design, links, dashboard, cards, corpus, leech

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
app.include_router(leech.router)

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
