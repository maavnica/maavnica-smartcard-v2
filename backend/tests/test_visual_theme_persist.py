"""Persistance admin visual_theme (PUT /api/cards/{id})."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Card, User


def _seed(engine):
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    s = SessionTest()
    u = User(email="vt@example.invalid", password_hash="x")
    s.add(u)
    s.commit()
    s.refresh(u)
    card = Card(
        user_id=u.id,
        company_name="Co",
        slug="demo-vt",
        plan_type="demo",
        region="fr",
        visual_theme="wellness-soft",
        theme="sante-wow",
        card_theme="experience",
    )
    s.add(card)
    s.commit()
    s.refresh(card)
    card_id = card.id
    s.close()
    return SessionTest, card_id


class VisualThemePersistTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        path = Path(self._tmpdir.name) / "vt.db"
        self._engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(bind=self._engine)
        self.SessionTest, self.card_id = _seed(self._engine)
        self._patcher = patch("app.database.SessionLocal", self.SessionTest)
        self._patcher.start()
        self._env = patch.dict(os.environ, {"ADMIN_API_KEY": "test-admin-key"})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._patcher.stop()
        self._engine.dispose()
        self._tmpdir.cleanup()

    def test_put_visual_theme_artisan_persists(self):
        from app.main import app

        client = TestClient(app)
        payload = {
            "company_name": "Co",
            "slug": "demo-vt",
            "plan_type": "demo",
            "region": "fr",
            "card_theme": "classic",
            "visual_theme": "artisan",
            "profile": "artisan",
            "theme": "apple",
        }
        r = client.put(
            f"/api/cards/{self.card_id}",
            json=payload,
            headers={"Authorization": "Bearer test-admin-key"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("visual_theme"), "artisan")

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.id == self.card_id).first()
            self.assertEqual(card.visual_theme, "artisan")
        finally:
            db.close()

    def test_resolve_visual_theme_prefers_sql_over_stale_orm(self):
        from app.database import write_card_visual_theme
        from app.main import _resolve_visual_theme

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.id == self.card_id).first()
            write_card_visual_theme(db, card.id, "artisan")
            db.commit()
            card.visual_theme = "wellness-soft"
            resolved = _resolve_visual_theme(card, db, slug="demo-vt")
            self.assertEqual(resolved, "artisan")
        finally:
            db.close()

    def test_put_admin_payload_without_legacy_theme_fields(self):
        """Payload admin simplifié : visual_theme + profile sans theme/card_theme."""
        from app.main import app

        client = TestClient(app)
        payload = {
            "company_name": "Co",
            "slug": "demo-vt",
            "plan_type": "demo",
            "region": "fr",
            "visual_theme": "artisan",
            "profile": "bien_etre",
        }
        r = client.put(
            f"/api/cards/{self.card_id}",
            json=payload,
            headers={"Authorization": "Bearer test-admin-key"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json().get("visual_theme"), "artisan")
        self.assertEqual(r.json().get("profile"), "bien_etre")

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.id == self.card_id).first()
            self.assertEqual(card.visual_theme, "artisan")
            self.assertEqual(card.profile, "bien_etre")
            self.assertEqual(card.theme, "sante-wow")
            self.assertEqual(card.card_theme, "experience")
        finally:
            db.close()

    def test_get_public_card_injects_artisan(self):
        from app.main import app

        db = self.SessionTest()
        try:
            card = db.query(Card).filter(Card.id == self.card_id).first()
            card.visual_theme = "artisan"
            db.commit()
        finally:
            db.close()

        client = TestClient(app)
        r = client.get("/c/demo-vt", follow_redirects=False)
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-theme="artisan"', r.text)


    def test_themes_css_contains_artisan_rules(self):
        from pathlib import Path

        css = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "public-card"
            / "themes.css"
        ).read_text(encoding="utf-8")
        self.assertIn('body[data-theme="artisan"]', css)
        self.assertIn('body[data-theme="artisan"] .phone-inner', css)
        wellness_part, artisan_part = css.split('body[data-theme="artisan"]', 1)
        self.assertIn("#3b6a52", wellness_part)
        self.assertIn("#8b5e3c", artisan_part)
        self.assertIn("#5a615e", artisan_part)


if __name__ == "__main__":
    unittest.main()
