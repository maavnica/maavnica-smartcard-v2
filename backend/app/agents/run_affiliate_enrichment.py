"""Lanceur local minimal pour générer un CSV prospects enrichis (chaîne complète)."""

from __future__ import annotations

from .enrichment_exporter import export_enriched_items_to_csv
from .enrichment_models import build_enriched_items_from_outreach
from .outreach_models import build_outreach_items_from_prospects
from .prospect_finder import TARGET_CATEGORIES, build_prospect_items

# Mettre à False pour utiliser OpenAI via generate_affiliate_message (clé OPENAI_API_KEY requise).
USE_MOCK_MESSAGES = True


def _mock_affiliate_message(name: str | None = None, activity: str | None = None) -> str:
    """Message factice pour tests locaux sans consommation API."""
    label = activity or "activité non précisée"
    return f"Message test pour {label} — [MOCK] pas d'appel OpenAI."


def main() -> None:
    target_cities = ["Auxerre", "Sens", "Joigny"]
    output_path = "./exports/enriched_affilies.csv"

    prospects = build_prospect_items(target_cities)
    if USE_MOCK_MESSAGES:
        outreach_items = build_outreach_items_from_prospects(
            prospects,
            message_builder=_mock_affiliate_message,
        )
    else:
        outreach_items = build_outreach_items_from_prospects(prospects)
    enriched_items = build_enriched_items_from_outreach(outreach_items)
    exported_file = export_enriched_items_to_csv(enriched_items, output_path)

    print()
    print("--- Résumé — enrichissement affiliés (local) ---")
    mode = "messages mock (sans OpenAI)" if USE_MOCK_MESSAGES else "messages via OpenAI"
    print(f"Mode : {mode}")
    print(f"Villes cibles : {', '.join(target_cities)}")
    print(f"Nombre de catégories ciblées : {len(TARGET_CATEGORIES)}")
    print(f"Total de prospects générés : {len(prospects)}")
    print(f"Total de messages générés : {len(outreach_items)}")
    print(f"Total d'entrées enrichies : {len(enriched_items)}")
    pending = sum(1 for row in enriched_items if row.enrichment_status == "pending")
    print(f"Entrées avec enrichissement « pending » (initial) : {pending}")
    ready = sum(1 for row in enriched_items if row.ready_to_contact)
    print(f"Prêts à être contactés (ready_to_contact) : {ready}")
    high_pri = sum(1 for row in enriched_items if row.priority == "high")
    print(f"Priorité « high » : {high_pri}")
    print(f"Fichier CSV exporté : {exported_file}")
    if enriched_items and enriched_items[0].search_url:
        print(f"Exemple d'URL de recherche : {enriched_items[0].search_url}")
    if enriched_items:
        print("Exemples (3 max.) :")
        for i, row in enumerate(enriched_items[:3], start=1):
            print(f"  {i}. {row}")
    print("--- Fin du résumé ---")
    print()


if __name__ == "__main__":
    main()
