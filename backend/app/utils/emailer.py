# backend/app/utils/emailer.py
import json
import logging
import os
import re
import socket
import ssl
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

logger = logging.getLogger(__name__)

_SECRET_IN_TEXT = re.compile(
    r"(?i)(api[-_]?key|x-key|smtp_password|smtp_pass|password|token|secret)\s*[:=]\s*\S+"
)
_NAMED_SMTP_ERRORS = (
    smtplib.SMTPAuthenticationError,
    smtplib.SMTPConnectError,
    smtplib.SMTPServerDisconnected,
    smtplib.SMTPRecipientsRefused,
    smtplib.SMTPSenderRefused,
    smtplib.SMTPDataError,
)


def _clean(v: str | None) -> str:
    return (v or "").strip().replace("\r", "").replace("\n", "")


def _smtp_password() -> str:
    """SMTP_PASSWORD (contact / Render), sinon ancien SMTP_PASS."""
    return _clean(os.getenv("SMTP_PASSWORD")) or _clean(os.getenv("SMTP_PASS"))


def _mask_email(email: str) -> str:
    if not email or "@" not in email:
        return "(inconnu)"
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _email_domain(email: str) -> str:
    """Domaine seul pour MAILTRACE (jamais d'adresse complète)."""
    cleaned = _clean(email)
    if not cleaned or "@" not in cleaned:
        return "(unknown)"
    domain = cleaned.rsplit("@", 1)[-1].strip().lower()
    return domain or "(unknown)"


def _safe_error_text(raw: str, limit: int = 300) -> str:
    text = _clean(raw)
    text = _SECRET_IN_TEXT.sub(r"\1=***", text)
    for env_name in ("SMTP_PASSWORD", "SMTP_PASS", "BREVO_API_KEY"):
        secret = _clean(os.getenv(env_name))
        if secret:
            text = text.replace(secret, "***")
    return text[:limit]


def _classify_smtp_error(exc: BaseException) -> str:
    if isinstance(exc, _NAMED_SMTP_ERRORS):
        return type(exc).__name__
    if isinstance(exc, ssl.SSLError):
        return "SSL error"
    if isinstance(exc, socket.gaierror):
        return "gaierror"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "TimeoutError"
    return type(exc).__name__


def _smtp_diag_ok() -> dict:
    return {"sent": True, "transport": "smtp"}


_SUBJECT_DECORATION_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def _plain_subject(subject: str) -> str:
    """Retire les emojis / décorations du sujet (alignement contact.py, texte simple)."""
    return " ".join(_SUBJECT_DECORATION_RE.sub(" ", subject).split())


def _smtp_diag_fail(error_type: str, error_message: str = "") -> dict:
    result = {
        "sent": False,
        "transport": "smtp",
        "error_type": error_type,
    }
    sanitized = _safe_error_text(error_message)
    if sanitized:
        result["error_message"] = sanitized
    return result


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
        logger.warning(
            "[MAILTRACE] BREVO_FAILED type=%s status=%s",
            type(e).__name__,
            e.code,
        )
        return False
    except Exception as e:
        logger.warning(
            "[MAIL] BREVO FAILED dest=%s error=%s detail=%s",
            dest,
            type(e).__name__,
            _safe_error_text(str(e)),
        )
        logger.warning(
            "[MAILTRACE] BREVO_FAILED type=%s status=-",
            type(e).__name__,
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
        logger.warning("[MAILTRACE] SMTP_FALLBACK_FAILED type=%s", type(e).__name__)
        return False


def _send_via_smtp_contact(
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
) -> dict:
    """Même handshake que ``contact.py`` : 465 = SMTP_SSL, sinon EHLO+STARTTLS+EHLO+LOGIN.

    Diagnostic délivrabilité : texte seul (pas de part HTML), comme ``contact.py``.
    """
    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = _plain_subject(subject)
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text)

    dest = _mask_email(to_email)
    try:
        timeout = 20
        if port == 465:
            with smtplib.SMTP_SSL(
                host,
                port,
                timeout=timeout,
                context=ssl.create_default_context(),
            ) as server:
                server.login(user, password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=timeout) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(user, password)
                server.send_message(msg)
        logger.info("[MAIL] SMTP OK dest=%s", dest)
        return _smtp_diag_ok()
    except Exception as e:
        logger.warning(
            "[MAIL] SMTP FAILED dest=%s error=%s detail=%s",
            dest,
            type(e).__name__,
            _safe_error_text(str(e)),
        )
        return _smtp_diag_fail(_classify_smtp_error(e), str(e))


