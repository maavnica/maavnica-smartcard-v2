"""Case admin « Proposition personnalisée Maavnica » → champ is_preview."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from tests.preview_card_fixtures import (
    CLIENT_SLUG,
    PREVIEW_ARTISAN_SLUG,
    seed_preview_safety_cards,
)

ROOT = Path(__file__).resolve().parents[2]
ADMIN_HTML = ROOT / "backend" / "static" / "admin" / "index.html"
ADMIN_JS = ROOT / "backend" / "static" / "admin" / "app.js"


def _admin_headers():
    return {"Authorization": "Bearer test-admin-key"}


class AdminPreviewToggleStaticTests(unittest.TestCase):
    def test_admin_form_has_preview_checkbox_unchecked_by_default(self):
        html = ADMIN_HTML.read_text(encoding="utf-8")
        self.assertIn('id="is-preview"', html)
        self.assertIn("Proposition personnalisée Maavnica", html)
        self.assertIn(
            "Carte de démonstration : affiche un cadre discret et désactive devis, avis, recommandation et analytics.",
            html,
        )
        self.assertNotRegex(html, r'id="is-preview"[^>]*\bchecked\b')
        self.assertNotIn('id="preview-origin"', html)
        self.assertNotIn('name="preview_origin"', html)
        self.assertIn('id="plan-type"', html)
        self.assertIn("Demo (sans expiration)", html)
        self.assertIn("Prévisualiser la carte (interne)", html)
        self.assertIn('id="btn-open-preview"', html)

    def test_admin_js_wires_is_preview_and_never_edits_origin(self):
        js = ADMIN_JS.read_text(encoding="utf-8")
        self.assertIn("function readIsPreviewFromForm", js)
        self.assertIn("function applyIsPreviewToForm", js)
        self.assertIn("function collectAdminCardPayload", js)
        self.assertIn("is_preview: readIsPreviewFromForm()", js)
        self.assertIn("el.checked = !!(card && card.is_preview === true)", js)
        self.assertIn("applyIsPreviewToForm(card)", js)
        self.assertIn("applyIsPreviewToForm({ is_preview: false })", js)
        self.assertIn("const payload = collectAdminCardPayload();", js)
        payload_fn = js[
            js.index("function collectAdminCardPayload") : js.index("function adminPreviewUrlForSlug")
        ]
        self.assertNotIn("preview_origin", payload_fn)
        self.assertNotIn('getElementById("preview-origin")', js)
        self.assertIn('id="plan-type"', ADMIN_HTML.read_text(encoding="utf-8"))
        self.assertIn("adminPreviewUrlForSlug", js)
        self.assertIn("?admin_view=1", js)

    def test_admin_js_payload_preview_and_normal_creation(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node indisponible pour exécuter le payload admin")
        js = ADMIN_JS.read_text(encoding="utf-8")
        start = js.index("function readIsPreviewFromForm")
        end = js.index("function adminPreviewUrlForSlug")
        snippet = js[start:end]
        harness = r"""
const NON_EXPIRING_PLANS = new Set(["demo", "lifetime"]);
function field(id, spec) {
  const value = spec.value == null ? "" : String(spec.value);
  return {
    value,
    checked: !!spec.checked,
    options: spec.options || [],
  };
}
function makeDocument(overrides) {
  const store = Object.assign({
    "company-name": { value: "Atelier Test" },
    slug: { value: "atelier-test" },
    "plan-type": { value: "demo" },
    "region-version": { value: "fr" },
    "visual-theme": { value: "artisan", options: [{ value: "artisan" }] },
    "expires-at": { value: "" },
    "is-preview": { value: "", checked: false },
    "enable-recommendation": { value: "", checked: false },
    "first-name": { value: "" },
    "last-name": { value: "" },
    city: { value: "" },
    "google-link": { value: "" },
    "google-rating": { value: "" },
    "google-review-count": { value: "" },
    phone: { value: "" },
    whatsapp: { value: "" },
    "payment-link": { value: "" },
    instagram: { value: "" },
    facebook: { value: "" },
    tiktok: { value: "" },
    profile: { value: "artisan" },
    "email-pro": { value: "" },
    "site-web": { value: "" },
    "avatar-url": { value: "" },
    "hero-title": { value: "" },
    "hero-text": { value: "" },
    "hero-cta-text": { value: "" },
    "display-name": { value: "" },
    "business-name-field": { value: "" },
    "job-title": { value: "" },
    "form-title": { value: "" },
    "recommendation-code": { value: "" },
  }, overrides || {});
  return {
    getElementById(id) {
      return field(id, store[id] || { value: "" });
    },
  };
}
function readVisualThemeFromSelect() {
  return document.getElementById("visual-theme").value || "wellness-soft";
}
"""
        script = (
            harness
            + snippet
            + r"""
