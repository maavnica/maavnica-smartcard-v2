from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.models import Base, Card


ROOT = Path(__file__).resolve().parents[2]
ADMIN_JS = ROOT / "backend" / "static" / "admin" / "app.js"
LOGIN_JS = ROOT / "backend" / "static" / "admin" / "login.js"
ADMIN_HTML = ROOT / "backend" / "static" / "admin" / "index.html"
LOGIN_HTML = ROOT / "backend" / "static" / "admin" / "login.html"


class AdminSessionAuthTests(unittest.TestCase):
    def setUp(self):
        from app.utils import rate_limit
        from app.utils import admin_auth

        with rate_limit._lock:
            rate_limit._buckets.clear()
        with admin_auth._active_admin_sessions_lock:
            admin_auth._active_admin_sessions.clear()

        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "admin_session.db"
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(bind=self._engine)
        self.SessionTest = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self._engine,
        )
        session = self.SessionTest()
        try:
            session.add(
                Card(
                    user_id=1,
                    company_name="Carte publique",
                    slug="carte-publique-session",
                    plan_type="demo",
                    profile="artisan",
                    visual_theme="artisan",
                    owner_share_key="owner-test",
                )
            )
            session.add(
                Card(
                    user_id=1,
                    company_name="Carte trial",
                    slug="carte-trial-session",
                    plan_type="trial",
                    profile="artisan",
                    visual_theme="artisan",
                    expires_at=datetime.utcnow() + timedelta(days=10),
                    owner_share_key="owner-trial-test",
                )
            )
            session.commit()
        finally:
            session.close()

        self._db_patch = patch("app.database.SessionLocal", self.SessionTest)
        self._db_patch.start()
        self._env_patch = patch.dict(os.environ, {"ADMIN_API_KEY": "test-admin-key"})
        self._env_patch.start()

        from app.main import app

        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self._env_patch.stop()
        self._db_patch.stop()
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _login(self, *, ip: str = "session-test"):
        return self.client.post(
            "/api/admin/session/login",
            json={"password": "test-admin-key"},
            headers={"x-forwarded-for": ip},
        )

    def test_admin_requires_login_and_correct_password_opens_session(self):
        denied = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(denied.status_code, 303)
        self.assertTrue(denied.headers["location"].startswith("/admin/login"))

        login_page = self.client.get(denied.headers["location"])
        self.assertEqual(login_page.status_code, 200)
        self.assertIn('type="password"', login_page.text)

        refused = self.client.post(
            "/api/admin/session/login",
            json={"password": "incorrect"},
            headers={"x-forwarded-for": "wrong-password"},
        )
        self.assertEqual(refused.status_code, 401)
        self.assertNotIn("incorrect", refused.text)

        accepted = self._login()
        self.assertEqual(accepted.status_code, 200, accepted.text)
        cookie = accepted.headers.get("set-cookie", "").lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=lax", cookie)
        self.assertIn("max-age=28800", cookie)
        self.assertNotIn("test-admin-key", cookie)

        first = self.client.get("/admin")
        reload_page = self.client.get("/admin")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(reload_page.status_code, 200)
        self.assertIn('id="btn-logout"', first.text)

    def test_session_api_supports_csrf_protected_write_and_bearer_still_works(self):
        login = self._login(ip="write-test")
        csrf = login.json()["csrf_token"]

        payload = {
            "company_name": "Session Create",
            "slug": "session-create",
            "plan_type": "demo",
            "profile": "artisan",
            "visual_theme": "artisan",
        }
        no_csrf = self.client.post("/api/cards/", json=payload)
        self.assertEqual(no_csrf.status_code, 403)
        self.assertEqual(no_csrf.json()["detail"], "Jeton CSRF invalide.")

        created = self.client.post(
            "/api/cards/",
            json=payload,
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(created.status_code, 201, created.text)

        bearer_list = TestClient(self.client.app).get(
            "/api/cards/",
            headers={"Authorization": "Bearer test-admin-key"},
        )
        self.assertEqual(bearer_list.status_code, 200, bearer_list.text)

    def test_logout_and_expiration_protect_access_again(self):
        from app.utils.admin_auth import ADMIN_SESSION_COOKIE

        login = self._login(ip="logout-test")
        csrf = login.json()["csrf_token"]
        copied_cookie = self.client.cookies.get(ADMIN_SESSION_COOKIE)

        missing_csrf = self.client.post("/api/admin/session/logout")
        self.assertEqual(missing_csrf.status_code, 403)

        logout = self.client.post(
            "/api/admin/session/logout",
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(logout.status_code, 204)
        denied = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(denied.status_code, 303)
        self.client.cookies.set(ADMIN_SESSION_COOKIE, copied_cookie)
        replayed = self.client.get("/api/admin/session")
        self.assertEqual(replayed.status_code, 401)

        self._login(ip="expiry-test")
        with patch("app.utils.admin_auth.time.time", return_value=10**12):
            expired = self.client.get("/api/admin/session")
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(
            expired.json()["detail"],
            "Session administrateur expirée ou absente.",
        )

    def test_ssr_admin_pages_use_session_and_business_actions_require_csrf(self):
        login = self._login(ip="ssr-test")
        csrf = login.json()["csrf_token"]

        analytics = self.client.get("/admin/analytics")
        business = self.client.get("/admin/business")
        self.assertEqual(analytics.status_code, 200, analytics.text)
        self.assertEqual(business.status_code, 200, business.text)
        self.assertIn(f'name="csrf_token" value="{csrf}"', business.text)

        session = self.SessionTest()
        try:
            trial_id = session.query(Card.id).filter(
                Card.slug == "carte-trial-session"
            ).scalar()
        finally:
            session.close()
        action = {
            "card_id": trial_id,
            "action_type": "extend_30",
            "filter": "all",
            "q": "",
            "sort": "expiring_soon",
        }
        rejected = self.client.post(
            "/admin/business/actions",
            data=action,
            follow_redirects=False,
        )
        self.assertEqual(rejected.status_code, 403)

        accepted = self.client.post(
            "/admin/business/actions",
            data={**action, "csrf_token": csrf},
            follow_redirects=False,
        )
        self.assertEqual(accepted.status_code, 303, accepted.text)

        basic_client = TestClient(self.client.app)
        legacy = basic_client.get(
            "/admin/analytics",
            auth=("admin", "test-admin-key"),
        )
        self.assertEqual(legacy.status_code, 200, legacy.text)
        basic_client.close()

    def test_public_card_stays_public_and_does_not_expose_owner_data(self):
        response = self.client.get("/api/cards/by-slug/carte-publique-session")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNone(response.json().get("owner_share_key"))

    def test_login_rate_limit_blocks_repeated_attempts(self):
        responses = [
            self.client.post(
                "/api/admin/session/login",
                json={"password": "incorrect"},
                headers={"x-forwarded-for": "rate-limit-test"},
            )
            for _ in range(6)
        ]
        self.assertTrue(all(response.status_code == 401 for response in responses[:5]))
        self.assertEqual(responses[5].status_code, 429)

    def test_browser_assets_do_not_store_or_send_the_admin_secret(self):
        bundle = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ADMIN_JS, LOGIN_JS, ADMIN_HTML, LOGIN_HTML)
        )
        self.assertNotIn("ADMIN_API_KEY", bundle)
        self.assertNotIn("sessionStorage", bundle)
        self.assertNotIn("localStorage", bundle)
        self.assertNotIn("Authorization", bundle)
        self.assertIn('type="password"', LOGIN_HTML.read_text(encoding="utf-8"))
        self.assertIn('type="password"', ADMIN_HTML.read_text(encoding="utf-8"))
        self.assertIn("adminFetch(", bundle)
        self.assertNotIn("location.reload", bundle)
        admin_js = ADMIN_JS.read_text(encoding="utf-8")
        auth_block = admin_js.split("function showToast", 1)[0]
        self.assertNotIn("resetForm(", auth_block)
        self.assertNotIn("fillForm(", auth_block)
        reauth_block = admin_js[
            admin_js.index("async function submitReauthentication") :
            admin_js.index("async function logoutAdmin")
        ]
        self.assertNotIn("adminFetch(", reauth_block)

    def test_render_runtime_enables_secure_cookie(self):
        from app.main import _admin_session_signing_key, _is_production_runtime
        from app.routers.admin_session import router as admin_session_router
        from app.utils.admin_auth import (
            ADMIN_SESSION_COOKIE,
            ADMIN_SESSION_MAX_AGE_SECONDS,
        )

        with patch.dict(
            os.environ,
            {"RENDER": "true", "ADMIN_API_KEY": "test-admin-key"},
            clear=True,
        ):
            self.assertTrue(_is_production_runtime())
            production_app = FastAPI()
            production_app.include_router(admin_session_router)
            production_app.add_middleware(
                SessionMiddleware,
                secret_key=_admin_session_signing_key(),
                session_cookie=ADMIN_SESSION_COOKIE,
                max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
                same_site="lax",
                https_only=_is_production_runtime(),
            )
            with TestClient(
                production_app,
                base_url="https://smartcard.example",
            ) as production_client:
                login = production_client.post(
                    "/api/admin/session/login",
                    json={"password": "test-admin-key"},
                    headers={
                        "x-forwarded-for": "render-proxy-test",
                        "x-forwarded-proto": "https",
                    },
                )
                self.assertEqual(login.status_code, 200, login.text)
                cookie = login.headers["set-cookie"].lower()
                self.assertIn("secure", cookie)
                self.assertIn("httponly", cookie)
                self.assertIn("samesite=lax", cookie)
                session_status = production_client.get("/api/admin/session")
                self.assertEqual(session_status.status_code, 200, session_status.text)
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(_is_production_runtime())


if __name__ == "__main__":
    unittest.main()
