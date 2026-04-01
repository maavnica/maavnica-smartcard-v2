"""Export CSV minimal pour les prospects enrichis."""

from __future__ import annotations

import csv
from pathlib import Path

from .enrichment_models import EnrichedProspectItem


def export_enriched_items_to_csv(items: list[EnrichedProspectItem], output_path: str) -> str:
    """
    Exporte une liste de EnrichedProspectItem dans un fichier CSV.

    Colonnes : category, city, query, status, notes, message, website, email, linkedin,
    search_url, source, contact_found, enrichment_status,
    ready_to_contact, contact_channel, priority.
    """
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "category",
        "city",
        "query",
        "status",
        "notes",
        "message",
        "website",
        "email",
        "linkedin",
        "search_url",
        "source",
        "contact_found",
        "enrichment_status",
        "ready_to_contact",
        "contact_channel",
        "priority",
    ]

    with target.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            writer.writerow(
                {
                    "category": item.category,
                    "city": item.city,
                    "query": item.query,
                    "status": item.status,
                    "notes": item.notes,
                    "message": item.message,
                    "website": item.website,
                    "email": item.email,
                    "linkedin": item.linkedin,
                    "search_url": item.search_url,
                    "source": item.source,
                    "contact_found": item.contact_found,
                    "enrichment_status": item.enrichment_status,
                    "ready_to_contact": item.ready_to_contact,
                    "contact_channel": item.contact_channel,
                    "priority": item.priority,
                }
            )

    return str(target)
