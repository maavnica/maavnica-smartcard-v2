# backend/app/utils/emailer.py
import os
import json
import urllib.request
import urllib.error


def _get_env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()


def send_email(to_email: str, subject: str, text: str) -> None:
    """
    Envoi d'email via l'API Brevo (HTTP) -> compatible Render (SMTP bloqué).
    Variables Render à définir :
      - BREVO_API_KEY
      - SMTP_FROM (ex: contact@maavnica.com)
      - SMTP_FROM_NAME (optionnel, ex: Maavnica SmartCard)
    """
    api_key = _get_env("BREVO_API_KEY")
    from_email = _get_env("SMTP_FROM")
    from_name = _get_env("SMTP_FROM_NAME", "Maavnica SmartCard")

    to_email = (to_email or "").strip()
    subject = (subject or "").strip()
    text = (text or "").strip()

    if not api_key:
        print("[MAIL] BREVO_API_KEY manquant -> email non envoyé")
        return
    if not from_email:
        print("[MAIL] SMTP_FROM manquant -> email non envoyé")
        return
    if not to_email:
        print("[MAIL] destinataire vide -> email non envoyé")
        return

    payload = {
        "sender": {"email": from_email, "name": from_name},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
    }

    req = urllib.request.Request(
        url="https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "content-type": "application/json",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            # on consomme la réponse pour éviter des warnings
            resp.read()
        print(f"[MAIL] OK -> {to_email}")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        print(f"[MAIL] HTTPError {e.code} -> {to_email} | {body}")
    except Exception as e:
        print(f"[MAIL] ERROR -> {to_email} | {e}")




