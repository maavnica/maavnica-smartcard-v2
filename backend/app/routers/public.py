from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, Feedback, Quote
from app.schemas import CardPublic, FeedbackCreate, QuoteCreate
from app.utils.emailer import send_email


router = APIRouter(
    prefix="/api/public",
    tags=["public"],
)

# =============================================================
# Helpers
# =============================================================

def get_card_by_id_or_404(card_id: int, db: Session) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def get_card_by_slug_or_404(slug: str, db: Session) -> Card:
    card = db.query(Card).filter(Card.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def notify_pro(
    background_tasks: BackgroundTasks,
    card: Card,
    subject: str,
    message: str,
):
    if not card.email_pro:
        return
    background_tasks.add_task(
        send_email,
        card.email_pro,
        subject,
        message,
    )

# =============================================================
# Carte publique (GET)
# =============================================================

@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)):
    return get_card_by_slug_or_404(slug, db)

# =============================================================
# Avis client (POST)
# =============================================================

@router.post(
    "/cards/{card_id}/feedback",
    status_code=status.HTTP_201_CREATED,
)
def create_feedback(
    card_id: int,
    payload: FeedbackCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    card = get_card_by_id_or_404(card_id, db)

    feedback = Feedback(
        card_id=card.id,
        satisfaction=payload.satisfaction,
        comment=payload.comment,
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # 🔔 Email au pro
    notify_pro(
        background_tasks,
        card,
        subject=f"🔔 Nouvel avis sur votre SmartCard – {card.company_name}",
        message=(
            f"Vous avez reçu un nouvel avis.\n\n"
            f"Satisfaction : {'Oui' if payload.satisfaction else 'Non'}\n"
            f"Commentaire : {payload.comment or '(aucun)'}\n\n"
            f"Carte : https://maavnica-smartcard-v2.onrender.com/c/{card.slug}"
        ),
    )

    return {"message": "Feedback created", "id": feedback.id}

# =============================================================
# Demande de devis (POST)
# =============================================================

@router.post(
    "/cards/{card_id}/quotes",
    status_code=status.HTTP_201_CREATED,
)
def create_quote(
    card_id: int,
    payload: QuoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    card = get_card_by_id_or_404(card_id, db)

    quote = Quote(
        card_id=card.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
    )

    db.add(quote)
    db.commit()
    db.refresh(quote)

    # 🔔 Email au pro
    notify_pro(
        background_tasks,
        card,
        subject=f"📩 Nouvelle demande de devis – {card.company_name}",
        message=(
            f"Nouvelle demande de devis reçue.\n\n"
            f"Nom : {payload.name}\n"
            f"Téléphone : {payload.phone}\n"
            f"Email : {payload.email or '(non renseigné)'}\n\n"
            f"Message :\n{payload.message}\n\n"
            f"Carte : https://maavnica-smartcard-v2.onrender.com/c/{card.slug}"
        ),
    )

    return {"message": "Quote created", "id": quote.id}








