"""Tests sécurité migration / tolérance erreurs OG."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.models import Base, Card, User


class EnsureGoogleRatingColumnsTests(unittest.TestCase):
    def test_adds_columns_on_sqlite_legacy_table(self):
        from app.database import ensure_google_rating_columns

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.db"
            engine = create_engine(f"sqlite:///{path}")
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "CREATE TABLE cards ("
                        "id INTEGER PRIMARY KEY, slug VARCHAR(64), region VARCHAR(16) DEFAULT 'fr'"
                        ")"
                    )
                )
            with patch("app.database.engine", engine):
                ensure_google_rating_columns()
            insp = inspect(engine)
            cols = {c["name"] for c in insp.get_columns("cards")}
            self.assertIn("google_rating", cols)
            self.assertIn("google_review_count", cols)
            engine.dispose()


class RegenerateLenientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import tools.regenerate_og as reg  # type: ignore

        cls.reg = reg

    def test_main_returns_zero_when_all_slugs_fail_lenient(self):
        reg = self.reg
        argv = ["regenerate_og.py", "--base-url", "http://127.0.0.1:10000"]
        with patch.dict(os.environ, {"OG_BUILD_LENIENT": "true"}):
            with patch.object(sys, "argv", argv):
                with patch.object(reg, "regenerate", return_value=(0, 3)):
                    with patch.object(reg, "_list_active_fr_slugs", return_value=["a", "b", "c"]):
                        rc = reg.main()
        self.assertEqual(rc, 0)

    def test_main_returns_one_when_all_fail_strict(self):
        reg = self.reg
        argv = ["regenerate_og.py", "--base-url", "http://127.0.0.1:10000"]
        with patch.dict(os.environ, {"OG_BUILD_LENIENT": "false"}):
            with patch.object(sys, "argv", argv):
                with patch.object(reg, "regenerate", return_value=(0, 2)):
                    with patch.object(reg, "_list_active_fr_slugs", return_value=["a", "b"]):
                        rc = reg.main()
        self.assertEqual(rc, 1)


class OgCacheBustIncompleteCardTests(unittest.TestCase):
    def test_hash_with_null_fields(self):
        from app.og_capture import og_cache_bust

        class Incomplete:
            slug = "demo2"
            updated_at = None
            visual_theme = None
            avatar_url = None

        h = og_cache_bust(Incomplete())
        self.assertEqual(len(h), 8)


class OgFallbackIntegrationTests(unittest.TestCase):
    def test_route_serves_default_when_generated_missing(self):
        from fastapi.testclient import TestClient

        from app.main import app

        with patch("app.routers.og.og_generated_path", return_value=Path("/no/generated.jpg")):
            with patch("app.routers.og.is_og_dynamic_enabled", return_value=True):
                client = TestClient(app)
                r = client.get("/og/inexistant-slug.jpg")
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.headers.get("content-type"), "image/jpeg")

    def test_build_og_url_fallback_when_file_missing(self):
        from app.og_capture import build_og_image_url

        with patch("app.og_capture.is_og_dynamic_enabled", return_value=True):
            with patch("app.og_capture.og_generated_path") as mock_path:
                mock_path.return_value.is_file = lambda: False
                url = build_og_image_url("https://x.test", "demo2", None)
                self.assertIn("/static/og-default.jpg?v=", url)


if __name__ == "__main__":
    unittest.main()
