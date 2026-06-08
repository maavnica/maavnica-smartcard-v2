"""
Régénère les images Open Graph SmartCard via capture Playwright du rendu réel /c/{slug}.

Usage local (serveur preview requis) :
  cd backend && uvicorn app.main:app --port 10000
  python tools/regenerate_og.py --base-url http://127.0.0.1:10000

Usage build Render : voir scripts/build_regenerate_og.sh
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from PIL import Image  # noqa: E402

from app.og_capture import (  # noqa: E402
    composite_og_canvas,
    css_color_to_rgb,
    ensure_og_dirs,
    og_cache_bust,
    og_generated_path,
    write_manifest_entry,
)
from app.models import Card  # noqa: E402
from app.database import SessionLocal  # noqa: E402

# Sélecteurs zone à forte valeur (photo → CTA principal)
_VALUE_ZONE_SELECTORS = [
    ".hero-avatar",
    "#person-name",
    "#hero-job-title",
    "#hero-city",
    "#hero-professional-tagline",
    "#hero-google-badge-compact",
    "#hero-google-badge",
    ".hero-google-badge-wrap",
    "#btn-primary-demande-contact",
]

_CROP_CLIP_JS = """
(slug) => {
  const shell = document.querySelector(".phone-shell");
  if (!shell) return null;

  const selectors = %s;
  const shellRect = shell.getBoundingClientRect();
  let top = shellRect.bottom;
  let bottom = shellRect.top;
  let found = false;

  const visible = (el) => {
    if (!el) return false;
    const st = getComputedStyle(el);
    if (st.display === "none" || st.visibility === "hidden" || st.opacity === "0") return false;
    const r = el.getBoundingClientRect();
    return r.width > 2 && r.height > 2;
  };

  for (const sel of selectors) {
    document.querySelectorAll(sel).forEach((el) => {
      if (!visible(el)) return;
      const r = el.getBoundingClientRect();
      found = true;
      top = Math.min(top, r.top);
      bottom = Math.max(bottom, r.bottom);
    });
  }

  const padTop = 14;
  const padBottom = 18;
  const padX = 10;

  if (!found) {
    const h = Math.min(shellRect.height, shellRect.width * 1.55);
    return {
      x: Math.max(0, shellRect.left - padX),
      y: Math.max(0, shellRect.top),
      width: shellRect.width + padX * 2,
      height: h,
    };
  }

  top = Math.max(shellRect.top, top - padTop);
  bottom = Math.min(shellRect.bottom, bottom + padBottom);

  return {
    x: Math.max(0, shellRect.left - padX),
    y: Math.max(0, top),
    width: shellRect.width + padX * 2,
    height: Math.max(80, bottom - top),
  };
}
""" % (
    str(_VALUE_ZONE_SELECTORS).replace("'", '"')
)

_CLEANUP_DOM_JS = """
() => {
  document.getElementById("maavnica-consent-banner")?.remove();
  document.getElementById("premium-load-layer")?.remove();
  document.getElementById("demo-banner-shell")?.remove();
  document.querySelectorAll(".demo-marketing").forEach((el) => el.remove());
  document.getElementById("admin-preview-badge")?.remove();
}
"""

_WAIT_READY_JS = """
() => {
  if (document.body.classList.contains("is-loading")) return false;
  const layer = document.getElementById("premium-load-layer");
  if (layer && layer.getAttribute("aria-hidden") !== "true") return false;
  const name = document.getElementById("person-name");
  const label = (name && name.textContent || "").trim();
  if (!label || label === "Prénom Nom") return false;
  const shell = document.querySelector(".phone-shell");
  if (!shell) return false;
  return true;
}
"""


def _is_build_lenient() -> bool:
    raw = (__import__("os").environ.get("OG_BUILD_LENIENT") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _list_active_fr_slugs(active_only: bool, slug_filter: str | None) -> list[str]:
    """Liste les slugs via SQL léger (slug/region/expires_at uniquement)."""
    from sqlalchemy import text

    db = SessionLocal()
    try:
        sql = (
            "SELECT slug FROM cards "
            "WHERE COALESCE(region, 'fr') != 'latam'"
        )
        params: dict = {}
        if active_only:
            sql += " AND (expires_at IS NULL OR expires_at > :now)"
            params["now"] = datetime.utcnow()
        if slug_filter:
            sql += " AND LOWER(slug) = :slug"
            params["slug"] = slug_filter.strip().lower()
        sql += " ORDER BY slug"
        rows = db.execute(text(sql), params).fetchall()
        return [str(r[0]).strip().lower() for r in rows if r and r[0]]
    except Exception as exc:
        print(f"[og] WARN: lecture slugs DB ignorée ({exc})", flush=True)
        return []
    finally:
        db.close()


def _capture_slug(page, base_url: str, slug: str) -> tuple[Image.Image, tuple[int, int, int]] | None:
    url = f"{base_url.rstrip('/')}/c/{slug}"
    page.goto(url, wait_until="networkidle", timeout=90000)
    page.wait_for_selector(".phone-shell", state="visible", timeout=30000)
    page.wait_for_function(_WAIT_READY_JS, timeout=45000)
    time.sleep(0.4)
    page.evaluate(_CLEANUP_DOM_JS)
    time.sleep(0.15)

    bg_css = page.evaluate(
        "() => getComputedStyle(document.body).backgroundColor || 'rgb(243, 237, 228)'"
    )
    bg_rgb = css_color_to_rgb(str(bg_css))

    clip = page.evaluate(_CROP_CLIP_JS)
    if not clip:
        return None

    png_bytes = page.screenshot(type="png", clip=clip)
    return Image.open(BytesIO(png_bytes)), bg_rgb


def regenerate(
    *,
    base_url: str,
    slugs: list[str],
    dry_run: bool = False,
) -> tuple[int, int]:
    from playwright.sync_api import sync_playwright

    ensure_og_dirs()
    ok = 0
    fail = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = browser.new_context(
            viewport={"width": 430, "height": 900},
            device_scale_factor=2,
        )
        context.add_init_script("localStorage.setItem('maavnica_consent', 'all');")
        page = context.new_page()

        for slug in slugs:
            try:
                print(f"[og] capture {slug} …", flush=True)
                captured = _capture_slug(page, base_url, slug)
                if captured is None:
                    print(f"[og] WARN {slug}: zone vide", flush=True)
                    fail += 1
                    continue
                card_img, bg_rgb = captured
                jpeg = composite_og_canvas(card_img, bg_rgb=bg_rgb)
                if dry_run:
                    print(f"[og] dry-run {slug}: {len(jpeg)} bytes", flush=True)
                    ok += 1
                    continue
                out = og_generated_path(slug)
                out.write_bytes(jpeg)
                bust = "0"
                try:
                    db = SessionLocal()
                    try:
                        card = db.query(Card).filter(Card.slug == slug).first()
                        bust = og_cache_bust(card) if card else "0"
                    finally:
                        db.close()
                    write_manifest_entry(slug, size=len(jpeg), cache_bust=bust)
                except Exception as manifest_exc:
                    print(
                        f"[og] WARN {slug}: manifest/hash ignoré ({manifest_exc})",
                        flush=True,
                    )
                print(f"[og] OK {slug} → {out} ({len(jpeg)} bytes)", flush=True)
                ok += 1
            except Exception as exc:
                print(f"[og] FAIL {slug}: {exc}", flush=True)
                fail += 1

        context.close()
        browser.close()

    return ok, fail


def main() -> int:
    parser = argparse.ArgumentParser(description="Régénère les images OG SmartCard")
    parser.add_argument(
        "--base-url",
        default=(__import__("os").environ.get("OG_PREVIEW_BASE_URL") or "http://127.0.0.1:10000"),
        help="URL du serveur preview (local build, pas la prod live)",
    )
    parser.add_argument("--slug", help="Un seul slug (optionnel)")
    parser.add_argument("--region", default="fr", help="Région (latam exclu par défaut)")
    parser.add_argument("--active-only", action="store_true", default=True)
    parser.add_argument("--all", dest="active_only", action="store_false")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    lenient = _is_build_lenient()
    try:
        if args.slug:
            slugs = [args.slug.strip().lower()]
        else:
            slugs = _list_active_fr_slugs(args.active_only, None)
    except Exception as exc:
        print(f"[og] WARN: liste slugs impossible ({exc})", flush=True)
        return 0 if lenient else 1

    if not slugs:
        print("[og] aucun slug à traiter — fallback og-default.jpg", flush=True)
        return 0

    print(f"[og] {len(slugs)} slug(s), base={args.base_url}", flush=True)
    try:
        ok, fail = regenerate(base_url=args.base_url, slugs=slugs, dry_run=args.dry_run)
    except Exception as exc:
        print(f"[og] FAIL batch: {exc}", flush=True)
        return 0 if lenient else 1

    print(f"[og] terminé: {ok} ok, {fail} échec(s)", flush=True)
    if lenient:
        return 0
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
