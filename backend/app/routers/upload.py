# backend/app/routers/upload.py
"""
Upload d'avatar pour SmartCard.
Endpoint: POST /api/upload/avatar

Comportement: l'image est uploadée directement sur Cloudinary (pas de stockage local),
et l'API renvoie l'URL `secure_url`.
"""

import asyncio
import os
import uuid
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile

try:
    from cloudinary import config as cloudinary_config
    from cloudinary import uploader as cloudinary_uploader
except ImportError:  # pragma: no cover
    cloudinary_config = None
    cloudinary_uploader = None

router = APIRouter()

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

def _get_safe_extension(filename: str) -> Optional[str]:
    """Retourne l'extension normalisée si autorisée, sinon None."""
    if not filename or "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


_CLOUDINARY_INITIALIZED = False


def _init_cloudinary() -> None:
    """
    Initialise le SDK Cloudinary à partir des variables d'environnement.

    Variables requises:
    - CLOUDINARY_CLOUD_NAME
    - CLOUDINARY_API_KEY
    - CLOUDINARY_API_SECRET
    """
    global _CLOUDINARY_INITIALIZED
    if _CLOUDINARY_INITIALIZED:
        return

    if cloudinary_config is None or cloudinary_uploader is None:
        raise HTTPException(
            status_code=500,
            detail="Le SDK Cloudinary n'est pas installé. Ajoute le package `cloudinary` côté backend.",
        )

    missing = []
    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")
    if not cloud_name:
        missing.append("CLOUDINARY_CLOUD_NAME")
    if not api_key:
        missing.append("CLOUDINARY_API_KEY")
    if not api_secret:
        missing.append("CLOUDINARY_API_SECRET")

    if missing:
        raise HTTPException(
            status_code=500,
            detail=f"Variables d'environnement Cloudinary manquantes: {', '.join(missing)}",
        )

    cloudinary_config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret,
        secure=True,
    )
    _CLOUDINARY_INITIALIZED = True


async def _upload_avatar_to_cloudinary(image_bytes: bytes, ext: str) -> str:
    """
    Upload des bytes d'une image vers Cloudinary et retourne `secure_url`.
    """
    _init_cloudinary()

    # Cloudinary s'attend à un "public_id" sans extension.
    public_id = uuid.uuid4().hex
    format_ = ext.lstrip(".")

    def _do_upload() -> str:
        result = cloudinary_uploader.upload(
            file=BytesIO(image_bytes),
            public_id=public_id,
            resource_type="image",
            format=format_,
            overwrite=True,
        )
        secure_url = result.get("secure_url")
        if not secure_url:
            raise RuntimeError(f"Cloudinary: secure_url manquant dans la réponse. keys={list(result.keys())}")
        return secure_url

    try:
        # La lib Cloudinary est synchrone: on la délègue au thread pool.
        return await asyncio.to_thread(_do_upload)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Impossible d'uploader l'avatar sur Cloudinary.",
        ) from e


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(..., alias="file")):
    """
    Reçoit une image, l'uploade sur Cloudinary et retourne l'URL `secure_url`.
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

    try:
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:  # 5 Mo max
            raise HTTPException(status_code=400, detail="Fichier trop volumineux (max 5 Mo).")
        if not contents:
            raise HTTPException(status_code=400, detail="Fichier vide.")
    except OSError as e:
        raise HTTPException(status_code=500, detail="Impossible de lire le fichier.") from e

    secure_url = await _upload_avatar_to_cloudinary(contents, ext=ext)
    return {"url": secure_url}
