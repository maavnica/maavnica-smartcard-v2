# backend/app/utils/emailer.py
import os
import json
import ssl
import smtplib
import urllib.request
import urllib.error
from email.message import EmailMessage


def _clean(v: str | None) -> str:
    return (v or "").strip().replace("\r", "").replace("\n", "")


def send_email(to_email: str, subject: str, text: str, html: str | None = None) -> bool:
    """
    Envoi email robuste :
    - Priorité: Brevo API (HTTPS / port 443) -> compatible Render.
    - Fallback: SMTP (si pas de BREVO_API_KEY).
    - Supporte texte + HTML (HTML optionnel).
    Env vars recommandées :
      - BREVO_API_KEY (fortement recommandé)
      - SMTP_FROM (email expéditeur)
      - SMTP_FROM_NAME (optionnel)
    Fallback SMTP env vars (si besoin) :
      - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_TLS/SMTP_SSL
    """
    to_email = _clean(to_email)
    subject = _clean(subject)
    text = text or ""
    html = html or ""

    if not to_email or not subject:
        print("[MAIL] SKIP: destinataire ou sujet vide")
        return False

    # ---- 1) Brevo API (recommandé) ----
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    from_email = _clean(os.getenv("SMTP_FROM")) or _clean(os.getenv("MAIL_FROM"))
    from_name = _clean(os.getenv("SMTP_FROM_NAME")) or "Maavnica SmartCard"

    if api_key and from_email:
        payload = {
            "sender": {"email": from_email, "name": from_name},
            "to": [{"email": to_email}],
            "subject": subject,
            "textContent": text,
        }
        if html:
            payload["htmlContent"] = html

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
                resp.read()
            print(f"[MAIL] OK (Brevo API) -> {to_email}")
            return True
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                body = ""
            print(f"[MAIL] HTTPError Brevo {e.code} -> {to_email} | {body}")
            return False
        except Exception as e:
            print(f"[MAIL] ERROR Brevo API -> {to_email} | {type(e).__name__}: {e}")
            return False

    # ---- 2) Fallback SMTP (si tu veux) ----
    host = _clean(os.getenv("SMTP_HOST"))
    port = int(_clean(os.getenv("SMTP_PORT", "587")) or "587")
    user = _clean(os.getenv("SMTP_USER"))
    password = _clean(os.getenv("SMTP_PASS"))
    if not from_email:
        from_email = user

    if not (host and user and password and from_email):
        print("[MAIL] SKIP: SMTP non configuré et BREVO_API_KEY absent")
        return False

    use_tls = _clean(os.getenv("SMTP_TLS", "true")).lower() in ("1", "true", "yes", "on")
    use_ssl = _clean(os.getenv("SMTP_SSL", "false")).lower() in ("1", "true", "yes", "on")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    if html:
        msg.add_alternative(html, subtype="html")

    try:
        timeout = 20
        if use_ssl or port == 465:
            with smtplib.SMTP_SSL(host, port, context=ssl.create_default_context(), timeout=timeout) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                if use_tls:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)

        print(f"[MAIL] OK (SMTP) -> {to_email}")
        return True
    except Exception as e:
        print(f"[MAIL] ERROR SMTP -> {to_email} | {type(e).__name__}: {e}")
        return False





