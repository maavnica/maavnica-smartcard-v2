from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter()


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

    # Mise à jour champ par champ
    for field, value in update_data.items():
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