function run(checked) {
  global.document = makeDocument({ "is-preview": { value: "", checked } });
  const payload = collectAdminCardPayload();
  return payload;
}
const preview = run(true);
const normal = run(false);
if (preview.is_preview !== true) throw new Error("preview payload must send is_preview true");
if (normal.is_preview !== false) throw new Error("normal payload must send is_preview false");
if (Object.prototype.hasOwnProperty.call(preview, "preview_origin")) {
  throw new Error("preview_origin must not be in admin payload");
}
if (preview.plan_type !== "demo" || normal.plan_type !== "demo") {
  throw new Error("plan demo must stay independent of is_preview");
}
console.log(JSON.stringify({ preview, normal }));
"""
        )
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
            fh.write(script)
            path = fh.name
        try:
            proc = subprocess.run(
                [node, path],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            os.unlink(path)
        data = json.loads(proc.stdout)
        self.assertIs(data["preview"]["is_preview"], True)
        self.assertIs(data["normal"]["is_preview"], False)
        self.assertNotIn("preview_origin", data["preview"])
        self.assertNotIn("preview_origin", data["normal"])
        self.assertEqual(data["preview"]["plan_type"], "demo")


class AdminPreviewToggleApiTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        path = Path(self._tmpdir.name) / "admin_preview_toggle.db"
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

    def test_existing_preview_card_reloads_is_preview_true_for_checkbox(self):
        client = self._client()
        r = client.get(
            f"/api/cards/by-slug/{PREVIEW_ARTISAN_SLUG}",
            headers=_admin_headers(),
        )
        self.assertEqual(r.status_code, 200, r.text)
        data = r.json()
        self.assertIs(data["is_preview"], True)
        box = {"checked": False}

        class _El:
            def __init__(self, state):
                self.state = state

            @property
            def checked(self):
                return self.state["checked"]

            @checked.setter
            def checked(self, value):
                self.state["checked"] = bool(value)

        el = _El(box)
        el.checked = data["is_preview"] is True
        self.assertTrue(box["checked"])
        self.assertEqual(data.get("preview_origin"), "local_finder")

    def test_admin_create_payload_preview_and_normal(self):
        client = self._client()
        preview_body = {
            "company_name": "Admin Preview Payload",
            "slug": "admin-toggle-preview-payload",
            "plan_type": "demo",
            "region": "fr",
            "profile": "artisan",
            "visual_theme": "artisan",
            "theme": "apple",
            "is_preview": True,
        }
        normal_body = {
            "company_name": "Admin Normal Payload",
            "slug": "admin-toggle-normal-payload",
            "plan_type": "demo",
            "region": "fr",
            "profile": "artisan",
            "visual_theme": "artisan",
            "theme": "apple",
            "is_preview": False,
        }
        self.assertNotIn("preview_origin", preview_body)
        self.assertNotIn("preview_origin", normal_body)
        rp = client.post("/api/cards/", json=preview_body, headers=_admin_headers())
        rn = client.post("/api/cards/", json=normal_body, headers=_admin_headers())
        self.assertEqual(rp.status_code, 201, rp.text)
        self.assertEqual(rn.status_code, 201, rn.text)
        self.assertTrue(rp.json()["is_preview"])
        self.assertFalse(rn.json()["is_preview"])
        pub_p = client.get("/api/public/cards/admin-toggle-preview-payload")
        pub_n = client.get("/api/public/cards/admin-toggle-normal-payload")
        self.assertTrue(pub_p.json()["is_preview"])
        self.assertIsNone(pub_p.json().get("preview_origin"))
        self.assertNotIn("local_finder", pub_p.text)
        self.assertFalse(pub_n.json()["is_preview"])
        self.assertIsNone(pub_n.json().get("preview_origin"))

    def test_non_preview_and_admin_view_unchanged(self):
        client = self._client()
        r = client.get(f"/api/public/cards/{CLIENT_SLUG}")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json().get("is_preview"))
        html = client.get(f"/c/{CLIENT_SLUG}?admin_view=1")
        self.assertEqual(html.status_code, 200)
        self.assertIn('id="preview-proposition-frame"', html.text)
        admin_page = client.get("/admin")
        self.assertEqual(admin_page.status_code, 200)
        self.assertIn('id="is-preview"', admin_page.text)
        self.assertIn("Proposition personnalisée Maavnica", admin_page.text)


if __name__ == "__main__":
    unittest.main()
