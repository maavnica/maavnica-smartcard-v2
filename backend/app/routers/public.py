# backend/routers/public_cards.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Carte, Commentaire, Devis
from ..schemas import CardPublic, FeedbackCreate, QuoteCreate

router = APIRouter(
    prefix="/api/public",
    tags=["public"],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_card_by_id_or_404(card_id: int, db: Session) -> Carte:
    card = db.query(Carte).filter(Carte.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _get_card_by_slug_or_404(slug: str, db: Session) -> Carte:
    card = db.query(Carte).filter(Carte.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


# ---------------------------------------------------------------------------
# Public: récupération de la carte
# ---------------------------------------------------------------------------

@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)) -> CardPublic:
    return _get_card_by_slug_or_404(slug, db)


# ---------------------------------------------------------------------------
# Public: avis clients
# ---------------------------------------------------------------------------

@router.post("/cards/{card_id}/feedback", status_code=status.HTTP_201_CREATED)
def create_feedback(card_id: int, payload: FeedbackCreate, db: Session = Depends(get_db)):
    card = _get_card_by_id_or_404(card_id, db)

    comment = Commentaire(
        card_id=card.id,
        is_positive=payload.is_positive,
        comment=payload.comment,
        phone=payload.phone,
        email=payload.email,
    )

    db.add(comment)
    db.commit()

    return {"message": "Feedback created"}


# ---------------------------------------------------------------------------
# Public: demandes de devis
# ---------------------------------------------------------------------------

@router.post("/cards/{card_id}/quotes", status_code=status.HTTP_201_CREATED)
def create_quote(card_id: int, payload: QuoteCreate, db: Session = Depends(get_db)):
    card = _get_card_by_id_or_404(card_id, db)

    quote = Devis(
        card_id=card.id,
        fullname=payload.fullname,
        phone=payload.phone,
        email=payload.email,
        description=payload.description,
    )

    db.add(quote)
    db.commit()

    return {"message": "Quote created"}





