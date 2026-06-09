"""DEPRECATED — utiliser tools/regenerate_og.py (capture produit V2).

Ancien générateur bannière marketing ; conservé pour référence locale uniquement.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "backend" / "static"
OUT = STATIC / "og-default.jpg"

W, H = 1200, 630
BG = (243, 237, 228)  # wellness --bg-page #f3ede4
ACCENT = (45, 74, 58)  # vert forêt premium
MUTED = (95, 88, 78)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    if bold:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            *candidates,
        ]
    for path in candidates:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _load_phone_shot() -> Image.Image:
    for rel in (
        "landing-v2/demo-bienetre.png",
        "hero-smartcard-premium.png",
    ):
        path = STATIC / rel
        if path.is_file():
            img = Image.open(path).convert("RGBA")
            # Retirer bannière cookies en bas (~12 %)
            crop_h = int(img.height * 0.88)
            return img.crop((0, 0, img.width, crop_h))
    raise FileNotFoundError("Aucune capture demo-bienetre trouvée dans backend/static/")


def main() -> None:
    canvas = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(canvas)

    # Bande verticale douce à gauche
    for x in range(520):
        t = x / 520
        shade = tuple(int(BG[i] * (1 - 0.04 * t)) for i in range(3))
        draw.line([(x, 0), (x, H)], fill=shade)

    # Logo palmier
    palm = Image.open(STATIC / "logo-palmier.png").convert("RGBA")
    palm_size = 72
    palm = palm.resize((palm_size, palm_size), Image.LANCZOS)
    canvas.paste(palm, (72, 64), palm)

    # Texte branding Premium
    draw.text((72, 148), "MAAVNICA", font=_font(22, bold=True), fill=ACCENT)
    draw.text((72, 198), "SmartCard Premium", font=_font(52, bold=True), fill=ACCENT)
    draw.text(
        (72, 272),
        "La carte professionnelle de confiance",
        font=_font(28),
        fill=MUTED,
    )
    draw.text(
        (72, 330),
        "Contact direct  •  Avis Google  •  Recommandations",
        font=_font(22),
        fill=MUTED,
    )

    # Pastille preuve sociale
    pill_y = 420
    draw.rounded_rectangle((72, pill_y, 430, pill_y + 52), radius=26, fill=(255, 252, 247))
    draw.text((96, pill_y + 12), "★  4,8 sur Google  •  Recommandé par vos clients", font=_font(20), fill=ACCENT)

    # Mockup téléphone (capture demo2 wellness premium)
    phone = _load_phone_shot()
    target_h = 540
    scale = target_h / phone.height
    target_w = int(phone.width * scale)
    phone = phone.resize((target_w, target_h), Image.LANCZOS)

    radius = 36
    mask = _rounded_mask((target_w, target_h), radius)
    phone_rgb = Image.new("RGB", phone.size, BG)
    phone_rgb.paste(phone, mask=phone.split()[3] if phone.mode == "RGBA" else None)

    # Ombre portée
    shadow = Image.new("RGBA", (target_w + 40, target_h + 40), (0, 0, 0, 0))
    sh = Image.new("RGBA", (target_w, target_h), (30, 50, 38, 90))
    sh.putalpha(mask)
    shadow.paste(sh, (20, 20), sh)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))

    phone_x = W - target_w - 88
    phone_y = (H - target_h) // 2
    canvas.paste(shadow, (phone_x - 12, phone_y - 8), shadow)
    canvas.paste(phone_rgb, (phone_x, phone_y), mask)

    # Bordure fine autour du mockup
    border = Image.new("RGBA", (target_w, target_h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(border)
    bdraw.rounded_rectangle(
        (0, 0, target_w - 1, target_h - 1),
        radius=radius,
        outline=(45, 74, 58, 40),
        width=2,
    )
    canvas.paste(border, (phone_x, phone_y), border)

    canvas.save(OUT, "JPEG", quality=92, optimize=True, subsampling=0)
    print(f"OK {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
