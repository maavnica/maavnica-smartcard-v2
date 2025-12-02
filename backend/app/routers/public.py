from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..utils.qrcode_utils import get_or_create_qr_for_slug

router = APIRouter()


# =============================================================
#  CARTE PUBLIQUE
# =============================================================

@router.get("/cards/{slug}", response_model=schemas.CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)) -> schemas.CardPublic:
    """
    Récupère une SmartCard publique à partir de son slug.

    Utilisée par /c/{slug} pour afficher la carte.
    On renvoie aussi theme, theme_color et le profil métier
    pour gérer le rendu visuel côté front.
    """
    card = (
        db.query(models.Card)
        .filter(models.Card.slug == slug)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    qr_url = get_or_create_qr_for_slug(slug)

    return schemas.CardPublic(
        id=card.id,
        company_name=card.company_name,
        slug=card.slug,

        # 🔹 Nouveaux champs profil / contact pro
        profile=(card.profile or "artisan"),
        email_pro=card.email_pro,
        site_web=card.site_web,

        google_review_link=card.google_review_link,
        phone=card.phone,
        whatsapp=card.whatsapp,
        payment_link=card.payment_link,
        instagram=card.instagram,
        facebook=card.facebook,
        tiktok=card.tiktok,
        theme=card.theme,
        theme_color=card.theme_color,
        qr_url=qr_url,
        created_at=card.created_at,
        updated_at=card.updated_at,
    )


# =============================================================
#  AVIS RAPIDES (public)
# =============================================================

@router.post(
    "/cards/{slug}/feedback",
    response_model=schemas.FeedbackOut,
    status_code=201,
)
def create_feedback(
    slug: str,
    feedback: schemas.FeedbackCreate,
    db: Session = Depends(get_db),
) -> schemas.FeedbackOut:
    """
    Création d’un avis rapide (satisfait / pas satisfait + commentaire optionnel)
    pour la carte correspondant au slug.
    """
    card = (
        db.query(models.Card)
        .filter(models.Card.slug == slug)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    db_feedback = models.Feedback(
        card_id=card.id,
        satisfaction=feedback.satisfaction,
        comment=feedback.comment,
    )
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


# =============================================================
#  DEMANDES DE DEVIS (public)
# =============================================================

@router.post(
    "/cards/{slug}/quote",
    response_model=schemas.QuoteOut,
    status_code=201,
)
def create_quote(
    slug: str,
    quote: schemas.QuoteCreate,
    db: Session = Depends(get_db),
) -> schemas.QuoteOut:
    """
    Création d’une demande de devis publique pour la carte liée à ce slug.
    """
    card = (
        db.query(models.Card)
        .filter(models.Card.slug == slug)
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    db_quote = models.Quote(
        card_id=card.id,
        name=quote.name,
        email=quote.email,
        phone=quote.phone,
        message=quote.message,
    )
    db.add(db_quote)
    db.commit()
    db.refresh(db_quote)
    return db_quote



