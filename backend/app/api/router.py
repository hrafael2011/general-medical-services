from fastapi import APIRouter

from backend.app.api.routes.admin_users import router as admin_users_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.availability import router as availability_router
from backend.app.api.routes.calendars import router as calendars_router
from backend.app.api.routes.catalogs import router as catalogs_router
from backend.app.api.routes.doctors import router as doctors_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.missions import router as missions_router
from backend.app.api.routes.notifications import router as notifications_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.import_staging import router as import_router
from backend.app.api.routes.telegram import router as telegram_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_users_router)
api_router.include_router(catalogs_router)
api_router.include_router(doctors_router)
api_router.include_router(availability_router)
api_router.include_router(audit_router)
api_router.include_router(calendars_router)
api_router.include_router(missions_router)
api_router.include_router(notifications_router)
api_router.include_router(reports_router)
api_router.include_router(telegram_router)
api_router.include_router(import_router)
api_router.include_router(health_router, tags=["health"])
