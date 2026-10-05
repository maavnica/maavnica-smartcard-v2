"""Traite un lot d'outbox ; point d'entrée pour un futur Cron Render."""

from __future__ import annotations

import argparse
import logging

from app.database import SessionLocal
from app.services.notification_outbox import process_one
from app.services.quote_notifications import deliver_quote_notification

logger = logging.getLogger(__name__)


def run(limit: int) -> dict[str, int]:
    counts = {"processed": 0, "sent": 0, "failed": 0, "unknown": 0}
    for _ in range(max(1, limit)):
        outcome = process_one(SessionLocal, deliver_quote_notification)
        if outcome is None:
            break
        counts["processed"] += 1
        counts[outcome.state] += 1
    logger.info(
        "[OUTBOX] batch complete processed=%s sent=%s failed=%s unknown=%s",
        counts["processed"],
        counts["sent"],
        counts["failed"],
        counts["unknown"],
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    run(args.limit)


if __name__ == "__main__":
    main()
