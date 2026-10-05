"""Pilotage administratif de l'outbox des demandes de devis."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import Card, Quote, QuoteNotificationOutbox
from app.services.notification_outbox import process_one, release_for_explicit_retry
from app.services.quote_notifications import (
    deliver_quote_notification,
    resolve_notification_recipient,
)
from app.utils.admin_auth import require_admin_api_key

router = APIRouter(
    prefix="/api/admin/notification-outbox",
    tags=["admin-notifications"],
    dependencies=[Depends(require_admin_api_key)],
)


def _summary(row: QuoteNotificationOutbox) -> dict:
    # Aucune adresse complète ni contenu du devis dans la réponse.
    return {
        "id": row.id,
        "quote_id": row.quote_id,
        "status": row.status,
        "attempts": row.attempts,
        "next_attempt_at": row.next_attempt_at,
        "processing_until": row.processing_until,
        "last_error": row.last_error,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
        "sent_at": row.sent_at,
    }


@router.get("")
def list_notifications(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(QuoteNotificationOutbox)
    if status_filter:
        if status_filter not in {"pending", "processing", "sent", "failed", "unknown"}:
            raise HTTPException(status_code=400, detail="Statut outbox invalide.")
        query = query.filter(QuoteNotificationOutbox.status == status_filter)
    rows = query.order_by(QuoteNotificationOutbox.id.desc()).limit(limit).all()
    return {"items": [_summary(row) for row in rows]}


@router.post("/process")
def process_notifications(
    limit: int = Query(20, ge=1, le=100),
):
    counts = {"sent": 0, "failed": 0, "unknown": 0}
    processed = 0
    for _ in range(limit):
        outcome = process_one(SessionLocal, deliver_quote_notification)
        if outcome is None:
            break
        processed += 1
        counts[outcome.state] += 1
    return {"processed": processed, **counts}


@router.post("/{outbox_id}/retry")
def retry_notification(
    outbox_id: int,
    confirm_unknown: bool = Query(False),
    db: Session = Depends(get_db),
):
    row = db.query(QuoteNotificationOutbox).filter_by(id=outbox_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification introuvable.")
    if row.status == "unknown" and not confirm_unknown:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Résultat ambigu : confirmer explicitement la relance "
                "avec confirm_unknown=true."
            ),
        )
    if row.status not in {"failed", "unknown"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Seules les notifications failed ou unknown sont relançables.",
        )

    quote = db.query(Quote).filter(Quote.id == row.quote_id).first()
    card = (
        db.query(Card).filter(Card.id == quote.card_id).first()
        if quote is not None
        else None
    )
    recipient = resolve_notification_recipient(card) if card is not None else None
    if not release_for_explicit_retry(db, outbox_id, recipient=recipient):
        raise HTTPException(status_code=409, detail="Relance impossible.")
    return {"id": outbox_id, "status": "pending"}
