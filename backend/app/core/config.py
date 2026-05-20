import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Medical Shift Scheduling System"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5433/medical_shifts"
    frontend_origin: str = "http://localhost:5173"
    secret_key: str = "change-this-local-secret"
    access_token_expire_minutes: int = 60 * 8
    failed_login_lock_threshold: int = 5
    failed_login_lock_minutes: int = 15
    confirmation_overdue_hours: int = 12
    token_audience: str = "medical-shifts-app"
    token_issuer: str = "medical-shifts-system"

    telegram_bot_username: str = "MedicalSchedule_bot"
    telegram_bot_token: str | None = None

    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    resend_api_key: str | None = None
    resend_from_email: str = "noreply@turnos-medicos.com"

    # Feature flags for partial deployment
    feature_notifications: bool = False
    feature_telegram: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    # Load .env into os.environ so os.environ.get() works everywhere
    env_file = settings.model_config.get("env_file", ".env")
    if env_file and os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove surrounding quotes
                if len(value) > 1 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if key:
                    os.environ[key] = value

    # Validate secret key in production
    if settings.app_env == "production" and settings.secret_key == "change-this-local-secret":
        import sys as _sys
        print("FATAL: SECRET_KEY must be changed for production.", file=_sys.stderr)
        _sys.exit(1)

    # Warn about missing optional keys — only when the feature is enabled
    import sys as _sys
    if settings.feature_telegram and not settings.telegram_bot_token:
        print("WARNING: TELEGRAM_BOT_TOKEN not set — Telegram bot will use FakeBotClient.", file=_sys.stderr)
    if settings.feature_telegram and not settings.deepseek_api_key:
        print("WARNING: DEEPSEEK_API_KEY not set — LLM agent will use FakeLLMProvider.", file=_sys.stderr)

    return settings


settings = get_settings()
