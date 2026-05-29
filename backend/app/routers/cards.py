import secrets
from datetime import datetime, timedelta
import math
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .. import models, schemas
from app.schemas import _ALLOWED_VISUAL_THEMES
from ..database import (
    get_db,
    read_card_visual_theme,
    read_card_visual_theme_by_slug,
    write_card_visual_theme,
)
from app.utils.admin_auth import admin_bearer_matches, require_admin_api_key
from app.utils.public_slug import sanitize_public_slug

router = APIRouter()

# ============================================================
#  PROFILS METIERS AUTORISÉS
# ============================================================
ALLOWED_PROFILES = {
    "artisan",
    "digital",
    "bien_etre",
    "medical",
    "immo",
    "resto",
    "generic",
}
ALLOWED_PLAN_TYPES = {"demo", "lifetime", "trial", "solo", "business"}


def _normalize_visual_theme(value) -> str:
    if value is None:
        return "wellness-soft"
    s = str(value).strip().lower()
    if s in _ALLOWED_VISUAL_THEMES:
        return s
    return "wellness-soft"


def _read_visual_theme(card: models.Card, db: Session) -> str:
    slug = getattr(card, "slug", None)
    if slug:
        sql_slug = read_card_visual_theme_by_slug(db, slug)
        if sql_slug:
            return _normalize_visual_theme(sql_slug)
    cid = getattr(card, "id", None)
    if cid is not None:
        sql_val = read_card_visual_theme(db, cid)
        if sql_val:
            return _normalize_visual_theme(sql_val)
    raw = getattr(card, "visual_theme", None) if hasattr(card, "visual_theme") else None
    if raw is not None and str(raw).strip():
        return _normalize_visual_theme(raw)
    return "wellness-soft"


def _persist_visual_theme(db: Session, card: models.Card, theme: str) -> None:
    safe = _normalize_visual_theme(theme)
    if hasattr(card, "visual_theme"):
        card.visual_theme = safe
    write_card_visual_theme(db, card.id, safe)


def _card_payload(card: schemas.CardCreate) -> dict:
    """Payload CardCreate (Pydantic v2)."""
    return card.model_dump()


def _card_update_payload(card_in: schemas.CardUpdate) -> dict:
    return card_in.model_dump(exclude_unset=True)


def _default_expiration_for_plan(plan_type: str) -> Optional[datetime]:
    now = datetime.utcnow()
    if plan_type == "trial":
        return now + timedelta(days=30)
    if plan_type in {"solo", "business"}:
        return now + timedelta(days=365)
    return None


def _is_card_expired(card: models.Card) -> bool:
    if not card.expires_at:
        return False
    return card.expires_at <= datetime.utcnow()


def _computed_status(card: models.Card) -> str:
    return "expired" if _is_card_expired(card) else "active"


def _days_remaining(card: models.Card) -> Optional[int]:
    if not card.expires_at:
        return None
    remaining_seconds = (card.expires_at - datetime.utcnow()).total_seconds()
    if remaining_seconds <= 0:
        return 0
    # Affichage admin lisible: toute fraction de journée restante compte pour 1 jour.
    return max(1, math.ceil(remaining_seconds / 86400))


def _card_to_public_dict(card: models.Card, db: Session) -> dict:
    """Construit le dict CardPublic sans lire owner_share_key depuis l’ORM (évite toute fuite)."""
    d = {}
    for name in schemas.CardPublic.model_fields:
        if name in ("owner_mode", "owner_share_key", "recommendation_share_count"):
            continue
        if hasattr(card, name):
            d[name] = getattr(card, name)
    theme = d.get("card_theme")
    if not theme or not str(theme).strip():
        d["card_theme"] = "classic"
    else:
        d["card_theme"] = str(theme).strip().lower()
    d["visual_theme"] = _read_visual_theme(card, db)
    return d


def _ensure_owner_share_key(db: Session, card: models.Card) -> None:
    if card.owner_share_key and str(card.owner_share_key).strip():
        return
    card.owner_share_key = secrets.token_urlsafe(10)
    db.commit()
    db.refresh(card)


def _count_recommend_link_created(db: Session, card_slug: str) -> int:
    """Compte les partages de lien traçable (?r=…) pour cette carte (métrique produit « recommandé »)."""
    try:
        return (
            db.query(models.RecommendationEvent)
            .filter(
                models.RecommendationEvent.card_slug == card_slug,
                models.RecommendationEvent.event_type == "recommend_link_created",
            )
            .count()
        )
    except OperationalError:
        db.rollback()
        return 0


