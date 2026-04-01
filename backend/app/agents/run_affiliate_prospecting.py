"""Lanceur local minimal pour générer et exporter des prospects affiliés."""

from __future__ import annotations

from .prospect_exporter import export_prospects_to_csv
from .prospect_finder import TARGET_CATEGORIES, build_prospect_items


def main() -> None:
    # Villes de départ (modifiable facilement).
    target_cities = ["Auxerre", "Sens", "Joigny"]
    output_path = "./exports/prospects_affilies.csv"

    items = build_prospect_items(target_cities)
    exported_file = export_prospects_to_csv(items, output_path)

    print()
    print("--- Résumé — prospection affiliés (local) ---")
    print(f"Villes cibles : {', '.join(target_cities)}")
    print(f"Nombre de catégories ciblées : {len(TARGET_CATEGORIES)}")
    print(f"Total d'entrées générées : {len(items)}")
    print(f"Fichier CSV exporté : {exported_file}")
    if items:
        print("Exemples (3 max.) :")
        for i, row in enumerate(items[:3], start=1):
            print(f"  {i}. {row}")
    print("--- Fin du résumé ---")
    print()


if __name__ == "__main__":
    main()

