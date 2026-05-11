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
        "demo": f"{BASE_URL}/c/demo?ref={ref}",
        "demo2": f"{BASE_URL}/c/demo2?ref={ref}",
        "demo3": f"{BASE_URL}/c/demo3?ref={ref}",
        "main": f"{BASE_URL}/?ref={ref}",
        "solo": f"{BASE_URL}/static/contact-smartcard.html?offre=solo&ref={ref}",
        "business": f"{BASE_URL}/static/contact-smartcard.html?offre=business&ref={ref}",
    }


def _build_kit_plain(first: str, last: str, ref: str, links: dict[str, str]) -> str:
    display = f"{first} {last}".strip()
    lm = links["main"]
    ld = links["demo"]
    ld2 = links["demo2"]
    ld3 = links["demo3"]
    msg_short = (
        "Je teste un outil qui transforme les clients satisfaits en recommandations.\n\n"
        "En clair, ca devient un generateur de business.\n\n"
        "Regarde la demo :\n"
        f"{ld}"
    )
    msg_raw = (
        "je teste un truc\n\n"
        "ca recupere les recommandations clients\n\n"
        "regarde 30 sec :\n"
        f"{ld}"
    )
    msg_raw_curiosity = (
        "regarde juste ca\n\n"
        "tu vas comprendre direct\n\n"
        f"{ld}"
    )
    msg_long = (
        "Salut,\n\n"
        "Je te partage SmartCard, un outil simple pour les pros.\n\n"
        "Solo sert a recevoir des contacts, des avis Google et des demandes entrantes.\n"
        "Business ajoute la recommandation client visible et tracable.\n\n"
        "La recommandation devient un generateur de business.\n\n"
        "Regarde la demo qui te correspond :\n"
        f"- Artisan / service local : {ld}\n"
        f"- Bien-etre / accompagnement : {ld2}\n"
        f"- Immobilier / mise en relation : {ld3}"
    )
    linkedin = (
        "Je teste SmartCard avec des professionnels de terrain.\n\n"
        "L'idee est simple : transformer les clients satisfaits en recommandations visibles et tracables.\n"
        "La recommandation devient un generateur de business.\n\n"
        "Demo :\n"
        f"{ld3}"
    )
    facebook = (
        "Nouveau : SmartCard pour les pros locaux.\n"
        "Solo pour contact + avis + demandes.\n"
        "Business pour recommander plus facilement autour de soi.\n\n"
        "La recommandation devient un generateur de business.\n\n"
        f"Demo : {ld}"
    )
    email = (
        "Objet : Un outil simple pour generer plus de recommandations\n\n"
        "Bonjour,\n\n"
        "Je vous recommande SmartCard, un outil qui transforme les clients satisfaits en recommandations visibles et tracables.\n"
        "En clair, la recommandation devient un generateur de business.\n\n"
        "Solo : contact + avis Google + demandes entrantes.\n"
        "Business : recommandation client + bouche-a-oreille digitalise.\n\n"
        f"Demo : {ld}\n"
    )
    lines = [
        f"Bonjour {display},",
        "",
        "Bienvenue dans le programme d’affiliation Maavnica SmartCard.",
        f"Votre référence affilié : {ref}",
        "",
        "💡 Tu connais des pros ?",
        "Ils ont deja des clients satisfaits...",
        "👉 mais ils ne les exploitent pas",
        "👉 ils perdent du business sans le savoir",
        "👉 montre-leur ca",
        "",
        "⚡ Mode rapide",
        "1. prends une demo",
        "2. copie un message",
        "3. envoie a 3 personnes",
        "👉 ca prend 2 minutes",
        "",
        "SmartCard aide les professionnels a transformer leurs clients satisfaits en recommandations visibles et tracables.",
        "La recommandation devient un generateur de business.",
        "",
        "👉 Aujourd'hui, la plupart des recommandations se perdent.",
        "SmartCard permet de les capter et de les transformer en contacts.",
        "Aujourd'hui, des clients recommandent... sans que le professionnel le sache.",
        "👉 des opportunites sont perdues sans etre visibles.",
        "",
        "— Resume simple —",
        "SmartCard Solo = contact + avis Google + demandes entrantes.",
        "SmartCard Business = recommandation client + bouche-a-oreille digitalise + recommandations tracables.",
        "Multi-cartes / equipes / agences / plusieurs etablissements = uniquement sur devis.",
        "",
        "— Profils a qui proposer SmartCard —",
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
        "— Quelle demo envoyer ? —",
        f"Demo 1 / Artisan / service local / intervention : {ld}",
        "👉 regarde cette demo",
        f"Demo 2 / Bien-etre / accompagnement / relation de confiance : {ld2}",
        "👉 regarde cette demo",
        f"Demo 3 / Agent immobilier / recommandation locale / mise en relation : {ld3}",
        "👉 regarde cette demo",
        "👉 En immobilier, une recommandation peut devenir un mandat.",
        "👉 C'est un levier direct de business.",
        "",
        "— Premiere mission (5 minutes) —",
        "🚀 Premiere mission (5 minutes)",
        "",
        "1. Choisis 1 professionnel",
        "2. Choisis la bonne demo",
        "3. Copie un message",
        "4. Envoie a 3 personnes",
        "",
        "Objectif : montrer que ses clients peuvent devenir un generateur de business.",
        "🎯 Resultat attendu :",
        "au moins 1 personne interessee",
        "",
        "— Mini scenario reel —",
        "Tu connais un artisan ?",
        "→ tu envoies la demo",
        "→ il comprend en 30 sec",
        "→ il teste",
        "→ il peut devenir client",
        "👉 c'est comme ca que tu declenches une vente",
        "",
        "— Permission d'envoi —",
        "👉 tu n'as rien a vendre",
        "👉 tu montres juste la demo",
        "👉 meme si tu n'es pas commercial",
        "👉 l'objectif est juste de faire decouvrir",
        "",
        "— Commissions (regle claire) —",
        "Une vente SmartCard Solo validee = 20 EUR",
        "Une vente SmartCard Business validee = 35 EUR",
        "Commission uniquement lors de la premiere souscription validee.",
        "Aucun revenu automatique.",
        "",
        "— Vos liens personnels (a utiliser tels quels) —",
        f"Lien principal (accueil + tracking) : {lm}",
        f"Lien offre Solo : {links['solo']}",
        f"Lien offre Business : {links['business']}",
        "",
        "A retenir :",
        "• Utiliser la demo adaptee avant de parler commande",
        "• Lien Solo pour l'offre Solo",
        "• Lien Business pour l'offre Business",
        "",
        "— Messages prets a envoyer —",
        "WhatsApp brut :",
        msg_raw,
        "",
        "Variante curiosite :",
        msg_raw_curiosity,
        "",
        "WhatsApp court :",
        msg_short,
        "",
        "WhatsApp detaille :",
        msg_long,
        "",
        "LinkedIn :",
        linkedin,
        "",
        "Facebook :",
        facebook,
        "",
        "Email :",
        email,
        "",
        "— Regles importantes —",
        "• Commission uniquement sur premiere souscription validee",
        "• Aucun revenu automatique",
        "• Presentation honnete et sans promesse exageree",
        "• Multi-cartes = sur devis",
        "• Ne pas promettre de resultats",
        "",
        "— A ne pas faire —",
        "❌ ne pas survendre",
        "❌ ne pas promettre des resultats",
        "❌ ne pas parler technique",
        "👉 montre juste la demo, c'est suffisant",
        "",
        "Important : utilisez toujours vos liens ci-dessus pour que vos recommandations soient rattachees a votre reference.",
        "",
        "Cordialement,",
        "L’équipe Maavnica",
    ]
    return "\n".join(lines)


