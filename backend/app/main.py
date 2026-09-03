from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT_DIR, settings
from app.db import init_db
from app.routers import chat, favorites, jobs, profile
from app.security import AccessGateMiddleware

DIST_DIR = ROOT_DIR / "frontend" / "dist"
SECURED = bool(settings.access_token.strip())
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    if not SECURED:
        logger.warning("ACCESS_TOKEN 为空：不要把 uvicorn 绑到 0.0.0.0，否则接口没有口令")
    elif not DIST_DIR.is_dir():
        logger.warning("未找到 frontend/dist，分享前请先在 frontend/ 执行 npm run build")
    yield


app = FastAPI(
    title="求职导航",
    version="0.1.0",
    lifespan=lifespan,
    redirect_slashes=False,
    docs_url=None if SECURED else "/docs",
    redoc_url=None if SECURED else "/redoc",
    openapi_url=None if SECURED else "/openapi.json",
)
app.add_middleware(AccessGateMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(favorites.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "name": "求职导航",
        "llm_model": settings.llm_model,
        "llm_ready": bool(settings.llm_api_key.strip()),
        "auth_required": SECURED,
    }


@app.get("/api/auth/check")
def auth_check() -> dict:
    return {"ok": True}


def _safe_dist_file(path: str) -> Path | None:
    if not path or path.startswith("api/"):
        return None
    target = (DIST_DIR / path).resolve()
    try:
        target.relative_to(DIST_DIR.resolve())
    except ValueError:
        return None
    return target if target.is_file() else None


if DIST_DIR.is_dir():
    assets = DIST_DIR / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        file = _safe_dist_file(path)
        if file:
            return FileResponse(file)
        return FileResponse(DIST_DIR / "index.html")
