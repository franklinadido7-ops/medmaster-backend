from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Sécurité
    SECRET_KEY: str = "MedMaster2026BeninadicLongueChaine123456789"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 jours

    # Base de données
    DATABASE_URL: str = "postgresql://medmaster:medmaster_password_change_me@localhost:5432/medmaster"

    # Qdrant (RAG)
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION_USER: str = "medmaster_user_docs"
    QDRANT_COLLECTION_REFERENCE: str = "medmaster_reference_docs"

    # IA
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    EMBEDDING_MODEL: str = "text-embedding-3-small"  # 1536 dimensions

    # Stockage fichiers
    STORAGE_BACKEND: str = "local"   # "local" | "s3"
    UPLOAD_DIR: str = "/app/uploads"
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_REGION: str = "auto"

    # RAG — découpage des documents
    CHUNK_SIZE: int = 800        # tokens approx. par chunk
    CHUNK_OVERLAP: int = 100     # chevauchement entre chunks
    RAG_TOP_K: int = 6           # nombre de passages récupérés par requête

    class Config:
        env_file = ".env"


settings = Settings()
