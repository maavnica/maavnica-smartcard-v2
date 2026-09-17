"""Cartes preview génériques (proposition SmartCard, Local Finder, etc.).

Le mode preview est un statut explicite (`is_preview`), indépendant du slug
et du plan_type. Les cartes client (`is_preview=false`) restent inchangées.

`preview_origin` (ex. ``local_finder``) est strictement interne : il n’est
jamais exposé au visiteur public.

Interface minimale future — Local Finder appellera ``POST /api/cards/``
(authentification admin déjà en place) avec, en plus des champs carte
habituels :

    {
      "slug": "lf-preview-projinov-auxerre",
      "is_preview": true,
      "preview_origin": "local_finder",
      "preview_expires_at": "<ISO-8601 optionnel>",
      "company_name": "...",
      "visual_theme": "artisan",
      "profile": "artisan"
    }
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

PREVIEW_WRITE_BLOCKED_DETAIL = (
    "Cette proposition n’enregistre pas de demandes."
)
PREVIEW_EXPIRED_DETAIL = "Cette proposition n’est plus disponible."


def is_preview_card(card) -> bool:
    if card is None:
        return False
    return bool(getattr(card, "is_preview", False))


def is_preview_expired(card, now: Optional[datetime] = None) -> bool:
    if not is_preview_card(card):
        return False
    exp = getattr(card, "preview_expires_at", None)
    if exp is None:
        return False
    return exp <= (now or datetime.utcnow())


def raise_if_preview_expired(card) -> None:
    if is_preview_expired(card):
        raise HTTPException(status_code=403, detail=PREVIEW_EXPIRED_DETAIL)


def raise_if_preview_writes(card) -> None:
    if is_preview_card(card):
        raise HTTPException(
            status_code=403,
            detail=PREVIEW_WRITE_BLOCKED_DETAIL,
        )


def load_card_by_public_slug(db: Session, slug: Optional[str]):
    """Lookup carte par slug public. None si absent / erreur non bloquante."""
    from sqlalchemy import func

    from app.models import Card
    from app.utils.public_slug import sanitize_public_slug

    s = sanitize_public_slug(slug)
    if not s:
        return None
    try:
        return (
            db.query(Card)
            .filter(func.lower(Card.slug) == s.lower())
            .first()
        )
    except OperationalError:
        db.rollback()
        return None


def should_skip_preview_persistence(db: Session, slug: Optional[str]) -> bool:
    """True si le slug correspond à une carte preview (aucune écriture métier)."""
    return is_preview_card(load_card_by_public_slug(db, slug))
