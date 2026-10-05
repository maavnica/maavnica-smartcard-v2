"""Outbox de devis : atomicité logique, lease, reprise et confidentialité."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import Card, Quote, QuoteNotificationOutbox, User
from app.routers.admin_notifications import list_notifications, retry_notification
from app.schemas import CardCreate, CardPublic, CardUpdate
from app.services.notification_outbox import (
    DeliveryOutcome,
    claim_notification,
    new_outbox,
    process_one,
    sanitize_outbox_error,
    utc_now,
)
from app.services.quote_notifications import (
    build_quote_notification,
    resolve_notification_recipient,
)


class NotificationOutboxTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        db_path = Path(self._tmp.name) / "outbox.sqlite3"
        self.engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

        with self.sessions() as db:
            user = User(email="owner@example.test", password_hash="x")
            db.add(user)
            db.flush()
            card = Card(
                user_id=user.id,
                company_name="Maavnica",
                slug="maavnica-test",
                profile="digital",
                email_pro="public@maavnica.test",
                notification_email="private@gmail.test",
            )
            db.add(card)
            db.flush()
            quote = Quote(
                card_id=card.id,
                name="Prospect",
                email="prospect@example.test",
                phone="0612345678",
                message="Demande",
            )
            db.add(quote)
            db.flush()
            outbox = new_outbox(
                quote_id=quote.id,
                recipient=card.notification_email or card.email_pro,
            )
            db.add(outbox)
            db.commit()
            self.outbox_id = outbox.id
            self.quote_id = quote.id

    def tearDown(self):
        self.engine.dispose()
        self._tmp.cleanup()

    def test_new_outbox_has_private_recipient_and_unique_key(self):
        with self.sessions() as db:
            row = db.get(QuoteNotificationOutbox, self.outbox_id)
            self.assertEqual(row.recipient, "private@gmail.test")
            self.assertEqual(row.status, "pending")
            self.assertEqual(row.attempts, 0)
            self.assertEqual(len(row.idempotency_key), 36)

    def test_postgresql_migration_uses_timezone_aware_timestamps(self):
        ddl = str(
            CreateTable(QuoteNotificationOutbox.__table__).compile(
                dialect=postgresql.dialect()
            )
        )
        self.assertIn("TIMESTAMP WITH TIME ZONE", ddl)

    def test_notification_email_then_email_pro_fallback(self):
        with self.sessions() as db:
            quote = db.get(Quote, self.quote_id)
            card = db.get(Card, quote.card_id)
            self.assertEqual(
                resolve_notification_recipient(card),
                "private@gmail.test",
            )
            card.notification_email = None
            self.assertEqual(
                resolve_notification_recipient(card),
                "public@maavnica.test",
            )

    def test_notification_email_is_admin_input_but_not_public_output(self):
        self.assertIn("notification_email", CardCreate.model_fields)
        self.assertIn("notification_email", CardUpdate.model_fields)
        self.assertNotIn("notification_email", CardPublic.model_fields)

    def test_reply_to_is_prospect_email(self):
        with self.sessions() as db:
            quote = db.get(Quote, self.quote_id)
            card = db.get(Card, quote.card_id)
            message = build_quote_notification(card, quote)
        self.assertEqual(message.reply_to, "prospect@example.test")

    def test_lease_prevents_two_workers_and_expires(self):
        now = utc_now()
        with self.sessions() as db:
            first = claim_notification(db, outbox_id=self.outbox_id, now=now)
        self.assertIsNotNone(first)

        with self.sessions() as db:
            concurrent = claim_notification(
                db,
                outbox_id=self.outbox_id,
                now=now + timedelta(seconds=30),
            )
        self.assertIsNone(concurrent)

        with self.sessions() as db:
            recovered = claim_notification(
                db,
                outbox_id=self.outbox_id,
                now=now + timedelta(seconds=121),
            )
        self.assertIsNotNone(recovered)
        self.assertNotEqual(first.lease_token, recovered.lease_token)

    def test_known_failure_is_persisted_then_retried_after_restart(self):
        first = process_one(
            self.sessions,
            lambda _job: DeliveryOutcome("failed", "smtp", "HTTP 500"),
            outbox_id=self.outbox_id,
        )
        self.assertEqual(first.state, "failed")
        with self.sessions() as db:
            row = db.get(QuoteNotificationOutbox, self.outbox_id)
            self.assertEqual(row.status, "pending")
            self.assertEqual(row.attempts, 1)
            row.next_attempt_at = utc_now() - timedelta(seconds=1)
            db.commit()

        # Nouvelle invocation indépendante, équivalente à un redémarrage/Cron.
        second = process_one(
            self.sessions,
            lambda _job: DeliveryOutcome("sent", "brevo"),
            outbox_id=self.outbox_id,
        )
        self.assertEqual(second.state, "sent")
        with self.sessions() as db:
            row = db.get(QuoteNotificationOutbox, self.outbox_id)
            self.assertEqual(row.status, "sent")
            self.assertEqual(row.attempts, 2)
            self.assertIsNotNone(row.sent_at)

    def test_unknown_is_not_retried_automatically(self):
        outcome = process_one(
            self.sessions,
            lambda _job: DeliveryOutcome("unknown", "brevo", "TimeoutError"),
            outbox_id=self.outbox_id,
        )
        self.assertEqual(outcome.state, "unknown")
        with self.sessions() as db:
            row = db.get(QuoteNotificationOutbox, self.outbox_id)
            self.assertEqual(row.status, "unknown")

        repeated = process_one(
            self.sessions,
            lambda _job: self.fail("unknown ne doit pas être repris automatiquement"),
            outbox_id=self.outbox_id,
        )
        self.assertIsNone(repeated)

    def test_unexpected_handler_error_masks_email_in_logs_and_last_error(self):
        raw_email = "unexpected.prospect@example.com"

        def failing_handler(_job):
            raise RuntimeError(f"provider failed for {raw_email}")

        with self.assertLogs(
            "app.services.notification_outbox",
            level="ERROR",
        ) as logs:
            outcome = process_one(
                self.sessions,
                failing_handler,
                outbox_id=self.outbox_id,
            )

        self.assertEqual(outcome.state, "unknown")
        dumped = "\n".join(logs.output)
        self.assertNotIn(raw_email, dumped)
        self.assertIn("***@***", dumped)
        with self.sessions() as db:
            row = db.get(QuoteNotificationOutbox, self.outbox_id)
            self.assertEqual(row.status, "unknown")
            self.assertNotIn(raw_email, row.last_error)
            self.assertIn("***@***", row.last_error)

    def test_unknown_requires_explicit_admin_confirmation(self):
        process_one(
            self.sessions,
            lambda _job: DeliveryOutcome("unknown", "brevo", "TimeoutError"),
            outbox_id=self.outbox_id,
        )
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as raised:
                retry_notification(self.outbox_id, confirm_unknown=False, db=db)
            self.assertEqual(raised.exception.status_code, 409)
        with self.sessions() as db:
            result = retry_notification(
                self.outbox_id,
                confirm_unknown=True,
                db=db,
            )
        self.assertEqual(result, {"id": self.outbox_id, "status": "pending"})

    def test_admin_listing_never_displays_recipient(self):
        with self.sessions() as db:
            result = list_notifications(status_filter=None, limit=50, db=db)
        dumped = str(result)
        self.assertNotIn("private@gmail.test", dumped)
        self.assertNotIn("recipient", dumped)

    def test_errors_are_sanitized(self):
        value = sanitize_outbox_error(
            "prospect@example.test api_key=secret-value\nSMTP timeout"
        )
        self.assertNotIn("prospect@example.test", value)
        self.assertNotIn("secret-value", value)
        self.assertIn("***@***", value)


if __name__ == "__main__":
    unittest.main()
