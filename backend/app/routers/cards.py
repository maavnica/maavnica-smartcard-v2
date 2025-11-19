from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

# Si dans main.py tu n'as pas de prefix, tu peux mettre :
# router = APIRouter(prefix="/api/cards", tags=["cards"])
# Sinon on laisse simple et le prefix est géré dans main.py.
router = APIRouter()


# -------------------------------------------------------------------
# CRÉATION D'UNE CARTE (ADMIN)
# -------------------------------------------------------------------
@router.post("/", response_model=schemas.CardOut, status_code=201)
def create_card(card: schemas.CardCreate, db: Session = Depends(get_db)):
    """
    Création d'une SmartCard.

    Pour l'instant on ne gère qu'un seul "propriétaire" de cartes,
    on force donc user_id = 1 pour satisfaire la contrainte NOT NULL.
    Le body correspond au schéma CardCreate.
    """
    db_card = models.Card(
        user_id=1,          # propriétaire par défaut
        **card.dict()
    )
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card


# -------------------------------------------------------------------
# MISE À JOUR D'UNE CARTE (ADMIN)
# -------------------------------------------------------------------
@router.put("/{card_id}", response_model=schemas.CardOut)
def update_card(
    card_id: int,
    card_in: schemas.CardUpdate,
    db: Session = Depends(get_db),
):
    """
    Met à jour une SmartCard existante.
    Utilisée par l'admin quand currentCardId est défini.
    """
    card = db.query(models.Card).get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    data = card_in.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


# -------------------------------------------------------------------
# RÉCUPÉRER UNE CARTE PAR SON SLUG (ADMIN)
# -------------------------------------------------------------------
@router.get("/by-slug/{slug}", response_model=schemas.CardOut)
def get_card_by_slug(slug: str, db: Session = Depends(get_db)):
    """
    Récupère une carte par son slug.
    Utilisée dans l'admin avec le bouton "Charger ma carte".
    """
    card = db.query(models.Card).filter(models.Card.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


# -------------------------------------------------------------------
# LISTE DES AVIS (ADMIN)
# -------------------------------------------------------------------
@router.get(
    "/{card_id}/feedback",
    response_model=List[schemas.FeedbackOut],
)
def list_feedback(card_id: int, db: Session = Depends(get_db)):
    """
    Liste tous les avis rapides liés à une carte.
    Affiché dans la colonne droite de l'admin.
    """
    card = db.query(models.Card).get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    feedbacks = (
        db.query(models.Feedback)
        .filter(models.Feedback.card_id == card_id)
        .order_by(models.Feedback.created_at.desc())
        .all()
    )
    return feedbacks


# -------------------------------------------------------------------
# LISTE DES DEMANDES DE DEVIS (ADMIN)
# -------------------------------------------------------------------
@router.get(
    "/{card_id}/quotes",
    response_model=List[schemas.QuoteOut],
)
def list_quotes(card_id: int, db: Session = Depends(get_db)):
    """
    Liste toutes les demandes de devis liées à une carte.
    Affiché dans la colonne droite de l'admin.
    """
    card = db.query(models.Card).get(card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    quotes = (
        db.query(models.Quote)
        .filter(models.Quote.card_id == card_id)
        .order_by(models.Quote.created_at.desc())
        .all()
    )
    return quotes



