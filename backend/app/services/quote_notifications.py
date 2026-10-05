"""Construction et livraison des notifications de demandes de devis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Optional

from app.database import SessionLocal
from app.models import Card, Quote
from app.services.notification_outbox import (
    DeliveryOutcome,
    NotificationJob,
)
from app.utils.emailer import send_email_result, smartcard_mail_from
from app.utils.recommender_display import effective_recommender_label


@dataclass(frozen=True)
class QuoteNotificationMessage:
    subject: str
    text: str
    html: str
    reply_to: Optional[str]


def resolve_notification_recipient(card: Card) -> Optional[str]:
    """Adresse privée si définie, sinon adresse professionnelle publique."""
    private = (getattr(card, "notification_email", None) or "").strip()
    public = (getattr(card, "email_pro", None) or "").strip()
    return private or public or None


def _norm_profile(profile: str | None) -> str:
    value = (profile or "").strip().lower()
    value = (
        value.replace("é", "e")
        .replace("è", "e")
        .replace("ê", "e")
        .replace("à", "a")
        .replace("ç", "c")
    )
    return re.sub(r"\s+", " ", value)


def lead_labels_for_profile(profile: str | None) -> dict:
    profile_norm = _norm_profile(profile)
    devis_keywords = {
        "artisan", "plombier", "electricien", "chauffagiste", "clim",
        "climatisation", "menuisier", "serrurier", "carreleur", "macon",
        "peintre", "couvreur", "charpentier", "vitrier", "jardinier",
        "paysagiste", "renovation", "renov", "btp", "garage", "garagiste",
        "mecanicien", "mecanique", "depannage", "travaux", "intervention",
        "installateur",
    }
    if any(keyword in profile_norm for keyword in devis_keywords):
        return {
            "title": "Nouvelle demande de devis",
            "subject_prefix": "📩 Nouvelle demande de devis",
            "section_label": "Demande de devis",
            "subtitle": (
                "Un prospect vous a envoyé une demande de devis "
                "depuis votre SmartCard."
            ),
            "cta": "Voir la demande",
        }

    rdv_keywords = {
        "coiffeur", "coiffeuse", "barbier", "estheticienne", "esthetique",
        "beaute", "massage", "kine", "osteopathe", "osteo", "therapeute",
        "naturopathe", "coach sportif", "bien etre", "spa", "onglerie",
    }
    if any(keyword in profile_norm for keyword in rdv_keywords):
        return {
            "title": "Nouvelle demande de rendez-vous",
            "subject_prefix": "📅 Nouvelle demande de rendez-vous",
            "section_label": "Demande de rendez-vous",
            "subtitle": (
                "Un prospect souhaite prendre rendez-vous via votre SmartCard."
            ),
            "cta": "Voir la demande",
        }

    if any(
        keyword in profile_norm
        for keyword in {
            "restaurant", "brasserie", "snack", "traiteur", "hotel", "bar", "cafe",
        }
    ):
        return {
            "title": "Nouvelle demande de réservation",
            "subject_prefix": "🍽️ Nouvelle demande de réservation",
            "section_label": "Demande de réservation",
            "subtitle": "Un prospect a demandé une réservation via votre SmartCard.",
            "cta": "Voir la demande",
        }

    if any(
        keyword in profile_norm
        for keyword in {
            "immobilier", "agent immobilier", "agence immobiliere", "syndic",
            "location", "vente",
        }
    ):
        return {
            "title": "Nouvelle demande d’information",
            "subject_prefix": "🏠 Nouvelle demande d’information",
            "section_label": "Demande d’information",
            "subtitle": "Un prospect vous a contacté via votre SmartCard.",
            "cta": "Voir la demande",
        }

    return {
        "title": "Nouvelle demande de contact / démo",
        "subject_prefix": "📨 Nouvelle demande de contact / démo",
        "section_label": "Demande de contact / démo",
        "subtitle": "Un prospect vous a contacté via votre SmartCard.",
        "cta": "Voir le contact",
    }


def _card_url(card: Card) -> str:
    return f"https://maavnica-smartcard-v2.onrender.com/c/{card.slug}"


def _base_email_html(
    title: str,
    subtitle: str,
    body_html: str,
    cta_url: str,
    cta_label: str,
) -> str:
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


def build_quote_notification(card: Card, quote: Quote) -> QuoteNotificationMessage:
    labels = lead_labels_for_profile(card.profile)
    prospect_email = quote.email or "(non renseigné)"
    reco_label = effective_recommender_label(
        quote.recommender_display_name,
        quote.referrer_id,
    )
    is_recommendation = quote.source_type == "recommendation"
    origin = "recommandation" if is_recommendation else "directe / autre"
    recommended_by = reco_label if is_recommendation else "—"
    text = (
        f"{labels['title']} via votre SmartCard Maavnica\n\n"
        f"Entreprise : {card.company_name}\n"
        f"Carte : {_card_url(card)}\n"
        f"Métier (profil) : {card.profile or '(non renseigné)'}\n\n"
        "Coordonnées du prospect :\n"
        f"- Nom : {quote.name}\n"
        f"- Téléphone : {quote.phone or '(non renseigné)'}\n"
        f"- Email : {prospect_email}\n\n"
        f"- Origine : {origin}\n"
        f"- Recommandé par : {recommended_by}\n\n"
        "Message :\n"
        f"{quote.message or ''}\n"
    )
    body_html = f"""
      <div style="margin:0 0 10px 0;">
        <b>Entreprise :</b> {escape(card.company_name)}<br/>
        <b>Carte :</b> <a href="{escape(_card_url(card))}" style="color:#93c5fd;text-decoration:none;">{escape(_card_url(card))}</a><br/>
        <b>Métier (profil) :</b> {escape(card.profile or "—")}
      </div>
      <div style="background:rgba(2,6,23,.35);border:1px solid rgba(148,163,184,.22);
                  border-radius:14px;padding:12px;">
        <div style="font-size:12px;color:rgba(148,163,184,.95);text-transform:uppercase;letter-spacing:.12em;">
          {escape(labels["section_label"])}
        </div>

        <div style="margin-top:8px;font-size:14px;">
          <b>Nom :</b> {escape(quote.name)}<br/>
          <b>Téléphone :</b> {escape(quote.phone or "—")}<br/>
          <b>Email :</b> {escape(quote.email or "—")}<br/>
          <b>Origine :</b> {escape(origin)}<br/>
          <b>Recommandé par :</b> {escape(recommended_by)}
        </div>

        <div style="margin-top:12px;">
          <b>Message</b><br/>
          <div style="margin-top:6px;white-space:pre-wrap;color:rgba(226,232,240,.92);">
            {escape(quote.message or "")}
          </div>
        </div>

        <div style="margin-top:12px;color:rgba(148,163,184,.92);font-size:12px;">
          Conseil : recontactez rapidement ce prospect pour maximiser vos chances.
        </div>
      </div>
    """
    return QuoteNotificationMessage(
        subject=f"{labels['subject_prefix']} – {card.company_name}",
        text=text,
        html=_base_email_html(
            labels["title"],
            labels["subtitle"],
            body_html,
            _card_url(card),
            labels["cta"],
        ),
        reply_to=quote.email or None,
    )


def deliver_quote_notification(
    job: NotificationJob,
    *,
    session_factory=SessionLocal,
) -> DeliveryOutcome:
    with session_factory() as db:
        quote = db.query(Quote).filter(Quote.id == job.quote_id).first()
        if quote is None:
            return DeliveryOutcome("failed", error="quote missing")
        card = db.query(Card).filter(Card.id == quote.card_id).first()
        if card is None:
            return DeliveryOutcome("failed", error="card missing")
        message = build_quote_notification(card, quote)

    result = send_email_result(
        job.recipient or "",
        message.subject,
        message.text,
        message.html,
        reply_to=message.reply_to,
        from_email=smartcard_mail_from() or None,
        idempotency_key=job.idempotency_key,
    )
    error_parts = [
        value
        for value in (
            result.error_type,
            f"http={result.http_status}" if result.http_status else None,
        )
        if value
    ]
    return DeliveryOutcome(
        result.state,
        transport=result.transport,
        error=" ".join(error_parts),
    )
