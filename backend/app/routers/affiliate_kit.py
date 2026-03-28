"""
Outil interne : génération + envoi du kit affilié par email.
Protégé par la même clé admin que le reste (Authorization: Bearer).
"""
from __future__ import annotations

import logging
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas import AffiliateKitSendRequest
from app.utils.admin_auth import require_admin_api_key
from app.utils.emailer import send_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/affiliate-kit", tags=["affiliate-kit"])

BASE_URL = "https://smartcard.maavnica.com"


def _affiliate_links(ref: str) -> dict[str, str]:
    return {
        "main": f"{BASE_URL}/?ref={ref}",
        "solo": f"{BASE_URL}/static/contact-smartcard.html?offre=solo&ref={ref}",
        "business": f"{BASE_URL}/static/contact-smartcard.html?offre=business&ref={ref}",
    }


def _build_kit_plain(first: str, last: str, ref: str, links: dict[str, str]) -> str:
    display = f"{first} {last}".strip()
    lm = links["main"]
    wa = (
        "Bonjour,\n"
        "je te partage une solution simple pour aider les professionnels à :\n"
        "- obtenir plus d’avis Google\n"
        "- recevoir plus de demandes clients\n"
        "- partager facilement leur carte pro avec un QR code\n\n"
        f"Voici le lien :\n{lm}"
    )
    sms = f"Si tu veux plus d’avis Google et plus de contacts clients, regarde ici :\n{lm}"
    lines = [
        f"Bonjour {display},",
        "",
        "Bienvenue dans le programme d’affiliation Maavnica SmartCard.",
        f"Votre référence affilié : {ref}",
        "",
        "— Profils à qui proposer SmartCard —",
        "Profils qui utilisent le plus SmartCard :",
        "- artisans",
        "- restaurateurs",
        "- esthéticiennes",
        "- thérapeutes",
        "- agents immobiliers",
        "- indépendants",
        "- coachs",
        "- consultants",
        "",
        "— Pourquoi SmartCard est utile —",
        "SmartCard permet aux professionnels de :",
        "- obtenir plus d’avis Google",
        "- gagner en crédibilité",
        "- recevoir plus de demandes clients",
        "- partager facilement leurs coordonnées via QR code",
        "",
        "— Vos liens personnels (à utiliser tels quels) —",
        f"Lien principal (accueil + tracking) : {lm}",
        f"Lien offre Solo : {links['solo']}",
        f"Lien offre Business : {links['business']}",
        "",
        "— Rémunération (rappel) —",
        "20 € par SmartCard Solo vendue (39 € HT / an).",
        "35 € par offre Business vendue (99 € HT / an, jusqu’à 5 cartes).",
        "Les commissions s’appliquent sur les ventes validées, selon les modalités en vigueur.",
        "",
        "— Message WhatsApp (à copier-coller) —",
        wa,
        "",
        "— SMS court (à copier-coller) —",
        sms,
        "",
        "Important : partagez toujours vos liens ci-dessus pour que vos recommandations soient rattachées à votre référence.",
        "",
        "Cordialement,",
        "L’équipe Maavnica",
    ]
    return "\n".join(lines)


def _build_kit_html(first: str, last: str, ref: str, links: dict[str, str]) -> str:
    display = escape(f"{first} {last}".strip())
    ref_e = escape(ref)
    lm = links["main"]
    wa_plain = (
        "Bonjour,\n"
        "je te partage une solution simple pour aider les professionnels à :\n"
        "- obtenir plus d’avis Google\n"
        "- recevoir plus de demandes clients\n"
        "- partager facilement leur carte pro avec un QR code\n\n"
        f"Voici le lien :\n{lm}"
    )
    sms_plain = f"Si tu veux plus d’avis Google et plus de contacts clients, regarde ici :\n{lm}"
    return f"""\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8" /></head>
<body style="font-family:system-ui,Segoe UI,sans-serif;line-height:1.5;color:#111;">
  <p>Bonjour {display},</p>
  <p>Bienvenue dans le programme d’affiliation <strong>Maavnica SmartCard</strong>.</p>
  <p><strong>Référence affilié :</strong> <code>{ref_e}</code></p>
  <h3 style="font-size:1rem;">Profils à qui proposer SmartCard</h3>
  <p style="margin:0 0 6px 0;">Profils qui utilisent le plus SmartCard :</p>
  <ul>
    <li>artisans</li>
    <li>restaurateurs</li>
    <li>esthéticiennes</li>
    <li>thérapeutes</li>
    <li>agents immobiliers</li>
    <li>indépendants</li>
    <li>coachs</li>
    <li>consultants</li>
  </ul>
  <h3 style="font-size:1rem;">Pourquoi SmartCard est utile</h3>
  <p style="margin:0 0 6px 0;">SmartCard permet aux professionnels de :</p>
  <ul>
    <li>obtenir plus d’avis Google</li>
    <li>gagner en crédibilité</li>
    <li>recevoir plus de demandes clients</li>
    <li>partager facilement leurs coordonnées via QR code</li>
  </ul>
  <h3 style="font-size:1rem;">Vos liens personnels</h3>
  <ul>
    <li><a href="{escape(lm)}">Lien principal</a> (accueil + tracking)</li>
    <li><a href="{escape(links['solo'])}">Offre Solo</a></li>
    <li><a href="{escape(links['business'])}">Offre Business</a></li>
  </ul>
  <h3 style="font-size:1rem;">Rémunération</h3>
  <ul>
    <li><strong>20 €</strong> par SmartCard Solo vendue (39 € HT / an)</li>
    <li><strong>35 €</strong> par offre Business vendue (99 € HT / an)</li>
  </ul>
  <p style="font-size:0.9rem;color:#444;">Les commissions s’appliquent sur les ventes validées, selon les modalités en vigueur.</p>
  <h3 style="font-size:1rem;">Message WhatsApp (copier-coller)</h3>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(wa_plain)}</pre>
  <h3 style="font-size:1rem;">SMS court (copier-coller)</h3>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(sms_plain)}</pre>
  <p><strong>Important :</strong> utilisez toujours <em>vos</em> liens ci-dessus pour rattacher vos recommandations à votre référence.</p>
  <p>Cordialement,<br/>L’équipe Maavnica</p>
</body>
</html>
"""


@router.post("/send")
def send_affiliate_kit(
    data: AffiliateKitSendRequest,
    request: Request,
    _: None = Depends(require_admin_api_key),
):
    ref = data.affiliate_ref
    links = _affiliate_links(ref)
    subject = "Votre kit affilié Maavnica SmartCard"
    text = _build_kit_plain(data.first_name, data.last_name, ref, links)
    html = _build_kit_html(data.first_name, data.last_name, ref, links)
    to = str(data.email)

    ok = send_email(to, subject, text, html)
    if not ok:
        logger.error("Échec envoi kit affilié (email destinataire présent mais transport mail KO)")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de l’envoi de l’email. Vérifiez la configuration mail (Brevo / SMTP).",
        )

    logger.info("Kit affilié envoyé (ref=%s)", ref)
    return {"ok": True, "message": "Kit affilié envoyé avec succès."}
