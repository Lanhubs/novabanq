"""API v1 router aggregator.

This module is the single place where all v1 feature routers are
registered. As features are added, they are included here — nothing
else changes.
"""

from fastapi import APIRouter

from app.features.identity.router import router as identity_router
from app.features.otp.router import router as otp_router
from app.features.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(otp_router, prefix="/otp", tags=["otp"])
api_router.include_router(identity_router, prefix="/identity", tags=["identity"])