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
    db: Session,
    user_id: str,
    query: str,
    ref_mode: str = "International",
    top_k: Optional[int] = None,
) -> dict:
    """
    Implémente la hiérarchie RAG décrite dans le cahier des charges :
      1. Documents de l'utilisateur (priorité maximale)
      2. Base documentaire MedMaster (cours validés, filtrés par ref_mode)
      3. (Sources externes validées — gérées directement par le prompt de Claude,
         qui peut s'appuyer sur ses connaissances + recommandations officielles)

    Retourne un dict avec les passages trouvés par niveau, pour construire le
    prompt de génération avec un contexte hiérarchisé et transparent.
    """
    top_k = top_k or settings.RAG_TOP_K
    qc.ensure_collections()

    query_vector = embed_texts([query])[0]

    # Niveau 1 — documents de l'utilisateur uniquement
    user_chunks = qc.search(
        settings.QDRANT_COLLECTION_USER,
        query_vector,
        top_k=top_k,
        filter_conditions={"user_id": user_id},
    )

    # Niveau 2 — base documentaire officielle, filtrée par mode de référence
    base_chunks = qc.search(
        settings.QDRANT_COLLECTION_REFERENCE,
        query_vector,
        top_k=top_k,
        filter_conditions={"ref_mode": ref_mode},
    )

    return {
        "user_chunks": user_chunks,    # niveau 1
        "base_chunks": base_chunks,    # niveau 2
        # Le niveau 3 (sources externes) et 4 (génération pure) sont couverts
        # par les connaissances de Claude lors de la génération si les niveaux
        # 1 et 2 sont insuffisants.
    }