def _build_kit_html(first: str, last: str, ref: str, links: dict[str, str]) -> str:
    display = escape(f"{first} {last}".strip())
    ref_e = escape(ref)
    lm = links["main"]
    ld = links["demo"]
    ld2 = links["demo2"]
    ld3 = links["demo3"]
    wa_short = (
        "Je teste un outil qui transforme les clients satisfaits en recommandations.\n\n"
        "En clair, ca devient un generateur de business.\n\n"
        "Regarde la demo :\n"
        f"{ld}"
    )
    wa_raw = (
        "je teste un truc\n\n"
        "ca recupere les recommandations clients\n\n"
        "regarde 30 sec :\n"
        f"{ld}"
    )
    wa_raw_curiosity = (
        "regarde juste ca\n\n"
        "tu vas comprendre direct\n\n"
        f"{ld}"
    )
    wa_long = (
        "Salut,\n\n"
        "Je te partage SmartCard, un outil simple pour les pros.\n\n"
        "Solo sert a recevoir des contacts, des avis Google et des demandes entrantes.\n"
        "Business ajoute la recommandation client visible et tracable.\n\n"
        "La recommandation devient un generateur de business.\n\n"
        "Regarde la demo qui te correspond :\n"
        f"- Artisan / service local : {ld}\n"
        f"- Bien-etre / accompagnement : {ld2}\n"
        f"- Immobilier / mise en relation : {ld3}"
    )
    linkedin = (
        "Je teste SmartCard avec des professionnels de terrain.\n\n"
        "L'idee est simple : transformer les clients satisfaits en recommandations visibles et tracables.\n"
        "La recommandation devient un generateur de business.\n\n"
        "Demo :\n"
        f"{ld3}"
    )
    facebook = (
        "Nouveau : SmartCard pour les pros locaux.\n"
        "Solo pour contact + avis + demandes.\n"
        "Business pour recommander plus facilement autour de soi.\n\n"
        "La recommandation devient un generateur de business.\n\n"
        f"Demo : {ld}"
    )
    email = (
        "Objet : Un outil simple pour generer plus de recommandations\n\n"
        "Bonjour,\n\n"
        "Je vous recommande SmartCard, un outil qui transforme les clients satisfaits en recommandations visibles et tracables.\n"
        "En clair, la recommandation devient un generateur de business.\n\n"
        "Solo : contact + avis Google + demandes entrantes.\n"
        "Business : recommandation client + bouche-a-oreille digitalise.\n\n"
        f"Demo : {ld}\n"
    )
    return f"""\
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8" /></head>
<body style="font-family:system-ui,Segoe UI,sans-serif;line-height:1.5;color:#111;">
  <p>Bonjour {display},</p>
  <p>Bienvenue dans le programme d’affiliation <strong>Maavnica SmartCard</strong>.</p>
  <p><strong>Référence affilié :</strong> <code>{ref_e}</code></p>
  <p><strong>💡 Tu connais des pros ?</strong><br/>
  Ils ont deja des clients satisfaits...<br/>
  👉 mais ils ne les exploitent pas<br/>
  👉 ils perdent du business sans le savoir<br/>
  <strong>👉 montre-leur ca</strong></p>
  <h3 style="font-size:1rem;">⚡ Mode rapide</h3>
  <p style="margin:0 0 6px 0;">1. prends une demo<br/>2. copie un message<br/>3. envoie a 3 personnes<br/>👉 ca prend 2 minutes</p>
  <p><strong>SmartCard aide les professionnels a transformer leurs clients satisfaits en recommandations visibles et tracables.</strong><br/>
  <strong>La recommandation devient un generateur de business.</strong></p>
  <p><strong>👉 Aujourd'hui, la plupart des recommandations se perdent.</strong><br/>
  SmartCard permet de les capter et de les transformer en contacts.</p>
  <p>Aujourd'hui, des clients recommandent... sans que le professionnel le sache.<br/>
  <strong>👉 des opportunites sont perdues sans etre visibles.</strong></p>
  <h3 style="font-size:1rem;">Resume simple</h3>
  <ul>
    <li>SmartCard Solo = contact + avis Google + demandes entrantes</li>
    <li>SmartCard Business = recommandation client + bouche-a-oreille digitalise + recommandations tracables</li>
    <li>Multi-cartes / equipes / agences / plusieurs etablissements = uniquement sur devis</li>
  </ul>
  <h3 style="font-size:1rem;">Profils a qui proposer SmartCard</h3>
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
  <h3 style="font-size:1rem;">Quelle demo envoyer ?</h3>
  <ul>
    <li>Demo 1: Artisan / service local / intervention — <a href="{escape(ld)}">/c/demo</a><br/>👉 regarde cette demo</li>
    <li>Demo 2: Bien-etre / accompagnement / relation de confiance — <a href="{escape(ld2)}">/c/demo2</a><br/>👉 regarde cette demo</li>
    <li>Demo 3: Agent immobilier / recommandation locale / mise en relation — <a href="{escape(ld3)}">/c/demo3</a><br/>👉 regarde cette demo</li>
  </ul>
  <p style="font-size:0.92rem;color:#444;margin:0 0 8px 0;"><strong>👉 En immobilier, une recommandation peut devenir un mandat.</strong><br/>
  👉 C'est un levier direct de business.</p>
  <h3 style="font-size:1rem;">🚀 Premiere mission (5 minutes)</h3>
  <ol>
    <li>Choisir 1 professionnel</li>
    <li>Choisir la bonne demo</li>
    <li>Copier un message</li>
    <li>Envoyer a 3 personnes</li>
  </ol>
  <p style="font-size:0.92rem;color:#444;margin:8px 0 8px 0;">Objectif: montrer que ses clients peuvent devenir un generateur de business.</p>
  <p style="font-size:0.92rem;color:#444;margin:8px 0 8px 0;"><strong>🎯 Resultat attendu :</strong><br/>au moins 1 personne interessee</p>
  <h3 style="font-size:1rem;">Mini scenario reel</h3>
  <p style="font-size:0.92rem;color:#444;margin:8px 0 8px 0;">Tu connais un artisan ? → tu envoies la demo → il comprend en 30 sec → il teste → il peut devenir client.<br/>
  👉 c'est comme ca que tu declenches une vente.</p>
  <h3 style="font-size:1rem;">Permission d'envoi</h3>
  <p style="font-size:0.92rem;color:#444;margin:8px 0 8px 0;">👉 tu n'as rien a vendre<br/>
  👉 tu montres juste la demo<br/>
  👉 meme si tu n'es pas commercial<br/>
  👉 l'objectif est juste de faire decouvrir</p>
  <p style="font-size:0.92rem;color:#444;margin:10px 0 0 0;"><strong>Commission seulement a la premiere souscription validee (20 EUR Solo, 35 EUR Business)</strong><br/>
  <strong>Aucun revenu automatique.</strong></p>
  <h3 style="font-size:1rem;">Vos liens personnels</h3>
  <ul>
    <li><a href="{escape(lm)}">Lien principal</a> (accueil + tracking)</li>
    <li><a href="{escape(links['solo'])}">Offre Solo</a> — pour commander l’offre Solo</li>
    <li><a href="{escape(links['business'])}">Offre Business</a> — pour commander l’offre Business</li>
  </ul>
  <h3 style="font-size:1rem;">Messages prets a envoyer</h3>
  <p style="font-size:0.9rem;color:#444;"><strong>WhatsApp brut</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(wa_raw)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>Variante curiosite</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(wa_raw_curiosity)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>WhatsApp court</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(wa_short)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>WhatsApp detaille</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(wa_long)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>LinkedIn</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(linkedin)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>Facebook</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(facebook)}</pre>
  <p style="font-size:0.9rem;color:#444;"><strong>Email</strong></p>
  <pre style="background:#f4f4f5;padding:12px;border-radius:8px;white-space:pre-wrap;">{escape(email)}</pre>
  <h3 style="font-size:1rem;">Regles importantes</h3>
  <ul>
    <li>Commission uniquement a la premiere souscription validee</li>
    <li>Aucun revenu automatique</li>
    <li>Presentation honnete, sans promesse exageree</li>
    <li>Multi-cartes = sur devis</li>
    <li>Ne pas promettre de resultats</li>
  </ul>
  <h3 style="font-size:1rem;">A ne pas faire</h3>
  <p style="font-size:0.92rem;color:#444;">❌ ne pas survendre<br/>❌ ne pas promettre des resultats<br/>❌ ne pas parler technique<br/>👉 montre juste la demo, c'est suffisant</p>
  <p><strong>Important :</strong> utilisez toujours <em>vos</em> liens ci-dessus pour rattacher vos recommandations a votre reference.</p>
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
