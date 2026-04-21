import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from app.utils.admin_auth import admin_bearer_matches, require_admin_api_key

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


def _card_payload(card: schemas.CardCreate) -> dict:
    """Pydantic v2 : model_dump() ; v1 : dict()."""
    if hasattr(card, "model_dump"):
        return card.model_dump()
    return card.dict()


def _card_update_payload(card_in: schemas.CardUpdate) -> dict:
    if hasattr(card_in, "model_dump"):
        return card_in.model_dump(exclude_unset=True)
    return card_in.dict(exclude_unset=True)


def _card_to_public_dict(card: models.Card) -> dict:
    """Construit le dict CardPublic sans lire owner_share_key depuis l’ORM (évite toute fuite)."""
    d = {}
    for name in schemas.CardPublic.model_fields:
        if name in ("owner_mode", "owner_share_key", "recommendation_share_count"):
            continue
        if hasattr(card, name):
            d[name] = getattr(card, name)
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
    d = _card_to_public_dict(card)
    base = schemas.CardPublic.model_validate(d)
    out = base.model_dump()
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

    # IMPORTANT : on force user_id = 1 pour cette V1
    db_card = models.Card(
        user_id=1,
        owner_share_key=secrets.token_urlsafe(10),
        **_card_payload(card),
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    return _serialize_card_public(
        db_card,
        request,
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

    # Vérifier que le profil envoyé est autorisé
    if "profile" in update_data:
        profile = update_data["profile"]
        if profile not in ALLOWED_PROFILES:
            raise HTTPException(
                status_code=400,
                detail=f"Profil métier invalide. Profils autorisés : {', '.join(ALLOWED_PROFILES)}",
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
        # Sécurité : éviter d'injecter un champ inexistant
        if hasattr(db_card, field):
            setattr(db_card, field, value)

    db.commit()
    db.refresh(db_card)
    _ensure_owner_share_key(db, db_card)
    return _serialize_card_public(
        db_card,
        request,
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

    card = (
        db.query(models.Card)
        .filter(models.Card.slug == slug)
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
        owner_query_key=o,
        recommendation_share_count=_count_recommend_link_created(db, card.slug),
    )


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



