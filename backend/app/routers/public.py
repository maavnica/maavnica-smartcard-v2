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

    satisfaction_label = "👍 Positif" if payload.satisfaction else "👎 Négatif"

    email_message = (
        "⭐ NOUVEL AVIS REÇU VIA VOTRE SMARTCARD MAAVNICA\n\n"
        f"Entreprise : {card.company_name}\n"
        f"Carte : https://maavnica-smartcard-v2.onrender.com/c/{card.slug}\n\n"
        f"Satisfaction : {satisfaction_label}\n"
        f"Commentaire :\n"
        f"{payload.comment or '(Aucun commentaire laissé)'}\n\n"
        "—\n"
        "Maavnica SmartCard\n"
        "Vous recevez cet email car un client a interagi avec votre carte."
    )

    notify_pro(
        background_tasks,
        card,
        subject=f"⭐ Nouvel avis reçu – {card.company_name}",
        message=email_message,
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

    email_message = (
        "📩 NOUVELLE DEMANDE DE DEVIS VIA VOTRE SMARTCARD MAAVNICA\n\n"
        f"Entreprise : {card.company_name}\n"
        f"Carte : https://maavnica-smartcard-v2.onrender.com/c/{card.slug}\n\n"
        "Coordonnées du prospect :\n"
        f"- Nom : {payload.name}\n"
        f"- Téléphone : {payload.phone}\n"
        f"- Email : {payload.email or '(non renseigné)'}\n\n"
        "Message du prospect :\n"
        f"{payload.message}\n\n"
        "👉 Conseil : recontactez rapidement ce prospect pour maximiser vos chances.\n\n"
        "—\n"
        "Maavnica SmartCard"
    )

    notify_pro(
        background_tasks,
        card,
        subject=f"📩 Nouvelle demande de devis – {card.company_name}",
        message=email_message,
    )

    return {"message": "Quote created", "id": quote.id}