def _serialize_card_public(
    card: models.Card,
    request: Request,
    db: Session,
    *,
    owner_query_key: Optional[str] = None,
    recommendation_share_count: int = 0,
) -> schemas.CardPublic:
    stored = (card.owner_share_key or "").strip()
    owner_mode = False
    if owner_query_key:
        o_stripped = owner_query_key.strip()
        if stored and o_stripped:
            owner_mode = secrets.compare_digest(stored, o_stripped)
    d = _card_to_public_dict(card, db)
    if not d.get("plan_type"):
        d["plan_type"] = "demo"
    r = d.get("region")
    if r is None or not str(r).strip():
        d["region"] = "fr"
    else:
        d["region"] = str(r).strip().lower()
    if "expires_at" not in d:
        d["expires_at"] = None
    base = schemas.CardPublic.model_validate(d)
    out = base.model_dump()
    out["computed_status"] = _computed_status(card)
    out["days_remaining"] = _days_remaining(card)
    out["owner_mode"] = owner_mode
    out["owner_share_key"] = card.owner_share_key if admin_bearer_matches(request) else None
    out["recommendation_share_count"] = recommendation_share_count
    return schemas.CardPublic(**out)


# ============================================================
#  CRÉATION D'UNE CARTE (ADMIN)
# ============================================================
@router.post(
    "/",
    response_model=schemas.CardPublic,
    status_code=status.HTTP_201_CREATED,
)
def create_card(
    card: schemas.CardCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
) -> schemas.CardPublic:

    # Vérifie si le slug existe déjà
    existing = (
        db.query(models.Card)
        .filter(models.Card.slug == card.slug)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ce slug est déjà utilisé par une autre carte.",
        )

    # Vérifier profil métier
    if card.profile not in ALLOWED_PROFILES:
        raise HTTPException(
            status_code=400,
            detail=f"Profil métier invalide. Profils autorisés : {', '.join(ALLOWED_PROFILES)}",
        )

    if card.plan_type not in ALLOWED_PLAN_TYPES:
        raise HTTPException(status_code=400, detail="plan_type invalide.")
    if card.plan_type in {"trial", "solo", "business"} and card.expires_at is None:
        fallback_exp = _default_expiration_for_plan(card.plan_type)
        payload = _card_payload(card)
        payload["expires_at"] = fallback_exp
    else:
        payload = _card_payload(card)

    # IMPORTANT : on force user_id = 1 pour cette V1
    db_card = models.Card(
        user_id=1,
        owner_share_key=secrets.token_urlsafe(10),
        **payload,
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    return _serialize_card_public(
        db_card,
        request,
        db,
        recommendation_share_count=_count_recommend_link_created(db, db_card.slug),
    )


# ============================================================
#  MISE À JOUR D'UNE CARTE (ADMIN)
# ============================================================
@router.put(
    "/{card_id}",
    response_model=schemas.CardPublic,
)
def update_card(
    card_id: int,
    card_in: schemas.CardUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
) -> schemas.CardPublic:

    db_card = (
        db.query(models.Card)
        .filter(models.Card.id == card_id)
        .first()
    )
    if not db_card:
        raise HTTPException(
            status_code=404,
            detail="Card not found",
        )

    update_data = _card_update_payload(card_in)
    # Garantir la persistance de region si le client l'envoie (évite tout écart exclude_unset / proxy).
    if "region" in card_in.model_fields_set:
        r = card_in.region
        update_data["region"] = r if r is not None else "fr"
    # Même principe que region pour card_theme (rendu /c/{slug}).
    if "card_theme" in card_in.model_fields_set:
        t = (card_in.card_theme or "classic").strip().lower()
        update_data["card_theme"] = t if t in ("classic", "experience") else "classic"
    visual_theme_to_persist: Optional[str] = None
    if "visual_theme" in card_in.model_fields_set:
        visual_theme_to_persist = _normalize_visual_theme(card_in.visual_theme)
        update_data["visual_theme"] = visual_theme_to_persist
    elif "visual_theme" in update_data:
        visual_theme_to_persist = _normalize_visual_theme(update_data.get("visual_theme"))
        update_data["visual_theme"] = visual_theme_to_persist
    # Même principe que region pour city (SEO local).
    if "city" in card_in.model_fields_set:
        update_data["city"] = card_in.city

    # Vérifier que le profil envoyé est autorisé
    if "profile" in update_data:
        profile = update_data["profile"]
        if profile not in ALLOWED_PROFILES:
            raise HTTPException(
                status_code=400,
                detail=f"Profil métier invalide. Profils autorisés : {', '.join(ALLOWED_PROFILES)}",
            )
    plan_type_before = db_card.plan_type or "demo"
    if "plan_type" in update_data:
        plan_type = update_data["plan_type"]
        if plan_type not in ALLOWED_PLAN_TYPES:
            raise HTTPException(status_code=400, detail="plan_type invalide.")
    else:
        plan_type = db_card.plan_type

    if plan_type in {"demo", "lifetime"}:
        update_data["expires_at"] = None
    if (
        plan_type in {"trial", "solo", "business"}
        and "expires_at" not in update_data
        and db_card.expires_at is None
    ):
        update_data["expires_at"] = _default_expiration_for_plan(plan_type)
    # Conversion commerciale simple : trial -> solo/business sans date fournie = +1 an.
    if (
        plan_type in {"solo", "business"}
        and plan_type_before == "trial"
        and "expires_at" not in update_data
    ):
        update_data["expires_at"] = _default_expiration_for_plan(plan_type)
    if plan_type in {"trial", "solo", "business"} and update_data.get("expires_at") is None:
        raise HTTPException(
            status_code=400,
            detail="expires_at est requis pour trial/solo/business.",
        )

    # Empêcher un nouveau slug qui existerait déjà
    if "slug" in update_data and update_data["slug"] != db_card.slug:
        slug_exists = (
            db.query(models.Card)
            .filter(models.Card.slug == update_data["slug"])
            .first()
        )
        if slug_exists:
            raise HTTPException(
                status_code=400,
                detail="Ce nouveau slug est déjà utilisé par une autre carte.",
            )

    # Mise à jour champ par champ
    for field, value in update_data.items():
        if field == "visual_theme":
            continue
        # Sécurité : éviter d'injecter un champ inexistant
        if hasattr(db_card, field):
            setattr(db_card, field, value)

    if visual_theme_to_persist is not None:
        _persist_visual_theme(db, db_card, visual_theme_to_persist)

    db.commit()
    db.refresh(db_card)
    _ensure_owner_share_key(db, db_card)
    return _serialize_card_public(
        db_card,
        request,
        db,
        recommendation_share_count=_count_recommend_link_created(db, db_card.slug),
    )


# ============================================================
#  RÉCUPÉRER UNE CARTE PAR SLUG (PUBLIC — page /c/{slug})
# ============================================================
@router.get(
    "/by-slug/{slug}",
    response_model=schemas.CardPublic,
)
def get_card_by_slug(
    slug: str,
    request: Request,
    o: Optional[str] = Query(
        None,
        description="Clé personnelle mode propriétaire (voir lien dans l’admin). Ne pas envoyer aux clients.",
    ),
    db: Session = Depends(get_db),
) -> schemas.CardPublic:

    s = sanitize_public_slug(slug)
    card = (
        db.query(models.Card)
        .filter(func.lower(models.Card.slug) == s.lower())
        .first()
    )
    if not card:
        raise HTTPException(
            status_code=404,
            detail="Card not found",
        )
    _ensure_owner_share_key(db, card)
    return _serialize_card_public(
        card,
        request,
        db,
        owner_query_key=o,
        recommendation_share_count=_count_recommend_link_created(db, card.slug),
    )


@router.get("/", response_model=List[schemas.CardPublic])
def list_cards(
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
) -> List[schemas.CardPublic]:
    cards = db.query(models.Card).order_by(models.Card.created_at.desc()).all()
    return [
        _serialize_card_public(
            c,
            request,
            db,
            recommendation_share_count=_count_recommend_link_created(db, c.slug),
        )
        for c in cards
    ]


# ============================================================
#  LISTE DES AVIS (ADMIN)
# ============================================================
@router.get(
    "/{card_id}/feedback",
    response_model=List[schemas.FeedbackOut],
)
def list_feedback(
    card_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
) -> List[schemas.FeedbackOut]:

    card_exists = (
        db.query(models.Card)
        .filter(models.Card.id == card_id)
        .first()
    )
    if not card_exists:
        raise HTTPException(status_code=404, detail="Card not found")

    return (
        db.query(models.Feedback)
        .filter(models.Feedback.card_id == card_id)
        .order_by(models.Feedback.created_at.desc())
        .all()
    )


# ============================================================
#  LISTE DES DEMANDES DE DEVIS (ADMIN)
# ============================================================
@router.get(
    "/{card_id}/quotes",
    response_model=List[schemas.QuoteOut],
)
def list_quotes(
    card_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_api_key),
) -> List[schemas.QuoteOut]:

    card_exists = (
        db.query(models.Card)
        .filter(models.Card.id == card_id)
        .first()
    )
    if not card_exists:
        raise HTTPException(status_code=404, detail="Card not found")

    return (
        db.query(models.Quote)
        .filter(models.Quote.card_id == card_id)
        .order_by(models.Quote.created_at.desc())
        .all()
    )



