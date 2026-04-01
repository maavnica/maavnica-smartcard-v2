"""Structures simples pour un prospect enrichi (points de contact à compléter plus tard)."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from .outreach_models import OutreachItem
from .prospect_models import ProspectStatus


def _google_search_url_from_query(query: str) -> str:
    """Construit une URL de recherche Google simple à partir du texte de requête (sans appel HTTP)."""
    q = quote_plus((query or "").strip())
    return f"https://www.google.com/search?q={q}"


@dataclass(slots=True)
class EnrichedProspectItem:
    """
    Prolonge l'outreach avec des champs contact prêts à être remplis manuellement
    ou par une future étape d'enrichissement (hors périmètre actuel).
    """

    category: str
    city: str
    query: str
    status: ProspectStatus = "new"
    notes: str = ""
    message: str = ""
    website: str = ""
    email: str = ""
    linkedin: str = ""
    search_url: str = ""
    source: str = ""
    contact_found: bool = False
    enrichment_status: str = "pending"
    ready_to_contact: bool = False
    contact_channel: str = ""
    priority: str = "normal"


def build_enriched_items_from_outreach(items: list[OutreachItem]) -> list[EnrichedProspectItem]:
    """
    Recopie les champs d'outreach, initialise les contacts à vide
    et prépare le suivi (URL de recherche, statut d'enrichissement).
    """
    enriched: list[EnrichedProspectItem] = []

    for item in items:
        enriched.append(
            EnrichedProspectItem(
                category=item.category,
                city=item.city,
                query=item.query,
                status=item.status,
                notes=item.notes,
                message=item.message,
                website="",
                email="",
                linkedin="",
                search_url=_google_search_url_from_query(item.query),
                source="",
                contact_found=False,
                enrichment_status="pending",
                ready_to_contact=False,
                contact_channel="",
                priority="normal",
            )
        )

    return enriched
