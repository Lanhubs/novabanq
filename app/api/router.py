"""Top-level API router.

Mounts the versioned routers under their respective prefixes. This
file should never contain feature-specific logic — its only job is to
compose the versioned routers into the root API surface.
"""

from fastapi import APIRouter

from app.api.v1.router import api_router as v1_router
from app.core.config import settings

api_router = APIRouter()

api_router.include_router(v1_router, prefix=settings.api_v1_prefix)