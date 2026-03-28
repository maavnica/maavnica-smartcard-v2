import html
import logging
import os
import smtplib
import ssl
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from threading import Lock

from fastapi import APIRouter, Body, HTTPException, Request, status
from pydantic import ValidationError

from app.schemas import ContactRequest

router = APIRouter(prefix="/api", tags=["contact"])
logger = logging.getLogger(__name__)

_RATE_LIMIT_REQUESTS = 5
_RATE_LIMIT_WINDOW_SECONDS = 60
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = Lock()


def _get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _is_rate_limited(client_ip: str) -> bool:
    now = time.monotonic()
    with _rate_limit_lock:
        queue = _rate_limit_buckets[client_ip]
        while queue and (now - queue[0]) > _RATE_LIMIT_WINDOW_SECONDS:
            queue.popleft()
        if len(queue) >= _RATE_LIMIT_REQUESTS:
            return True
        queue.append(now)
        return False


def _mask_email_for_log(email: str) -> str:
    """Réduit l'exposition des emails dans les logs (debug / abuse)."""
    if not email or "@" not in email:
        return "(inconnu)"
    local, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(local) <= 1:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def _env_required(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise RuntimeError(f"Variable d'environnement manquante: {name}")
    return value


def _send_contact_email(payload: ContactRequest) -> None:
    smtp_host = _env_required("SMTP_HOST")
    smtp_port = int(_env_required("SMTP_PORT"))
    smtp_user = _env_required("SMTP_USER")
    smtp_password = _env_required("SMTP_PASSWORD")
    mail_from = _env_required("MAIL_FROM")
    mail_to = _env_required("MAIL_TO")

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg["Subject"] = f"Nouveau contact SmartCard - {payload.company_name}"
    msg["Reply-To"] = payload.email
    body_lines = [
        "Nouveau message du formulaire SmartCard",
        "",
        f"Prénom: {payload.first_name}",
        f"Nom: {payload.last_name}",
        f"Email: {payload.email}",
        f"Téléphone: {payload.phone}",
        f"Entreprise: {payload.company_name}",
        f"Source: {payload.source}",
    ]
    if payload.affiliate_ref:
        body_lines.append(f"Réf. affiliation: {payload.affiliate_ref}")
    body_lines.extend(["", "Message:", payload.message])

    msg.set_content("\n".join(body_lines))

    timeout = 20
    if smtp_port == 465:
        with smtplib.SMTP_SSL(
            smtp_host,
            smtp_port,
            timeout=timeout,
            context=ssl.create_default_context(),
        ) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=timeout) as server:
            server.ehlo()
            server.starttls(context=ssl.create_default_context())
            server.ehlo()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)


@router.post("/contact")
async def submit_contact(
    request: Request,
    body: dict = Body(...),
):
    client_ip = _get_client_ip(request)

    if _is_rate_limited(client_ip):
        logger.warning("Rate limit contact atteint (ip=%s)", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez dans une minute.",
        )

    try:
        payload = ContactRequest(**body)
    except ValidationError as exc:
        logger.warning("Validation contact invalide (ip=%s): %s", client_ip, exc.errors())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Données de formulaire invalides.",
        ) from exc

    if payload.honey:
        logger.warning("Honeypot détecté (ip=%s)", client_ip)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requête invalide.",
        )

    payload = ContactRequest(
        first_name=html.escape(payload.first_name, quote=False),
        last_name=html.escape(payload.last_name, quote=False),
        email=payload.email,
        phone=html.escape(payload.phone, quote=False),
        company_name=html.escape(payload.company_name, quote=False),
        message=html.escape(payload.message, quote=False),
        source=html.escape(payload.source, quote=False),
        honey=payload.honey,
        affiliate_ref=html.escape(payload.affiliate_ref, quote=False)
        if payload.affiliate_ref
        else "",
    )

    try:
        _send_contact_email(payload)
    except Exception as exc:
        logger.exception("Echec envoi email contact (ip=%s): %s", client_ip, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de l'envoi de l'email.",
        ) from exc

    logger.info(
        "Contact envoyé avec succès (ip=%s, email=%s, source=%s)",
        client_ip,
        _mask_email_for_log(str(payload.email)),
        payload.source,
    )
    return {"ok": True, "message": "Message envoyé avec succès."}
