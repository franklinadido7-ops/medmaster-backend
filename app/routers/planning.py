from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user
from app.core.claude_client import call_claude, extract_json

router = APIRouter(prefix="/planning", tags=["Planning intelligent"])


@router.post("/generate", response_model=schemas.PlanningResponse)
def generate_plan(
    payload: schemas.PlanningRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    decks = db.query(models.Deck).filter(models.Deck.user_id == current_user.id).all()
    deck_summaries = []
    total_due = 0
    for d in decks:
        due = sum(1 for c in d.cards if c.next_review <= datetime.utcnow())
        total_due += due
        deck_summaries.append({"name": d.name, "total": len(d.cards), "due": due})

    weak_concepts = (
        db.query(models.Concept)
        .filter(models.Concept.user_id == current_user.id, models.Concept.mastery < 0.5)
        .order_by(models.Concept.mastery.asc())
        .limit(8)
        .all()
    )

    today = datetime.utcnow().date()
    days_until_exam = (payload.exam_date - today).days if payload.exam_date else None
    if days_until_exam is not None and days_until_exam < 0:
        days_until_exam = 0

    context = {
        "today": today.isoformat(),
        "exam_date": payload.exam_date.isoformat() if payload.exam_date else None,
        "days_until_exam": days_until_exam,
        "decks": deck_summaries,
        "total_due": total_due,
        "weak_concepts": [
            {"label": c.label, "category": c.category, "mastery": c.mastery} for c in weak_concepts
        ],
    }

    prompt = f"""Tu es MedMaster AI, planificateur de révisions médicales. Voici le contexte de
l'étudiant en JSON :
{context}

Génère un planning de révision intelligent pour les 7 prochains jours (à partir d'aujourd'hui
{context['today']}). Priorise : 1) les cartes SM-2 dues, 2) les concepts faibles (mastery<0.5),
3) si une date d'examen est fournie, intensifie les révisions à l'approche.

Réponds UNIQUEMENT avec ce JSON (sans markdown) :
{{
  "intro": "Une phrase de conseil personnalisé en français",
  "days": [
    {{"date":"YYYY-MM-DD","title":"Titre court du jour","tasks":[
      {{"type":"révision|lecture|qcm|concept|fiche|pause","label":"Description courte","duration":"30 min"}}
    ]}}
  ]
}}
7 jours exactement, 2 à 4 tâches par jour, durées réalistes (15-60 min), en français."""

    raw = call_claude([{"role": "user", "content": prompt}], max_tokens=3000)
    try:
        parsed = extract_json(raw)
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=502, detail=f"Erreur de génération du planning : {exc}")

    # Sauvegarde du planning généré
    plan_record = models.StudyPlan(
        user_id=current_user.id,
        exam_date=payload.exam_date,
        plan_json=parsed,
    )
    db.add(plan_record)
    db.commit()

    return parsed
