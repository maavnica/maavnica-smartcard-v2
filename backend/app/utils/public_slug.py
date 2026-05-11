"""Normalisation des slugs d’URL publiques (/c/…, API cartes publiques)."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import unquote


def sanitize_public_slug(raw_slug: str | None) -> str:
    """
    Nettoie un slug public : espaces, guillemets, caractères de contrôle / format,
    caractère de remplacement, séquences %XX éventuellement encodées plusieurs fois,
    tout caractère hors [A-Za-z0-9-].
    """
    if raw_slug is None:
        return ""
    slug = (raw_slug or "").strip().strip("\"'")
    if "%" in slug:
        for _ in range(8):
            if "%" not in slug:
                break
            try:
                decoded = unquote(slug)
            except (ValueError, UnicodeDecodeError):
                break
            if decoded == slug:
                break
            slug = decoded
    slug = "".join(
        ch for ch in slug if not ch.isspace() and not unicodedata.category(ch).startswith("C")
    )
    slug = slug.replace("\ufffd", "")
    return re.sub(r"[^A-Za-z0-9-]+", "", slug)
