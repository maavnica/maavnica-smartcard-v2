import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email(to_email: str, subject: str, text: str) -> bool:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", user)

    if not all([host, port, user, password, from_email, to_email]):
        print("[MAIL] SKIP: config SMTP incomplète")
        return False

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context, timeout=20) as server:
            server.login(user, password)
            server.send_message(msg)

        print(f"[MAIL] OK -> {to_email}")
        return True

    except Exception as e:
        print(f"[MAIL] ERROR -> {to_email} | {e}")
        return False


