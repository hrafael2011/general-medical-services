from fastapi import APIRouter

from backend.app.api.routes.action_alerts import router as action_alerts_router
from backend.app.api.routes.admin_trash import router as admin_trash_router
from backend.app.api.routes.admin_users import router as admin_users_router
from backend.app.api.routes.audit import router as audit_router
from backend.app.api.routes.auth import router as auth_router
from backend.app.api.routes.availability import router as availability_router
from backend.app.api.routes.calendars import router as calendars_router
from backend.app.api.routes.catalogs import router as catalogs_router
from backend.app.api.routes.confirmations import router as confirmations_router
from backend.app.api.routes.doctors import router as doctors_router
from backend.app.api.routes.feature_flags import router as feature_flags_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.missions import router as missions_router
from backend.app.api.routes.notifications import router as notifications_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.telegram import router as telegram_router
from backend.app.api.routes.webhooks import router as webhooks_router
from backend.app.core.config import settings

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(admin_trash_router)
api_router.include_router(admin_users_router)
api_router.include_router(action_alerts_router)
api_router.include_router(catalogs_router)
api_router.include_router(confirmations_router)
api_router.include_router(doctors_router)
api_router.include_router(availability_router)
api_router.include_router(audit_router)
api_router.include_router(calendars_router)
api_router.include_router(feature_flags_router)
api_router.include_router(missions_router)
if settings.feature_notifications:
    api_router.include_router(notifications_router)
api_router.include_router(reports_router)
if settings.feature_telegram:
    api_router.include_router(telegram_router)
api_router.include_router(webhooks_router)
api_router.include_router(health_router, tags=["health"])
if settings.app_env == "staging":
    from backend.app.api.routes.seed_staging import router as seed_staging_router
    api_router.include_router(seed_staging_router)
