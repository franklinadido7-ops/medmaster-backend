# 🩺 MedMaster AI — Backend

Backend de l'application **MedMaster AI**, destinée aux étudiants en médecine,
pharmacie et odontologie (Bénin / Afrique de l'Ouest).

## ⚡ Démarrage rapide

```bash
cp .env.example .env
# → remplir SECRET_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY dans .env

docker compose up -d

# Créer le premier compte administrateur
docker compose exec api python -m app.scripts.seed_admin
```

Puis ouvrez **http://localhost:8000/docs** pour tester l'API.

## 📚 Documentation

- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) — guide pas-à-pas (installation, test, déploiement)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — fonctionnement détaillé (RAG hiérarchisé, SM-2, etc.)

## 🧱 Stack technique

| Composant | Technologie |
|---|---|
| API | FastAPI (Python) |
| Base relationnelle | PostgreSQL |
| Base vectorielle (RAG) | Qdrant |
| Génération IA | Anthropic Claude |
| Embeddings (RAG) | OpenAI |
| Conteneurisation | Docker / Docker Compose |

## ✅ Fonctionnalités couvertes

- Authentification (inscription / connexion JWT)
- Import de documents (PDF, Word, PowerPoint, images) + indexation RAG
- Génération de fiches, flashcards et QCM (architecture RAG hiérarchisée)
- Révision espacée SM-2 (paquets, cartes, notation, calcul du prochain rappel)
- Bibliothèque de contenus sauvegardés (avec correction manuelle des sources)
- Assistant IA pédagogique conversationnel (mode Faculté / National & International)
- Carte des connaissances (concepts + niveau de maîtrise)
- Planning de révision intelligent généré par IA
- Interface d'administration (gestion des cours de référence, utilisateurs, statistiques)

## ⚠️ Sécurité avant mise en production

- [ ] Changer `SECRET_KEY` et les mots de passe PostgreSQL par défaut
- [ ] Restreindre `allow_origins` (CORS) dans `app/main.py`
- [ ] Mettre en place HTTPS (reverse proxy Caddy/Traefik)
- [ ] Sauvegardes régulières du volume PostgreSQL
