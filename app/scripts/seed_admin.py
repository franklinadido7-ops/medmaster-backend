"""
Crée le premier compte administrateur.

Usage (dans le conteneur API) :
    docker compose exec api python -m app.scripts.seed_admin

Le script demande un email et un mot de passe, puis crée (ou met à jour) un
utilisateur avec is_admin=True.
"""
import getpass

from app.database import SessionLocal
from app import models
from app.core.security import get_password_hash


def main():
    email = input("Email de l'administrateur : ").strip()
    password = getpass.getpass("Mot de passe : ").strip()

    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.hashed_password = get_password_hash(password)
            user.is_admin = True
            print(f"✅ Utilisateur existant '{email}' promu administrateur.")
        else:
            user = models.User(
                email=email,
                hashed_password=get_password_hash(password),
                full_name="Administrateur",
                is_admin=True,
            )
            db.add(user)
            print(f"✅ Compte administrateur '{email}' créé.")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
