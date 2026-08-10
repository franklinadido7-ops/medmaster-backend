"""
Embeddings sémantiques via fastembed (léger, sans PyTorch, gratuit).
Modèle : BAAI/bge-small-en-v1.5 — 384 dimensions
"""
from typing import List
from fastembed import TextEmbedding

_model = None

def _get_model():
    global _model
    if _model is None:
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model

def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = _get_model()
    embeddings = list(model.embed(texts))
    return [e.tolist() for e in embeddings]

def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]