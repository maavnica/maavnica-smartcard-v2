"""Prise en charge durable et concurrente des notifications de devis."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Literal, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, sessionmaker

from app.models import QuoteNotificationOutbox
from app.utils.log_safety import sanitize_log_text

logger = logging.getLogger(__name__)

OUTBOX_STATUSES = frozenset({"pending", "processing", "sent", "failed", "unknown"})
DEFAULT_LEASE_SECONDS = 120
DEFAULT_MAX_ATTEMPTS = 6
RETRY_DELAYS_SECONDS = (60, 300, 900, 3600, 21600)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sanitize_outbox_error(value: object, limit: int = 500) -> str:
    """Conserve un diagnostic exploitable sans adresse ni secret."""
    return sanitize_log_text(value, limit=limit)


@dataclass(frozen=True)
class NotificationJob:
    outbox_id: int
    quote_id: int
    recipient: Optional[str]
    idempotency_key: str
    lease_token: str


@dataclass(frozen=True)
class DeliveryOutcome:
    state: Literal["sent", "failed", "unknown"]
    transport: Optional[str] = None
    error: str = ""


DeliveryHandler = Callable[[NotificationJob], DeliveryOutcome]


def new_outbox(
    *,
    quote_id: int,
    recipient: Optional[str],
    now: Optional[datetime] = None,
) -> QuoteNotificationOutbox:
    timestamp = now or utc_now()
    return QuoteNotificationOutbox(
        quote_id=quote_id,
        recipient=(recipient or "").strip() or None,
        status="pending",
        attempts=0,
        next_attempt_at=timestamp,
        idempotency_key=str(uuid.uuid4()),
        processing_until=None,
        locked_by=None,
        created_at=timestamp,
        updated_at=timestamp,
        sent_at=None,
    )


def _eligible_filter(now: datetime):
    return or_(
        and_(
            QuoteNotificationOutbox.status == "pending",
            QuoteNotificationOutbox.next_attempt_at <= now,
        ),
        and_(
            QuoteNotificationOutbox.status == "processing",
            QuoteNotificationOutbox.processing_until.isnot(None),
            QuoteNotificationOutbox.processing_until <= now,
        ),
    )


def claim_notification(
    db: Session,
    *,
    outbox_id: Optional[int] = None,
    now: Optional[datetime] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> Optional[NotificationJob]:
    """Réserve puis commit une lease avant tout appel réseau."""
    timestamp = now or utc_now()
    query = db.query(QuoteNotificationOutbox).filter(_eligible_filter(timestamp))
    if outbox_id is not None:
        query = query.filter(QuoteNotificationOutbox.id == outbox_id)
    query = query.order_by(
        QuoteNotificationOutbox.next_attempt_at.asc(),
        QuoteNotificationOutbox.id.asc(),
    )
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    row = query.first()
    if row is None:
        db.rollback()
        return None

    lease_token = str(uuid.uuid4())
    row.status = "processing"
    row.processing_until = timestamp + timedelta(seconds=max(30, lease_seconds))
    row.locked_by = lease_token
    row.updated_at = timestamp
    db.commit()
    return NotificationJob(
        outbox_id=row.id,
        quote_id=row.quote_id,
        recipient=row.recipient,
        idempotency_key=row.idempotency_key,
        lease_token=lease_token,
    )


def _retry_at(now: datetime, attempts: int) -> datetime:
    index = min(max(attempts - 1, 0), len(RETRY_DELAYS_SECONDS) - 1)
    return now + timedelta(seconds=RETRY_DELAYS_SECONDS[index])


def finalize_notification(
    db: Session,
    job: NotificationJob,
    outcome: DeliveryOutcome,
    *,
    now: Optional[datetime] = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> bool:
    """Termine une tentative uniquement si sa lease est toujours propriétaire."""
    timestamp = now or utc_now()
    row = (
        db.query(QuoteNotificationOutbox)
        .filter(
            QuoteNotificationOutbox.id == job.outbox_id,
            QuoteNotificationOutbox.status == "processing",
            QuoteNotificationOutbox.locked_by == job.lease_token,
        )
        .first()
    )
    if row is None:
        db.rollback()
        logger.warning(
            "[OUTBOX] lease perdue outbox_id=%s quote_id=%s",
            job.outbox_id,
            job.quote_id,
        )
        return False

    row.attempts += 1
    row.updated_at = timestamp
    row.processing_until = None
    row.locked_by = None
    row.last_error = sanitize_outbox_error(outcome.error) or None

    if outcome.state == "sent":
        row.status = "sent"
        row.sent_at = timestamp
        row.next_attempt_at = timestamp
    elif outcome.state == "unknown":
        # Décision humaine requise : aucune relance automatique.
        row.status = "unknown"
        row.sent_at = None
        row.next_attempt_at = timestamp
    elif row.attempts >= max(1, max_attempts):
        row.status = "failed"
        row.sent_at = None
        row.next_attempt_at = timestamp
    else:
        row.status = "pending"
        row.sent_at = None
        row.next_attempt_at = _retry_at(timestamp, row.attempts)

    db.commit()
    return True


def process_one(
    session_factory: sessionmaker,
    handler: DeliveryHandler,
    *,
    outbox_id: Optional[int] = None,
    now: Optional[datetime] = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> Optional[DeliveryOutcome]:
    """Réserve une ligne, ferme la transaction, envoie, puis finalise."""
    with session_factory() as db:
        job = claim_notification(
            db,
            outbox_id=outbox_id,
            now=now,
            lease_seconds=lease_seconds,
        )
    if job is None:
        return None

    try:
        if not job.recipient:
            outcome = DeliveryOutcome(
                "failed",
                error="configuration missing: notification recipient",
            )
        else:
            outcome = handler(job)
    except Exception as exc:  # garde-fou : le processeur ne perd jamais la ligne
        safe_detail = sanitize_outbox_error(str(exc))
        logger.error(
            "[OUTBOX] handler failed outbox_id=%s quote_id=%s "
            "error_type=%s detail=%s",
            job.outbox_id,
            job.quote_id,
            type(exc).__name__,
            safe_detail or "-",
        )
        outcome = DeliveryOutcome(
            "unknown",
            error=(
                f"handler exception: {type(exc).__name__} "
                f"{safe_detail or '-'}"
            ),
        )

    with session_factory() as db:
        finalize_notification(
            db,
            job,
            outcome,
            now=now,
            max_attempts=max_attempts,
        )
    return outcome


def release_for_explicit_retry(
    db: Session,
    outbox_id: int,
    *,
    recipient: Optional[str] = None,
    now: Optional[datetime] = None,
) -> bool:
    """Replace explicitement une ligne failed/unknown en attente."""
    timestamp = now or utc_now()
    row = db.query(QuoteNotificationOutbox).filter_by(id=outbox_id).first()
    if row is None or row.status not in {"failed", "unknown"}:
        db.rollback()
        return False
    if recipient is not None:
        row.recipient = recipient.strip() or None
    row.status = "pending"
    row.next_attempt_at = timestamp
    row.processing_until = None
    row.locked_by = None
    row.last_error = None
    row.updated_at = timestamp
    db.commit()
    return True
