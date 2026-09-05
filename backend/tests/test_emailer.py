"""Choix de transport emailer + notify_pro (skip email_pro vide)."""

from __future__ import annotations

import io
import json
import os
import unittest
import urllib.error
from email.message import Message
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.database import get_db
from app.routers.public import _send_pro_notification, create_feedback, create_quote, notify_pro
from app.schemas import FeedbackCreate, QuoteCreate
from app.utils import emailer


def _smtp_env(**extra: str) -> dict[str, str]:
    base = {
        "SMTP_HOST": "smtp.example.test",
        "SMTP_PORT": "587",
        "SMTP_USER": "smtp-user@example.test",
        "SMTP_PASSWORD": "smtp-password-value",
        "MAIL_FROM": "from@maavnica.com",
    }
    base.update(extra)
    return base


class _DummySMTP:
    instances: list["_DummySMTP"] = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.logged_in = None
        self.sent = []
        self.started_tls = False
        _DummySMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self):
        return True

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


class EmailerTransportTests(unittest.TestCase):
    def setUp(self):
        _DummySMTP.instances = []

    def _send(self, smtp_only: bool = False, **env):
        with patch.dict(os.environ, env, clear=True):
            return emailer.send_email(
                "pro@maavnica.com",
                "Sujet test",
                "corps texte",
                "<p>html</p>",
                reply_to="prospect@example.com",
                smtp_only=smtp_only,
            )

    def test_cas1_brevo_absent_smtp_password_used(self):
        with (
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            patch.object(emailer.smtplib, "SMTP_SSL", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="INFO") as logs,
        ):
            ok = self._send(**_smtp_env())
        self.assertTrue(ok)
        self.assertEqual(len(_DummySMTP.instances), 1)
        inst = _DummySMTP.instances[0]
        self.assertEqual(inst.logged_in, ("smtp-user@example.test", "smtp-password-value"))
        msg = inst.sent[0]
        self.assertEqual(msg["From"], "from@maavnica.com")
        self.assertEqual(msg["To"], "pro@maavnica.com")
        self.assertEqual(msg["Reply-To"], "prospect@example.com")
        self.assertTrue(any("[MAIL] SMTP OK" in m for m in logs.output))
        self.assertFalse(any("[MAIL] BREVO OK" in m for m in logs.output))

    def test_smtp_pass_takes_precedence_over_smtp_password(self):
        with patch.object(emailer.smtplib, "SMTP", _DummySMTP):
            ok = self._send(
                **_smtp_env(SMTP_PASS="legacy-pass-value")
            )
        self.assertTrue(ok)
        self.assertEqual(
            _DummySMTP.instances[0].logged_in,
            ("smtp-user@example.test", "legacy-pass-value"),
        )

    def test_cas2_brevo_fails_then_smtp_fallback(self):
        fp = io.BytesIO(b'{"message":"sender not verified"}')
        err = urllib.error.HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            400,
            "Bad Request",
            hdrs=Message(),
            fp=fp,
        )

        with (
            patch.object(emailer.urllib.request, "urlopen", side_effect=err),
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="INFO") as logs,
        ):
            ok = self._send(**_smtp_env(BREVO_API_KEY="brevo-key-not-logged"))
        self.assertTrue(ok)
        self.assertEqual(len(_DummySMTP.instances), 1)
        joined = "\n".join(logs.output)
        self.assertIn("[MAIL] BREVO FAILED", joined)
        self.assertIn("http=400", joined)
        self.assertIn("[MAIL] SMTP OK", joined)
        self.assertNotIn("brevo-key-not-logged", joined)

    def test_cas3_brevo_ok_skips_smtp(self):
        fake_resp = MagicMock()
        fake_resp.read.return_value = b"{}"
        fake_resp.__enter__.return_value = fake_resp
        fake_resp.__exit__.return_value = False

        captured = {}

        def fake_urlopen(req, timeout=15):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data.decode("utf-8"))
            return fake_resp

        with (
            patch.object(emailer.urllib.request, "urlopen", side_effect=fake_urlopen),
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="INFO") as logs,
        ):
            ok = self._send(**_smtp_env(BREVO_API_KEY="brevo-key-not-logged"))
        self.assertTrue(ok)
        self.assertEqual(_DummySMTP.instances, [])
        self.assertTrue(any("[MAIL] BREVO OK" in m for m in logs.output))
        self.assertFalse(any("[MAIL] SMTP OK" in m for m in logs.output))
        self.assertEqual(captured["body"]["sender"]["email"], "from@maavnica.com")
        self.assertEqual(captured["body"]["replyTo"]["email"], "prospect@example.com")
        self.assertNotEqual(captured["body"]["sender"]["email"], "prospect@example.com")

    def test_cas4_no_transport(self):
        with (
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="WARNING") as logs,
        ):
            ok = self._send(MAIL_FROM="from@maavnica.com")
        self.assertFalse(ok)
        self.assertEqual(_DummySMTP.instances, [])
        self.assertTrue(any("[MAIL] SKIP NO TRANSPORT" in m for m in logs.output))

    def test_empty_recipient_skips(self):
        with (
            patch.dict(os.environ, _smtp_env(), clear=True),
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="WARNING") as logs,
        ):
            ok = emailer.send_email("", "Sujet", "texte")
        self.assertFalse(ok)
        self.assertEqual(_DummySMTP.instances, [])
        self.assertTrue(any("[MAIL] SKIP NO RECIPIENT" in m for m in logs.output))

    def test_send_email_four_positional_args_still_work(self):
        """Compat affiliate_kit.py : send_email(to, subject, text, html)."""
        with (
            patch.dict(os.environ, _smtp_env(), clear=True),
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
        ):
            ok = emailer.send_email(
                "kit@example.com",
                "Kit",
                "plain",
                "<p>html</p>",
            )
        self.assertTrue(ok)
        self.assertIsNone(_DummySMTP.instances[0].sent[0]["Reply-To"])

    def test_smartcard_smtp_only_ignores_brevo(self):
        fake_urlopen = MagicMock(side_effect=AssertionError("Brevo ne doit pas être appelé"))
        with (
            patch.object(emailer.urllib.request, "urlopen", fake_urlopen),
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            self.assertLogs("app.utils.emailer", level="INFO") as logs,
        ):
            ok = self._send(
                smtp_only=True,
                **_smtp_env(BREVO_API_KEY="brevo-key-not-logged", SMTP_FROM="other@example.com"),
            )
        self.assertTrue(ok)
        fake_urlopen.assert_not_called()
        inst = _DummySMTP.instances[0]
        self.assertTrue(inst.started_tls)
        self.assertEqual(inst.logged_in, ("smtp-user@example.test", "smtp-password-value"))
        msg = inst.sent[0]
        self.assertEqual(msg["From"], "from@maavnica.com")
        self.assertEqual(msg["To"], "pro@maavnica.com")
        self.assertEqual(msg["Reply-To"], "prospect@example.com")
        self.assertTrue(any("[MAIL] SMTP OK" in m for m in logs.output))
        self.assertFalse(any("[MAIL] BREVO" in m for m in logs.output))

    def test_smartcard_smtp_only_uses_ssl_on_465(self):
        smtp_plain = MagicMock(side_effect=AssertionError("SMTP plain ne doit pas être appelé"))
        with (
            patch.object(emailer.smtplib, "SMTP", smtp_plain),
            patch.object(emailer.smtplib, "SMTP_SSL", _DummySMTP),
        ):
            ok = self._send(smtp_only=True, **_smtp_env(SMTP_PORT="465"))
        self.assertTrue(ok)
        self.assertEqual(len(_DummySMTP.instances), 1)
        self.assertFalse(_DummySMTP.instances[0].started_tls)
        smtp_plain.assert_not_called()

    def test_smartcard_smtp_only_ignores_smtp_pass(self):
        with patch.object(emailer.smtplib, "SMTP", _DummySMTP):
            ok = self._send(
                smtp_only=True,
                **_smtp_env(SMTP_PASS="legacy-pass-value"),
            )
        self.assertTrue(ok)
        self.assertEqual(
            _DummySMTP.instances[0].logged_in,
            ("smtp-user@example.test", "smtp-password-value"),
        )


