"""Tests slug public : sanitize, redirect /c/, API /api/public/cards/."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Card, User
from app.utils.public_slug import sanitize_public_slug


def _seed_demo2(engine):
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = SessionTest()
    u = User(email="slugtest@example.invalid", password_hash="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    s.add(
        Card(
            user_id=u.id,
            company_name="Co",
            slug="demo2",
            plan_type="demo",
            region="fr",
            avatar_url="https://res.cloudinary.com/test/demo2-avatar.png",
        )
    )
    s.commit()
    s.close()
    return SessionTest


def _engine_and_session_with_demo2(tmpdir: str):
    path = Path(tmpdir) / "slug_test.db"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(bind=engine)
    SessionTest = _seed_demo2(engine)
    return engine, SessionTest


class SanitizePublicSlugTests(unittest.TestCase):
    def test_demo2_unchanged(self):
        self.assertEqual(sanitize_public_slug("demo2"), "demo2")

    def test_demo2_trailing_quote_removed(self):
        self.assertEqual(sanitize_public_slug('demo2"'), "demo2")

    def test_demo2_invisible_unicode_removed(self):
        self.assertEqual(sanitize_public_slug("demo2" + "\u2060" + "\ufffd"), "demo2")

    def test_demo2_percent_encoded_string(self):
        self.assertEqual(sanitize_public_slug("demo2%E2%81%A0%EF%BF%BD"), "demo2")

    def test_latam_slug_kept(self):
        self.assertEqual(sanitize_public_slug("demo-latam-plomero"), "demo-latam-plomero")

    def test_arnaud_slug_kept(self):
        self.assertEqual(sanitize_public_slug("arnaud-huard"), "arnaud-huard")

    def test_demo_demo3(self):
        self.assertEqual(sanitize_public_slug("demo"), "demo")
        self.assertEqual(sanitize_public_slug("demo3"), "demo3")

    def test_none_empty(self):
        self.assertEqual(sanitize_public_slug(None), "")
        self.assertEqual(sanitize_public_slug(""), "")


class FrPublicOgImageUrlTests(unittest.TestCase):
    """Règles og:image serveur (_fr_public_og_image_url) — demo2 marketing, arnaud-huard dédié."""

    base = "https://smartcard.maavnica.com"

    def test_demo2_uses_og_default_not_avatar(self):
        from app.main import _fr_public_og_image_url

        class CardWithAvatar:
            avatar_url = "https://res.cloudinary.com/x/image/upload/v1/demo.png"

        url = _fr_public_og_image_url(self.base, "demo2", CardWithAvatar())
        self.assertEqual(url, f"{self.base}/static/og-default.jpg?v=2")

    def test_arnaud_huard_uses_dedicated_jpg(self):
        from app.main import _fr_public_og_image_url

        class CardWithAvatar:
            avatar_url = "https://res.cloudinary.com/x/y.png"

        url = _fr_public_og_image_url(self.base, "arnaud-huard", CardWithAvatar())
        self.assertEqual(url, f"{self.base}/static/og-arnaud-huard.jpg")

    def test_other_slug_still_uses_avatar_when_present(self):
        from app.main import _fr_public_og_image_url

        class CardWithAvatar:
            avatar_url = "https://cdn.example/photo.jpg"

        url = _fr_public_og_image_url(self.base, "autre-pro", CardWithAvatar())
        self.assertEqual(url, "https://cdn.example/photo.jpg")


class PublicSlugHttpTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._engine, self.SessionTest = _engine_and_session_with_demo2(self._tmpdir.name)
        self._patcher = patch("app.database.SessionLocal", self.SessionTest)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._engine.dispose()
        self._tmpdir.cleanup()

    def test_redirect_dirty_slug_preserves_query(self):
        from fastapi.testclient import TestClient

        from app.main import app

        dirty_path = "/c/" + quote("demo2" + "\u2060" + "\ufffd", safe="")
        client = TestClient(app)
        r = client.get(dirty_path + "?fbclid=abc&r=rec_123", follow_redirects=False)
        self.assertEqual(r.status_code, 301)
        self.assertEqual(r.headers["location"], "/c/demo2?fbclid=abc&r=rec_123")

    def test_clean_slug_no_redirect(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)

    def test_c_demo2_html_og_image_is_default(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('property="og:image"', r.text)
        self.assertIn("/static/og-default.jpg?v=2", r.text)

    def test_c_demo2_classic_template_by_default(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("smartcard-v3", r.text)
        self.assertNotIn("/static/public-card/v3.css", r.text)

    def test_c_demo2_default_visual_theme_wellness_soft(self):
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-theme="wellness-soft"', r.text)

    def test_c_demo2_visual_theme_artisan_injected(self):
        from fastapi.testclient import TestClient

        from app.main import app

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.slug == "demo2").first()
            card.visual_theme = "artisan"
            db.commit()
        finally:
            db.close()

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-theme="artisan"', r.text)
        self.assertNotIn('data-theme="wellness-soft"', r.text)

    def test_c_demo2_experience_still_serves_classic(self):
        from fastapi.testclient import TestClient

        from app.main import app

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.slug == "demo2").first()
            card.card_theme = "experience"
            db.commit()
        finally:
            db.close()

        client = TestClient(app)
        r = client.get("/c/demo2", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("smartcard-v3", r.text)
        self.assertNotIn("SMARTCARD_V3_ACTIVE", r.text)
        self.assertNotIn("/static/public-card/v3.css", r.text)

    def test_api_public_cards_dirty_slug(self):
        from fastapi.testclient import TestClient

        from app.main import app

        seg = quote("demo2" + "\u2060" + "\ufffd", safe="")
        client = TestClient(app)
        r_clean = client.get("/api/public/cards/demo2")
        r_dirty = client.get(f"/api/public/cards/{seg}")
        self.assertEqual(r_clean.status_code, 200)
        self.assertEqual(r_dirty.status_code, 200)
        self.assertEqual(r_clean.json().get("slug"), "demo2")
        self.assertEqual(r_dirty.json().get("slug"), "demo2")


if __name__ == "__main__":
    unittest.main()
