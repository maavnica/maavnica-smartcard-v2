# backend/routers/public_cards.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Card, Feedback, Quote   # <-- corrigé
from ..schemas import CardPublic, FeedbackCreate, QuoteCreate

router = APIRouter(
    prefix="/api/public",
    tags=["public"],
)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _get_card_by_id_or_404(card_id: int, db: Session) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _get_card_by_slug_or_404(slug: str, db: Session) -> Card:
    card = db.query(Card).filter(Card.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


# ---------------------------------------------------------
# Récupération de carte publique
# ---------------------------------------------------------

@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)):
    return _get_card_by_slug_or_404(slug, db)


# ---------------------------------------------------------
# Feedback / Avis clients
# ---------------------------------------------------------

@router.post("/cards/{card_id}/feedback", status_code=status.HTTP_201_CREATED)
def create_feedback(card_id: int, payload: FeedbackCreate, db: Session = Depends(get_db)):

    card = _get_card_by_id_or_404(card_id, db)

    fb = Feedback(
        card_id=card.id,
        satisfaction=payload.satisfaction,
        comment=payload.comment
    )

    db.add(fb)
    db.commit()
    db.refresh(fb)

    return {"message": "Feedback created", "id": fb.id}


# ---------------------------------------------------------
# Demande de devis
# ---------------------------------------------------------

@router.post("/cards/{card_id}/quotes", status_code=status.HTTP_201_CREATED)
def create_quote(card_id: int, payload: QuoteCreate, db: Session = Depends(get_db)):

    card = _get_card_by_id_or_404(card_id, db)

    q = Quote(
        card_id=card.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
    )

    db.add(q)
    db.commit()
    db.refresh(q)

    return {"message": "Quote created", "id": q.id}






