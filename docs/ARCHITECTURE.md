# 🏗️ Architecture technique — MedMaster AI

## 1. Vue d'ensemble

Le backend suit une architecture **monolithique modulaire** avec FastAPI :
simple à déployer (un seul service), mais organisée en modules clairs
(`routers/`, `rag/`, `core/`) pour faciliter une future séparation en
microservices si nécessaire.

```
medmaster-backend/
├── docker-compose.yml      ← orchestration des 3 services (api, postgres, qdrant)
├── Dockerfile               ← image de l'API
├── requirements.txt
├── .env.example
├── sql/schema.sql           ← schéma PostgreSQL complet
├── docs/                    ← documentation (ce dossier)
└── app/
    ├── main.py               ← point d'entrée FastAPI
    ├── config.py             ← variables d'environnement (pydantic-settings)
    ├── database.py           ← connexion SQLAlchemy
    ├── models.py              ← tables ORM
    ├── schemas.py             ← schémas Pydantic (requêtes/réponses API)
    ├── sm2.py                 ← algorithme de répétition espacée
    ├── core/
    │   ├── security.py         ← JWT, hashing, dépendances d'auth
    │   └── claude_client.py    ← wrapper Anthropic
    ├── rag/
    │   ├── embeddings.py       ← génération d'embeddings (OpenAI)
    │   ├── qdrant_client.py    ← gestion des collections vectorielles
    │   ├── document_processor.py ← extraction texte + découpage en chunks
    │   └── ingest.py            ← pipeline complet d'indexation + récupération
    └── routers/
        ├── auth.py
        ├── documents.py
        ├── generate.py
        ├── decks.py
        ├── library.py
        ├── assistant.py
        ├── concepts.py
        ├── planning.py
        └── admin.py
```

---

## 2. Architecture RAG hiérarchisée (cœur du cahier des charges)

Le cahier des charges impose un ordre de priorité strict pour les sources
d'information utilisées par l'IA :

```
1. Documents envoyés par l'utilisateur        ← priorité maximale
2. Base documentaire officielle (cours validés)
3. Sources externes médicales validées
4. Génération pure (connaissances du modèle)
```

### Comment c'est implémenté

**Deux collections Qdrant distinctes** :
- `medmaster_user_docs` : un point par chunk de document utilisateur, avec
  `payload.user_id` pour filtrer (chaque étudiant ne voit que ses propres
  documents).
- `medmaster_reference_docs` : un point par chunk de cours de référence
  officiel, avec `payload.ref_mode` ("Faculté" ou "International") pour
  filtrer selon le mode actif de l'étudiant.

**Lors d'une génération ou d'une question à l'assistant** (`app/rag/ingest.py`,
fonction `retrieve_context`) :
1. La requête est transformée en vecteur (embedding).
2. Recherche dans `medmaster_user_docs` filtrée par `user_id` → **niveau 1**.
3. Recherche dans `medmaster_reference_docs` filtrée par `ref_mode` → **niveau 2**.
4. Les deux résultats sont injectés dans le prompt envoyé à Claude, avec des
   instructions explicites de priorisation (niveau 1 > niveau 2 > connaissances
   générales = niveaux 3-4).

**Transparence des sources** : Claude renvoie un champ `sources` (`{user, base,
ext}`, somme = 100) reflétant la répartition réelle utilisée. Une estimation
initiale est calculée côté backend (`_build_context_block` dans
`routers/generate.py`) selon ce qui a été trouvé dans Qdrant, et Claude
l'affine dans sa réponse finale.

---

## 3. Préférences de pondération & correction manuelle

Deux mécanismes complémentaires (déjà présents dans le frontend, à connecter
au backend) :

- **Préférences** (`users.rag_pref_user/base/ext`) : l'étudiant indique une
  répartition cible. Elle est injectée dans le prompt ("rapproche-toi de cette
  répartition SI le contenu le permet") — n'altère jamais la véracité de
  l'origine réelle.
- **Override manuel** (`library_items.sources_pct` +
  `sources_overridden`) : l'étudiant peut corriger après coup les % affichés
  pour un contenu sauvegardé, via `PATCH /library/{id}/sources`.

---

## 4. Algorithme SM-2 (répétition espacée)

Implémenté dans `app/sm2.py`, identique à la version JavaScript du prototype
frontend (même formules), pour garantir un comportement cohérent si le
frontend bascule du calcul local vers le backend.

- `quality` (0 à 5) : qualité du rappel par l'étudiant
- Calcule `repetitions`, `ease_factor`, `interval_days`, `next_review`
- Endpoint : `POST /decks/cards/{card_id}/review`

---

## 5. Authentification

JWT (JSON Web Tokens) via `python-jose` :
- `POST /auth/register` : création de compte (email + mot de passe haché bcrypt)
- `POST /auth/login` : retourne un `access_token` (valide 7 jours par défaut)
- Toutes les routes protégées attendent `Authorization: Bearer <token>`
- `is_admin=True` sur un utilisateur débloque les routes `/admin/*`

---

## 6. Génération de contenu (`POST /generate`)

1. Récupère le contexte RAG hiérarchisé pour les documents sélectionnés.
2. Construit un prompt structuré incluant :
   - le contexte par niveau (avec labels de source),
   - les préférences de pondération de l'utilisateur,
   - le mode de référence actif (Faculté / International),
   - le format JSON exact attendu (topic, sources, fiche, flashcards, qcm, concepts).
3. Appelle Claude, parse le JSON, retourne la réponse typée
   (`schemas.GenerateResponse`).

Le frontend peut ensuite :
- Sauvegarder le résultat via `POST /library`
- Créer un paquet de révision via `POST /decks` (avec les flashcards)
- Envoyer les `concepts` à `POST /concepts/bulk` pour la carte des connaissances

---

## 7. Assistant IA (`POST /assistant/chat`)

Même logique RAG que la génération, appliquée à la dernière question de
l'utilisateur. Le system prompt intègre le contexte documentaire, le mode de
référence (avec mention explicite du contexte Bénin/CEDEAO), et les
préférences de pondération.

---

## 8. Planning intelligent (`POST /planning/generate`)

Récupère :
- le nombre de cartes SM-2 dues par paquet,
- les concepts avec `mastery < 0.5` (lacunes),
- la date d'examen optionnelle (`exam_date`),

... et demande à Claude un programme de révision sur 7 jours, sauvegardé dans
`study_plans` pour historique.

---

## 9. Points d'extension futurs

- **Notifications push** : un job planifié (ex: Celery + Redis, ou simple cron)
  pourrait vérifier quotidiennement `flashcards.next_review <= now()` par
  utilisateur et déclencher une notification mobile (Flutter → Firebase Cloud
  Messaging).
- **QCM adaptatif** : actuellement les QCM sont générés statiquement par
  thème. Un futur algorithme pourrait sélectionner les questions selon le
  niveau de maîtrise des concepts liés (`concepts.mastery`).
- **Stockage S3/R2** : `app/routers/documents.py` est conçu pour basculer
  facilement de stockage local vers S3 (variables `.env` déjà prévues).
- **Migrations Alembic** : `alembic` est inclus dans `requirements.txt` mais
  non configuré — recommandé dès que le schéma évoluera après la mise en
  production (éviter de modifier `sql/schema.sql` directement sur une base
  existante).
