"""NovaBanq API application entry point.

Builds the FastAPI application, wires middleware, registers exception
handlers, and mounts the versioned API router.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.infra.firebase.client import get_firebase_app


logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: runs on startup and shutdown."""
    logger.info(
        "Starting %s v%s (env=%s, demo_mode=%s).",
        settings.app_name,
        settings.app_version,
        settings.app_env,
        settings.demo_mode,
    )
    firebase_app = get_firebase_app()
    logger.info("Firebase project connected: %s", firebase_app.project_id)
    yield
    logger.info("Shutting down %s.", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(api_router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness probe. Returns app status and current environment."""
    return {
        "success": True,
        "data": {
            "status": "ok",
            "app": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
            "demo_mode": settings.demo_mode,
        },
        "error": None,
    }