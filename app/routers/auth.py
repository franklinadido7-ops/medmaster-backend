from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from collections import defaultdict
import time
from app import models, schemas
from app.database import get_db
from app.core.security import (
    get_password_hash, verify_password, create_access_token, get_current_user
)

router = APIRouter(prefix="/auth", tags=["Authentification"])

# ── Protection brute force ────────────────────────────────────────
_login_attempts: dict = defaultdict(list)
MAX_ATTEMPTS = 5
BLOCK_DURATION = 300  # 5 minutes

def _check_brute_force(email: str):
    now = time.time()
    _login_attempts[email] = [t for t in _login_attempts[email] if now - t < BLOCK_DURATION]
    if len(_login_attempts[email]) >= MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives échouées. Réessayez dans 5 minutes."
        )

def _record_failed(email: str):
    _login_attempts[email].append(time.time())

def _clear_attempts(email: str):
    _login_attempts[email] = []

# ── Routes ────────────────────────────────────────────────────────
@router.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Un compte existe déjà avec cet email.")
    user = models.User(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        full_name=payload.full_name,
        university=payload.university,
        study_level=payload.study_level,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Connexion. Utilise le format standard OAuth2 (username = email, password)."""
    # Vérification brute force avant tout
    _check_brute_force(form_data.username)

    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        # Enregistrer la tentative échouée
        _record_failed(form_data.username)
        remaining = MAX_ATTEMPTS - len(_login_attempts[form_data.username])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Email ou mot de passe incorrect. {remaining} tentative(s) restante(s).",
        )
    # Connexion réussie — réinitialiser le compteur
    _clear_attempts(form_data.username)
    token = create_access_token(data={"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if payload.full_name is not None:
        current_user.full_name = payload.full_name
    if payload.university is not None:
        current_user.university = payload.university
    if payload.study_level is not None:
        current_user.study_level = payload.study_level
    if payload.ref_mode is not None:
        current_user.ref_mode = payload.ref_mode
    if payload.rag_prefs is not None:
        total = payload.rag_prefs.user + payload.rag_prefs.base + payload.rag_prefs.ext
        if total != 100:
            raise HTTPException(status_code=400, detail="La somme des préférences RAG doit être égale à 100.")
        current_user.rag_pref_user = payload.rag_prefs.user
        current_user.rag_pref_base = payload.rag_prefs.base
        current_user.rag_pref_ext = payload.rag_prefs.ext
    db.commit()
    db.refresh(current_user)
    return current_user