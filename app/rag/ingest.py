"""
Pipeline d'ingestion RAG : Document → extraction texte → chunks → embeddings → Qdrant.

Utilisé pour :
1. Les documents importés par un utilisateur (collection "user_docs", filtré par user_id)
2. Les cours de référence officiels ajoutés par l'admin (collection "reference_docs")
"""
import uuid
from typing import Optional

from sqlalchemy.orm import Session

from app import models
from app.config import settings
from app.rag import qdrant_client as qc
from app.rag.document_processor import extract_text, chunk_text
from app.rag.embeddings import embed_texts


def ingest_user_document(db: Session, document: models.Document) -> int:
    """Traite un document utilisateur : extraction, découpage, embeddings, indexation."""
    document.status = "processing"
    db.commit()

    try:
        text = extract_text(document.storage_path, document.file_type)

        if not text.strip():
            # Cas des images : pas d'indexation textuelle (utilisées en vision par Claude)
            document.status = "indexed"
            document.chunk_count = 0
            db.commit()
            return 0

        chunks = chunk_text(text)
        vectors = embed_texts(chunks)

        qc.ensure_collections()
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": vec,
                "payload": {
                    "text": chunk,
                    "document_id": document.id,
                    "user_id": document.user_id,
                    "filename": document.filename,
                    "source_level": "user",  # niveau 1 — priorité maximale
                },
            }
            for chunk, vec in zip(chunks, vectors)
        ]
        qc.upsert_chunks(settings.QDRANT_COLLECTION_USER, points)

        document.status = "indexed"
        document.chunk_count = len(chunks)
        db.commit()
        return len(chunks)

    except Exception as exc:
        document.status = "error"
        db.commit()
        raise exc


def ingest_reference_document(db: Session, ref_doc: models.ReferenceDocument) -> int:
    """Traite un cours de référence officiel (ajouté par un administrateur)."""
    text = extract_text(ref_doc.storage_path, "pdf")  # cours de référence : PDF attendu
    chunks = chunk_text(text)
    vectors = embed_texts(chunks)

    qc.ensure_collections()
    points = [
        {
            "id": str(uuid.uuid4()),
            "vector": vec,
            "payload": {
                "text": chunk,
                "document_id": ref_doc.id,
                "title": ref_doc.title,
                "category": ref_doc.category,
                "ref_mode": ref_doc.ref_mode,
                "source_label": ref_doc.source_label,
                "source_level": "base",  # niveau 2
            },
        }
        for chunk, vec in zip(chunks, vectors)
    ]
    qc.upsert_chunks(settings.QDRANT_COLLECTION_REFERENCE, points)

    ref_doc.chunk_count = len(chunks)
    db.commit()
    return len(chunks)

def retrieve_context(
    db,
    user_id: str,
    query: str,
    ref_mode: str = "International",
    top_k=None,
) -> dict:
    """RAG simplifié pour Render — retourne contexte vide.
    Claude utilisera ses connaissances générales pour générer le contenu.
    Le vrai RAG sera activé sur Railway avec Qdrant."""
    return {"user_chunks": [], "base_chunks": []}