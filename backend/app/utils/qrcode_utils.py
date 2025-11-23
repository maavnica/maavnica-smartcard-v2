from pathlib import Path
import os

import qrcode

# On remonte jusqu'au dossier racine "maavnica-smartcard"
# Structure : maavnica-smartcard/backend/app/utils/qrcode_utils.py
BASE_DIR = Path(__file__).resolve().parents[3]

# Dossier où seront générés les QR codes
QR_BASE_DIR = BASE_DIR / "static" / "qr"
QR_BASE_DIR.mkdir(parents=True, exist_ok=True)

# Domaine public de la SmartCard
# Tu peux le surcharger avec une variable d'environnement PUBLIC_BASE_URL
DEFAULT_PUBLIC_BASE_URL = "https://maavnica-smartcard-v2.onrender.com"
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL)


def get_or_create_qr_for_slug(slug: str) -> str:
    """
    Crée un QR code pour l'URL publique d'une SmartCard, si besoin,
    et retourne l'URL du fichier accessible via /static/qr/slug.png
    """
    filename = QR_BASE_DIR / f"{slug}.png"

    if not filename.exists():
        # URL publique de la carte
        base = PUBLIC_BASE_URL.rstrip("/")
        url = f"{base}/c/{slug}"

        img = qrcode.make(url)
        img.save(filename)

    # URL relative servie par FastAPI depuis /static
    return f"/static/qr/{slug}.png"

