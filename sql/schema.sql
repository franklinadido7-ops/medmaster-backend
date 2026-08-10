-- ════════════════════════════════════════════════════════════════════════════
-- MEDMASTER AI — SCHÉMA POSTGRESQL
-- Exécuté automatiquement au premier démarrage du conteneur postgres
-- ════════════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─── Utilisateurs ───────────────────────────────────────────────────────────
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255),
    university      VARCHAR(255),                 -- ex: "Faculté des Sciences de la Santé - UAC"
    study_level     VARCHAR(50),                   -- préclinique / externat / internat
    ref_mode        VARCHAR(50) DEFAULT 'International', -- 'Faculté' | 'International'
    rag_pref_user   INTEGER DEFAULT 80,            -- préférence pondération sources (somme = 100)
    rag_pref_base   INTEGER DEFAULT 15,
    rag_pref_ext    INTEGER DEFAULT 5,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── Documents importés par l'utilisateur ──────────────────────────────────
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        VARCHAR(500) NOT NULL,
    file_type       VARCHAR(20) NOT NULL,          -- pdf, docx, pptx, jpg, png...
    storage_path    VARCHAR(1000) NOT NULL,
    status          VARCHAR(50) DEFAULT 'uploaded', -- uploaded | processing | indexed | error
    chunk_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── Cours de référence officiels (base documentaire MedMaster) ────────────
CREATE TABLE reference_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           VARCHAR(500) NOT NULL,
    category        VARCHAR(100),                  -- cardiologie, pneumologie...
    ref_mode        VARCHAR(50) NOT NULL,           -- 'Faculté' | 'International'
    source_label    VARCHAR(255),                   -- ex: "HAS 2023", "OMS Guidelines"
    storage_path    VARCHAR(1000),
    chunk_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── Contenus générés enregistrés (bibliothèque) ───────────────────────────
CREATE TABLE library_items (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic           VARCHAR(500) NOT NULL,
    fiche_md        TEXT,                           -- fiche au format markdown
    flashcards      JSONB,                          -- [{q,a}, ...]
    qcm             JSONB,                          -- [{question, options, correct, explication}, ...]
    sources_pct     JSONB NOT NULL DEFAULT '{"user":80,"base":15,"ext":5}',
    sources_overridden BOOLEAN DEFAULT FALSE,       -- true si l'utilisateur a corrigé manuellement
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- ─── Paquets de flashcards (révision SM-2) ─────────────────────────────────
CREATE TABLE decks (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            VARCHAR(500) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE flashcards (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deck_id         UUID NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    -- Algorithme SM-2
    repetitions     INTEGER DEFAULT 0,
    ease_factor     REAL DEFAULT 2.5,
    interval_days   INTEGER DEFAULT 1,
    last_quality    SMALLINT,                       -- 0-5
    next_review     TIMESTAMPTZ DEFAULT now(),
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_flashcards_next_review ON flashcards(next_review);
CREATE INDEX idx_flashcards_deck ON flashcards(deck_id);

-- ─── Concepts / carte des connaissances ────────────────────────────────────
CREATE TABLE concepts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    external_id     VARCHAR(100),                   -- id généré par l'IA (pour les relations)
    label           VARCHAR(500) NOT NULL,
    category        VARCHAR(100),                   -- physiopathologie, traitement, diagnostic...
    mastery         REAL DEFAULT 0,                  -- 0.0 à 1.0
    related         JSONB DEFAULT '[]',              -- liste d'external_id liés
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_concepts_user ON concepts(user_id);

-- ─── Planning de révision généré par l'IA ──────────────────────────────────
CREATE TABLE study_plans (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    exam_date       DATE,
    plan_json       JSONB NOT NULL,                  -- {intro, days:[{date,title,tasks:[...]}]}
    generated_at    TIMESTAMPTZ DEFAULT now()
);

-- ─── Trigger pour updated_at automatique ───────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ─── Compte administrateur par défaut (à changer immédiatement) ────────────
-- Email: admin@medmaster.ai / Mot de passe: à définir via le script seed_admin.py
