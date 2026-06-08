"""
Vérifie que la base (PostgreSQL Render ou SQLite locale) possède les colonnes
requises pour la génération OG SmartCard.

Usage :
  cd backend && python ../tools/verify_og_db_schema.py
  # ou avec DATABASE_URL Render (shell Render / CI)
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

REQUIRED_COLUMNS = (
    "google_rating",
    "google_review_count",
    "visual_theme",
    "avatar_url",
    "updated_at",
    "slug",
    "region",
    "expires_at",
)


def main() -> int:
    from sqlalchemy import inspect

    from app.database import engine, ensure_google_rating_columns

    dialect = engine.dialect.name
    print(f"[schema] dialect={dialect}")
    print(f"[schema] url={engine.url.render_as_string(hide_password=True)}")

    ensure_google_rating_columns()

    insp = inspect(engine)
    if not insp.has_table("cards"):
        print("[schema] ERREUR: table cards absente")
        return 1

    existing = {c["name"] for c in insp.get_columns("cards")}
    missing = [col for col in REQUIRED_COLUMNS if col not in existing]
    present = [col for col in REQUIRED_COLUMNS if col in existing]

    print("[schema] colonnes OK:", ", ".join(present))
    if missing:
        print("[schema] colonnes MANQUANTES:", ", ".join(missing))
        return 1

    print("[schema] toutes les colonnes OG requises sont présentes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
