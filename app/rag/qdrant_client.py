"""
Client Qdrant — gestion des collections vectorielles.

Deux collections :
- medmaster_user_docs       : chunks des documents importés par chaque utilisateur
- medmaster_reference_docs  : chunks des cours de référence officiels (admin)

Chaque point stocke un payload avec les métadonnées nécessaires pour reconstruire
le contexte et appliquer la hiérarchie RAG (utilisateur > base > externe).
"""
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings

EMBEDDING_DIM = 384  # text-embedding-3-small

_client: Optional[QdrantClient] = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.QDRANT_URL)
    return _client


def ensure_collections():
    """Crée les collections si elles n'existent pas encore (idempotent)."""
    client = get_client()
    for name in (settings.QDRANT_COLLECTION_USER, settings.QDRANT_COLLECTION_REFERENCE):
        existing = [c.name for c in client.get_collections().collections]
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=qmodels.VectorParams(size=EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
            )


def upsert_chunks(
    collection: str,
    points: List[Dict[str, Any]],
):
    """
    points: liste de dicts {id, vector, payload}
    payload doit contenir au minimum : text, document_id, user_id (ou None), ref_mode (optionnel)
    """
    client = get_client()
    client.upsert(
        collection_name=collection,
        points=[
            qmodels.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ],
    )


def search(
    collection: str,
    query_vector: List[float],
    top_k: int = 6,
    filter_conditions: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Recherche les chunks les plus pertinents. filter_conditions ex: {"user_id": "..."}"""
    client = get_client()
    qfilter = None
    if filter_conditions:
        qfilter = qmodels.Filter(
            must=[
                qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v))
                for k, v in filter_conditions.items()
            ]
        )
    results = client.search(
        collection_name=collection,
        query_vector=query_vector,
        query_filter=qfilter,
        limit=top_k,
        with_payload=True,
    )
    return [{"score": r.score, **r.payload} for r in results]


def delete_document_chunks(collection: str, document_id: str):
    client = get_client()
    client.delete(
        collection_name=collection,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[qmodels.FieldCondition(key="document_id", match=qmodels.MatchValue(value=document_id))]
            )
        ),
    )
