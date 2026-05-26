#!/usr/bin/env python3
"""Génère index_v3.html, v3-layout.css et public-card-runtime.js depuis index.html."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "backend" / "static" / "public-card" / "index.html"
OUT_DIR = ROOT / "backend" / "static" / "public-card"


def main() -> None:
    text = INDEX.read_text(encoding="utf-8")
    style_start = text.index("<style>") + len("<style>")
    style_end = text.index("</style>", style_start)
    css = text[style_start:style_end].strip()

    body_start = text.index("<body")
    body_end = text.index('<script src="/static/maavnica-consent.js">')
    body = text[body_start:body_end].strip()
    body = body.replace(
        'class="theme-apple is-loading"',
        'class="theme-apple is-loading smartcard-v3 public-card--compact"',
        1,
    )

    script_start = text.index("<script>", text.index("maavnica-consent.js")) + len("<script>")
    script_end = text.rindex("</script>", 0, text.rindex("serviceWorker"))
    js = text[script_start:script_end].strip()

    v3_patch = """
    function applyPublicCardUiMode(card) {
      if (document.body.classList.contains("smartcard-v3")) {
        document.body.classList.remove("public-card--legacy");
        document.body.classList.add("public-card--compact");
        return;
      }
"""
    if "function applyPublicCardUiMode(card) {" in js and v3_patch.strip() not in js:
        js = js.replace(
            "function applyPublicCardUiMode(card) {",
            v3_patch.strip(),
            1,
        )

    (OUT_DIR / "v3-layout.css").write_text(css + "\n", encoding="utf-8")
    (OUT_DIR / "public-card-runtime.js").write_text(js + "\n", encoding="utf-8")

    head = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>Maavnica SmartCard – Carte publique</title>
  <meta name="description" content="Carte professionnelle Maavnica. Contact rapide, avis clients et recommandations." />
  <meta property="og:title" content="Maavnica SmartCard" />
  <meta property="og:description" content="Contact direct, avis clients et recommandation simplifiée." />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <link rel="manifest" href="/static/manifest.webmanifest">
  <meta name="theme-color" content="#f5f0e8">
  <link rel="stylesheet" href="/static/public-card/v3-layout.css" />
  <link rel="stylesheet" href="/static/public-card/v3.css" />
</head>
"""
    tail = """
  <script src="/static/maavnica-consent.js"></script>
  <script src="/static/public-card/public-card-runtime.js"></script>
  <script>
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/static/service-worker.js").catch(function () {});
    }
  </script>
</html>
"""
    (OUT_DIR / "index_v3.html").write_text(head + "\n" + body + "\n" + tail, encoding="utf-8")
    print("OK:", OUT_DIR / "index_v3.html", OUT_DIR / "v3-layout.css", OUT_DIR / "public-card-runtime.js")


if __name__ == "__main__":
    main()