def _card_pro() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        email_pro="contact@maavnica.com",
        company_name="Maavnica",
        slug="arnaud-huard",
        profile="digital",
    )


def _db_committed(lead_id: int = 36) -> MagicMock:
    db = MagicMock()

    def _refresh(obj):
        obj.id = lead_id

    db.refresh.side_effect = _refresh
    return db


def _quote_payload() -> QuoteCreate:
    return QuoteCreate(
        name="Test SMTP",
        phone="0612345678",
        message="Demande de demo",
        email="prospect@example.com",
    )


class NotifyProTests(unittest.TestCase):
    def test_cas5_empty_email_pro_skips_send(self):
        card = SimpleNamespace(id=10, email_pro=None)
        with (
            patch("app.routers.public.send_email") as mocked,
            self.assertLogs("app.routers.public", level="WARNING") as logs,
        ):
            notify_pro(card, "Sujet", "texte", "<p>x</p>", reply_to="a@b.c")
        mocked.assert_not_called()
        self.assertTrue(any("[MAIL] SKIP NO RECIPIENT" in m for m in logs.output))

    def test_blank_email_pro_skips_send(self):
        card = SimpleNamespace(id=10, email_pro="   ")
        with (
            patch("app.routers.public.send_email") as mocked,
            self.assertLogs("app.routers.public", level="WARNING") as logs,
        ):
            notify_pro(card, "Sujet", "texte", "<p>x</p>")
        mocked.assert_not_called()
        self.assertTrue(any("[MAIL] SKIP NO RECIPIENT" in m for m in logs.output))

    def test_notify_pro_calls_send_email_directly(self):
        card = _card_pro()
        with (
            patch("app.routers.public.send_email", return_value=True) as mocked,
            self.assertLogs("app.routers.public", level="INFO") as logs,
        ):
            notify_pro(
                card,
                "Sujet",
                "texte",
                "<p>x</p>",
                reply_to="prospect@example.com",
            )
        mocked.assert_called_once_with(
            "contact@maavnica.com",
            "Sujet",
            "texte",
            "<p>x</p>",
            reply_to="prospect@example.com",
            smtp_only=True,
        )
        self.assertTrue(any("[MAIL] notify_pro ok" in m for m in logs.output))

    def test_create_quote_commits_before_direct_notification(self):
        db = _db_committed(36)
        order: list[str] = []
        db.commit.side_effect = lambda: order.append("commit")

        def _notify(*args, **kwargs):
            order.append("notify")

        with (
            patch("app.routers.public.get_card_by_id_or_404", return_value=_card_pro()),
            patch("app.routers.public._send_pro_notification", side_effect=_notify) as notify,
        ):
            result = create_quote(10, _quote_payload(), db)

        self.assertEqual(result, {"message": "Quote created", "id": 36})
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], "contact@maavnica.com")
        self.assertEqual(notify.call_args.args[4], "prospect@example.com")
        self.assertEqual(order, ["commit", "notify"])

    def test_create_quote_smtp_failure_keeps_lead_and_http_201(self):
        self._assert_public_post_keeps_201(
            "/api/public/cards/10/quotes",
            {
                "name": "Test SMTP",
                "phone": "0612345678",
                "message": "Demande de demo",
                "email": "prospect@example.com",
            },
            send_ok=False,
        )

    def test_create_quote_smtp_success_keeps_http_201(self):
        self._assert_public_post_keeps_201(
            "/api/public/cards/10/quotes",
            {
                "name": "Test SMTP",
                "phone": "0612345678",
                "message": "Demande de demo",
                "email": "prospect@example.com",
            },
            send_ok=True,
        )

    def test_create_feedback_commits_before_direct_notification(self):
        db = _db_committed(12)
        order: list[str] = []
        db.commit.side_effect = lambda: order.append("commit")

        def _notify(*args, **kwargs):
            order.append("notify")

        payload = FeedbackCreate(satisfaction=True, comment="Super echange")
        with (
            patch("app.routers.public.get_card_by_id_or_404", return_value=_card_pro()),
            patch("app.routers.public._send_pro_notification", side_effect=_notify) as notify,
        ):
            result = create_feedback(10, payload, db)

        self.assertEqual(result, {"message": "Feedback created", "id": 12})
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        notify.assert_called_once()
        self.assertEqual(notify.call_args.args[0], "contact@maavnica.com")
        self.assertIsNone(notify.call_args.args[4])
        self.assertEqual(order, ["commit", "notify"])

    def test_create_feedback_smtp_failure_keeps_lead_and_http_201(self):
        self._assert_public_post_keeps_201(
            "/api/public/cards/10/feedback",
            {"satisfaction": True, "comment": "Super echange"},
            send_ok=False,
        )

    def test_create_feedback_smtp_success_keeps_http_201(self):
        self._assert_public_post_keeps_201(
            "/api/public/cards/10/feedback",
            {"satisfaction": True, "comment": "Super echange"},
            send_ok=True,
        )

    def test_send_pro_notification_calls_send_email_smtp_only(self):
        with patch("app.routers.public.send_email", return_value=True) as mocked:
            _send_pro_notification(
                "contact@maavnica.com",
                "Sujet",
                "texte",
                "<p>x</p>",
                "prospect@example.com",
                10,
            )
        mocked.assert_called_once_with(
            "contact@maavnica.com",
            "Sujet",
            "texte",
            "<p>x</p>",
            reply_to="prospect@example.com",
            smtp_only=True,
        )

    def test_sync_path_uses_same_smtp_contact_function(self):
        """Appel direct : send_email → _send_via_smtp_contact (SMTP-only)."""
        _DummySMTP.instances = []
        with (
            patch.dict(os.environ, _smtp_env(BREVO_API_KEY="must-not-be-used"), clear=True),
            patch.object(emailer.urllib.request, "urlopen") as brevo,
            patch.object(emailer.smtplib, "SMTP", _DummySMTP),
            patch.object(
                emailer,
                "_send_via_smtp_contact",
                wraps=emailer._send_via_smtp_contact,
            ) as smtp_contact,
            self.assertLogs("app.utils.emailer", level="INFO") as logs,
        ):
            _send_pro_notification(
                "contact@maavnica.com",
                "Sujet sync",
                "corps texte",
                "<p>html</p>",
                "prospect@example.com",
                10,
            )
        brevo.assert_not_called()
        smtp_contact.assert_called_once()
        self.assertEqual(smtp_contact.call_args.kwargs["to_email"], "contact@maavnica.com")
        self.assertEqual(smtp_contact.call_args.kwargs["reply_to"], "prospect@example.com")
        self.assertEqual(len(_DummySMTP.instances), 1)
        msg = _DummySMTP.instances[0].sent[0]
        self.assertEqual(msg["From"], "from@maavnica.com")
        self.assertEqual(msg["To"], "contact@maavnica.com")
        self.assertEqual(msg["Reply-To"], "prospect@example.com")
        self.assertTrue(any("[MAIL] SMTP OK" in m for m in logs.output))

    def _assert_public_post_keeps_201(self, path: str, payload: dict, *, send_ok: bool) -> None:
        from app.main import app

        db = _db_committed(36)

        def _override_db():
            yield db

        app.dependency_overrides[get_db] = _override_db
        try:
            with (
                patch("app.routers.public.get_card_by_id_or_404", return_value=_card_pro()),
                patch("app.routers.public.send_email", return_value=send_ok) as mocked,
            ):
                client = TestClient(app)
                response = client.post(path, json=payload)
        finally:
            app.dependency_overrides.pop(get_db, None)

        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn("id", response.json())
        db.commit.assert_called_once()
        db.rollback.assert_not_called()
        mocked.assert_called_once()
        self.assertEqual(mocked.call_args.kwargs.get("smtp_only"), True)
        self.assertEqual(mocked.call_args.args[0], "contact@maavnica.com")


if __name__ == "__main__":
    unittest.main()
