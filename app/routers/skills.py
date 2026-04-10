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

"""CRUD endpoints for Skills — contextual operating modes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Artifact,
    Directive,
    Domain,
    Protocol,
    Skill,
    SkillDirective,
    SkillDomain,
    SkillProtocol,
)
from app.schemas.directives import DirectiveResponse
from app.schemas.domains import DomainResponse
from app.schemas.protocols import ProtocolResponse
from app.schemas.skills import (
    SkillCreate,
    SkillFullResponse,
    SkillResponse,
    SkillUpdate,
)

router = APIRouter()
skill_domains_router = APIRouter()
skill_protocols_router = APIRouter()
skill_directives_router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_skill_with_relations(db: Session, skill_id: UUID) -> Skill | None:
    """Load a skill with eager-loaded domains, protocols, directives, artifact."""
    return (
        db.query(Skill)
        .options(
            joinedload(Skill.domains),
            joinedload(Skill.protocols),
            joinedload(Skill.directives),
            joinedload(Skill.artifact),
        )
        .filter(Skill.id == skill_id)
        .first()
    )


# ---------------------------------------------------------------------------
# Skill CRUD — /api/skills
# ---------------------------------------------------------------------------


@router.post("/", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(payload: SkillCreate, db: Session = Depends(get_db)) -> Skill:
    """Create a new skill with optional relationship linking."""
    # Unique name check
    existing = db.query(Skill).filter(Skill.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Skill name already exists")

    # is_default constraint
    if payload.is_default:
        current_default = db.query(Skill).filter(Skill.is_default.is_(True)).first()
        if current_default:
            raise HTTPException(
                status_code=409,
                detail="Another skill is already the default",
            )

    # Validate artifact_id
    if payload.artifact_id is not None:
        if not db.query(Artifact).filter(Artifact.id == payload.artifact_id).first():
            raise HTTPException(status_code=400, detail="Artifact not found")

    # Validate domain_ids
    domains = []
    if payload.domain_ids:
        for did in payload.domain_ids:
            domain = db.query(Domain).filter(Domain.id == did).first()
            if not domain:
                raise HTTPException(status_code=400, detail=f"Domain {did} not found")
            domains.append(domain)

    # Validate protocol_ids
    protocols = []
    if payload.protocol_ids:
        for pid in payload.protocol_ids:
            protocol = db.query(Protocol).filter(Protocol.id == pid).first()
            if not protocol:
                raise HTTPException(status_code=400, detail=f"Protocol {pid} not found")
            protocols.append(protocol)

    # Validate directive_ids
    directives = []
    if payload.directive_ids:
        for did in payload.directive_ids:
            directive = db.query(Directive).filter(Directive.id == did).first()
            if not directive:
                raise HTTPException(status_code=400, detail=f"Directive {did} not found")
            directives.append(directive)

    skill = Skill(
        **payload.model_dump(exclude={"domain_ids", "protocol_ids", "directive_ids"}),
    )
    db.add(skill)
    db.flush()

    for domain in domains:
        db.add(SkillDomain(skill_id=skill.id, domain_id=domain.id))
    for protocol in protocols:
        db.add(SkillProtocol(skill_id=skill.id, protocol_id=protocol.id))
    for directive in directives:
        db.add(SkillDirective(skill_id=skill.id, directive_id=directive.id))

    db.commit()
    db.refresh(skill)

    return _load_skill_with_relations(db, skill.id)


@router.get("/", response_model=list[SkillResponse])
def list_skills(
    search: str | None = Query(None, description="Case-insensitive name search"),
    is_seedable: bool | None = Query(None),
    is_default: bool | None = Query(None),
    domain_id: UUID | None = Query(None, description="Skills linked to this domain"),
    db: Session = Depends(get_db),
) -> list[Skill]:
    """List skills with composable filters."""
    query = db.query(Skill)

    if search is not None:
        query = query.filter(Skill.name.ilike(f"%{search}%"))
    if is_seedable is not None:
        query = query.filter(Skill.is_seedable == is_seedable)
    if is_default is not None:
        query = query.filter(Skill.is_default == is_default)
    if domain_id is not None:
        query = query.filter(Skill.domains.any(Domain.id == domain_id))

    skills = query.order_by(Skill.created_at.desc()).all()

    # Eager-load relationships for response serialization
    skill_ids = [s.id for s in skills]
    if skill_ids:
        skills = (
            db.query(Skill)
            .options(
                joinedload(Skill.domains),
                joinedload(Skill.protocols),
                joinedload(Skill.directives),
            )
            .filter(Skill.id.in_(skill_ids))
            .order_by(Skill.created_at.desc())
            .all()
        )
        # Deduplicate from joinedload
        seen = set()
        unique = []
        for s in skills:
            if s.id not in seen:
                seen.add(s.id)
                unique.append(s)
        skills = unique

    return skills


@router.get("/{skill_id}", response_model=SkillResponse)
def get_skill(skill_id: UUID, db: Session = Depends(get_db)) -> Skill:
    """Get a single skill with resolved relationships."""
    skill = _load_skill_with_relations(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.get("/{skill_id}/full", response_model=SkillFullResponse)
def get_skill_full(skill_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Get a skill with resolved relationships and grouped directives.

    This is the primary bootstrap endpoint — a fresh Claude session calls
    get_skill_full("core-protocol") to load all default behavioral context.
    """
    skill = _load_skill_with_relations(db, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Skill-linked directives sorted by priority desc
    skill_directives = sorted(skill.directives, key=lambda d: d.priority, reverse=True)

    # ALL global directives sorted by priority desc
    global_directives = (
        db.query(Directive)
        .filter(Directive.scope == "global")
        .order_by(Directive.priority.desc())
        .all()
    )

    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "adhd_patterns": skill.adhd_patterns,
        "is_seedable": skill.is_seedable,
        "is_default": skill.is_default,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
        "artifact": skill.artifact,
        "domains": skill.domains,
        "protocols": skill.protocols,
        "directives": {
            "global_directives": global_directives,
            "skill": skill_directives,
        },
    }


