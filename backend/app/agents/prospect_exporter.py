"""Export CSV minimal pour les prospects préparés."""

from __future__ import annotations

import csv
from pathlib import Path

from .prospect_models import ProspectItem


def export_prospects_to_csv(items: list[ProspectItem], output_path: str) -> str:
    """
    Exporte une liste de ProspectItem dans un fichier CSV.

    Colonnes exportées:
    - category
    - city
    - query
    - status
    - notes
    """
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(
            file_obj,
            fieldnames=["category", "city", "query", "status", "notes"],
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
                }
            )

    return str(target)

