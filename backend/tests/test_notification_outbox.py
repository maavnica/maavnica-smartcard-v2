"""Outbox de devis : atomicité logique, lease, reprise et confidentialité."""

from __future__ import annotations

import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Card, Quote, QuoteNotificationOutbox, User
from app.services.notification_outbox import (
    DeliveryOutcome,
    claim_notification,
    new_outbox,
    process_one,
    sanitize_outbox_error,
    utc_now,
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

    def test_errors_are_sanitized(self):
        value = sanitize_outbox_error(
            "prospect@example.test api_key=secret-value\nSMTP timeout"
        )
        self.assertNotIn("prospect@example.test", value)
        self.assertNotIn("secret-value", value)
        self.assertIn("***@***", value)


if __name__ == "__main__":
    unittest.main()
