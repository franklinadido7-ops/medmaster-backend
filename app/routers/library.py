from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user

router = APIRouter(prefix="/library", tags=["Bibliothèque"])


@router.post("", response_model=schemas.LibraryItemOut, status_code=201)
def save_to_library(
    payload: schemas.LibraryItemCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = models.LibraryItem(
        user_id=current_user.id,
        topic=payload.topic,
        fiche_md=payload.fiche_md,
        flashcards=[f.model_dump() for f in payload.flashcards] if payload.flashcards else None,
        qcm=[q.model_dump() for q in payload.qcm] if payload.qcm else None,
        sources_pct=payload.sources_pct.model_dump(),
        sources_overridden=False,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[schemas.LibraryItemOut])
def list_library(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.LibraryItem)
        .filter(models.LibraryItem.user_id == current_user.id)
        .order_by(models.LibraryItem.created_at.desc())
        .all()
    )


@router.patch("/{item_id}/sources", response_model=schemas.LibraryItemOut)
def update_sources(
    item_id: str,
    payload: schemas.SourcesUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Permet à l'utilisateur de corriger manuellement les % de sources affichés."""
    item = (
        db.query(models.LibraryItem)
        .filter(models.LibraryItem.id == item_id, models.LibraryItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Élément introuvable.")

    total = payload.sources_pct.user + payload.sources_pct.base + payload.sources_pct.ext
    if total != 100:
        raise HTTPException(status_code=400, detail="La somme des pourcentages doit être égale à 100.")

    item.sources_pct = payload.sources_pct.model_dump()
    item.sources_overridden = True
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
def delete_library_item(
    item_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    item = (
        db.query(models.LibraryItem)
        .filter(models.LibraryItem.id == item_id, models.LibraryItem.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Élément introuvable.")
    db.delete(item)
    db.commit()
