"""API v1 router aggregator.

This module is the single place where all v1 feature routers are
registered. As features are added, they are included here — nothing
else changes.
"""

from fastapi import APIRouter

from app.features.accounts.router import router as accounts_router
from app.features.funding.router import router as funding_router
from app.features.identity.router import router as identity_router
from app.features.otp.router import router as otp_router
from app.features.transactions.router import router as transactions_router
from app.features.transfers.router import router as transfers_router
from app.features.users.router import router as users_router

api_router = APIRouter()

api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(otp_router, prefix="/otp", tags=["otp"])
api_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
api_router.include_router(transfers_router, prefix="/transfers", tags=["transfers"])
api_router.include_router(
    transactions_router, prefix="/transactions", tags=["transactions"]
)
api_router.include_router(funding_router, prefix="", tags=["funding"])