@router.patch("/{skill_id}", response_model=SkillResponse)
def update_skill(
    skill_id: UUID, payload: SkillUpdate, db: Session = Depends(get_db)
) -> Skill:
    """Partial update of a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    updates = payload.model_dump(exclude_unset=True)

    # Unique name check on update
    if "name" in updates and updates["name"] is not None:
        conflict = (
            db.query(Skill)
            .filter(Skill.name == updates["name"], Skill.id != skill_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=409, detail="Skill name already exists")

    # Validate artifact_id if provided
    if "artifact_id" in updates and updates["artifact_id"] is not None:
        if not db.query(Artifact).filter(Artifact.id == updates["artifact_id"]).first():
            raise HTTPException(status_code=400, detail="Artifact not found")

    # is_default constraint
    if updates.get("is_default") is True:
        current_default = (
            db.query(Skill)
            .filter(Skill.is_default.is_(True), Skill.id != skill_id)
            .first()
        )
        if current_default:
            raise HTTPException(
                status_code=409,
                detail="Another skill is already the default",
            )

    for field, value in updates.items():
        setattr(skill, field, value)

    db.commit()
    db.refresh(skill)

    return _load_skill_with_relations(db, skill.id)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(skill_id: UUID, db: Session = Depends(get_db)) -> None:
    """Delete a skill. Cascades to join tables."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    db.delete(skill)
    db.commit()


# ---------------------------------------------------------------------------
# Skill-Domain relationship — /api/skills/{skill_id}/domains
# ---------------------------------------------------------------------------


@skill_domains_router.get("/{skill_id}/domains", response_model=list[DomainResponse])
def list_domains_on_skill(
    skill_id: UUID, db: Session = Depends(get_db)
) -> list[Domain]:
    """List all domains linked to a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.domains


@skill_domains_router.post(
    "/{skill_id}/domains/{domain_id}", response_model=DomainResponse,
)
def link_domain_to_skill(
    skill_id: UUID, domain_id: UUID, db: Session = Depends(get_db)
) -> Domain:
    """Link a domain to a skill. Idempotent."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    existing = (
        db.query(SkillDomain)
        .filter(SkillDomain.skill_id == skill_id, SkillDomain.domain_id == domain_id)
        .first()
    )
    if not existing:
        db.add(SkillDomain(skill_id=skill_id, domain_id=domain_id))
        db.commit()

    return domain


