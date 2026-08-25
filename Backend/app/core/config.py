from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "Abhyaas API"
    api_v1_prefix: str = "/api/v1"
    frontend_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/abhyaas"
    jwt_secret: str = Field(default="development-only-change-me", min_length=16)
    jwt_issuer: str = "abhyaas-api"
    jwt_audience: str = "abhyaas-web"
    access_token_minutes: int = 15
    refresh_token_days: int = 7
    login_attempt_limit: int = 5
    login_attempt_window_minutes: int = 15
    email_token_minutes: int = 30
    email_provider: str = "console"
    cookie_secure: bool = False
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8001/api/v1/auth/google/callback"

    @property
    def google_auth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
