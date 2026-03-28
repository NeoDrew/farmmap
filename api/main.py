"""FarmMap FastAPI application."""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.routers import companies, map_data, stats

app = FastAPI(
    title="FarmMap API",
    description="Companies House farm business geographic dashboard API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(companies.router)
app.include_router(map_data.router)
app.include_router(stats.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


# Serve React frontend static files if the dist directory exists
_FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """Serve React SPA — return index.html for all non-API routes."""
        index = _FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