@skill_domains_router.delete(
    "/{skill_id}/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_domain_from_skill(
    skill_id: UUID, domain_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a domain from a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    link = (
        db.query(SkillDomain)
        .filter(SkillDomain.skill_id == skill_id, SkillDomain.domain_id == domain_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=404, detail="Domain is not linked to this skill")
    db.delete(link)
    db.commit()


# ---------------------------------------------------------------------------
# Skill-Protocol relationship — /api/skills/{skill_id}/protocols
# ---------------------------------------------------------------------------


@skill_protocols_router.get(
    "/{skill_id}/protocols", response_model=list[ProtocolResponse],
)
def list_protocols_on_skill(
    skill_id: UUID, db: Session = Depends(get_db)
) -> list[Protocol]:
    """List all protocols linked to a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.protocols


@skill_protocols_router.post(
    "/{skill_id}/protocols/{protocol_id}", response_model=ProtocolResponse,
)
def link_protocol_to_skill(
    skill_id: UUID, protocol_id: UUID, db: Session = Depends(get_db)
) -> Protocol:
    """Link a protocol to a skill. Idempotent."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")

    existing = (
        db.query(SkillProtocol)
        .filter(
            SkillProtocol.skill_id == skill_id,
            SkillProtocol.protocol_id == protocol_id,
        )
        .first()
    )
    if not existing:
        db.add(SkillProtocol(skill_id=skill_id, protocol_id=protocol_id))
        db.commit()

    return protocol


@skill_protocols_router.delete(
    "/{skill_id}/protocols/{protocol_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_protocol_from_skill(
    skill_id: UUID, protocol_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a protocol from a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if not protocol:
        raise HTTPException(status_code=404, detail="Protocol not found")

    link = (
        db.query(SkillProtocol)
        .filter(
            SkillProtocol.skill_id == skill_id,
            SkillProtocol.protocol_id == protocol_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=404, detail="Protocol is not linked to this skill",
        )
    db.delete(link)
    db.commit()


# ---------------------------------------------------------------------------
# Skill-Directive relationship — /api/skills/{skill_id}/directives
# ---------------------------------------------------------------------------


@skill_directives_router.get(
    "/{skill_id}/directives", response_model=list[DirectiveResponse],
)
def list_directives_on_skill(
    skill_id: UUID, db: Session = Depends(get_db)
) -> list[Directive]:
    """List all directives linked to a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill.directives


@skill_directives_router.post(
    "/{skill_id}/directives/{directive_id}", response_model=DirectiveResponse,
)
def link_directive_to_skill(
    skill_id: UUID, directive_id: UUID, db: Session = Depends(get_db)
) -> Directive:
    """Link a directive to a skill. Idempotent."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")

    existing = (
        db.query(SkillDirective)
        .filter(
            SkillDirective.skill_id == skill_id,
            SkillDirective.directive_id == directive_id,
        )
        .first()
    )
    if not existing:
        db.add(SkillDirective(skill_id=skill_id, directive_id=directive_id))
        db.commit()

    return directive


@skill_directives_router.delete(
    "/{skill_id}/directives/{directive_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_directive_from_skill(
    skill_id: UUID, directive_id: UUID, db: Session = Depends(get_db)
) -> None:
    """Remove a directive from a skill."""
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    directive = db.query(Directive).filter(Directive.id == directive_id).first()
    if not directive:
        raise HTTPException(status_code=404, detail="Directive not found")

    link = (
        db.query(SkillDirective)
        .filter(
            SkillDirective.skill_id == skill_id,
            SkillDirective.directive_id == directive_id,
        )
        .first()
    )
    if not link:
        raise HTTPException(
            status_code=404, detail="Directive is not linked to this skill",
        )
    db.delete(link)
    db.commit()
