"""Mise à jour locale des prospects enrichis (recherche manuelle / semi-manuelle)."""

from __future__ import annotations

from dataclasses import replace

from .enrichment_models import EnrichedProspectItem

_ALLOWED_ENRICHMENT_STATUS = frozenset({"pending", "started", "completed"})
_ALLOWED_PRIORITY = frozenset({"low", "normal", "high"})
_ALLOWED_CONTACT_CHANNEL = frozenset({"", "email", "linkedin", "website", "phone"})


def _validate_enrichment_status(value: str) -> None:
    if value not in _ALLOWED_ENRICHMENT_STATUS:
        allowed = ", ".join(sorted(_ALLOWED_ENRICHMENT_STATUS))
        raise ValueError(
            f"enrichment_status invalide : {value!r}. Valeurs autorisées : {allowed}."
        )


def _validate_priority(value: str) -> None:
    if value not in _ALLOWED_PRIORITY:
        allowed = ", ".join(sorted(_ALLOWED_PRIORITY))
        raise ValueError(f"priority invalide : {value!r}. Valeurs autorisées : {allowed}.")


def _validate_contact_channel(value: str) -> None:
    if value not in _ALLOWED_CONTACT_CHANNEL:
        opts = "chaîne vide, " + ", ".join(sorted(c for c in _ALLOWED_CONTACT_CHANNEL if c))
        raise ValueError(f"contact_channel invalide : {value!r}. Valeurs autorisées : {opts}.")


def update_enriched_item(
    item: EnrichedProspectItem,
    website: str | None = None,
    email: str | None = None,
    linkedin: str | None = None,
    source: str | None = None,
    contact_found: bool | None = None,
    enrichment_status: str | None = None,
    notes: str | None = None,
    ready_to_contact: bool | None = None,
    contact_channel: str | None = None,
    priority: str | None = None,
) -> EnrichedProspectItem:
    """
    Retourne une copie de l'item avec uniquement les champs fournis (non None) modifiés.
    """
    changes: dict[str, str | bool] = {}

    if website is not None:
        changes["website"] = website
    if email is not None:
        changes["email"] = email
    if linkedin is not None:
        changes["linkedin"] = linkedin
    if source is not None:
        changes["source"] = source
    if contact_found is not None:
        changes["contact_found"] = contact_found
    if enrichment_status is not None:
        _validate_enrichment_status(enrichment_status)
        changes["enrichment_status"] = enrichment_status
    if notes is not None:
        changes["notes"] = notes
    if ready_to_contact is not None:
        changes["ready_to_contact"] = ready_to_contact
    if contact_channel is not None:
        _validate_contact_channel(contact_channel)
        changes["contact_channel"] = contact_channel
    if priority is not None:
        _validate_priority(priority)
        changes["priority"] = priority

    if not changes:
        return item

    return replace(item, **changes)


def mark_items_as_started(items: list[EnrichedProspectItem]) -> list[EnrichedProspectItem]:
    """Retourne une nouvelle liste avec enrichment_status='started' pour chaque entrée."""
    return [replace(item, enrichment_status="started") for item in items]
