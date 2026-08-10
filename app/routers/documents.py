import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.config import settings
from app.core.security import get_current_user
from app.rag.ingest import ingest_user_document
from app.rag import qdrant_client as qc

router = APIRouter(prefix="/documents", tags=["Documents"])

ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "ppt", "pptx", "jpg", "jpeg", "png"}


@router.post("/upload", response_model=schemas.DocumentOut, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Format non supporté : .{ext}")

    user_dir = os.path.join(settings.UPLOAD_DIR, current_user.id)
    os.makedirs(user_dir, exist_ok=True)

    stored_name = f"{uuid.uuid4()}.{ext}"
    storage_path = os.path.join(user_dir, stored_name)

    contents = await file.read()
    with open(storage_path, "wb") as f:
        f.write(contents)

    document = models.Document(
        user_id=current_user.id,
        filename=file.filename,
        file_type=ext,
        storage_path=storage_path,
        status="uploaded",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Indexation RAG en arrière-plan (ne bloque pas la réponse HTTP)
    background_tasks.add_task(_ingest_background, document.id)

    return document


def _ingest_background(document_id: str):
    """Exécuté en tâche de fond : ouvre sa propre session DB."""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if doc:
            ingest_user_document(db, doc)
    finally:
        db.close()


@router.get("/", response_model=list[schemas.DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Document)
        .filter(models.Document.user_id == current_user.id)
        .order_by(models.Document.created_at.desc())
        .all()
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    doc = (
        db.query(models.Document)
        .filter(models.Document.id == document_id, models.Document.user_id == current_user.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    # Supprime les vecteurs associés dans Qdrant
    try:
        qc.delete_document_chunks(settings.QDRANT_COLLECTION_USER, doc.id)
    except Exception:
        pass

    # Supprime le fichier physique
    if os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)

    db.delete(doc)
    db.commit()
