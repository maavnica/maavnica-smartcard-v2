# app/routes/public_cards.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db

from models import Card, Feedback, Quote
from schemas import CardPublic, FeedbackCreate, QuoteCreate

router = APIRouter(
    prefix="/api/public",
    tags=["public"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_card_by_id_or_404(card_id: int, db: Session) -> Card:
    """Récupère une carte par id ou renvoie une 404."""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _get_card_by_slug_or_404(slug: str, db: Session) -> Card:
    """Récupère une carte par slug ou renvoie une 404."""
    card = db.query(Card).filter(Card.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


# ---------------------------------------------------------------------------
# Public: récupération de la carte
# ---------------------------------------------------------------------------

@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)) -> CardPublic:
    """
    Retourne les informations publiques d'une carte à partir de son slug.

    Utilisé par la page publique `/c/{slug}` qui fait un fetch vers
    `/api/public/cards/{slug}`.
    """
    card = _get_card_by_slug_or_404(slug, db)
    return card


# ---------------------------------------------------------------------------
# Public: avis clients
# ---------------------------------------------------------------------------

@router.post(
    "/cards/{card_id}/feedback",
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    card_id: int,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Crée un avis (satisfait / pas satisfait + commentaire optionnel)
    pour une carte donnée.
    """
    card = _get_card_by_id_or_404(card_id, db)

    feedback = Feedback(
        card_id=card.id,
        is_positive=payload.is_positive,
        comment=payload.comment,
        phone=payload.phone,
        email=payload.email,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {"message": "Feedback created"}


# ---------------------------------------------------------------------------
# Public: demandes de devis
# ---------------------------------------------------------------------------

@router.post(
    "/cards/{card_id}/quotes",
    status_code=status.HTTP_201_CREATED,
)
def create_quote(
    card_id: int,
    payload: QuoteCreate,
    db: Session = Depends(get_db),
) -> dict:
    """
    Crée une demande de devis liée à une carte.
    """
    card = _get_card_by_id_or_404(card_id, db)

    quote = Quote(
        card_id=card.id,
        fullname=payload.fullname,
        phone=payload.phone,
        email=payload.email,
        description=payload.description,
    )

    db.add(quote)
    db.commit()
    db.refresh(quote)

    return {"message": "Quote created"}




