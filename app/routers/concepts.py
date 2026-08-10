from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/concepts", tags=["Carte des connaissances"])


@router.get("", response_model=list[schemas.ConceptOut])
def list_concepts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    concepts = db.query(models.Concept).filter(models.Concept.user_id == current_user.id).all()
    return [
        schemas.ConceptOut(
            id=c.external_id or c.id,
            label=c.label,
            category=c.category or "default",
            mastery=c.mastery,
            related=c.related or [],
        )
        for c in concepts
    ]


@router.post("/bulk", response_model=list[schemas.ConceptOut], status_code=201)
def add_concepts(
    concepts_in: list[schemas.ConceptOut],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Ajoute (ou met à jour) une liste de concepts générés lors d'une génération IA."""
    created = []
    for c in concepts_in:
        existing = (
            db.query(models.Concept)
            .filter(models.Concept.user_id == current_user.id, models.Concept.external_id == c.id)
            .first()
        )
        if existing:
            existing.label = c.label
            existing.category = c.category
            existing.mastery = c.mastery
            existing.related = c.related
            db.commit()
            created.append(c)
            continue

        concept = models.Concept(
            user_id=current_user.id,
            external_id=c.id,
            label=c.label,
            category=c.category,
            mastery=c.mastery,
            related=c.related,
        )
        db.add(concept)
        db.commit()
        created.append(c)
    return created
