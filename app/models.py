import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column, String, Boolean, Integer, Float, SmallInteger,
    DateTime, Date, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    university = Column(String(255))
    study_level = Column(String(50))
    ref_mode = Column(String(50), default="International")
    rag_pref_user = Column(Integer, default=80)
    rag_pref_base = Column(Integer, default=15)
    rag_pref_ext = Column(Integer, default=5)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    library_items = relationship("LibraryItem", back_populates="owner", cascade="all, delete-orphan")
    decks = relationship("Deck", back_populates="owner", cascade="all, delete-orphan")
    concepts = relationship("Concept", back_populates="owner", cascade="all, delete-orphan")
    study_plans = relationship("StudyPlan", back_populates="owner", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    storage_path = Column(String(1000), nullable=False)
    status = Column(String(50), default="uploaded")  # uploaded | processing | indexed | error
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="documents")


class ReferenceDocument(Base):
    """Cours de référence officiels — base documentaire MedMaster (admin)."""
    __tablename__ = "reference_documents"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    title = Column(String(500), nullable=False)
    category = Column(String(100))
    ref_mode = Column(String(50), nullable=False)  # 'Faculté' | 'International'
    source_label = Column(String(255))
    storage_path = Column(String(1000))
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class LibraryItem(Base):
    __tablename__ = "library_items"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    topic = Column(String(500), nullable=False)
    fiche_md = Column(Text, nullable=True)
    flashcards = Column(JSONB, nullable=True)
    qcm = Column(JSONB, nullable=True)
    sources_pct = Column(JSONB, nullable=False, default=lambda: {"user": 80, "base": 15, "ext": 5})
    sources_overridden = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="library_items")


class Deck(Base):
    __tablename__ = "decks"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="decks")
    cards = relationship("Flashcard", back_populates="deck", cascade="all, delete-orphan")


class Flashcard(Base):
    __tablename__ = "flashcards"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    deck_id = Column(UUID(as_uuid=False), ForeignKey("decks.id", ondelete="CASCADE"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    # Algorithme SM-2
    repetitions = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    interval_days = Column(Integer, default=1)
    last_quality = Column(SmallInteger, nullable=True)
    next_review = Column(DateTime, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow)

    deck = relationship("Deck", back_populates="cards")


class Concept(Base):
    __tablename__ = "concepts"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(100))
    label = Column(String(500), nullable=False)
    category = Column(String(100))
    mastery = Column(Float, default=0.0)
    related = Column(JSONB, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="concepts")


class StudyPlan(Base):
    __tablename__ = "study_plans"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exam_date = Column(Date, nullable=True)
    plan_json = Column(JSONB, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="study_plans")
