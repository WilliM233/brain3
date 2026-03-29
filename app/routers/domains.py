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
