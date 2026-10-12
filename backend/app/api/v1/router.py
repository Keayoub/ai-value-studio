from __future__ import annotations

from app.api.v1.documents import router as documents_router
from app.api.v1.me import router as me_router
from app.api.v1.members import router as members_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.programs import router as programs_router
from app.api.v1.reviews import router as reviews_router
from app.api.v1.use_cases import router as use_cases_router
from app.api.v1.value_scorecards import router as value_scorecards_router
from app.api.v1.wizard import router as wizard_router
from app.api.v1.workspaces import router as workspaces_router
from fastapi import APIRouter

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(me_router)
api_router.include_router(workspaces_router)
api_router.include_router(members_router)
api_router.include_router(programs_router)
api_router.include_router(use_cases_router)
api_router.include_router(portfolio_router)
api_router.include_router(wizard_router)
api_router.include_router(value_scorecards_router)
api_router.include_router(reviews_router)
api_router.include_router(documents_router)
