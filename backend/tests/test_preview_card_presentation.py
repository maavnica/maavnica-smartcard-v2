"""Rendu cartes preview : titre long visible, CTA mailto, pas de devis."""

from __future__ import annotations

import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models import Base, CardEvent, CardVisit, Quote, RecommendationEvent
from tests.preview_card_fixtures import (
    CLIENT_SLUG,
    PREVIEW_ARTISAN_SLUG,
    PREVIEW_LONG_TITLE_SLUG,
    seed_preview_safety_cards,
)

ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_CSS = ROOT / "backend" / "static" / "public-card" / "components.css"
WELLNESS_CSS = ROOT / "backend" / "static" / "public-card" / "wellness-soft.css"
ARTISAN_CSS = ROOT / "backend" / "static" / "public-card" / "artisan-premium.css"
SHARED_JS = ROOT / "backend" / "static" / "public-card" / "shared.js"
INDEX_HTML = ROOT / "backend" / "static" / "public-card" / "index.html"
LONG_TITLE = "PROJINOV Menuiseries Auxerre"


class PreviewPresentationStaticTests(unittest.TestCase):
    def test_hero_title_wraps_long_names_without_ellipsis_clip(self):
        css = COMPONENTS_CSS.read_text(encoding="utf-8")
        match = re.search(r"\.hero-title\s*\{([^}]+)\}", css)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertIn("white-space: normal", block)
        self.assertIn("overflow: visible", block)
        self.assertIn("overflow-wrap: break-word", block)
        self.assertIn("text-wrap: balance", block)
        self.assertIn("max-width: 100%", block)
        self.assertIn("min-width: 0", block)
        self.assertNotIn("white-space: nowrap", block)
        self.assertNotIn("text-overflow: ellipsis", block)
        self.assertNotIn("overflow: hidden", block)

        wellness = WELLNESS_CSS.read_text(encoding="utf-8")
        self.assertIn("#person-name.hero-title", wellness)
        self.assertIn("white-space: normal", wellness)
        self.assertIn("overflow-wrap: break-word", wellness)
        self.assertIn("text-align: center", wellness)
        self.assertIn("line-height: 1.15", wellness)
        self.assertIn("clamp(2.35rem, 8.2vw, 2.95rem)", wellness)

        artisan = ARTISAN_CSS.read_text(encoding="utf-8")
        self.assertIn("body[data-theme=\"artisan\"] .hero-texts", artisan)
        self.assertIn("max-width: 100%", artisan)
        self.assertIn("min-width: 0", artisan)

    def test_preview_cta_is_maavnica_mailto_not_quote(self):
        js = SHARED_JS.read_text(encoding="utf-8")
        css = COMPONENTS_CSS.read_text(encoding="utf-8")
        self.assertIn('PREVIEW_EXCHANGE_LABEL = "Échanger avec Maavnica"', js)
        self.assertIn('PREVIEW_EXCHANGE_MAILTO = "mailto:contact@maavnica.com"', js)
        self.assertNotIn("mailto:contact@maavnica.com?subject", js)
        self.assertNotIn("mailto:contact@maavnica.com?body", js)
        self.assertIn("function applyPreviewExchangePresentation", js)
        self.assertIn("window.location.href = PREVIEW_EXCHANGE_MAILTO", js)
        self.assertIn("if (isPreviewSafeMode)", js)
        self.assertIn("body.preview-card-mode #panel-quote", css)
        self.assertIn("body.preview-card-mode #btn-send-quote", css)
        self.assertIn("body.preview-card-mode #acc-trigger-quote", css)
        self.assertIn("body.preview-card-mode .qr-copy-hint--default", css)

    def test_standard_card_cta_source_unchanged(self):
        js = SHARED_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('"Demande de devis"', js)
        self.assertIn("!isPreviewSafeMode", js)
        self.assertIn("function resolvePremiumHeroCta", js)
        self.assertIn(">Demande de contact</span>", html)
        self.assertNotIn("Échanger avec Maavnica", html)


class PreviewPresentationApiTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        path = Path(self._tmpdir.name) / "preview_presentation.db"
        self._engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(bind=self._engine)
        self.SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=self._engine)
        session = self.SessionTest()
        try:
            self.ids = seed_preview_safety_cards(session)
        finally:
            session.close()
        self._patcher = patch("app.database.SessionLocal", self.SessionTest)
        self._patcher.start()
        self._env = patch.dict(os.environ, {"ADMIN_API_KEY": "test-admin-key"})
        self._env.start()

    def tearDown(self):
        self._env.stop()
        self._patcher.stop()
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _client(self) -> TestClient:
        from app.main import app

        return TestClient(app)

    def _count(self, model, **filters) -> int:
        db = self.SessionTest()
        try:
            q = db.query(func.count(model.id))
            for key, value in filters.items():
                q = q.filter(getattr(model, key) == value)
            return int(q.scalar() or 0)
        finally:
            db.close()

    def test_long_company_title_is_complete_in_public_payload_and_html(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{PREVIEW_LONG_TITLE_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["company_name"], LONG_TITLE)
        self.assertEqual(data["display_name"], LONG_TITLE)
        self.assertTrue(data["is_preview"])
        html = client.get(f"/c/{PREVIEW_LONG_TITLE_SLUG}")
        self.assertEqual(html.status_code, 200)
        self.assertIn('id="person-name"', html.text)
        self.assertIn("preview-proposition-frame", html.text)
        self.assertIn("preview-card-mode", html.text)
        self.assertIn('data-preview="1"', html.text)
        self.assertIn("Proposition personnalisée Maavnica", html.text)

    def test_preview_cta_label_and_mailto_without_devis(self):
        client = self._client()
        html = client.get(f"/c/{PREVIEW_LONG_TITLE_SLUG}").text
        self.assertIn("Échanger avec Maavnica", html)
        self.assertIn("mailto:contact@maavnica.com", SHARED_JS.read_text(encoding="utf-8"))
        cta = re.search(
            r'id="wellness-cta-label"[^>]*>(.*?)</span>',
            html,
            re.IGNORECASE | re.DOTALL,
        )
        self.assertIsNotNone(cta)
        self.assertEqual(cta.group(1).strip(), "Échanger avec Maavnica")
        self.assertNotIn("devis", cta.group(1).lower())
        self.assertNotIn("Demande de devis", html.split('id="wellness-cta-label"')[1][:200])

    def test_preview_quote_post_still_blocked(self):
        client = self._client()
        card_id = self.ids[PREVIEW_ARTISAN_SLUG]
        before = self._count(Quote, card_id=card_id)
        r = client.post(
            f"/api/public/cards/{card_id}/quotes",
            json={"name": "Jeanne", "phone": "0612345678", "message": "devis"},
        )
        self.assertEqual(r.status_code, 403, r.text)
        self.assertEqual(self._count(Quote, card_id=card_id), before)

    def test_preview_analytics_not_written(self):
        client = self._client()
        slug = PREVIEW_LONG_TITLE_SLUG
        before_v = self._count(CardVisit, slug=slug)
        before_e = self._count(CardEvent, slug=slug)
        before_r = self._count(RecommendationEvent, card_slug=slug)
        self.assertEqual(client.post("/api/analytics/visit", json={"slug": slug}).status_code, 204)
        self.assertEqual(
            client.post(
                "/api/analytics/event",
                json={"slug": slug, "event_type": "phone_click"},
            ).status_code,
            204,
        )
        self.assertEqual(self._count(CardVisit, slug=slug), before_v)
        self.assertEqual(self._count(CardEvent, slug=slug), before_e)
        self.assertEqual(self._count(RecommendationEvent, card_slug=slug), before_r)

    def test_standard_card_still_accepts_quotes_and_keeps_cta(self):
        client = self._client()
        card_id = self.ids[CLIENT_SLUG]
        r = client.post(
            f"/api/public/cards/{card_id}/quotes",
            json={"name": "Jeanne", "phone": "0612345678", "message": "devis client"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        pub = client.get(f"/api/public/cards/{CLIENT_SLUG}")
        self.assertFalse(pub.json().get("is_preview"))
        html = client.get(f"/c/{CLIENT_SLUG}").text
        self.assertNotIn("preview-card-mode", html)
        self.assertNotIn("Échanger avec Maavnica", html)
        self.assertIn("Demande de contact", html)
        self.assertIn('"Demande de devis"', SHARED_JS.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
