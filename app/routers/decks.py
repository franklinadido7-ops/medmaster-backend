from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user
from app.sm2 import apply_sm2

router = APIRouter(prefix="/decks", tags=["Révision SM-2"])


@router.post("", response_model=schemas.DeckOut, status_code=201)
def create_deck_from_flashcards(
    name: str,
    flashcards: list[schemas.Flashcard],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Crée un nouveau paquet de révision SM-2 à partir de flashcards générées."""
    deck = models.Deck(user_id=current_user.id, name=name)
    db.add(deck)
    db.commit()
    db.refresh(deck)

    for fc in flashcards:
        card = models.Flashcard(deck_id=deck.id, question=fc.q, answer=fc.a)
        db.add(card)
    db.commit()
    db.refresh(deck)
    return _deck_to_out(deck)


def _deck_to_out(deck: models.Deck) -> schemas.DeckOut:
    cards = deck.cards
    due_count = sum(1 for c in cards if c.next_review <= datetime.utcnow())
    mastered_count = sum(1 for c in cards if c.repetitions >= 3)
    return schemas.DeckOut(
        id=deck.id,
        name=deck.name,
        card_count=len(cards),
        due_count=due_count,
        mastered_count=mastered_count,
    )


@router.get("", response_model=list[schemas.DeckOut])
def list_decks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    decks = db.query(models.Deck).filter(models.Deck.user_id == current_user.id).all()
    return [_deck_to_out(d) for d in decks]


@router.get("/{deck_id}/due", response_model=list[schemas.FlashcardOut])
def get_due_cards(
    deck_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deck = (
        db.query(models.Deck)
        .filter(models.Deck.id == deck_id, models.Deck.user_id == current_user.id)
        .first()
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Paquet introuvable.")

    return (
        db.query(models.Flashcard)
        .filter(models.Flashcard.deck_id == deck_id, models.Flashcard.next_review <= datetime.utcnow())
        .order_by(models.Flashcard.next_review.asc())
        .all()
    )


@router.post("/cards/{card_id}/review", response_model=schemas.FlashcardOut)
def review_card(
    card_id: str,
    payload: schemas.ReviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    card = (
        db.query(models.Flashcard)
        .join(models.Deck)
        .filter(models.Flashcard.id == card_id, models.Deck.user_id == current_user.id)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Flashcard introuvable.")

    repetitions, ease_factor, interval_days, next_review = apply_sm2(
        card.repetitions, card.ease_factor, card.interval_days, payload.quality
    )

    card.repetitions = repetitions
    card.ease_factor = ease_factor
    card.interval_days = interval_days
    card.last_quality = payload.quality
    card.next_review = next_review

    db.commit()
    db.refresh(card)
    return card


@router.delete("/{deck_id}", status_code=204)
def delete_deck(
    deck_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    deck = (
        db.query(models.Deck)
        .filter(models.Deck.id == deck_id, models.Deck.user_id == current_user.id)
        .first()
    )
    if not deck:
        raise HTTPException(status_code=404, detail="Paquet introuvable.")
    db.delete(deck)
    db.commit()
