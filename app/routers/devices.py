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

"""CRUD endpoints for app device (FCM) registration.

Mounted under ``/api/app/devices`` and therefore gated by the App API
bearer middleware (see ``app/auth.py``). Phase 2 is single-user, so the
table has no ``user_id`` — every registered device receives every push.
"""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppDevice
from app.schemas.devices import (
    DeviceListResponse,
    DeviceRegisterRequest,
    DeviceResponse,
)

router = APIRouter()


@router.post("", response_model=DeviceResponse)
def register_device(
    payload: DeviceRegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> AppDevice:
    """Register or refresh a device by ``fcm_token``.

    Upsert semantics: a new ``fcm_token`` inserts and returns 201; an
    existing token updates ``last_seen_at`` (and ``platform`` / ``label``
    when supplied) and returns 200.
    """
    existing = (
        db.query(AppDevice)
        .filter(AppDevice.fcm_token == payload.fcm_token)
        .first()
    )
    if existing is not None:
        existing.platform = payload.platform
        if payload.label is not None:
            existing.label = payload.label
        existing.last_seen_at = datetime.now(tz=UTC)
        db.commit()
        db.refresh(existing)
        response.status_code = status.HTTP_200_OK
        return existing

    device = AppDevice(
        fcm_token=payload.fcm_token,
        platform=payload.platform,
        label=payload.label,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    response.status_code = status.HTTP_201_CREATED
    return device


@router.get("", response_model=DeviceListResponse)
def list_devices(db: Session = Depends(get_db)) -> DeviceListResponse:
    """List all registered devices (debugging / admin)."""
    rows = (
        db.query(AppDevice)
        .order_by(AppDevice.registered_at.desc())
        .all()
    )
    return DeviceListResponse(
        items=[DeviceResponse.model_validate(r) for r in rows],
        count=len(rows),
    )


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(
    device_id: UUID, db: Session = Depends(get_db),
) -> None:
    """Unregister a device by id (used on logout / uninstall)."""
    device = db.query(AppDevice).filter(AppDevice.id == device_id).first()
    if device is None:
        raise HTTPException(status_code=404, detail="Device not found")
    db.delete(device)
    db.commit()
