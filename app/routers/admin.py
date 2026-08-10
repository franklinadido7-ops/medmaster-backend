import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db, SessionLocal
from app.config import settings
from app.core.security import get_current_admin
from app.rag.ingest import ingest_reference_document

router = APIRouter(prefix="/admin", tags=["Administration"])

REF_DOCS_DIR = os.path.join(settings.UPLOAD_DIR, "reference")


@router.post("/reference-documents", status_code=201)
async def upload_reference_document(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    category: str = Form(...),
    ref_mode: str = Form(...),  # 'Faculté' | 'International'
    source_label: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    if ref_mode not in ("Faculté", "International"):
        raise HTTPException(status_code=400, detail="ref_mode doit être 'Faculté' ou 'International'.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Les cours de référence doivent être au format PDF.")

    os.makedirs(REF_DOCS_DIR, exist_ok=True)
    storage_path = os.path.join(REF_DOCS_DIR, f"{uuid.uuid4()}.pdf")
    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    ref_doc = models.ReferenceDocument(
        title=title,
        category=category,
        ref_mode=ref_mode,
        source_label=source_label,
        storage_path=storage_path,
    )
    db.add(ref_doc)
    db.commit()
    db.refresh(ref_doc)

    background_tasks.add_task(_ingest_ref_background, ref_doc.id)

    return {"id": ref_doc.id, "title": ref_doc.title, "status": "indexation en cours"}


def _ingest_ref_background(ref_doc_id: str):
    db = SessionLocal()
    try:
        ref_doc = db.query(models.ReferenceDocument).filter(models.ReferenceDocument.id == ref_doc_id).first()
        if ref_doc:
            ingest_reference_document(db, ref_doc)
    finally:
        db.close()


@router.get("/reference-documents")
def list_reference_documents(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    docs = db.query(models.ReferenceDocument).order_by(models.ReferenceDocument.created_at.desc()).all()
    return [
        {
            "id": d.id, "title": d.title, "category": d.category, "ref_mode": d.ref_mode,
            "source_label": d.source_label, "chunk_count": d.chunk_count, "created_at": d.created_at,
        }
        for d in docs
    ]


@router.delete("/reference-documents/{doc_id}", status_code=204)
def delete_reference_document(
    doc_id: str,
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    from app.rag import qdrant_client as qc

    doc = db.query(models.ReferenceDocument).filter(models.ReferenceDocument.id == doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    try:
        qc.delete_document_chunks(settings.QDRANT_COLLECTION_REFERENCE, doc.id)
    except Exception:
        pass

    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)

    db.delete(doc)
    db.commit()


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    users = db.query(models.User).order_by(models.User.created_at.desc()).all()
    return [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name, "university": u.university,
            "study_level": u.study_level, "ref_mode": u.ref_mode, "is_admin": u.is_admin,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.get("/stats")
def platform_stats(
    db: Session = Depends(get_db),
    _admin: models.User = Depends(get_current_admin),
):
    return {
        "total_users": db.query(models.User).count(),
        "total_documents": db.query(models.Document).count(),
        "total_library_items": db.query(models.LibraryItem).count(),
        "total_decks": db.query(models.Deck).count(),
        "total_flashcards": db.query(models.Flashcard).count(),
        "total_reference_documents": db.query(models.ReferenceDocument).count(),
    }
