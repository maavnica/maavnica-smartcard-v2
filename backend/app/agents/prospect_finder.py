"""Base simple pour préparer des recherches de prospects affiliés."""

from __future__ import annotations

from .prospect_models import ProspectItem


# Catégories initiales ciblées pour le recrutement d'affiliés.
TARGET_CATEGORIES: list[str] = [
    "community manager",
    "graphiste freelance",
    "créateur de site web",
    "consultant marketing",
    "agence communication",
    "photographe professionnel",
]


def _clean_cities(cities: list[str]) -> list[str]:
    """Nettoyage minimal pour éviter les entrées vides."""
    return [city.strip() for city in cities if city and city.strip()]


def build_prospect_queries(cities: list[str]) -> list[str]:
    """
    Construit des requêtes prospects à partir de villes fournies.

    Exemple de sortie:
    - "community manager Auxerre"
    - "graphiste freelance Sens"
    """
    queries: list[str] = []

    clean_cities = _clean_cities(cities)

    for city in clean_cities:
        for category in TARGET_CATEGORIES:
            queries.append(f"{category} {city}")

    return queries


def build_prospect_items(cities: list[str]) -> list[ProspectItem]:
    """
    Construit des objets prospects structurés à partir d'une liste de villes.

    Chaque item est initialisé en statut "new" avec notes vides.
    """
    items: list[ProspectItem] = []
    clean_cities = _clean_cities(cities)

    for city in clean_cities:
        for category in TARGET_CATEGORIES:
            query = f"{category} {city}"
            items.append(
                ProspectItem(
                    category=category,
                    city=city,
                    query=query,
                    status="new",
                    notes="",
                )
            )

    return items

