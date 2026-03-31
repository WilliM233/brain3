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

"""CRUD endpoints for Domains."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Domain
from app.schemas.domains import (
    DomainCreate,
    DomainDetailResponse,
    DomainResponse,
    DomainUpdate,
)

router = APIRouter()


@router.post("/", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def create_domain(payload: DomainCreate, db: Session = Depends(get_db)) -> Domain:
    """Create a new domain."""
    domain = Domain(**payload.model_dump())
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/", response_model=list[DomainResponse])
def list_domains(db: Session = Depends(get_db)) -> list[Domain]:
    """List all domains."""
    return db.query(Domain).order_by(Domain.sort_order, Domain.name).all()


@router.get("/{domain_id}", response_model=DomainDetailResponse)
def get_domain(domain_id: UUID, db: Session = Depends(get_db)) -> Domain:
    """Get a single domain with its nested goals."""
    domain = (
        db.query(Domain)
        .options(joinedload(Domain.goals))
        .filter(Domain.id == domain_id)
        .first()
    )
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    return domain


@router.patch("/{domain_id}", response_model=DomainResponse)
def update_domain(
    domain_id: UUID, payload: DomainUpdate, db: Session = Depends(get_db)
) -> Domain:
    """Partial update of a domain."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(domain, field, value)

    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(domain_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a domain and cascade to its goals."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    db.delete(domain)
    db.commit()
