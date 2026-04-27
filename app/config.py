# BRAIN 3.0 — AI-powered personal operating system for ADHD
# Copyright (C) 2026 L (WilliM233)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Application configuration via Pydantic Settings."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """BRAIN 3.0 application settings, loaded from environment variables / .env file."""

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"

    # Shared-secret bearer token gating /api/app/* (companion app + scheduler).
    # Distinct from any MCP token. Unset in dev → middleware skipped with a
    # startup warning. Required in production.
    APP_BEARER_TOKEN: str | None = Field(
        default=None, validation_alias="BRAIN3_APP_BEARER_TOKEN",
    )

    # IANA zoneinfo key used for TZ-sensitive server-side logic (e.g. EOD-local
    # routine_checklist expiry). Validated at startup — a bad key fails fast
    # rather than silently producing wrong expiries.
    SERVER_TZ: str = Field(
        default="America/Chicago", validation_alias="BRAIN3_SERVER_TZ",
    )

    # Firebase Cloud Messaging (FCM) HTTP v1 — push delivery to the companion
    # app. Both must be set in production. When either is unset, FCM dispatch
    # is skipped with a startup warning (dev convenience, mirrors the
    # APP_BEARER_TOKEN pattern). The service-account JSON path is loaded at
    # call time, so rotation does not require a restart.
    FCM_PROJECT_ID: str | None = Field(
        default=None, validation_alias="BRAIN3_FCM_PROJECT_ID",
    )
    FCM_SERVICE_ACCOUNT_JSON_PATH: str | None = Field(
        default=None, validation_alias="BRAIN3_FCM_SERVICE_ACCOUNT_JSON_PATH",
    )

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", populate_by_name=True,
    )

    @field_validator("SERVER_TZ")
    @classmethod
    def _validate_server_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except ZoneInfoNotFoundError as exc:
            msg = f"SERVER_TZ {v!r} is not a valid IANA zoneinfo key"
            raise ValueError(msg) from exc
        return v

    @property
    def server_tz(self) -> ZoneInfo:
        """Return SERVER_TZ as a resolved ZoneInfo."""
        return ZoneInfo(self.SERVER_TZ)

    @property
    def database_url(self) -> str:
        """Construct the PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


settings = Settings()
