"""Fondation du module agent IA affiliés (non branché aux routes FastAPI)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


def _clean(value: str | None) -> str:
    """Nettoie une valeur texte optionnelle."""
    return (value or "").strip()


def _normalize_message_for_csv(text: str) -> str:
    """
    Force un texte sur une seule ligne, sans Markdown ni placeholders,
    adapté à un export CSV (pas de retours ligne dans la cellule).
    """
    s = _clean(text)
    # Liens Markdown [libellé](url) -> URL seule, en clair
    s = re.sub(r"\[([^\]]*)\]\((https?://[^)\s]+)\)", r"\2", s)
    # Astérisques / soulignement Markdown résiduels
    s = re.sub(r"\*+", "", s)
    s = re.sub(r"_+", " ", s)
    # Placeholders fictifs courants entre crochets
    s = re.sub(
        r"\[(?:nom|votre\s+nom|vos\s+coordonnées|prénom|votre\s+prénom|signature)[^\]]*\]",
        "",
        s,
        flags=re.IGNORECASE,
    )
    # Tout saut de ligne ou espaces multiples -> un seul espace
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _build_user_context(name: str | None, activity: str | None) -> str:
    """Construit un contexte utilisateur simple pour le prompt."""
    cleaned_name = _clean(name)
    cleaned_activity = _clean(activity)

    if cleaned_name and cleaned_activity:
        return f"Prospect: {cleaned_name} | Activité: {cleaned_activity}"
    if cleaned_name:
        return f"Prospect: {cleaned_name}"
    if cleaned_activity:
        return f"Activité: {cleaned_activity}"
    return "Prospect: non précisé | Activité: non précisée"


def generate_affiliate_message(name: str | None = None, activity: str | None = None) -> str:
    """
    Génère un message de prospection affilié via OpenAI.

    - Entrées optionnelles : `name`, `activity`
    - Source de clé API : variable d'environnement `OPENAI_API_KEY`
    - Sortie : une seule ligne, sans Markdown, prête pour email/DM/CSV
    """
    api_key = _clean(os.getenv("OPENAI_API_KEY"))
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY est manquante.")

    context_line = _build_user_context(name=name, activity=activity)

    system_prompt = (
        "Tu écris des messages courts pour partenariat B2B en français. "
        "Sortie strictement en texte brut : une seule phrase continue ou un seul bloc, sans mise en forme."
    )
    user_prompt = (
        "Rédige UN SEUL paragraphe de prospection en français (60 à 100 mots), ton naturel et professionnel.\n"
        "Contraintes obligatoires:\n"
        "- Une seule ligne de texte : aucun retour à la ligne, aucune liste à puces, aucun titre.\n"
        "- Aucun Markdown : pas de **, pas de liens [texte](url).\n"
        "- Aucun placeholder entre crochets (pas de [Nom], [Votre nom], etc.).\n"
        "- Aucune formule de signature en fin de message (pas de Cordialement, pas de nom fictif).\n"
        "- Les deux URLs suivantes doivent apparaître en entier, telles quelles, dans le texte :\n"
        "  https://smartcard.maavnica.com/c/demo\n"
        "  https://smartcard.maavnica.com/c/demo2\n"
        "- Mentionner SmartCard Maavnica.\n"
        "- Mentionner : avis Google, demandes clients, partage des coordonnées.\n"
        "- Mentionner la rémunération affilié : 20€ Solo / 35€ Business.\n"
        "- Ton partenariat, pas agressif ; finir par une seule question courte.\n"
        "- Contexte prospect :\n"
        f"{context_line}"
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.6,
    }

    request = urllib.request.Request(
        url="https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Erreur OpenAI HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Erreur réseau OpenAI: {exc.reason}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Réponse OpenAI invalide: contenu introuvable.") from exc

    return _normalize_message_for_csv(content)

