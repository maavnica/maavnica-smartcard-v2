"""Export CSV minimal pour les prospects enrichis (outreach)."""

from __future__ import annotations

import csv
from pathlib import Path

from .outreach_models import OutreachItem


def export_outreach_to_csv(items: list[OutreachItem], output_path: str) -> str:
    """
    Exporte une liste de OutreachItem dans un fichier CSV.

    Colonnes exportées:
    - category
    - city
    - query
    - status
    - notes
    - message
    """
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=["category", "city", "query", "status", "notes", "message"],
        )
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
                }
            )

    return str(target)

