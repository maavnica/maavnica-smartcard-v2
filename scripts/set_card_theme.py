#!/usr/bin/env python3
"""
Bascule le thème de rendu public d'une carte (classic | experience).

Usage:
  python scripts/set_card_theme.py demo2 experience
  python scripts/set_card_theme.py demo2 classic
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal, ensure_card_theme_column  # noqa: E402
from app.models import Card  # noqa: E402

_ALLOWED = {"classic", "experience"}


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__.strip())
        return 1

    slug = sys.argv[1].strip().lower()
    theme = sys.argv[2].strip().lower()
    if theme not in _ALLOWED:
        print(f"Thème invalide : {theme!r} (classic | experience)")
        return 1

    ensure_card_theme_column()
    db = SessionLocal()
    try:
        card = db.query(Card).filter(func.lower(Card.slug) == slug).first()
        if not card:
            print(f"Carte introuvable : {slug!r}")
            return 1
        card.card_theme = theme
        db.commit()
        print(f"OK — {slug} → card_theme={theme}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
