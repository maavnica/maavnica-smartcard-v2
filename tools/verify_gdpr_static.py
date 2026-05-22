#!/usr/bin/env python3
"""Vérification rapide liens RGPD /static/ et consentement analytics."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "static"
LANDING = ROOT / "landing"

PUBLIC = [
    ("/", LANDING / "index.html"),
    ("/static/contact-smartcard.html", STATIC / "contact-smartcard.html"),
    ("/static/recontact-smartcard.html", STATIC / "recontact-smartcard.html"),
    ("/static/devenir-affilie.html", STATIC / "devenir-affilie.html"),
    ("/static/devenir-affilie-merci.html", STATIC / "devenir-affilie-merci.html"),
    ("/static/affiliation.html", STATIC / "affiliation.html"),
    ("/static/form-smartcard.html", STATIC / "form-smartcard.html"),
    ("/static/success-smartcard.html", STATIC / "success-smartcard.html"),
    ("/static/confidentialite.html", STATIC / "confidentialite.html"),
    ("/static/mentions-legales.html", STATIC / "mentions-legales.html"),
    ("/static/cookies.html", STATIC / "cookies.html"),
    ("/static/cgv-smartcard.html", STATIC / "cgv-smartcard.html"),
    ("/static/guide-smartcard.html", STATIC / "guide-smartcard.html"),
    ("/static/kit-affilie.html", STATIC / "kit-affilie.html"),
    ("/c/slug FR", STATIC / "public-card" / "index.html"),
    ("/c/slug LATAM", STATIC / "public-card" / "index_latam.html"),
]

LEGAL_PAT = re.compile(r"confidentialite\.html|mentions-legales\.html")
STATIC_HREF = re.compile(r'href=["\'](/static/[^"\']+)["\']')

missing_legal = []
broken = []
no_consent = []

for route, path in PUBLIC:
    if not path.exists():
        broken.append((route, str(path), "FILE_MISSING"))
        continue
    text = path.read_text(encoding="utf-8", errors="replace")
    if "slug" not in route and not LEGAL_PAT.search(text):
        missing_legal.append((route, str(path)))
    for href in STATIC_HREF.findall(text):
        rel = href[len("/static/") :]
        if not (STATIC / rel).exists():
            broken.append((route, href, "404_STATIC"))

for base in (STATIC, LANDING):
    for html in base.rglob("*.html"):
        t = html.read_text(encoding="utf-8", errors="replace")
        if "site-analytics.js" in t and "maavnica-consent.js" not in t:
            no_consent.append(str(html.relative_to(ROOT)))

sa = (STATIC / "site-analytics.js").read_text(encoding="utf-8")
assert "STORAGE_CONSENT" in sa
pc = (STATIC / "public-card" / "index.html").read_text(encoding="utf-8")
assert "maavnica_consent" in pc and "maavnica-consent.js" in pc

print("Missing legal:", missing_legal or "none")
print("Broken href:", broken or "none")
print("Analytics w/o consent.js:", no_consent or "none")
for f in ("confidentialite.html", "mentions-legales.html", "cookies.html", "maavnica-consent.js"):
    print(f, (STATIC / f).exists())
