from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.core.security import get_current_user
from app.core.claude_client import call_claude, extract_json
from app.rag.ingest import retrieve_context

router = APIRouter(prefix="/generate", tags=["Génération IA"])


def _build_context_block(retrieval: dict) -> tuple[str, dict]:
    """
    Construit le bloc de contexte hiérarchisé pour le prompt, et calcule
    une estimation initiale des % de sources en fonction de ce qui a été
    trouvé (affinée ensuite par Claude dans sa réponse).
    """
    user_chunks = retrieval["user_chunks"]
    base_chunks = retrieval["base_chunks"]

    blocks = []
    if user_chunks:
        blocks.append("### NIVEAU 1 — Documents de l'étudiant (PRIORITÉ MAXIMALE)\n" +
                       "\n---\n".join(c["text"] for c in user_chunks))
    if base_chunks:
        labels = ", ".join(sorted({c.get("source_label", "Base MedMaster") for c in base_chunks}))
        blocks.append(f"### NIVEAU 2 — Base documentaire MedMaster ({labels})\n" +
                       "\n---\n".join(c["text"] for c in base_chunks))

    context_text = "\n\n".join(blocks) if blocks else "(Aucun document indexé trouvé — utilise tes connaissances médicales générales et indique-le dans 'sources'.)"

    # Estimation grossière par défaut (Claude affinera dans sa réponse JSON)
    if user_chunks and base_chunks:
        estimate = {"user": 60, "base": 30, "ext": 10}
    elif user_chunks:
        estimate = {"user": 85, "base": 10, "ext": 5}
    elif base_chunks:
        estimate = {"user": 0, "base": 80, "ext": 20}
    else:
        estimate = {"user": 0, "base": 10, "ext": 90}

    return context_text, estimate


@router.post("", response_model=schemas.GenerateResponse)
def generate_content(
    payload: schemas.GenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not (payload.generate_fiche or payload.generate_flashcards or payload.generate_qcm):
        raise HTTPException(status_code=400, detail="Sélectionnez au moins un type de contenu à générer.")

    ref_mode = payload.ref_mode or current_user.ref_mode
    rag_prefs = payload.rag_prefs or schemas.RagPrefs(
        user=current_user.rag_pref_user,
        base=current_user.rag_pref_base,
        ext=current_user.rag_pref_ext,
    )

    # Construit une requête de récupération à partir des documents sélectionnés
    docs = (
        db.query(models.Document)
        .filter(models.Document.id.in_(payload.document_ids), models.Document.user_id == current_user.id)
        .all()
    )
    if not docs:
        raise HTTPException(status_code=404, detail="Aucun document valide trouvé pour cet utilisateur.")

    query_text = " ".join(d.filename for d in docs)
    retrieval = retrieve_context(db, current_user.id, query_text, ref_mode=ref_mode)
    context_text, estimate = _build_context_block(retrieval)

    json_spec_parts = [
        '"topic":"titre court du sujet"',
        f'"sources":{{"user":{estimate["user"]},"base":{estimate["base"]},"ext":{estimate["ext"]}}}',
    ]
    if payload.generate_fiche:
        json_spec_parts.append('"fiche":"## Titre\\n\\n### Section\\n- Point 1\\n- Point 2\\n**Clé à retenir**"')
    else:
        json_spec_parts.append('"fiche":null')

    if payload.generate_flashcards:
        json_spec_parts.append(
            '"flashcards":[{"q":"Question 1","a":"Réponse 1"},{"q":"Question 2","a":"Réponse 2"},'
            '{"q":"Question 3","a":"Réponse 3"},{"q":"Question 4","a":"Réponse 4"},'
            '{"q":"Question 5","a":"Réponse 5"},{"q":"Question 6","a":"Réponse 6"}]'
        )
    else:
        json_spec_parts.append('"flashcards":null')

    if payload.generate_qcm:
        json_spec_parts.append(
            '"qcm":[{"question":"Q1","options":["A","B","C","D"],"correct":0,"explication":"Expl"},'
            '{"question":"Q2","options":["A","B","C","D"],"correct":1,"explication":"Expl"},'
            '{"question":"Q3","options":["A","B","C","D"],"correct":2,"explication":"Expl"},'
            '{"question":"Q4","options":["A","B","C","D"],"correct":0,"explication":"Expl"},'
            '{"question":"Q5","options":["A","B","C","D"],"correct":3,"explication":"Expl"}],'
            '"concepts":[{"id":"c1","label":"Concept A","category":"physiopathologie","mastery":0.2,"related":["c2"]},'
            '{"id":"c2","label":"Concept B","category":"traitement","mastery":0.5,"related":["c1"]}]'
        )
    else:
        json_spec_parts.append('"qcm":null,"concepts":[]')

    prompt = f"""Tu es MedMaster AI, assistant pédagogique médical. Voici le contexte documentaire disponible,
classé par ordre de priorité (architecture RAG hiérarchisée) :

{context_text}

CONSIGNES :
- Le niveau 1 (documents de l'étudiant) doit toujours être privilégié s'il est pertinent.
- Le niveau 2 (base MedMaster) complète si le niveau 1 est insuffisant.
- Si aucun niveau n'est suffisant, complète avec tes connaissances médicales validées (sources externes).
- L'étudiant a indiqué une préférence de répartition souhaitée : Cours utilisateur {rag_prefs.user}% ·
  Base MedMaster {rag_prefs.base}% · Sources externes {rag_prefs.ext}%. Rapproche-toi en de cette
  répartition dans le champ "sources" SI le contenu disponible le permet raisonnablement — ne mens
  jamais sur l'origine réelle des informations utilisées.
- Mode de référence actif : {ref_mode} (Bénin/CEDEAO + référentiels internationaux si "International").
- Réponds UNIQUEMENT avec ce JSON (sans markdown, sans backticks), en français :

{{{",".join(json_spec_parts)}}}
"""

    raw = call_claude([{"role": "user", "content": prompt}], max_tokens=4500)
    try:
        parsed = extract_json(raw)
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=502, detail=f"Erreur de génération IA : {exc}")

    return parsed
