import os
import smtplib
from email.message import EmailMessage


def _clean(v: str) -> str:
    # évite les erreurs "Header values may not contain linefeed..."
    return (v or "").strip().replace("\r", "").replace("\n", "")


def send_email(to_email: str, subject: str, text: str) -> None:
    host = _clean(os.getenv("SMTP_HOST", ""))
    port = int(_clean(os.getenv("SMTP_PORT", "587")) or "587")
    user = _clean(os.getenv("SMTP_USER", ""))
    password = _clean(os.getenv("SMTP_PASS", ""))
    from_email = _clean(os.getenv("SMTP_FROM", user))
    use_tls = _clean(os.getenv("SMTP_TLS", "true")).lower() in ("1", "true", "yes", "on")
    use_ssl = _clean(os.getenv("SMTP_SSL", "false")).lower() in ("1", "true", "yes", "on")

    to_email = _clean(to_email)
    subject = _clean(subject)

    if not (host and user and password and from_email and to_email):
        print("[MAIL] SMTP non configuré -> email ignoré")
        return

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    try:
        timeout = 20

        # Règles simples :
        # - 465 => SSL direct
        # - sinon => SMTP + (STARTTLS si activé)
        if use_ssl or port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=timeout) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()
                server.login(user, password)
                server.send_message(msg)

        print(f"[MAIL] OK -> {to_email}")

    except Exception as e:
        print(f"[MAIL] ERREUR -> {to_email} | {type(e).__name__}: {e}")



