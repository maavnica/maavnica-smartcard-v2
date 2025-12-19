import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(to_email: str, subject: str, text: str) -> bool:
    """
    Envoie un email via SMTP (Brevo).
    - Retourne True si envoyé, False sinon.
    - Ne casse jamais l'API : log en console Render en cas de souci.
    """
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    from_email = os.getenv("SMTP_FROM", "").strip() or user

    if not to_email:
        print("[MAIL] SKIP: to_email vide")
        return False

    missing = [k for k, v in {
        "SMTP_HOST": host,
        "SMTP_USER": user,
        "SMTP_PASS": password,
        "SMTP_FROM": from_email,
    }.items() if not v]

    if missing:
        print(f"[MAIL] SKIP: config SMTP manquante ({', '.join(missing)})")
        return False

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)  # STARTTLS 587
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)

        print(f"[MAIL] OK -> {to_email} | subject={subject}")
        return True

    except Exception as e:
        print(f"[MAIL] ERROR -> {to_email} | {type(e).__name__}: {e}")
        return False

