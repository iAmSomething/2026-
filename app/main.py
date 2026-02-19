import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

DEFAULT_CORS_ALLOW_ORIGINS = (
    "https://2026-deploy.vercel.app,"
    "http://127.0.0.1:3000,"
    "http://localhost:3000,"
    "http://127.0.0.1:3300,"
    "http://localhost:3300"
)


def _resolve_cors_allow_origins() -> list[str]:
    raw = os.getenv("CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="Election 2026 Backend MVP", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_resolve_cors_allow_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
