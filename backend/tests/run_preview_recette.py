"""Recette locale du mode preview — SQLite dédiée, hors production.

Usage (depuis la racine du dépôt, PowerShell) :

    $env:DATABASE_URL = "sqlite:///" + (Resolve-Path backend/tests/_preview_recette.db).Path.Replace('\\','/')
    python backend/tests/run_preview_recette.py
    cd backend
    python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.models import Base  # noqa: E402
from tests.preview_card_fixtures import (  # noqa: E402
    CLIENT_SLUG,
    PREVIEW_ARTISAN_SLUG,
    PREVIEW_LONG_TITLE_SLUG,
    PREVIEW_THERAPIST_SLUG,
    seed_preview_safety_cards,
)

RECETTE_DB = Path(__file__).resolve().parent / "_preview_recette.db"


def main() -> None:
    if RECETTE_DB.exists():
        RECETTE_DB.unlink()
    engine = create_engine(f"sqlite:///{RECETTE_DB}")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        seed_preview_safety_cards(session)
    finally:
        session.close()
        engine.dispose()
    posix = RECETTE_DB.resolve().as_posix()
    print("Recette SQLite prête (aucune base de production) :")
    print(f"  {posix}")
    print()
    print("Cartes de recette :")
    print(f"  artisan preview   http://127.0.0.1:8765/c/{PREVIEW_ARTISAN_SLUG}")
    print(f"  titre long        http://127.0.0.1:8765/c/{PREVIEW_LONG_TITLE_SLUG}")
    print(f"  therapist preview http://127.0.0.1:8765/c/{PREVIEW_THERAPIST_SLUG}")
    print(f"  client normale    http://127.0.0.1:8765/c/{CLIENT_SLUG}")
    print()
    print("Ensuite, dans PowerShell :")
    print(f'  $env:DATABASE_URL = "sqlite:///{posix}"')
    print("  cd backend")
    print("  python -m uvicorn app.main:app --host 127.0.0.1 --port 8765")


if __name__ == "__main__":
    main()
