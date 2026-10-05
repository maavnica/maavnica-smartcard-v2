from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import Response
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, sessionmaker
from html import escape

from app.database import get_db
from app.models import Card, Feedback, Quote, RecommendationEvent
from app.schemas import CardPublic, FeedbackCreate, QuoteCreate
from app.routers.cards import (
    _count_recommend_link_created,
    _ensure_owner_share_key,
    _serialize_card_public,
)
from app.utils.emailer import send_email, smartcard_mail_from
from app.utils.rate_limit import rate_limit_by_ip
from app.utils.recommender_display import build_recommender_display_name, effective_recommender_label
from app.utils.public_slug import sanitize_public_slug
from app.utils.preview_card import raise_if_preview_expired, raise_if_preview_writes
from app.services.notification_outbox import new_outbox, process_one
from app.services.quote_notifications import (
    deliver_quote_notification,
    resolve_notification_recipient,
)


router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger(__name__)


def get_card_by_id_or_404(card_id: int, db: Session) -> Card:
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def get_card_by_slug_or_404(slug: str, db: Session) -> Card:
    s = sanitize_public_slug(slug)
    card = (
        db.query(Card)
        .filter(func.lower(Card.slug) == s.lower())
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def _latest_recommender_row_for_token(
    db: Session, token: str, card_slug: str
) -> Optional[RecommendationEvent]:
    """
    Dernière ligne d'événement portant une identité humaine pour ce token,
    sur la même carte. Préfère recommend_link_created (où prénom/nom sont renseignés).
    Comparaison de token insensible à la casse (URL vs stockage).
    """
    tnorm = (token or "").strip().lower()
    slug = (card_slug or "").strip()
    if not tnorm or not slug:
        return None

    disp = RecommendationEvent.recommender_display_name
    fn = RecommendationEvent.recommender_first_name
    ln = RecommendationEvent.recommender_last_name
    has_human = or_(
        and_(disp.isnot(None), func.length(func.trim(disp)) > 0),
        and_(fn.isnot(None), func.length(func.trim(fn)) > 0),
        and_(ln.isnot(None), func.length(func.trim(ln)) > 0),
    )

    slug_norm = slug.lower()
    q = (
        db.query(RecommendationEvent)
        .filter(func.lower(RecommendationEvent.referrer_id) == tnorm)
        .filter(func.lower(RecommendationEvent.card_slug) == slug_norm)
    )

    row = (
        q.filter(RecommendationEvent.event_type == "recommend_link_created")
        .filter(has_human)
        .order_by(RecommendationEvent.id.desc())
        .first()
    )
    if row:
        return row
    return q.filter(has_human).order_by(RecommendationEvent.id.desc()).first()


def _sanitize_public_referrer_token(raw: Optional[str]) -> Optional[str]:
    """Aligné sur le client public-card (lettres, chiffres, tirets, underscores, max 64)."""
    if raw is None:
        return None
    s = "".join(ch for ch in str(raw).strip().lower() if ch.isalnum() or ch in "-_")[:64]
    return s or None


def _recommend_arrival_attribution(
    db: Session, token: Optional[str], card_slug: str
) -> Optional[str]:
    """
    Libellé affichable pour une arrivée via ?r= (données déjà stockées lors du recommend_link_created).
    Aucun nom inventé : null si jeton inconnu ou identité non humaine (ex. rec_* sans nom).
    """
    t = _sanitize_public_referrer_token(token)
    slug = (card_slug or "").strip()
    if not t or not slug:
        return None
    ev = _latest_recommender_row_for_token(db, t, slug)
    if not ev:
        return None
    reco_first = ev.recommender_first_name
    reco_last = ev.recommender_last_name
    stored = (ev.recommender_display_name or "").strip()
    reco_display = stored or build_recommender_display_name(reco_first, reco_last)
    label = effective_recommender_label(reco_display, t)
    if not label or label.strip() == "—":
        return None
    return label.strip()


def _card_url(card: Card) -> str:
    return f"https://maavnica-smartcard-v2.onrender.com/c/{card.slug}"


def _vcard_escape(s: str) -> str:
    """Échappe les caractères spéciaux pour vCard 3.0 (\\ ; \\n)."""
    if not s:
        return ""
    return (
        s.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _build_vcard(card: Card) -> str:
    """
    Construit une vCard (.vcf) à partir des champs existants du modèle Card.
    Utilise : company_name (nom complet), phone, email_pro, site_web.
    """
    # Nom complet : le modèle n'a pas first_name/last_name, on utilise company_name
    name = (card.company_name or "").strip()
    if not name:
        name = "SmartCard"
    n_escaped = _vcard_escape(name)
    fn_escaped = _vcard_escape(name)

    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{n_escaped};;;",
        f"FN:{fn_escaped}",
    ]
    if name:
        lines.append(f"ORG:{_vcard_escape(name)}")
    if card.phone and card.phone.strip():
        lines.append(f"TEL;TYPE=CELL,VOICE:{_vcard_escape(card.phone.strip())}")
    if card.email_pro and card.email_pro.strip():
        lines.append(f"EMAIL;TYPE=INTERNET:{_vcard_escape(card.email_pro.strip())}")
    if card.site_web and card.site_web.strip():
        lines.append(f"URL:{_vcard_escape(card.site_web.strip())}")
    lines.append("END:VCARD")

    return "\r\n".join(lines)


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


def _send_pro_notification(
    to_email: str,
    subject: str,
    text: str,
    html: str,
    reply_to: Optional[str],
    card_id: Optional[int],
) -> None:
    try:
        ok = send_email(
            to_email,
            subject,
            text,
            html,
            reply_to=reply_to,
            from_email=smartcard_mail_from() or None,
        )
    except Exception:
        logger.exception("[MAIL] notify_pro failed card_id=%s", card_id)
        return
    if ok:
        logger.info("[MAIL] notify_pro ok card_id=%s", card_id)
    else:
        logger.error("[MAIL] notify_pro failed card_id=%s", card_id)


def notify_pro(
    card: Card,
    subject: str,
    text: str,
    html: str,
    reply_to: Optional[str] = None,
) -> None:
    to_email = (card.email_pro or "").strip()
    if not to_email:
        logger.warning(
            "[MAIL] SKIP NO RECIPIENT card_id=%s",
            getattr(card, "id", None),
        )
        return
    rt = (reply_to or "").strip() or None
    try:
        _send_pro_notification(
            to_email,
            subject,
            text,
            html,
            rt,
            getattr(card, "id", None),
        )
    except Exception:
        logger.exception(
            "[MAIL] notify_pro failed card_id=%s",
            getattr(card, "id", None),
        )


@router.get("/cards/{slug}", response_model=CardPublic)
def get_public_card(
    slug: str,
    request: Request,
    o: Optional[str] = Query(None),
    r: Optional[str] = Query(None, description="Jeton ?r= pour libellé d’arrivée relationnelle (optionnel)"),
    db: Session = Depends(get_db),
):
    card = get_card_by_slug_or_404(slug, db)
    raise_if_preview_expired(card)
    if card.expires_at and card.expires_at <= datetime.utcnow():
        raise HTTPException(
            status_code=403,
            detail="Cette carte n’est actuellement plus active.",
        )
    _ensure_owner_share_key(db, card)
    base = _serialize_card_public(
        card,
        request,
        db,
        owner_query_key=o,
        recommendation_share_count=_count_recommend_link_created(db, card.slug),
    )
    arrival = _recommend_arrival_attribution(db, r, card.slug)
    if arrival is None:
        return base
    data = base.model_dump()
    data["recommend_arrival_attribution"] = arrival
    return CardPublic(**data)


@router.get("/cards/{slug}/vcard")
def get_vcard(slug: str, db: Session = Depends(get_db)):
    """Télécharge une vCard (.vcf) avec les infos principales de la carte."""
    card = get_card_by_slug_or_404(slug, db)
    raise_if_preview_expired(card)
    vcard = _build_vcard(card)
    filename = f"{card.slug}.vcf"
    return Response(
        content=vcard,
        media_type="text/vcard",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/cards/{card_id}/feedback", status_code=status.HTTP_201_CREATED)
def create_feedback(
    card_id: int,
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(5, 60)),
):
    card = get_card_by_id_or_404(card_id, db)
    raise_if_preview_writes(card)

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
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(5, 60)),
):
    card = get_card_by_id_or_404(card_id, db)
    raise_if_preview_writes(card)

    reco_first: Optional[str] = None
    reco_last: Optional[str] = None
    reco_display: Optional[str] = None
    if payload.source_type == "recommendation" and payload.referrer_id:
        ev = _latest_recommender_row_for_token(db, payload.referrer_id, card.slug)
        if ev:
            reco_first = ev.recommender_first_name
            reco_last = ev.recommender_last_name
            stored = (ev.recommender_display_name or "").strip()
            reco_display = stored or build_recommender_display_name(reco_first, reco_last)

    quote = Quote(
        card_id=card.id,
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
        source_type=payload.source_type,
        referrer_id=payload.referrer_id,
        recommender_first_name=reco_first,
        recommender_last_name=reco_last,
        recommender_display_name=reco_display,
    )
    db.add(quote)
    db.flush()
    outbox = new_outbox(
        quote_id=quote.id,
        recipient=resolve_notification_recipient(card),
    )
    db.add(outbox)
    db.commit()
    db.refresh(quote)
    db.refresh(outbox)

    try:
        outbox_sessions = sessionmaker(
            bind=db.get_bind(),
            autocommit=False,
            autoflush=False,
        )
        process_one(
            outbox_sessions,
            lambda job: deliver_quote_notification(
                job,
                session_factory=outbox_sessions,
            ),
            outbox_id=outbox.id,
        )
    except Exception:
        # Le devis et son outbox sont déjà commités : le prospect reçoit 201,
        # et le Cron / l'admin pourra reprendre cette notification.
        logger.exception(
            "[OUTBOX] immediate processing failed outbox_id=%s quote_id=%s",
            outbox.id,
            quote.id,
        )

    return {"message": "Quote created", "id": quote.id}









