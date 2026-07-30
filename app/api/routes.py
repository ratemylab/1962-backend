from fastapi import APIRouter

from app.api.endpoints.admin import router as admin_router
from app.api.endpoints.tickets import router as tickets_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(tickets_router)
api_router.include_router(admin_router)
