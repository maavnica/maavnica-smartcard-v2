# backend/app/routers/upload.py
"""
Upload d'avatar pour SmartCard.
Endpoint: POST /api/upload/avatar
Comportement: l'image est uploadée directement sur Cloudinary (pas de stockage local),
et l'API renvoie l'URL `secure_url`.
"""
import asyncio
import logging
import os
import uuid
from io import BytesIO
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

try:
    import cloudinary
    from cloudinary import uploader as cloudinary_uploader
except ImportError:  # pragma: no cover
    cloudinary = None
    cloudinary_uploader = None

router = APIRouter()
logger = logging.getLogger(__name__)

from app.utils.admin_auth import require_admin_api_key

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

_CLOUDINARY_INITIALIZED = False


def _get_safe_extension(filename: str) -> Optional[str]:
    """Retourne l'extension normalisée si autorisée, sinon None."""
    if not filename or "." not in filename:
        return None
    ext = "." + filename.rsplit(".", 1)[-1].lower()
    return ext if ext in ALLOWED_EXTENSIONS else None


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

    if cloudinary is None or cloudinary_uploader is None:
        logger.error("Cloudinary SDK indisponible: package non installé côté runtime.")
        raise HTTPException(
            status_code=500,
            detail="Le SDK Cloudinary n'est pas installé côté backend.",
        )

    cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
    api_key = os.getenv("CLOUDINARY_API_KEY")
    api_secret = os.getenv("CLOUDINARY_API_SECRET")

    missing = []
    if not cloud_name:
        missing.append("CLOUDINARY_CLOUD_NAME")
    if not api_key:
        missing.append("CLOUDINARY_API_KEY")
    if not api_secret:
        missing.append("CLOUDINARY_API_SECRET")

    if missing:
        logger.error("Variables Cloudinary manquantes: %s", ", ".join(missing))
        raise HTTPException(
            status_code=500,
            detail=f"Variables d'environnement Cloudinary manquantes: {', '.join(missing)}",
        )

    try:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        _CLOUDINARY_INITIALIZED = True
        logger.info(
            "Cloudinary initialisé avec succès (cloud_name=%s, api_key_present=%s, api_secret_present=%s)",
            cloud_name,
            bool(api_key),
            bool(api_secret),
        )
    except Exception as e:
        logger.exception("Échec de l'initialisation Cloudinary: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Impossible d'initialiser Cloudinary.",
        ) from e


async def _upload_avatar_to_cloudinary(image_bytes: bytes, ext: str) -> str:
    """
    Upload des bytes d'une image vers Cloudinary et retourne `secure_url`.
    """
    _init_cloudinary()

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
            raise RuntimeError(
                f"Cloudinary: secure_url manquant dans la réponse. keys={list(result.keys())}"
            )
        return secure_url

    try:
        secure_url = await asyncio.to_thread(_do_upload)
        logger.info("Upload Cloudinary OK pour public_id=%s", public_id)
        return secure_url
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Échec upload Cloudinary pour public_id=%s: %s", public_id, e)
        raise HTTPException(
            status_code=500,
            detail="Impossible d'uploader l'avatar sur Cloudinary.",
        ) from e


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(..., alias="file"),
    _: None = Depends(require_admin_api_key),
):
    """
    Reçoit une image, l'uploade sur Cloudinary et retourne l'URL `secure_url`.
    Accepte : .jpg, .jpeg, .png, .webp
    """
    logger.info(
        "POST /api/upload/avatar reçu (filename=%s, content_type=%s)",
        file.filename,
        file.content_type,
    )

    ext = _get_safe_extension(file.filename or "")
    if not ext:
        logger.warning("Extension non autorisée pour filename=%s", file.filename)
        raise HTTPException(
            status_code=400,
            detail="Type de fichier non autorisé. Utilisez : .jpg, .jpeg, .png ou .webp",
        )

    content_type = (file.content_type or "").strip().lower()
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(
            "Type MIME non autorisé pour filename=%s: %s",
            file.filename,
            content_type,
        )
        raise HTTPException(
            status_code=400,
            detail="Type MIME non autorisé. Utilisez une image JPEG, PNG ou WebP.",
        )

    try:
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            logger.warning(
                "Fichier trop volumineux pour filename=%s: %s octets",
                file.filename,
                len(contents),
            )
            raise HTTPException(
                status_code=400,
                detail="Fichier trop volumineux (max 5 Mo).",
            )
        if not contents:
            logger.warning("Fichier vide pour filename=%s", file.filename)
            raise HTTPException(status_code=400, detail="Fichier vide.")
    except OSError as e:
        logger.exception("Impossible de lire le fichier %s: %s", file.filename, e)
        raise HTTPException(
            status_code=500,
            detail="Impossible de lire le fichier.",
        ) from e

    secure_url = await _upload_avatar_to_cloudinary(contents, ext=ext)
    return {"url": secure_url}
