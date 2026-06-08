"""Tests génération / service Open Graph dynamique."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from app.og_capture import (
    OG_HEIGHT,
    OG_WIDTH,
    build_og_image_url,
    composite_og_canvas,
    og_cache_bust,
    og_generated_path,
)


class _FakeCard:
    def __init__(self, **kwargs):
        self.slug = kwargs.get("slug", "demo2")
        self.updated_at = kwargs.get("updated_at", datetime(2026, 6, 8, 12, 0, 0))
        self.visual_theme = kwargs.get("visual_theme", "wellness-soft")
        self.avatar_url = kwargs.get("avatar_url", "https://cdn.example/a.png")


class OgCacheBustTests(unittest.TestCase):
    def test_same_card_same_hash(self):
        card = _FakeCard()
        self.assertEqual(og_cache_bust(card), og_cache_bust(card))

    def test_different_avatar_different_hash(self):
        a = _FakeCard(avatar_url="https://a")
        b = _FakeCard(avatar_url="https://b")
        self.assertNotEqual(og_cache_bust(a), og_cache_bust(b))


class OgCompositeTests(unittest.TestCase):
    def test_output_dimensions(self):
        src = Image.new("RGBA", (400, 700), (255, 0, 0, 255))
        out = composite_og_canvas(src, bg_rgb=(243, 237, 228))
        img = Image.open(BytesIO(out))
        self.assertEqual(img.size, (OG_WIDTH, OG_HEIGHT))
        self.assertEqual(img.format, "JPEG")


class BuildOgImageUrlTests(unittest.TestCase):
    base = "https://smartcard.maavnica.com"

    def test_dynamic_enabled_with_generated_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            gen_dir = Path(tmp) / "generated"
            gen_dir.mkdir(parents=True)
            (gen_dir / "demo2.jpg").write_bytes(b"fake")
            with patch("app.og_capture.OG_GENERATED_DIR", gen_dir):
                with patch("app.og_capture.is_og_dynamic_enabled", return_value=True):
                    card = _FakeCard()
                    url = build_og_image_url(self.base, "demo2", card)
                    self.assertIn("/og/demo2.jpg?v=", url)

    def test_fallback_when_missing_file(self):
        with patch("app.og_capture.is_og_dynamic_enabled", return_value=True):
            with patch("app.og_capture.og_generated_path", return_value=Path("/nonexistent/x.jpg")):
                url = build_og_image_url(self.base, "missing", _FakeCard())
                self.assertIn("/static/og-default.jpg?v=", url)

    def test_disabled_uses_default(self):
        with patch("app.og_capture.is_og_dynamic_enabled", return_value=False):
            url = build_og_image_url(self.base, "demo2", _FakeCard())
            self.assertIn("/static/og-default.jpg?v=", url)


class OgRouteTests(unittest.TestCase):
    def test_serve_generated(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with tempfile.TemporaryDirectory() as tmp:
            gen_dir = Path(tmp)
            (gen_dir / "demo2.jpg").write_bytes(
                composite_og_canvas(Image.new("RGBA", (400, 700), (10, 20, 30, 255)))
            )
            with patch("app.routers.og.og_generated_path", side_effect=lambda s: gen_dir / f"{s}.jpg"):
                with patch("app.routers.og.is_og_dynamic_enabled", return_value=True):
                    client = TestClient(app)
                    r = client.get("/og/demo2.jpg")
                    self.assertEqual(r.status_code, 200)
                    self.assertEqual(r.headers.get("content-type"), "image/jpeg")

    def test_fallback_default(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with patch("app.routers.og.is_og_dynamic_enabled", return_value=True):
            with patch("app.routers.og.og_generated_path", return_value=Path("/no/such.jpg")):
                client = TestClient(app)
                r = client.get("/og/unknown-slug.jpg")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("content-type"), "image/jpeg")


if __name__ == "__main__":
    unittest.main()
