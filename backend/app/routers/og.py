"""Route de service des images Open Graph pré-générées (cache statique, sans Playwright)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.og_capture import (
    OG_DEFAULT_PATH,
    is_og_dynamic_enabled,
    og_generated_path,
)
from app.utils.public_slug import sanitize_public_slug

router = APIRouter(tags=["og"])


@router.get("/og/{slug}.jpg", include_in_schema=False)
async def serve_og_image(slug: str):
    """Sert l'image OG pré-générée ou le fallback marketing minimal."""
    slug_norm = sanitize_public_slug(slug)
    if not slug_norm:
        raise HTTPException(status_code=404, detail="Slug invalide")

    if not is_og_dynamic_enabled():
        if not OG_DEFAULT_PATH.is_file():
            raise HTTPException(status_code=404, detail="Image OG par défaut introuvable")
        return FileResponse(
            path=str(OG_DEFAULT_PATH),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    generated = og_generated_path(slug_norm)
    if generated.is_file():
        return FileResponse(
            path=str(generated),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    if OG_DEFAULT_PATH.is_file():
        return FileResponse(
            path=str(OG_DEFAULT_PATH),
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    raise HTTPException(status_code=404, detail="Image OG introuvable")
