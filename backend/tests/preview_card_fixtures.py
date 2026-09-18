"""Fixtures locales (SQLite dédiée) — cartes preview + carte client.

Aucune connexion à la base de production. Les slugs sont strictement de test.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy.orm import Session

from app.models import Card, User


CLIENT_SLUG = "client-normal-fixture"
PREVIEW_ARTISAN_SLUG = "preview-artisan-fixture"
PREVIEW_LONG_TITLE_SLUG = "preview-long-title-fixture"
PREVIEW_THERAPIST_SLUG = "preview-therapist-fixture"
PREVIEW_DEMO_SLUG = "demo-preview-safety-slug"
PREVIEW_EXPIRED_SLUG = "preview-expired-fixture"
CLASSIC_EXPIRED_SLUG = "client-expired-fixture"
CLASSIC_DEMO_SLUG = "demo-classic-fixture"


def seed_preview_safety_cards(session: Session) -> Dict[str, int]:
    """Crée un jeu de cartes de recette. Retourne {slug: id}."""
    user = User(email="preview-safety@example.invalid", password_hash="x")
    session.add(user)
    session.commit()
    session.refresh(user)

    now = datetime.utcnow()
    specs = [
        dict(
            slug=CLIENT_SLUG,
            company_name="Atelier Dupont",
            display_name="Marie Dupont",
            job_title="Artisane peintre",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            is_preview=False,
            preview_origin=None,
            phone="0611223344",
            whatsapp="33611223344",
            google_review_link="https://maps.google.com/?q=atelier-dupont",
            enable_recommendation=True,
        ),
        dict(
            slug=PREVIEW_ARTISAN_SLUG,
            company_name="Atelier Martin",
            display_name="Paul Martin",
            job_title="Artisan menuisier",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            is_preview=True,
            preview_origin="local_finder",
            phone="0622334455",
            whatsapp="33622334455",
            google_review_link="https://maps.google.com/?q=atelier-martin",
            enable_recommendation=True,
        ),
        dict(
            slug=PREVIEW_LONG_TITLE_SLUG,
            company_name="PROJINOV Menuiseries Auxerre",
            display_name="PROJINOV Menuiseries Auxerre",
            job_title="Menuisier",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            is_preview=True,
            preview_origin="local_finder",
            phone="0622334455",
            whatsapp="33622334455",
            google_review_link="https://maps.google.com/?q=projinov-auxerre",
            enable_recommendation=True,
        ),
        dict(
            slug=PREVIEW_THERAPIST_SLUG,
            company_name="Studio Harmonie",
            display_name="Claire Bernard",
            job_title="Thérapeute",
            city="Auxerre",
            profile="bien_etre",
            visual_theme="wellness-soft",
            is_preview=True,
            preview_origin="local_finder",
            phone="0633445566",
            whatsapp="33633445566",
            google_review_link="https://maps.google.com/?q=studio-harmonie",
            enable_recommendation=True,
        ),
        dict(
            slug=PREVIEW_DEMO_SLUG,
            company_name="Preview Slug Indep",
            display_name="Slug Indep",
            job_title="Artisan",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            is_preview=True,
            preview_origin="local_finder",
            phone="0644556677",
        ),
        dict(
            slug=PREVIEW_EXPIRED_SLUG,
            company_name="Proposition expirée",
            display_name="Expirée",
            job_title="Artisan",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            is_preview=True,
            preview_origin="local_finder",
            preview_expires_at=now - timedelta(hours=1),
            phone="0655667788",
        ),
        dict(
            slug=CLASSIC_EXPIRED_SLUG,
            company_name="Client expiré",
            display_name="Client Expiré",
            job_title="Artisan",
            city="Auxerre",
            profile="artisan",
            visual_theme="artisan",
            plan_type="trial",
            expires_at=now - timedelta(days=1),
            is_preview=False,
            phone="0666778899",
        ),
        dict(
            slug=CLASSIC_DEMO_SLUG,
            company_name="Démo marketing",
            display_name="Démo Marketing",
            job_title="Artisan",
            city="Auxerre",
            profile="artisan",
            visual_theme="wellness-soft",
            is_preview=False,
            phone="0677889900",
        ),
    ]

    ids: Dict[str, int] = {}
    for spec in specs:
        card = Card(
            user_id=user.id,
            company_name=spec["company_name"],
            display_name=spec.get("display_name"),
            job_title=spec.get("job_title"),
            city=spec.get("city"),
            slug=spec["slug"],
            plan_type=spec.get("plan_type", "demo"),
            region="fr",
            profile=spec.get("profile", "artisan"),
            visual_theme=spec.get("visual_theme", "wellness-soft"),
            theme="apple",
            card_theme="classic",
            is_preview=bool(spec.get("is_preview", False)),
            preview_origin=spec.get("preview_origin"),
            preview_expires_at=spec.get("preview_expires_at"),
            expires_at=spec.get("expires_at"),
            phone=spec.get("phone"),
            whatsapp=spec.get("whatsapp"),
            google_review_link=spec.get("google_review_link"),
            enable_recommendation=bool(spec.get("enable_recommendation", False)),
        )
        session.add(card)
        session.flush()
        ids[card.slug] = card.id
    session.commit()
    return ids
