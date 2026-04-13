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

"""CRUD endpoints for the Notification Queue."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationQueue
from app.schemas.notifications import (
    NotificationCreate,
    NotificationResponse,
    NotificationUpdate,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------

VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"delivered", "expired"},
    "delivered": {"responded", "expired"},
    "responded": set(),
    "expired": set(),
}

# Fields that cannot be changed via PATCH
IMMUTABLE_FIELDS = {
    "notification_type",
    "target_entity_type",
    "target_entity_id",
    "scheduled_by",
    "response",
    "responded_at",
}


def validate_status_transition(current: str, requested: str) -> bool:
    """Return True if the status transition is allowed."""
    return requested in VALID_TRANSITIONS.get(current, set())


# ---------------------------------------------------------------------------
# POST — create notification
# ---------------------------------------------------------------------------

@router.post(
    "/", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED,
)
def create_notification(
    payload: NotificationCreate, db: Session = Depends(get_db),
) -> NotificationQueue:
    """Create a notification. Status is always set to pending."""
    data = payload.model_dump()
    data["status"] = "pending"
    notification = NotificationQueue(**data)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# ---------------------------------------------------------------------------
# GET list — with composable filters
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[NotificationResponse])
def list_notifications(
    notification_type: str | None = Query(None),
    notification_status: str | None = Query(None, alias="status"),
    delivery_type: str | None = Query(None),
    target_entity_type: str | None = Query(None),
    target_entity_id: UUID | None = Query(None),
    scheduled_by: str | None = Query(None),
    scheduled_after: datetime | None = Query(None),
    scheduled_before: datetime | None = Query(None),
    has_response: bool | None = Query(None),
    rule_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> list[NotificationQueue]:
    """List notifications with composable filters."""
    query = db.query(NotificationQueue)

    if notification_type is not None:
        query = query.filter(NotificationQueue.notification_type == notification_type)
    if notification_status is not None:
        query = query.filter(NotificationQueue.status == notification_status)
    if delivery_type is not None:
        query = query.filter(NotificationQueue.delivery_type == delivery_type)
    if target_entity_type is not None:
        query = query.filter(
            NotificationQueue.target_entity_type == target_entity_type,
        )
    if target_entity_id is not None:
        query = query.filter(
            NotificationQueue.target_entity_id == target_entity_id,
        )
    if scheduled_by is not None:
        query = query.filter(NotificationQueue.scheduled_by == scheduled_by)
    if scheduled_after is not None:
        query = query.filter(NotificationQueue.scheduled_at >= scheduled_after)
    if scheduled_before is not None:
        query = query.filter(NotificationQueue.scheduled_at < scheduled_before)
    if has_response is True:
        query = query.filter(NotificationQueue.status == "responded")
    elif has_response is False:
        query = query.filter(NotificationQueue.status != "responded")
    if rule_id is not None:
        query = query.filter(NotificationQueue.rule_id == rule_id)

    return query.order_by(NotificationQueue.scheduled_at.desc()).all()


# ---------------------------------------------------------------------------
# GET detail
# ---------------------------------------------------------------------------

@router.get("/{notification_id}", response_model=NotificationResponse)
def get_notification(
    notification_id: UUID, db: Session = Depends(get_db),
) -> NotificationQueue:
    """Get a single notification by ID."""
    notification = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.id == notification_id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


# ---------------------------------------------------------------------------
# PATCH — partial update with status transition enforcement
# ---------------------------------------------------------------------------

@router.patch("/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: UUID,
    request: Request,
    payload: NotificationUpdate,
    db: Session = Depends(get_db),
) -> NotificationQueue:
    """Partial update of a notification with status state machine enforcement."""
    notification = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.id == notification_id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Check raw request body for immutable fields (Pydantic strips unknown keys)
    raw_body = await request.json()
    immutable_in_request = set(raw_body.keys()) & IMMUTABLE_FIELDS
    if immutable_in_request:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot update immutable fields: {', '.join(sorted(immutable_in_request))}",
        )

    updates = payload.model_dump(exclude_unset=True)

    # Enforce status state machine
    if "status" in updates:
        requested = updates["status"]
        current = notification.status
        if not validate_status_transition(current, requested):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status transition: {current} → {requested}",
            )

    for field, value in updates.items():
        setattr(notification, field, value)

    db.commit()
    db.refresh(notification)
    return notification


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID, db: Session = Depends(get_db),
) -> None:
    """Delete a notification."""
    notification = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.id == notification_id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()
