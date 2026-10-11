"""Régressions ciblées pour l'authentification de l'administration SmartCard."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from app.utils.admin_auth import require_admin_api_key


ROOT = Path(__file__).resolve().parents[2]
ADMIN_HTML = ROOT / "backend" / "static" / "admin" / "index.html"
ADMIN_JS = ROOT / "backend" / "static" / "admin" / "app.js"


class AdminAuthUiTests(unittest.TestCase):
    def test_backend_rejects_an_invalid_bearer_with_the_expected_detail(self):
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/cards/",
                "headers": [(b"authorization", b"Bearer mauvaise-cle")],
            }
        )
        with patch.dict(os.environ, {"ADMIN_API_KEY": "bonne-cle"}):
            with self.assertRaises(HTTPException) as raised:
                require_admin_api_key(request)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.detail, "Clé admin invalide.")

    def test_auth_controls_and_centralized_fetch_are_present(self):
        html = ADMIN_HTML.read_text(encoding="utf-8")
        js = ADMIN_JS.read_text(encoding="utf-8")

        self.assertIn('id="btn-change-admin-key"', html)
        self.assertIn('id="admin-auth-status"', html)
        self.assertIn('id="admin-auth-detail"', html)
        self.assertIn("function adminFetch(", js)
        self.assertIn("function verifyAdminApiKey(", js)
        self.assertIn("function clearAdminApiKey(", js)
        self.assertIn("sessionStorage.removeItem", js)
        self.assertIn(
            "Clé administrateur invalide. Saisissez à nouveau votre clé ; vos informations sont conservées.",
            js,
        )

        auth_block = js[
            js.index("const ADMIN_AUTH_INVALID_DETAIL") : js.index("function showToast")
        ]
        self.assertNotIn("resetForm(", auth_block)
        self.assertNotIn("fillForm(", auth_block)
        self.assertNotIn("location.reload", auth_block)

        fetch_calls = [line.strip() for line in js.splitlines() if "fetch(" in line]
        self.assertEqual(fetch_calls, ["return fetch(url, requestOptions);"])

    def test_authentication_state_transitions(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node indisponible pour exécuter les tests frontend")

        js = ADMIN_JS.read_text(encoding="utf-8")
        auth_block = js[
            js.index("const ADMIN_AUTH_INVALID_DETAIL") : js.index("function showToast")
        ]
        harness = r"""
const API_BASE = "/api/cards";
let ADMIN_API_KEY = "";
const storage = new Map();
const sessionStorage = {
  getItem(key) { return storage.get(key) || null; },
  setItem(key, value) { storage.set(key, value); },
  removeItem(key) { storage.delete(key); },
};
const elements = {
  "admin-auth-status": { textContent: "", className: "" },
  "admin-auth-detail": { textContent: "", className: "" },
};
const document = { getElementById(id) { return elements[id] || null; } };
let promptResult = null;
const window = { prompt() { return promptResult; } };
const toasts = [];
function showToast(message, isError) { toasts.push({ message, isError }); }
function response(status, detail) {
  return {
    ok: status >= 200 && status < 300,
    status,
    clone() { return response(status, detail); },
    async json() { return { detail }; },
  };
}
function assert(condition, message) {
  if (!condition) throw new Error(message);
}
"""
        scenarios = r"""
(async () => {
  ADMIN_API_KEY = "refusee";
  adminAuthState = "unverified";
  storage.set("ADMIN_API_KEY", "refusee");
  global.fetch = async () => response(403, "Clé admin invalide.");
  const refused = await ensureAdminApiKey();
  assert(refused === "", "une clé refusée ne doit pas être retournée");
  assert(ADMIN_API_KEY === "", "une clé refusée doit être vidée en mémoire");
  assert(!storage.has("ADMIN_API_KEY"), "une clé refusée doit être supprimée de sessionStorage");
  assert(elements["admin-auth-detail"].textContent.includes("vos informations sont conservées"), "message invalide précis absent");

  ADMIN_API_KEY = "ancienne-valide";
  adminAuthState = "authenticated";
  storage.set("ADMIN_API_KEY", ADMIN_API_KEY);
  promptResult = null;
  let fetchCount = 0;
  global.fetch = async () => { fetchCount += 1; return response(200); };
  const canceled = await changeAdminApiKey();
  assert(canceled === false && fetchCount === 0, "annuler ne doit pas lancer de requête");
  assert(ADMIN_API_KEY === "ancienne-valide", "annuler doit conserver la clé précédente");

  promptResult = "nouvelle-refusee";
  global.fetch = async () => response(403, "Clé admin invalide.");
  const invalidChange = await changeAdminApiKey();
  assert(invalidChange === false, "une nouvelle clé refusée ne doit pas être acceptée");
  assert(ADMIN_API_KEY === "" && !storage.has("ADMIN_API_KEY"), "une nouvelle clé refusée doit être effacée");

  ADMIN_API_KEY = "ancienne-valide";
  adminAuthState = "authenticated";
  storage.set("ADMIN_API_KEY", ADMIN_API_KEY);
  promptResult = "nouvelle-cle";
  global.fetch = async () => { throw new Error("network down"); };
  const networkFailure = await changeAdminApiKey();
  assert(networkFailure === false, "une panne réseau ne doit pas valider la clé");
  assert(ADMIN_API_KEY === "ancienne-valide", "une panne réseau doit conserver la clé précédente");
  assert(adminAuthState === "authenticated", "une panne réseau ne doit pas déclarer la clé précédente invalide");

  ADMIN_API_KEY = "";
  adminAuthState = "missing";
  storage.delete("ADMIN_API_KEY");
  promptResult = "nouvelle-valide";
  global.fetch = async () => response(200);
  const changed = await changeAdminApiKey();
  assert(changed === true, "une clé correcte doit être validée");
  assert(ADMIN_API_KEY === "nouvelle-valide", "la clé validée doit être mémorisée");
  assert(storage.get("ADMIN_API_KEY") === "nouvelle-valide", "la clé validée doit être stockée");

  fetchCount = 0;
  global.fetch = async () => {
    fetchCount += 1;
    return response(403, "Clé admin invalide.");
  };
  const failedWrite = await adminFetch("/api/cards/", { method: "POST", body: "{}" });
  assert(failedWrite === null, "un appel refusé doit s'arrêter");
  assert(fetchCount === 1, "un POST refusé ne doit jamais être répété automatiquement");
  assert(ADMIN_API_KEY === "" && !storage.has("ADMIN_API_KEY"), "le refus d'un appel doit effacer la clé");

  console.log(JSON.stringify({ ok: true }));
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        script = harness + auth_block + scenarios
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
        self.assertEqual(json.loads(proc.stdout), {"ok": True})


if __name__ == "__main__":
    unittest.main()
