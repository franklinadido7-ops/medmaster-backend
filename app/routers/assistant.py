from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user
from app.core.claude_client import call_claude
from app.rag.ingest import retrieve_context

router = APIRouter(prefix="/assistant", tags=["Assistant IA"])


@router.post("/chat", response_model=schemas.ChatResponse)
def chat(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    ref_mode = payload.ref_mode or current_user.ref_mode
    rag_prefs = payload.rag_prefs or schemas.RagPrefs(
        user=current_user.rag_pref_user,
        base=current_user.rag_pref_base,
        ext=current_user.rag_pref_ext,
    )

    last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")

    # Récupération RAG sur la dernière question pour enrichir le contexte
    retrieval = retrieve_context(db, current_user.id, last_user_msg, ref_mode=ref_mode)
    context_chunks = []
    if retrieval["user_chunks"]:
        context_chunks.append(
            "Extraits pertinents des cours de l'étudiant :\n" +
            "\n---\n".join(c["text"] for c in retrieval["user_chunks"][:4])
        )
    if retrieval["base_chunks"]:
        context_chunks.append(
            "Extraits pertinents de la base documentaire MedMaster :\n" +
            "\n---\n".join(c["text"] for c in retrieval["base_chunks"][:4])
        )
    context_block = "\n\n".join(context_chunks)

    system = f"""Tu es MedMaster AI, assistant pédagogique médical expert en mode "{ref_mode}".
Tu aides les étudiants en médecine, pharmacie et odontologie au Bénin et en Afrique de l'Ouest.
Réponds en français, de manière structurée et pédagogique, avec des exemples cliniques concrets.

En mode International, appuie-toi sur les recommandations de l'OMS, les protocoles nationaux du
Bénin/CEDEAO et les référentiels internationaux (ESC, AHA, etc.), en tenant compte du contexte
sanitaire local.

Préférence de pondération des sources indiquée par l'étudiant : cours utilisateur {rag_prefs.user}%,
base documentaire MedMaster {rag_prefs.base}%, sources externes {rag_prefs.ext}%. Tiens-en compte
autant que possible sans jamais inventer une origine.

Architecture RAG — contexte documentaire disponible pour cette question (priorise le niveau 1,
complète avec le niveau 2, puis tes connaissances générales si nécessaire) :

{context_block if context_block else "(Aucun document indexé pertinent — réponds avec tes connaissances médicales validées.)"}

Tu n'as qu'un rôle pédagogique : reste centré sur l'enseignement médical."""

    messages = [{"role": m.role, "content": m.content} for m in payload.messages if m.role in ("user", "assistant")]
    reply = call_claude(messages, system=system, max_tokens=1500)

    # Estimation de la répartition des sources pour cette réponse (transparence)
    if retrieval["user_chunks"] and retrieval["base_chunks"]:
        sources = schemas.RagPrefs(user=55, base=30, ext=15)
    elif retrieval["user_chunks"]:
        sources = schemas.RagPrefs(user=80, base=10, ext=10)
    elif retrieval["base_chunks"]:
        sources = schemas.RagPrefs(user=0, base=70, ext=30)
    else:
        sources = schemas.RagPrefs(user=0, base=20, ext=80)

    return schemas.ChatResponse(reply=reply, sources=sources)
