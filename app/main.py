from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app import models  # noqa: F401 — assure l'enregistrement des modèles
from app.routers import auth, documents, generate, decks, library, assistant, concepts, planning, admin

# Crée les tables si elles n'existent pas encore (complément du sql/schema.sql)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="MedMaster AI — API",
    description=(
        "Backend de l'application MedMaster AI : import de cours, génération IA "
        "(fiches, flashcards, QCM), révision espacée SM-2, assistant pédagogique, "
        "planning intelligent et architecture RAG hiérarchisée."
    ),
    version="1.0.0",
)

# CORS — autorise le frontend (React / Flutter Web) à appeler l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ à restreindre en production (domaine du frontend)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(generate.router)
app.include_router(decks.router)
app.include_router(library.router)
app.include_router(assistant.router)
app.include_router(concepts.router)
app.include_router(planning.router)
app.include_router(admin.router)


@app.get("/", tags=["Santé"])
def health_check():
    return {"status": "ok", "service": "MedMaster AI API"}
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="/app/static"), name="static")
