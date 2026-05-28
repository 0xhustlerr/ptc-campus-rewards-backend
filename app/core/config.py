"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

JwtAlgorithm = Literal["HS256"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "PTC Campus Rewards API"
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: PostgresDsn = Field(...)
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_echo: bool = False

    redis_url: RedisDsn = Field(...)

    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: JwtAlgorithm = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    qr_session_ttl_seconds: int = 60
    required_attendance_days_per_week: int = 5
    attendance_rule_code: str = "ATTENDANCE_ON_TIME"
    perfect_attendance_rule_code: str = "PERFECT_ATTENDANCE_WEEK"

    rate_limit_auth: str = "10/minute"
    rate_limit_qr_scan: str = "30/minute"
    rate_limit_redeem: str = "20/minute"

    default_page_size: int = 50
    max_page_size: int = 200
    max_password_length: int = 128

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def sqlalchemy_database_url(self) -> str:
        url = str(self.database_url)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
