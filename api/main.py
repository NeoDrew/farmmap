"""FarmMap FastAPI application."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
