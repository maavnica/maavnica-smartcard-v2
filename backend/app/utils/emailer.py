import os
import smtplib
from email.message import EmailMessage


def send_email(to_email: str, subject: str, text: str) -> None:
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("SMTP_FROM", user)

    if not (host and user and password and from_email and to_email):
        # Pas de config -> on ne casse rien, on sort juste
        return

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text)

    # STARTTLS standard (587)
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
