# 🚀 Guide d'installation — MedMaster AI Backend

Ce document explique comment installer, lancer et déployer le backend de
MedMaster AI. Il est destiné au développeur qui prendra en charge la mise en
production.

---

## 1. Vue d'ensemble de l'architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Frontend        │────▶│   API FastAPI    │────▶│   PostgreSQL    │
│  (React / Flutter)│     │   (port 8000)    │     │   (port 5432)   │
└─────────────────┘     └────────┬─────────┘     └─────────────────┘
                                  │
                                  ▼
                          ┌──────────────────┐
                          │   Qdrant (RAG)   │
                          │   (port 6333)    │
                          └──────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │  Anthropic Claude (génération) │
                    │  OpenAI (embeddings)            │
                    └─────────────────────────────┘
```

- **PostgreSQL** : stocke les utilisateurs, documents, flashcards, bibliothèque, etc.
- **Qdrant** : base vectorielle pour le RAG (recherche de passages pertinents).
- **API FastAPI** : logique métier, authentification, appels IA.
- **Claude (Anthropic)** : génération des fiches, flashcards, QCM, assistant IA.
- **OpenAI** : uniquement pour générer les embeddings (vecteurs) du RAG.

---

## 2. Prérequis

- [Docker](https://www.docker.com/products/docker-desktop/) installé (Docker Desktop sur Windows/Mac, ou Docker Engine sur Linux)
- Une clé API **Anthropic** : https://console.anthropic.com/
- Une clé API **OpenAI** (pour les embeddings uniquement) : https://platform.openai.com/

Aucune autre installation n'est nécessaire — Docker s'occupe de PostgreSQL, Qdrant et Python.

---

## 3. Installation en local (développement)

### Étape 1 — Configuration

```bash
cd medmaster-backend
cp .env.example .env
```

Ouvrez le fichier `.env` et remplissez :
- `SECRET_KEY` : une chaîne aléatoire longue (générez-la avec `openssl rand -hex 32`)
- `ANTHROPIC_API_KEY` : votre clé Claude
- `OPENAI_API_KEY` : votre clé OpenAI

### Étape 2 — Lancement

```bash
docker compose up -d
```

Cette commande télécharge et lance automatiquement :
- PostgreSQL (avec le schéma de base de données déjà créé)
- Qdrant
- L'API FastAPI

### Étape 3 — Vérification

- API : http://localhost:8000 → doit retourner `{"status":"ok",...}`
- **Documentation interactive** (très utile pour tester) : http://localhost:8000/docs
- Dashboard Qdrant : http://localhost:6333/dashboard

### Étape 4 — Créer le premier compte administrateur

```bash
docker compose exec api python -m app.scripts.seed_admin
```

Suivez les instructions (email + mot de passe).

---

## 4. Tester l'API sans coder

Rendez-vous sur **http://localhost:8000/docs** : chaque endpoint peut être testé
directement depuis le navigateur (bouton "Try it out").

Parcours de test recommandé :
1. `POST /auth/register` → créer un compte étudiant
2. `POST /auth/login` → récupérer un token (cliquez sur "Authorize" en haut de
   la page et collez le token pour activer les endpoints protégés)
3. `POST /documents/upload` → importer un PDF de cours
4. `POST /generate` → générer fiche/flashcards/QCM à partir de ce document
5. `POST /assistant/chat` → poser une question à l'assistant IA

---

## 5. Connecter les applications clientes

### Application Flutter (recommandée — incluse dans `medmaster_flutter/`)

L'application Flutter fournie dans ce même dossier (`../medmaster_flutter/`)
est **déjà câblée** pour consommer cette API : tous les appels réseau sont
centralisés dans `medmaster_flutter/lib/services/api_client.dart`.

Étapes :
1. Démarrez ce backend (`docker compose up -d`).
2. Vérifiez/ajustez `medmaster_flutter/lib/services/api_config.dart`
   (voir `medmaster_flutter/README.md` pour les valeurs selon l'environnement :
   émulateur Android, simulateur iOS, Web, téléphone physique, production).
3. `cd ../medmaster_flutter && flutter pub get && flutter run -d chrome`

L'authentification JWT, la génération RAG, le SM-2, la bibliothèque, le
planning et les préférences de pondération sont déjà reliés aux bons endpoints.

### Prototype React (web, fourni précédemment)

Le prototype React appelle actuellement directement l'API Anthropic depuis le
navigateur. Pour le connecter à ce backend :

1. Remplacez les appels `fetch("https://api.anthropic.com/v1/messages", ...)`
   par des appels vers votre API, par exemple :
   - `POST http://localhost:8000/generate` (au lieu d'appeler Claude directement)
   - `POST http://localhost:8000/assistant/chat`
