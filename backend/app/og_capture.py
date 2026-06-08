"""Open Graph SmartCard — chemins cache, hash, composition 1200×630 (sans Playwright)."""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Tuple

from PIL import Image

# Layout OG (validé Phase 1)
OG_WIDTH = 1200
OG_HEIGHT = 630
OG_CARD_TARGET_WIDTH = 840  # ~70 % du canvas
OG_CARD_MAX_HEIGHT = 600
OG_BRAND_LOGO_SIZE = 28
OG_BRAND_LOGO_OPACITY = 0.35
OG_BRAND_LOGO_MARGIN = 24

APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
STATIC_DIR = BACKEND_DIR / "static"
if not STATIC_DIR.exists():
    STATIC_DIR = BACKEND_DIR.parent / "static"

OG_GENERATED_DIR = STATIC_DIR / "og" / "generated"
OG_DEFAULT_PATH = STATIC_DIR / "og-default.jpg"
OG_LOGO_PATH = STATIC_DIR / "logo-palmier.png"
OG_MANIFEST_PATH = OG_GENERATED_DIR / "manifest.json"


def ensure_og_dirs() -> None:
    OG_GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def is_og_dynamic_enabled() -> bool:
    raw = (os.environ.get("OG_DYNAMIC_ENABLED") or "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def og_cache_bust(card: Any) -> str:
    """Version courte pour ?v= — change quand la carte ou son visuel change."""
    updated = getattr(card, "updated_at", None)
    if isinstance(updated, datetime):
        ts = int(updated.timestamp())
    else:
        ts = 0
    payload = "|".join(
        [
            str(getattr(card, "slug", "") or ""),
            str(ts),
            str(getattr(card, "visual_theme", "") or ""),
            str(getattr(card, "avatar_url", "") or ""),
        ]
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:8]


def og_generated_path(slug: str) -> Path:
    safe = (slug or "").strip().lower()
    return OG_GENERATED_DIR / f"{safe}.jpg"


def build_og_image_url(base_url: str, slug: str, card: Optional[Any]) -> str:
    """URL publique de l'image OG pour une carte FR."""
    base = (base_url or "").rstrip("/")
    slug_norm = (slug or "").strip().lower()
    if not is_og_dynamic_enabled() or not slug_norm:
        return f"{base}/static/og-default.jpg?v={_og_default_version()}"
    version = og_cache_bust(card) if card is not None else "0"
    if og_generated_path(slug_norm).is_file():
        return f"{base}/og/{slug_norm}.jpg?v={version}"
    return f"{base}/static/og-default.jpg?v={_og_default_version()}"


def _og_default_version() -> str:
    return (os.environ.get("OG_DEFAULT_IMAGE_VERSION") or "3").strip()


def _parse_css_color_to_rgb(color: str) -> Tuple[int, int, int]:
    c = (color or "").strip().lower()
    if c.startswith("#") and len(c) == 7:
        return (int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16))
    if c.startswith("rgb"):
        nums = [int(x) for x in "".join(ch if ch.isdigit() or ch == "," else " " for ch in c).split(",") if x.strip().isdigit()]
        if len(nums) >= 3:
            return (nums[0], nums[1], nums[2])
    return (243, 237, 228)  # wellness --bg-page


def composite_og_canvas(
    card_image: Image.Image,
    *,
    bg_rgb: Tuple[int, int, int] = (243, 237, 228),
    logo_path: Optional[Path] = None,
) -> bytes:
    """Compose la capture recadrée sur un canvas 1200×630."""
    card = card_image.convert("RGBA")
    target_w = OG_CARD_TARGET_WIDTH
    scale = target_w / max(card.width, 1)
    target_h = int(card.height * scale)
    if target_h > OG_CARD_MAX_HEIGHT:
        scale = OG_CARD_MAX_HEIGHT / max(card.height, 1)
        target_w = int(card.width * scale)
        target_h = OG_CARD_MAX_HEIGHT
    card = card.resize((target_w, target_h), Image.LANCZOS)

    canvas = Image.new("RGB", (OG_WIDTH, OG_HEIGHT), bg_rgb)
    x = (OG_WIDTH - target_w) // 2
    y = (OG_HEIGHT - target_h) // 2
    canvas.paste(card, (x, y), card)

    logo_file = logo_path or OG_LOGO_PATH
    if logo_file.is_file():
        logo = Image.open(logo_file).convert("RGBA")
        logo = logo.resize((OG_BRAND_LOGO_SIZE, OG_BRAND_LOGO_SIZE), Image.LANCZOS)
        alpha = logo.split()[3].point(lambda p: int(p * OG_BRAND_LOGO_OPACITY))
        logo.putalpha(alpha)
        lx = OG_WIDTH - OG_BRAND_LOGO_SIZE - OG_BRAND_LOGO_MARGIN
        ly = OG_HEIGHT - OG_BRAND_LOGO_SIZE - OG_BRAND_LOGO_MARGIN
        canvas.paste(logo, (lx, ly), logo)

    buf = io.BytesIO()
    canvas.save(buf, format="JPEG", quality=92, optimize=True, subsampling=0)
    return buf.getvalue()


def write_manifest_entry(slug: str, *, size: int, cache_bust: str) -> None:
    ensure_og_dirs()
    data: dict[str, Any] = {}
    if OG_MANIFEST_PATH.is_file():
        try:
            data = json.loads(OG_MANIFEST_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data[slug] = {
        "size": size,
        "v": cache_bust,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    OG_MANIFEST_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def css_color_to_rgb(css_color: str) -> Tuple[int, int, int]:
    return _parse_css_color_to_rgb(css_color)
