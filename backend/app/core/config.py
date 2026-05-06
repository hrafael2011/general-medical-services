from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Medical Shift Scheduling System"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5433/medical_shifts"
    frontend_origin: str = "http://localhost:5173"
    secret_key: str = "change-this-local-secret"
    access_token_expire_minutes: int = 60 * 8
    failed_login_lock_threshold: int = 5
    failed_login_lock_minutes: int = 15

    telegram_bot_username: str = "MedicalSchedule_bot"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