def send_smtp_only_result(
    to_email: str,
    subject: str,
    text: str,
    html: str | None = None,
    reply_to: str | None = None,
) -> dict:
    """SMTP-only (SmartCard) : même transport que ``send_email(..., smtp_only=True)``, avec diagnostic."""
    to_email = _clean(to_email)
    subject = _clean(subject)
    text = text or ""
    html = html or ""
    reply_to = _clean(reply_to)

    if not to_email:
        logger.warning("[MAIL] SKIP NO RECIPIENT")
        return _smtp_diag_fail("configuration missing", "no recipient")
    if not subject:
        logger.warning("[MAIL] SKIP empty subject dest=%s", _mask_email(to_email))
        return _smtp_diag_fail("configuration missing", "empty subject")

    host = _clean(os.getenv("SMTP_HOST"))
    port_raw = _clean(os.getenv("SMTP_PORT"))
    user = _clean(os.getenv("SMTP_USER"))
    password = _clean(os.getenv("SMTP_PASSWORD"))
    from_email = _clean(os.getenv("MAIL_FROM"))
    try:
        port = int(port_raw) if port_raw else 587
    except ValueError:
        logger.warning("[MAIL] SKIP NO TRANSPORT")
        return _smtp_diag_fail("configuration missing", "invalid SMTP port")
    if not _smtp_configured(host, user, password, from_email):
        logger.warning("[MAIL] SKIP NO TRANSPORT")
        return _smtp_diag_fail("configuration missing", "SMTP settings incomplete")

    return _send_via_smtp_contact(
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
    )


def send_email(
    to_email: str,
    subject: str,
    text: str,
    html: str | None = None,
    reply_to: str | None = None,
    smtp_only: bool = False,
) -> bool:
    """
    Envoi email (historique SmartCard) :
    - Brevo API si BREVO_API_KEY + SMTP_FROM/MAIL_FROM.
    - Sinon fallback SMTP (SMTP_PASSWORD, sinon SMTP_PASS).
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

    if smtp_only:
        return send_smtp_only_result(
            to_email,
            subject,
            text,
            html,
            reply_to=reply_to,
        )["sent"]

    api_key = _clean(os.getenv("BREVO_API_KEY"))
    from_email = _clean(os.getenv("SMTP_FROM")) or _clean(os.getenv("MAIL_FROM"))
    from_name = _clean(os.getenv("SMTP_FROM_NAME")) or "Maavnica SmartCard"

    logger.warning(
        "[MAILTRACE] CONFIG brevo_key_present=%s sender_present=%s",
        "true" if api_key else "false",
        "true" if from_email else "false",
    )
    logger.warning("[MAILTRACE] TO_DOMAIN=%s", _email_domain(to_email))
    logger.warning("[MAILTRACE] FROM_DOMAIN=%s", _email_domain(from_email))

    if api_key and from_email:
        logger.warning("[MAILTRACE] BREVO_ATTEMPT")
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
            logger.warning("[MAILTRACE] BREVO_OK")
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

    logger.warning("[MAILTRACE] SMTP_FALLBACK_ATTEMPT")
    ok = _send_via_smtp(
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
    if ok:
        logger.warning("[MAILTRACE] SMTP_FALLBACK_OK")
    return ok
