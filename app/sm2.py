"""
Algorithme SM-2 (SuperMemo 2) — répétition espacée.

Port direct de la logique utilisée côté frontend (JavaScript) pour garantir
un comportement identique entre le prototype et le backend.
"""
from datetime import datetime, timedelta
from typing import Tuple


def apply_sm2(
    repetitions: int,
    ease_factor: float,
    interval_days: int,
    quality: int,
) -> Tuple[int, float, int, datetime]:
    """
    Calcule les nouveaux paramètres SM-2 après une révision.

    quality : note de 0 (blackout total) à 5 (réponse parfaite et immédiate)
    Retourne : (repetitions, ease_factor, interval_days, next_review)
    """
    if quality >= 3:
        if repetitions == 0:
            interval_days = 1
        elif repetitions == 1:
            interval_days = 6
        else:
            interval_days = round(interval_days * ease_factor)
        repetitions += 1
    else:
        repetitions = 0
        interval_days = 1

    ease_factor = max(
        1.3,
        ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
    )

    next_review = datetime.utcnow() + timedelta(days=interval_days)

    return repetitions, ease_factor, interval_days, next_review
