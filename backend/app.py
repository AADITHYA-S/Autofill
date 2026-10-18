from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from backend.routes.auth_routes import router as auth_router
from backend.routes.document_routes import router as document_router
from backend.routes.form_routes import router as form_router
from backend.routes.profile_routes import router as profile_router

app = FastAPI(
    title="Major Project Unified API",
    version="1.0.0",
    description="Unified FastAPI backend with the working document extraction service plus placeholder routes for future integration.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(document_router)
app.include_router(auth_router)
app.include_router(profile_router)
app.include_router(form_router)

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"


@app.get("/", include_in_schema=False)
async def serve_landing_page():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.mount(
    "/",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)
