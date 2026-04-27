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

from datetime import UTC, date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NotificationQueue
from app.schemas.notifications import (
    NotificationCreate,
    NotificationListResponse,
    NotificationRespondRequest,
    NotificationResponse,
    NotificationUpdate,
)
from app.services.notification_defaults import calculate_expires_at, get_default_responses

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
    """Create a notification. Status is always set to pending.

    When canned_responses is null/omitted, auto-populates from type defaults.
    """
    data = payload.model_dump()
    data["status"] = "pending"
    if data.get("canned_responses") is None:
        data["canned_responses"] = get_default_responses(data["notification_type"])
    notification = NotificationQueue(**data)
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# ---------------------------------------------------------------------------
# GET list — with composable filters
# ---------------------------------------------------------------------------

@router.get("/", response_model=NotificationListResponse)
def list_notifications(
    notification_type: str | None = Query(None),
    notification_status: str | None = Query(None, alias="status"),
    delivery_type: str | None = Query(None),
    target_entity_type: str | None = Query(None),
    target_entity_id: UUID | None = Query(None),
    scheduled_by: str | None = Query(None),
    scheduled_after: datetime | None = Query(None),
    scheduled_before: datetime | None = Query(None),
    scheduled_date: date | None = Query(None),
    has_response: bool | None = Query(None),
    rule_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
) -> NotificationListResponse:
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
    if scheduled_date is not None:
        query = query.filter(NotificationQueue.scheduled_date == scheduled_date)
    if has_response is True:
        query = query.filter(NotificationQueue.status == "responded")
    elif has_response is False:
        query = query.filter(NotificationQueue.status != "responded")
    if rule_id is not None:
        query = query.filter(NotificationQueue.rule_id == rule_id)

    results = query.order_by(NotificationQueue.scheduled_at.desc()).all()
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in results],
        count=len(results),
    )


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
# POST — record a response to a delivered notification
# ---------------------------------------------------------------------------

@router.post("/{notification_id}/respond", response_model=NotificationResponse)
def respond_to_notification(
    notification_id: UUID,
    payload: NotificationRespondRequest,
    db: Session = Depends(get_db),
) -> NotificationQueue:
    """Record a user response to a delivered notification.

    Idempotent on the (notification_id, response, response_note) tuple: a
    repeat call with the same ``response`` and ``response_note`` as the
    already-recorded values returns 200 with the existing notification
    unchanged (no DB write, ``responded_at`` not bumped). A repeat call
    with a different ``response`` or ``response_note`` is a legitimate
    conflict and returns 409.

    Idempotent retry contract: clients (e.g. the Stream C canned-response
    queue) treat a 200 response as "your write was applied — you can
    clear it from the queue" regardless of whether it was the original
    write or a retry. The server does not distinguish first-vs-retry in
    the status code.
    """
    notification = (
        db.query(NotificationQueue)
        .filter(NotificationQueue.id == notification_id)
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Status-specific error responses
    if notification.status == "pending":
        raise HTTPException(
            status_code=409,
            detail="Notification has not been delivered yet",
        )
    if notification.status == "responded":
        if (
            notification.response == payload.response
            and notification.response_note == payload.response_note
        ):
            # Idempotent retry — return existing row, no write, no status change.
            return notification
        raise HTTPException(
            status_code=409,
            detail="Notification has already been responded to",
        )
    if notification.status == "expired":
        raise HTTPException(
            status_code=410,
            detail="Notification has expired",
        )

    # Validate response against canned_responses (if defined)
    if payload.response != "partial" and notification.canned_responses is not None:
        if payload.response not in notification.canned_responses:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Invalid response: must be one of {notification.canned_responses} "
                    'or "partial"'
                ),
            )

    notification.response = payload.response
    notification.response_note = payload.response_note
    notification.responded_at = datetime.now(tz=UTC)
    notification.status = "responded"

    db.commit()
    db.refresh(notification)
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

    # Auto-populate expires_at on delivery
    if updates.get("status") == "delivered":
        delivered_at = datetime.now(tz=UTC)
        notification.expires_at = calculate_expires_at(
            notification.notification_type,
            delivered_at,
            notification.expires_at,
        )

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
