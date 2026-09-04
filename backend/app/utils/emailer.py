# backend/app/utils/emailer.py
import json
import logging
import os
import re
import ssl
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_SECRET_IN_TEXT = re.compile(
    r"(?i)(api[-_]?key|x-key|password|token|secret)\s*[:=]\s*\S+"
)


def _clean(v: str | None) -> str:
    return (v or "").strip().replace("\r", "").replace("\n", "")


def _smtp_password() -> str:
    """SMTP_PASS d'abord, puis SMTP_PASSWORD (variable déjà utilisée par /api/contact)."""
    return _clean(os.getenv("SMTP_PASS")) or _clean(os.getenv("SMTP_PASSWORD"))


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "(inconnu)"
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _safe_error_text(raw: str, limit: int = 300) -> str:
    text = _clean(raw)
    text = _SECRET_IN_TEXT.sub(r"\1=***", text)
    return text[:limit]


def _smtp_configured(host: str, user: str, password: str, from_email: str) -> bool:
    return bool(host and user and password and from_email)


def _send_via_brevo(
    *,
    api_key: str,
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    text: str,
    html: str,
    reply_to: str,
) -> bool:
    payload: dict = {
        "sender": {"email": from_email, "name": from_name},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": text,
    }
    if html:
        payload["htmlContent"] = html
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

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
    dest = _mask_email(to_email)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
        logger.info("[MAIL] BREVO OK dest=%s", dest)
        return True
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        logger.warning(
            "[MAIL] BREVO FAILED dest=%s http=%s detail=%s",
            dest,
            e.code,
            _safe_error_text(body or str(e)),
        )
        return False
    except Exception as e:
        logger.warning(
            "[MAIL] BREVO FAILED dest=%s error=%s detail=%s",
            dest,
            type(e).__name__,
            _safe_error_text(str(e)),
        )
        return False


def _send_via_smtp(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    from_email: str,
    to_email: str,
    subject: str,
    text: str,
    html: str,
    reply_to: str,
    use_tls: bool,
    use_ssl: bool,
) -> bool:
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    dest = _mask_email(to_email)
    try:
        timeout = 20
        if use_ssl or port == 465:
            with smtplib.SMTP_SSL(
                host, port, context=ssl.create_default_context(), timeout=timeout
            ) as server:
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
        logger.info("[MAIL] SMTP OK dest=%s", dest)
        return True
    except Exception as e:
        logger.warning(
            "[MAIL] SMTP FAILED dest=%s error=%s detail=%s",
            dest,
            type(e).__name__,
            _safe_error_text(str(e)),
        )
        return False


def send_email(
    to_email: str,
    subject: str,
    text: str,
    html: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """
    Envoi email :
    - Priorité: API Brevo (HTTPS).
    - Si Brevo est absent ou échoue: SMTP (SMTP_PASS, sinon SMTP_PASSWORD).
    - Jamais deux envois si Brevo a réussi.
    - reply_to optionnel (jamais utilisé comme From).
    """
    to_email = _clean(to_email)
    subject = _clean(subject)
    text = text or ""
    html = html or ""
    reply_to = _clean(reply_to)

    if not to_email:
        logger.warning("[MAIL] SKIP NO RECIPIENT")
        return False
    if not subject:
        logger.warning("[MAIL] SKIP empty subject dest=%s", _mask_email(to_email))
        return False

    api_key = _clean(os.getenv("BREVO_API_KEY"))
    from_email = _clean(os.getenv("SMTP_FROM")) or _clean(os.getenv("MAIL_FROM"))
    from_name = _clean(os.getenv("SMTP_FROM_NAME")) or "Maavnica SmartCard"

    if api_key and from_email:
        if _send_via_brevo(
            api_key=api_key,
            from_email=from_email,
            from_name=from_name,
            to_email=to_email,
            subject=subject,
            text=text,
            html=html,
            reply_to=reply_to,
        ):
            return True
        logger.info("[MAIL] BREVO FAILED falling back to SMTP dest=%s", _mask_email(to_email))

    host = _clean(os.getenv("SMTP_HOST"))
    port = int(_clean(os.getenv("SMTP_PORT", "587")) or "587")
    user = _clean(os.getenv("SMTP_USER"))
    password = _smtp_password()
    if not from_email:
        from_email = user

    if not _smtp_configured(host, user, password, from_email):
        logger.warning("[MAIL] SKIP NO TRANSPORT")
        return False

    use_tls = _clean(os.getenv("SMTP_TLS", "true")).lower() in ("1", "true", "yes", "on")
    use_ssl = _clean(os.getenv("SMTP_SSL", "false")).lower() in ("1", "true", "yes", "on")

    return _send_via_smtp(
        host=host,
        port=port,
        user=user,
        password=password,
        from_email=from_email,
        to_email=to_email,
        subject=subject,
        text=text,
        html=html,
        reply_to=reply_to,
        use_tls=use_tls,
        use_ssl=use_ssl,
    )
