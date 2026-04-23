"""Affichage recommandant (prénom + nom) — logique partagée, sans dépendance lourde."""

from __future__ import annotations

from typing import Optional


def normalize_recommender_part(value: Optional[str]) -> str:
    if not value or not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def build_recommender_display_name(
    first: Optional[str],
    last: Optional[str],
) -> Optional[str]:
    f = normalize_recommender_part(first)
    l = normalize_recommender_part(last)
    if f and l:
        return f"{f} {l}"
    if f:
        return f
    if l:
        return l
    return None


def effective_recommender_label(
    display_name: Optional[str],
    legacy_referrer_id: Optional[str],
) -> str:
    """Libellé humain : display si présent ; sinon anciens id lisibles (ex. ?r=marc).
    Les jetons opaques rec_* ne sont pas affichés à l'artisan (traçabilité interne uniquement)."""
    d = normalize_recommender_part(display_name) if display_name else ""
    if d:
        return d
    rid = (legacy_referrer_id or "").strip()
    if not rid:
        return "—"
    if rid.lower().startswith("rec_"):
        return "—"
    return rid
