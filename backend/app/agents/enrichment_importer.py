"""Import local d'un CSV enrichi vers des EnrichedProspectItem."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import cast

from .enrichment_models import EnrichedProspectItem
from .prospect_models import ProspectStatus

_REQUIRED_COLUMNS: tuple[str, ...] = (
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
)

_ALLOWED_PROSPECT_STATUS: frozenset[str] = frozenset({"new", "reviewed", "contacted"})
_ALLOWED_ENRICHMENT_STATUS: frozenset[str] = frozenset({"pending", "started", "completed"})


def _cell(row: dict[str, str], key: str) -> str:
    v = row.get(key)
    if v is None:
        return ""
    return str(v).strip()


def _parse_contact_found(raw: str) -> bool:
    """Interprète une cellule CSV en booléen (tolérant aux variantes courantes)."""
    if not raw or not raw.strip():
        return False
    v = raw.strip().lower()
    if v in ("true", "1", "yes", "oui", "vrai", "x", "o"):
        return True
    if v in ("false", "0", "no", "non", "faux", "n"):
        return False
    return False


def _validate_choice(value: str, column: str, allowed: frozenset[str]) -> str:
    if value not in allowed:
        opts = ", ".join(sorted(allowed))
        raise ValueError(
            f"CSV invalide : colonne {column!r}, valeur {value!r} non reconnue. "
            f"Valeurs autorisées : {opts}."
        )
    return value


def import_enriched_items_from_csv(input_path: str) -> list[EnrichedProspectItem]:
    """
    Lit un CSV produit par l'export enrichi et reconstruit des EnrichedProspectItem.

    Exige la présence de toutes les colonnes attendues dans l'en-tête.
    """
    path = Path(input_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Fichier CSV introuvable : {path}")

    items: list[EnrichedProspectItem] = []

    with path.open(newline="", encoding="utf-8-sig") as file_obj:
        reader = csv.DictReader(file_obj)
        if not reader.fieldnames:
            raise ValueError("CSV invalide : fichier vide ou sans ligne d'en-tête.")

        header = [h.strip() for h in reader.fieldnames if h is not None]
        missing = [c for c in _REQUIRED_COLUMNS if c not in header]
        if missing:
            raise ValueError(
                "CSV invalide : colonnes manquantes : "
                + ", ".join(missing)
                + ". Colonnes attendues : "
                + ", ".join(_REQUIRED_COLUMNS)
            )

        for line_no, row in enumerate(reader, start=2):
            # DictReader peut laisser des clés absentes
            row_norm = {k.strip(): (v if v is not None else "") for k, v in row.items() if k}

            category = _cell(row_norm, "category")
            city = _cell(row_norm, "city")
            query = _cell(row_norm, "query")
            if not category and not city and not query:
                continue

            status_raw = _cell(row_norm, "status")
            status = cast(
                ProspectStatus,
                _validate_choice(status_raw, "status", _ALLOWED_PROSPECT_STATUS),
            )
            enrichment_raw = _cell(row_norm, "enrichment_status")
            enrichment_status = _validate_choice(
                enrichment_raw, "enrichment_status", _ALLOWED_ENRICHMENT_STATUS
            )

            contact_raw = _cell(row_norm, "contact_found")
            contact_found = _parse_contact_found(contact_raw)

            try:
                items.append(
                    EnrichedProspectItem(
                        category=category,
                        city=city,
                        query=query,
                        status=status,
                        notes=_cell(row_norm, "notes"),
                        message=_cell(row_norm, "message"),
                        website=_cell(row_norm, "website"),
                        email=_cell(row_norm, "email"),
                        linkedin=_cell(row_norm, "linkedin"),
                        search_url=_cell(row_norm, "search_url"),
                        source=_cell(row_norm, "source"),
                        contact_found=contact_found,
                        enrichment_status=enrichment_status,
                    )
                )
            except TypeError as exc:
                raise ValueError(f"CSV invalide (ligne {line_no}) : {exc}") from exc

    return items
