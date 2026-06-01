from fastapi import APIRouter

from backend.app.core.config import settings

router = APIRouter()


@router.get("/feature-flags")
def get_feature_flags() -> dict[str, bool]:
    return {
        "notifications": settings.feature_notifications,
        "telegram": settings.feature_telegram,
        "confirmations": settings.feature_notifications,
    }