2. Ajoutez la gestion du token JWT (stocké après `/auth/login`) dans l'en-tête
   `Authorization: Bearer <token>` de chaque requête.
3. Le stockage local (`window.storage`) peut être progressivement remplacé par
   les endpoints `/library`, `/decks`, `/concepts`.

---

## 6. Déploiement en production

### Option simple — VPS unique (recommandé pour démarrer)

Un serveur cloud (ex: Hetzner, DigitalOcean, OVH, Contabo — à partir de ~5-10€/mois)
avec Docker installé peut faire tourner `docker compose up -d` directement.

Étapes supplémentaires en production :
1. **Changez tous les mots de passe par défaut** (`docker-compose.yml`, `.env`)
2. Mettez un **reverse proxy HTTPS** devant l'API (ex: [Caddy](https://caddyserver.com/)
   ou [Traefik](https://traefik.io/) — génèrent automatiquement les certificats SSL)
3. Restreignez `allow_origins` dans `app/main.py` au(x) domaine(s) du frontend
4. Sauvegardez régulièrement le volume `postgres_data` (ex: `pg_dump` planifié)

### Option stockage cloud (S3 / R2)

Par défaut, les fichiers importés sont stockés sur le disque du serveur
(`STORAGE_BACKEND=local`). Pour utiliser Cloudflare R2 ou Amazon S3 (recommandé
si plusieurs serveurs / forte volumétrie), il faudra étendre
`app/routers/documents.py` pour utiliser un client S3 (boto3) — les variables
`.env` correspondantes (`S3_BUCKET`, `S3_ENDPOINT_URL`, etc.) sont déjà prévues.

---

## 7. Alimenter la base documentaire MedMaster (cours de référence)

En tant qu'administrateur, utilisez `POST /admin/reference-documents` (visible
dans `/docs` une fois connecté avec un compte admin) pour ajouter des PDF de
référence :
- **Mode Faculté** : polycopiés et cours de votre université
- **Mode International** : protocoles OMS, recommandations ESC/AHA, guides
  CEDEAO/Bénin, etc.

Chaque document est automatiquement découpé, vectorisé et indexé dans Qdrant.
L'assistant et la génération de contenu les utiliseront ensuite selon la
hiérarchie RAG (documents utilisateur > base MedMaster > connaissances générales).

---

## 8. Coûts à anticiper

| Service | Usage | Coût approximatif |
|---|---|---|
| Serveur cloud (VPS) | Hébergement complet | ~5-20 €/mois selon trafic |
| API Anthropic (Claude) | Génération de contenu + assistant | Facturation à l'usage (tokens) |
| API OpenAI (embeddings) | Indexation RAG uniquement | Très faible coût (modèle "small") |

💡 Conseil : commencez avec un petit VPS et surveillez l'usage des API IA via
les tableaux de bord Anthropic/OpenAI pour ajuster le budget.

---

## 9. Support

Pour toute question sur l'architecture de ce code, consultez également
`docs/ARCHITECTURE.md` qui détaille le fonctionnement du RAG hiérarchisé et
les choix techniques effectués.
