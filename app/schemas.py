from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field


# ─── AUTH ────────────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: Optional[str] = None
    university: Optional[str] = None
    study_level: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RagPrefs(BaseModel):
    user: int = 80
    base: int = 15
    ext: int = 5


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: Optional[str]
    university: Optional[str]
    study_level: Optional[str]
    ref_mode: str
    rag_pref_user: int
    rag_pref_base: int
    rag_pref_ext: int
    is_admin: bool

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    university: Optional[str] = None
    study_level: Optional[str] = None
    ref_mode: Optional[str] = None  # 'Faculté' | 'International'
    rag_prefs: Optional[RagPrefs] = None


# ─── DOCUMENTS ───────────────────────────────────────────────────────────────
class DocumentOut(BaseModel):
    id: str
    filename: str
    file_type: str
    status: str
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── GÉNÉRATION IA ───────────────────────────────────────────────────────────
class GenerateRequest(BaseModel):
    document_ids: List[str] = []
    generate_fiche: bool = True
    generate_flashcards: bool = True
    generate_qcm: bool = True
    ref_mode: Optional[str] = None        # surcharge ponctuelle, sinon profil utilisateur
    rag_prefs: Optional[RagPrefs] = None  # surcharge ponctuelle


class Flashcard(BaseModel):
    q: str
    a: str


class QCMQuestion(BaseModel):
    question: str
    options: List[str]
    correct: int
    explication: str


class ConceptOut(BaseModel):
    id: str
    label: str
    category: str
    mastery: float = 0.0
    related: List[str] = []


class GenerateResponse(BaseModel):
    topic: str
    sources: RagPrefs
    fiche: Optional[str] = None
    flashcards: Optional[List[Flashcard]] = None
    qcm: Optional[List[QCMQuestion]] = None
    concepts: Optional[List[ConceptOut]] = None


# ─── BIBLIOTHÈQUE ────────────────────────────────────────────────────────────
class LibraryItemCreate(BaseModel):
    topic: str
    fiche_md: Optional[str] = None
    flashcards: Optional[List[Flashcard]] = None
    qcm: Optional[List[QCMQuestion]] = None
    sources_pct: RagPrefs = RagPrefs()


class LibraryItemOut(BaseModel):
    id: str
    topic: str
    fiche_md: Optional[str]
    flashcards: Optional[List[Dict[str, Any]]]
    qcm: Optional[List[Dict[str, Any]]]
    sources_pct: Dict[str, int]
    sources_overridden: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SourcesUpdate(BaseModel):
    sources_pct: RagPrefs


# ─── SM-2 / FLASHCARDS ───────────────────────────────────────────────────────
class DeckOut(BaseModel):
    id: str
    name: str
    card_count: int
    due_count: int
    mastered_count: int

    class Config:
        from_attributes = True


class FlashcardOut(BaseModel):
    id: str
    question: str
    answer: str
    repetitions: int
    ease_factor: float
    interval_days: int
    next_review: datetime

    class Config:
        from_attributes = True


class ReviewRequest(BaseModel):
    quality: int = Field(ge=0, le=5)  # 0=blackout ... 5=parfait


# ─── ASSISTANT IA ────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    ref_mode: Optional[str] = None
    rag_prefs: Optional[RagPrefs] = None


class ChatResponse(BaseModel):
    reply: str
    sources: RagPrefs


# ─── PLANNING ────────────────────────────────────────────────────────────────
class PlanningRequest(BaseModel):
    exam_date: Optional[date] = None


class PlanningTask(BaseModel):
    type: str
    label: str
    duration: str


class PlanningDay(BaseModel):
    date: date
    title: str
    tasks: List[PlanningTask]


class PlanningResponse(BaseModel):
    intro: str
    days: List[PlanningDay]
