"""Sécurité du mode carte preview — indépendant du slug, sans écriture métier."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from app.models import Base, CardEvent, CardVisit, Feedback, Quote, RecommendationEvent
from tests.preview_card_fixtures import (
    CLASSIC_DEMO_SLUG,
    CLASSIC_EXPIRED_SLUG,
    CLIENT_SLUG,
    PREVIEW_ARTISAN_SLUG,
    PREVIEW_DEMO_SLUG,
    PREVIEW_EXPIRED_SLUG,
    PREVIEW_THERAPIST_SLUG,
    seed_preview_safety_cards,
)

ROOT = Path(__file__).resolve().parents[2]
SHARED_JS = ROOT / "backend" / "static" / "public-card" / "shared.js"
INDEX_HTML = ROOT / "backend" / "static" / "public-card" / "index.html"


class PreviewCardSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        path = Path(self._tmpdir.name) / "preview_safety.db"
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

    def test_classic_card_public_payload_unchanged(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{CLIENT_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertEqual(data["slug"], CLIENT_SLUG)
        self.assertFalse(data.get("is_preview"))
        self.assertIsNone(data.get("preview_origin"))
        self.assertEqual(data["visual_theme"], "artisan")
        self.assertEqual(data["phone"], "0611223344")
        self.assertTrue(data["enable_recommendation"])

    def test_classic_demo_slug_is_not_preview(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{CLASSIC_DEMO_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data["slug"].startswith("demo"))
        self.assertFalse(data.get("is_preview"))
        self.assertIsNone(data.get("preview_origin"))

    def test_preview_artisan_payload_and_hidden_origin(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{PREVIEW_ARTISAN_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data["is_preview"])
        self.assertIsNone(data.get("preview_origin"))
        self.assertNotIn("local_finder", r.text)
        self.assertEqual(data["visual_theme"], "artisan")
        self.assertEqual(data["phone"], "0622334455")
        self.assertEqual(data["whatsapp"], "33622334455")
        self.assertTrue(data["google_review_link"])

    def test_preview_therapist_keeps_wellness_theme(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{PREVIEW_THERAPIST_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data["is_preview"])
        self.assertEqual(data["visual_theme"], "wellness-soft")
        self.assertEqual(data["profile"], "bien_etre")

    def test_preview_does_not_depend_on_demo_slug(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{PREVIEW_DEMO_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertTrue(data["slug"].startswith("demo"))
        self.assertTrue(data["is_preview"])
        html = client.get(f"/c/{PREVIEW_DEMO_SLUG}")
        self.assertEqual(html.status_code, 200)
        self.assertIn("preview-proposition-frame", html.text)
        self.assertIn("Proposition personnalisée Maavnica", html.text)
        self.assertIn('id="demo-banner-shell"', html.text)

    def test_public_html_contains_proposition_frame_not_forced_on(self):
        client = self._client()
        r = client.get(f"/c/{PREVIEW_ARTISAN_SLUG}")
        self.assertEqual(r.status_code, 200)
        self.assertIn('data-theme="artisan"', r.text)
        self.assertIn("Proposition personnalisée Maavnica", r.text)
        self.assertIn("preview-proposition-frame", r.text)
        self.assertIn("hidden", r.text)

        client_html = client.get(f"/c/{CLIENT_SLUG}")
        self.assertEqual(client_html.status_code, 200)
        self.assertIn('data-theme="artisan"', client_html.text)
        self.assertIn("preview-proposition-frame", client_html.text)

        therapist = client.get(f"/c/{PREVIEW_THERAPIST_SLUG}")
        self.assertEqual(therapist.status_code, 200)
        self.assertIn('data-theme="wellness-soft"', therapist.text)

    def test_admin_view_query_still_serves_card(self):
        client = self._client()
        r = client.get(f"/c/{CLIENT_SLUG}?admin_view=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("phone-shell", r.text)
        preview = client.get(f"/c/{PREVIEW_ARTISAN_SLUG}?admin_view=1")
        self.assertEqual(preview.status_code, 200)
        api = client.get(f"/api/public/cards/{CLIENT_SLUG}?admin_view=1")
        self.assertEqual(api.status_code, 200)
        self.assertFalse(api.json().get("is_preview"))

    def test_admin_sees_preview_origin(self):
        client = self._client()
        r = client.get(
            "/api/cards/",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        by_slug = {row["slug"]: row for row in r.json()}
        preview = by_slug[PREVIEW_ARTISAN_SLUG]
        self.assertTrue(preview["is_preview"])
        self.assertEqual(preview["preview_origin"], "local_finder")
        classic = by_slug[CLIENT_SLUG]
        self.assertFalse(classic["is_preview"])
        self.assertIsNone(classic.get("preview_origin"))

    def test_classic_quote_and_feedback_still_write(self):
        client = self._client()
        card_id = self.ids[CLIENT_SLUG]
        before_q = self._count(Quote, card_id=card_id)
        before_f = self._count(Feedback, card_id=card_id)
        q = client.post(
            f"/api/public/cards/{card_id}/quotes",
            json={
                "name": "Jeanne Test",
                "phone": "0612345678",
                "message": "Bonjour je souhaite un devis",
            },
        )
        self.assertEqual(q.status_code, 201, q.text)
        f = client.post(
            f"/api/public/cards/{card_id}/feedback",
            json={"satisfaction": True, "comment": "Très bien"},
        )
        self.assertEqual(f.status_code, 201, f.text)
        self.assertEqual(self._count(Quote, card_id=card_id), before_q + 1)
        self.assertEqual(self._count(Feedback, card_id=card_id), before_f + 1)

    def test_preview_quote_feedback_do_not_write(self):
        client = self._client()
        card_id = self.ids[PREVIEW_ARTISAN_SLUG]
        before_q = self._count(Quote, card_id=card_id)
        before_f = self._count(Feedback, card_id=card_id)
        q = client.post(
            f"/api/public/cards/{card_id}/quotes",
            json={
                "name": "Jeanne Test",
                "phone": "0612345678",
                "message": "Bonjour je souhaite un devis",
            },
        )
        self.assertEqual(q.status_code, 403, q.text)
        self.assertIn("proposition", q.text.lower())
        f = client.post(
            f"/api/public/cards/{card_id}/feedback",
            json={"satisfaction": True, "comment": "Très bien"},
        )
        self.assertEqual(f.status_code, 403, f.text)
        self.assertEqual(self._count(Quote, card_id=card_id), before_q)
        self.assertEqual(self._count(Feedback, card_id=card_id), before_f)

    def test_preview_analytics_and_recommendation_do_not_write(self):
        client = self._client()
        slug = PREVIEW_THERAPIST_SLUG
        before_v = self._count(CardVisit, slug=slug)
        before_e = self._count(CardEvent, slug=slug)
        before_r = self._count(RecommendationEvent, card_slug=slug)
        v = client.post("/api/analytics/visit", json={"slug": slug, "src": "test"})
        self.assertEqual(v.status_code, 204)
        e = client.post(
            "/api/analytics/event",
            json={"slug": slug, "event_type": "phone_click"},
        )
        self.assertEqual(e.status_code, 204)
        rec = client.post(
            "/api/analytics/recommendation-event",
            json={
                "card_slug": slug,
                "referrer_id": "rec_testtoken",
                "event_type": "recommend_link_created",
                "recommender_first_name": "Ada",
                "recommender_last_name": "Lovelace",
            },
        )
        self.assertEqual(rec.status_code, 204)
        self.assertEqual(self._count(CardVisit, slug=slug), before_v)
        self.assertEqual(self._count(CardEvent, slug=slug), before_e)
        self.assertEqual(self._count(RecommendationEvent, card_slug=slug), before_r)

    def test_classic_analytics_still_write(self):
        client = self._client()
        slug = CLIENT_SLUG
        before_v = self._count(CardVisit, slug=slug)
        before_e = self._count(CardEvent, slug=slug)
        v = client.post("/api/analytics/visit", json={"slug": slug})
        self.assertEqual(v.status_code, 204)
        e = client.post(
            "/api/analytics/event",
            json={"slug": slug, "event_type": "whatsapp_click"},
        )
        self.assertEqual(e.status_code, 204)
        self.assertEqual(self._count(CardVisit, slug=slug), before_v + 1)
        self.assertEqual(self._count(CardEvent, slug=slug), before_e + 1)

    def test_preview_vcard_qr_and_non_persistent_cta_fields(self):
        client = self._client()
        vcf = client.get(f"/api/public/cards/{PREVIEW_ARTISAN_SLUG}/vcard")
        self.assertEqual(vcf.status_code, 200, vcf.text)
        self.assertIn("BEGIN:VCARD", vcf.text)
        self.assertIn("Atelier Martin", vcf.text)
        data = client.get(f"/api/public/cards/{PREVIEW_ARTISAN_SLUG}").json()
        self.assertTrue(data["phone"])
        self.assertTrue(data["whatsapp"])
        self.assertTrue(data["google_review_link"])
        html = client.get(f"/c/{PREVIEW_ARTISAN_SLUG}").text
        self.assertIn('id="qr-image"', html)
        self.assertIn('id="btn-call"', html)
        self.assertIn('id="btn-whatsapp"', html)
        self.assertIn("updateQrCode", SHARED_JS.read_text(encoding="utf-8"))

    def test_preview_expiration_blocks_access(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{PREVIEW_EXPIRED_SLUG}")
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("plus disponible", r.json()["detail"])
        vcf = client.get(f"/api/public/cards/{PREVIEW_EXPIRED_SLUG}/vcard")
        self.assertEqual(vcf.status_code, 403)
        html = client.get(f"/c/{PREVIEW_EXPIRED_SLUG}")
        self.assertEqual(html.status_code, 200)

    def test_classic_expiration_message_unchanged(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{CLASSIC_EXPIRED_SLUG}")
        self.assertEqual(r.status_code, 403, r.text)
        self.assertIn("plus active", r.json()["detail"])
        vcf = client.get(f"/api/public/cards/{CLASSIC_EXPIRED_SLUG}/vcard")
        self.assertEqual(vcf.status_code, 200)
        self.assertIn("BEGIN:VCARD", vcf.text)

    def test_future_admin_create_preview_interface(self):
        client = self._client()
        payload = {
            "company_name": "Proposition LF",
            "slug": "lf-preview-interface-minimale",
            "plan_type": "demo",
            "region": "fr",
            "profile": "artisan",
            "visual_theme": "artisan",
            "theme": "apple",
            "is_preview": True,
            "preview_origin": "local_finder",
            "phone": "0688990011",
        }
        r = client.post(
            "/api/cards/",
            json=payload,
            headers={"Authorization": "Bearer test-admin-key"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        created = r.json()
        self.assertTrue(created["is_preview"])
        self.assertEqual(created["preview_origin"], "local_finder")
        pub = client.get("/api/public/cards/lf-preview-interface-minimale")
        self.assertEqual(pub.status_code, 200)
        self.assertTrue(pub.json()["is_preview"])
        self.assertIsNone(pub.json().get("preview_origin"))

    def test_frontend_preview_is_not_slug_based(self):
        js = SHARED_JS.read_text(encoding="utf-8")
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn("function isPreviewCardPayload", js)
        self.assertIn("card.is_preview === true", js)
        self.assertIn("syncPreviewPropositionFrame", js)
        self.assertIn("isPreviewSafeMode", js)
        self.assertIn("function isDemoSlug", js)
        self.assertIn('startsWith("demo")', js)
        self.assertIn("Cette proposition est une démonstration — aucune demande", js)
        self.assertIn("Cette proposition est une démonstration — aucun avis", js)
        self.assertIn("!isPreviewSafeMode && (isDemoCard || recommendEnabled)", js)
        self.assertIn("if (isPreviewSafeMode) return false;", js)
        self.assertIn("Proposition personnalisée Maavnica", html)
        self.assertIn('id="preview-proposition-frame"', html)
        self.assertNotRegex(
            js,
            r"isPreviewCardPayload\([^)]*startsWith",
        )


if __name__ == "__main__":
    unittest.main()
