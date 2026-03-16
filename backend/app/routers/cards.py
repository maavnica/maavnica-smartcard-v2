from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

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
    db: Session = Depends(get_db),
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
        **card.dict(),
    )

    db.add(db_card)
    db.commit()
    db.refresh(db_card)

    return db_card


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
    db: Session = Depends(get_db),
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

    update_data = card_in.dict(exclude_unset=True)

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
    return db_card


# ============================================================
#  RÉCUPÉRER UNE CARTE PAR SLUG (ADMIN)
# ============================================================
@router.get(
    "/by-slug/{slug}",
    response_model=schemas.CardPublic,
)
def get_card_by_slug(
    slug: str,
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
    return card


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



