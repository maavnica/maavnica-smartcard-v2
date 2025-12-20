from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from html import escape

from app.database import get_db
from app.models import Card, Feedback, Quote
from app.schemas import CardPublic, FeedbackCreate, QuoteCreate
from app.utils.emailer import send_email


router = APIRouter(prefix="/api/public", tags=["public"])


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


def _card_url(card: Card) -> str:
    return f"https://maavnica-smartcard-v2.onrender.com/c/{card.slug}"


def _base_email_html(title: str, subtitle: str, body_html: str, cta_url: str, cta_label: str) -> str:
    # HTML simple, responsive, compatible Gmail/mobile
    return f"""\
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background:#0b1220;font-family:Arial,Helvetica,sans-serif;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:linear-gradient(135deg,#0f172a,#111827);border:1px solid rgba(148,163,184,.25);border-radius:18px;overflow:hidden;">
      <div style="padding:18px 18px 10px 18px;border-bottom:1px solid rgba(148,163,184,.18);">
        <div style="font-size:12px;letter-spacing:.18em;color:#93c5fd;text-transform:uppercase;">
          Maavnica SmartCard
        </div>
        <div style="margin-top:8px;font-size:20px;line-height:1.2;color:#ffffff;font-weight:700;">
          {escape(title)}
        </div>
        <div style="margin-top:6px;font-size:13px;color:rgba(226,232,240,.85);">
          {escape(subtitle)}
        </div>
      </div>

      <div style="padding:18px;color:rgba(226,232,240,.92);font-size:14px;line-height:1.5;">
        {body_html}
        <div style="margin-top:18px;">
          <a href="{escape(cta_url)}"
             style="display:inline-block;padding:12px 14px;border-radius:12px;
                    background:#22c55e;color:#0b1220;text-decoration:none;font-weight:700;">
            {escape(cta_label)}
          </a>
        </div>
      </div>

      <div style="padding:14px 18px;border-top:1px solid rgba(148,163,184,.18);
                  color:rgba(148,163,184,.92);font-size:12px;">
        Vous recevez cet email car un prospect a interagi avec votre SmartCard.
      </div>
    </div>

    <div style="text-align:center;color:rgba(148,163,184,.72);font-size:11px;margin-top:14px;">
      © {escape("2025")} Maavnica — L'écosystème digital des indépendants.
    </div>
  </div>
</body>
</html>
"""


def notify_pro(background_tasks: BackgroundTasks, card: Card, subject: str, text: str, html: str) -> None:
    if not card.email_pro:
        return
    background_tasks.add_task(send_email, card.email_pro, subject, text, html)


@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(slug: str, db: Session = Depends(get_db)):
    return get_card_by_slug_or_404(slug, db)


@router.post("/cards/{card_id}/feedback", status_code=status.HTTP_201_CREATED)
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

    sat_label = "Positif 👍" if payload.satisfaction else "Négatif 👎"
    comment = payload.comment or "(Aucun commentaire)"

    # TEXTE (fallback)
    text = (
        "⭐ Nouvel avis reçu via votre SmartCard Maavnica\n\n"
        f"Entreprise : {card.company_name}\n"
        f"Carte : {_card_url(card)}\n\n"
        f"Satisfaction : {sat_label}\n"
        "Commentaire :\n"
        f"{comment}\n"
    )

    # HTML premium
    body_html = f"""
      <div style="margin:0 0 10px 0;">
        <b>Entreprise :</b> {escape(card.company_name)}<br/>
        <b>Carte :</b> <a href="{escape(_card_url(card))}" style="color:#93c5fd;text-decoration:none;">{escape(_card_url(card))}</a>
      </div>

      <div style="background:rgba(2,6,23,.35);border:1px solid rgba(148,163,184,.22);
                  border-radius:14px;padding:12px;">
        <div style="font-size:12px;color:rgba(148,163,184,.95);text-transform:uppercase;letter-spacing:.12em;">
          Avis client
        </div>
        <div style="margin-top:8px;font-size:14px;">
          <b>Satisfaction :</b> {escape(sat_label)}
        </div>
        <div style="margin-top:10px;">
          <b>Commentaire</b><br/>
          <div style="margin-top:6px;white-space:pre-wrap;color:rgba(226,232,240,.92);">
            {escape(comment)}
          </div>
        </div>
      </div>
    """

    html = _base_email_html(
        title="Nouvel avis reçu",
        subtitle="Un prospect a laissé un avis depuis votre SmartCard.",
        body_html=body_html,
        cta_url=_card_url(card),
        cta_label="Ouvrir la SmartCard",
    )

    notify_pro(
        background_tasks,
        card,
        subject=f"⭐ Nouvel avis – {card.company_name}",
        text=text,
        html=html,
    )

    return {"message": "Feedback created", "id": feedback.id}


@router.post("/cards/{card_id}/quotes", status_code=status.HTTP_201_CREATED)
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

    prospect_email = payload.email or "(non renseigné)"

    # TEXTE (fallback)
    text = (
        "📩 Nouvelle demande de devis via votre SmartCard Maavnica\n\n"
        f"Entreprise : {card.company_name}\n"
        f"Carte : {_card_url(card)}\n\n"
        "Coordonnées du prospect :\n"
        f"- Nom : {payload.name}\n"
        f"- Téléphone : {payload.phone}\n"
        f"- Email : {prospect_email}\n\n"
        "Message :\n"
        f"{payload.message}\n"
    )

    # HTML premium
    body_html = f"""
      <div style="margin:0 0 10px 0;">
        <b>Entreprise :</b> {escape(card.company_name)}<br/>
        <b>Carte :</b> <a href="{escape(_card_url(card))}" style="color:#93c5fd;text-decoration:none;">{escape(_card_url(card))}</a>
      </div>

      <div style="background:rgba(2,6,23,.35);border:1px solid rgba(148,163,184,.22);
                  border-radius:14px;padding:12px;">
        <div style="font-size:12px;color:rgba(148,163,184,.95);text-transform:uppercase;letter-spacing:.12em;">
          Demande de devis
        </div>

        <div style="margin-top:8px;font-size:14px;">
          <b>Nom :</b> {escape(payload.name)}<br/>
          <b>Téléphone :</b> {escape(payload.phone)}<br/>
          <b>Email :</b> {escape(payload.email or "—")}
        </div>

        <div style="margin-top:12px;">
          <b>Message</b><br/>
          <div style="margin-top:6px;white-space:pre-wrap;color:rgba(226,232,240,.92);">
            {escape(payload.message)}
          </div>
        </div>

        <div style="margin-top:12px;color:rgba(148,163,184,.92);font-size:12px;">
          Conseil : recontactez ce prospect rapidement pour maximiser vos chances.
        </div>
      </div>
    """

    html = _base_email_html(
        title="Nouvelle demande de devis",
        subtitle="Un prospect vous a envoyé une demande depuis votre SmartCard.",
        body_html=body_html,
        cta_url=_card_url(card),
        cta_label="Voir la SmartCard",
    )

    notify_pro(
        background_tasks,
        card,
        subject=f"📩 Nouvelle demande de devis – {card.company_name}",
        text=text,
        html=html,
    )

    return {"message": "Quote created", "id": quote.id}









