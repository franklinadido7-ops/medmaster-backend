"""
Client Anthropic partagé — utilisé pour la génération de contenu pédagogique
(fiches, flashcards, QCM) et l'assistant IA conversationnel.
"""
import json
import re
from typing import List, Dict, Any, Optional

from anthropic import Anthropic

from app.config import settings

_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def call_claude(
    messages: List[Dict[str, Any]],
    system: str = "",
    max_tokens: int = 2000,
) -> str:
    client = get_client()
    kwargs = {
        "model": settings.CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return "".join(block.text for block in response.content if block.type == "text")


def extract_json(raw: str) -> dict:
    """Extrait et parse le premier objet JSON trouvé dans une réponse texte."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Aucun JSON trouvé dans la réponse de Claude.")
    return json.loads(cleaned[start:end + 1])
