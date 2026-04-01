"""Lanceur local minimal pour générer un CSV outreach affiliés."""

from __future__ import annotations

from .outreach_exporter import export_outreach_to_csv
from .outreach_models import build_outreach_items_from_prospects
from .prospect_finder import TARGET_CATEGORIES, build_prospect_items

# Mettre à False pour utiliser OpenAI via generate_affiliate_message (clé OPENAI_API_KEY requise).
USE_MOCK_MESSAGES = True


def _mock_affiliate_message(name: str | None = None, activity: str | None = None) -> str:
    """Message factice pour tests locaux sans consommation API."""
    label = activity or "activité non précisée"
    return f"Message test pour {label} — [MOCK] pas d'appel OpenAI."


def main() -> None:
    # Villes de départ (modifiable facilement).
    target_cities = ["Auxerre", "Sens", "Joigny"]
    output_path = "./exports/outreach_affilies.csv"

    prospects = build_prospect_items(target_cities)
    if USE_MOCK_MESSAGES:
        outreach_items = build_outreach_items_from_prospects(
            prospects,
            message_builder=_mock_affiliate_message,
        )
    else:
        outreach_items = build_outreach_items_from_prospects(prospects)
    exported_file = export_outreach_to_csv(outreach_items, output_path)

    print()
    print("--- Résumé — outreach affiliés (local) ---")
    mode = "messages mock (sans OpenAI)" if USE_MOCK_MESSAGES else "messages via OpenAI"
    print(f"Mode : {mode}")
    print(f"Villes cibles : {', '.join(target_cities)}")
    print(f"Nombre de catégories ciblées : {len(TARGET_CATEGORIES)}")
    print(f"Total de prospects générés : {len(prospects)}")
    print(f"Total de messages générés : {len(outreach_items)}")
    print(f"Fichier CSV exporté : {exported_file}")
    if outreach_items:
        print("Exemples (3 max.) :")
        for i, row in enumerate(outreach_items[:3], start=1):
            print(f"  {i}. {row}")
    print("--- Fin du résumé ---")
    print()


if __name__ == "__main__":
    main()

