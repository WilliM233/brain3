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

"""Pydantic schemas for App Device registration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DevicePlatform = Literal["android", "ios"]


class DeviceRegisterRequest(BaseModel):
    """Body of POST /api/app/devices — register or refresh a device."""

    fcm_token: str = Field(min_length=1, max_length=4096)
    platform: DevicePlatform
    label: str | None = Field(default=None, max_length=200)


class DeviceResponse(BaseModel):
    """Device row returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fcm_token: str
    platform: str
    label: str | None = None
    registered_at: datetime
    last_seen_at: datetime


class DeviceListResponse(BaseModel):
    """Envelope for GET /api/app/devices."""

    items: list[DeviceResponse]
    count: int
