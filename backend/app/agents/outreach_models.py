"""Structures et transformation simples pour l'outreach affilié."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .affiliate_agent import generate_affiliate_message
from .prospect_models import ProspectItem, ProspectStatus


@dataclass(slots=True)
class OutreachItem:
    """Prospect enrichi avec un message prêt à envoyer."""

    category: str
    city: str
    query: str
    status: ProspectStatus = "new"
    notes: str = ""
    message: str = ""


def build_outreach_items_from_prospects(
    items: list[ProspectItem],
    message_builder: Callable[[str | None, str | None], str] | None = None,
) -> list[OutreachItem]:
    """
    Transforme des ProspectItem en OutreachItem avec message généré.

    Par défaut, le message est produit via `generate_affiliate_message` (OpenAI),
    avec l'activité « catégorie + ville » pour contextualiser le texte.

    Si `message_builder` est fourni, il remplace l'appel OpenAI (ex. tests locaux).
    """
    outreach_items: list[OutreachItem] = []

    def _default_message(name: str | None, activity: str | None) -> str:
        return generate_affiliate_message(name=name, activity=activity)

    builder = message_builder or _default_message

    for item in items:
        activity = f"{item.category} à {item.city}"
        message = builder(None, activity)
        outreach_items.append(
            OutreachItem(
                category=item.category,
                city=item.city,
                query=item.query,
                status=item.status,
                notes=item.notes,
                message=message,
            )
        )

    return outreach_items

