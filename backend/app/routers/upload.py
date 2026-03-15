# backend/app/routers/upload.py
"""
Upload d'avatar pour SmartCard.
Endpoint: POST /api/upload/avatar
Fichiers enregistrés dans backend/static/uploads/
"""

import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter()

# Chemins (compatible local + Render)
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
STATIC_DIR = BACKEND_DIR / "static"
UPLOADS_DIR = STATIC_DIR / "uploads"

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


def _ensure_uploads_dir() -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOADS_DIR


def _get_safe_extension(filename: str) -> Optional[str]:
    """Retourne l'extension normalisée si autorisée, sinon None."""
    if not filename or "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(..., alias="file")):
    """
    Reçoit une image, la sauvegarde dans static/uploads/ et retourne l'URL publique.
    Accepte : .jpg, .jpeg, .png, .webp
    """
    ext = _get_safe_extension(file.filename or "")
    if not ext:
        raise HTTPException(
            status_code=400,
            detail="Type de fichier non autorisé. Utilisez : .jpg, .jpeg, .png ou .webp",
        )

    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Type MIME non autorisé. Utilisez une image JPEG, PNG ou WebP.",
        )

    _ensure_uploads_dir()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOADS_DIR / unique_name

    try:
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:  # 5 Mo max
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 5 Mo).")
        file_path.write_bytes(contents)
    except OSError as e:
        raise HTTPException(status_code=500, detail="Impossible d'enregistrer le fichier.") from e

    url = f"/static/uploads/{unique_name}"
    return {"url": url}
