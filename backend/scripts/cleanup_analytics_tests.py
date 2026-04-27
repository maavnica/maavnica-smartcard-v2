"""
Nettoyage ciblé des analytics de test SmartCard.

Par défaut, ce script est en DRY_RUN=True:
- affiche les diagnostics demandés
- affiche ce qui serait supprimé
- ne supprime rien tant que DRY_RUN reste activé
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from sqlalchemy import and_, func, inspect


# DRY_RUN par défaut (sécurité)
DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() not in {"0", "false", "no"}

# Contrainte métier fournie par l'utilisateur
PROTECTED_RECOMMENDATION_SLUG = "arnaud-huard"

# Slugs de nettoyage par défaut (modifiable via CLEANUP_TEST_SLUGS="a,b,c")
DEFAULT_TEST_SLUGS = {"demo", "demo2", "demo3"}
CLEANUP_TEST_SLUGS_ENV = os.getenv("CLEANUP_TEST_SLUGS", "")

# Supprime aussi tous les slugs commençant par "demo" (ex: demo-artisan)
MATCH_DEMO_PREFIX = True

# Événements de card_events ciblés dans les tests d'ouverture
CARD_EVENT_TYPES_TO_DELETE = {"visit_from_recommendation"}


def _bootstrap_path() -> None:
    # backend/scripts -> backend (pour "import app.*")
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


_bootstrap_path()

from app.database import SessionLocal  # noqa: E402
from app.models import CardEvent, CardVisit, RecommendationEvent  # noqa: E402


def parse_target_slugs() -> List[str]:
    extra = {
        s.strip()
        for s in CLEANUP_TEST_SLUGS_ENV.split(",")
        if s.strip()
    }
    all_slugs = set(DEFAULT_TEST_SLUGS) | extra
    return sorted(all_slugs)


def slug_is_targeted(slug: str, explicit_targets: Iterable[str]) -> bool:
    if slug in explicit_targets:
        return True
    return MATCH_DEMO_PREFIX and slug.startswith("demo")


def print_section(title: str) -> None:
    print("\n" + "=" * 90)
    print(title)
    print("=" * 90)


def print_table(rows: List[Tuple], headers: Tuple[str, ...]) -> None:
    if not rows:
        print("(aucune ligne)")
        return
    widths = [len(h) for h in headers]
    for r in rows:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], len(str(v)))
    fmt = " | ".join("{:<" + str(w) + "}" for w in widths)
    sep = "-+-".join("-" * w for w in widths)
    print(fmt.format(*headers))
    print(sep)
    for r in rows:
        print(fmt.format(*[str(v) for v in r]))


def table_exists(db, table_name: str) -> bool:
    try:
        insp = inspect(db.bind)
        return insp.has_table(table_name)
    except Exception:
        return False


def diagnostics_before(db) -> None:
    print_section("DIAGNOSTIC AVANT NETTOYAGE")

    print("\n1) Nombre de visites par slug (card_visits)")
    if not table_exists(db, "card_visits"):
        print("(table absente)")
    else:
        visits_by_slug = (
            db.query(CardVisit.slug, func.count(CardVisit.id))
            .group_by(CardVisit.slug)
            .order_by(func.count(CardVisit.id).desc(), CardVisit.slug.asc())
            .all()
        )
        print_table([(s, c) for s, c in visits_by_slug], ("slug", "visits_count"))

    print("\n2) Nombre d'evenements analytics par slug/event_type (card_events)")
    if not table_exists(db, "card_events"):
        print("(table absente)")
    else:
        events_by_slug_type = (
            db.query(CardEvent.slug, CardEvent.event_type, func.count(CardEvent.id))
            .group_by(CardEvent.slug, CardEvent.event_type)
            .order_by(CardEvent.slug.asc(), func.count(CardEvent.id).desc(), CardEvent.event_type.asc())
            .all()
        )
        print_table(
            [(s, et, c) for s, et, c in events_by_slug_type],
            ("slug", "event_type", "events_count"),
        )

    print("\n3) Nombre d'evenements recommendation par slug/event_type (recommendation_events)")
    if not table_exists(db, "recommendation_events"):
        print("(table absente)")
        arnaud_events = []
    else:
        rec_by_slug_type = (
            db.query(
                RecommendationEvent.card_slug,
                RecommendationEvent.event_type,
                func.count(RecommendationEvent.id),
            )
            .group_by(RecommendationEvent.card_slug, RecommendationEvent.event_type)
            .order_by(
                RecommendationEvent.card_slug.asc(),
                func.count(RecommendationEvent.id).desc(),
                RecommendationEvent.event_type.asc(),
            )
            .all()
        )
        print_table(
            [(s, et, c) for s, et, c in rec_by_slug_type],
            ("card_slug", "event_type", "events_count"),
        )

        arnaud_events = (
            db.query(
                RecommendationEvent.card_slug,
                RecommendationEvent.event_type,
                RecommendationEvent.referrer_id,
                RecommendationEvent.visitor_id,
                RecommendationEvent.created_at,
            )
            .filter(RecommendationEvent.card_slug == PROTECTED_RECOMMENDATION_SLUG)
            .order_by(RecommendationEvent.created_at.desc(), RecommendationEvent.id.desc())
            .all()
        )
    print(f"\n4) Evenements lies a {PROTECTED_RECOMMENDATION_SLUG!r}")
    print_table(
        [(s, et, r, v, dt) for s, et, r, v, dt in arnaud_events],
        ("card_slug", "event_type", "referrer_id", "visitor_id", "created_at"),
    )


def collect_deletion_plan(db, explicit_targets: List[str]) -> Dict[str, Dict[str, int]]:
    plan: Dict[str, Dict[str, int]] = {
        "card_visits": defaultdict(int),
        "card_events": defaultdict(int),
        "recommendation_events": defaultdict(int),
    }

    # 1) card_visits: toutes les visites des slugs de demo/tests ciblés
    if table_exists(db, "card_visits"):
        for slug, cnt in (
            db.query(CardVisit.slug, func.count(CardVisit.id))
            .group_by(CardVisit.slug)
            .all()
        ):
            if slug and slug_is_targeted(slug, explicit_targets):
                plan["card_visits"][slug] = cnt

    # 2) card_events: uniquement visit_from_recommendation sur slugs de demo/tests
    if table_exists(db, "card_events"):
        for slug, event_type, cnt in (
            db.query(CardEvent.slug, CardEvent.event_type, func.count(CardEvent.id))
            .group_by(CardEvent.slug, CardEvent.event_type)
            .all()
        ):
            if not slug:
                continue
            if not slug_is_targeted(slug, explicit_targets):
                continue
            if event_type in CARD_EVENT_TYPES_TO_DELETE:
                plan["card_events"][f"{slug}::{event_type}"] = cnt

    # 3) recommendation_events:
    #    - on supprime seulement recommend_visit sur slugs de demo/tests
    #    - on conserve TOUS les evenements pour arnaud-huard
    if table_exists(db, "recommendation_events"):
        for card_slug, event_type, cnt in (
            db.query(
                RecommendationEvent.card_slug,
                RecommendationEvent.event_type,
                func.count(RecommendationEvent.id),
            )
            .group_by(RecommendationEvent.card_slug, RecommendationEvent.event_type)
            .all()
        ):
            if not card_slug:
                continue
            if card_slug == PROTECTED_RECOMMENDATION_SLUG:
                continue
            if not slug_is_targeted(card_slug, explicit_targets):
                continue
            if event_type == "recommend_visit":
                plan["recommendation_events"][f"{card_slug}::{event_type}"] = cnt

    return plan


def print_deletion_plan(plan: Dict[str, Dict[str, int]], explicit_targets: List[str]) -> None:
    print_section("PLAN DE NETTOYAGE PROPOSE (AUCUNE SUPPRESSION SI DRY_RUN=True)")
    print(f"Slugs explicitement cibles: {explicit_targets}")
    print(f"Regle prefix demo active: {MATCH_DEMO_PREFIX}")
    print(f"Slug recommendation protege: {PROTECTED_RECOMMENDATION_SLUG}")

    print("\nA) card_visits a supprimer")
    rows_a = sorted(plan["card_visits"].items(), key=lambda x: (-x[1], x[0]))
    print_table(rows_a, ("slug", "rows_to_delete"))

    print("\nB) card_events a supprimer (event_type cible)")
    rows_b = sorted(plan["card_events"].items(), key=lambda x: (-x[1], x[0]))
    print_table(rows_b, ("slug::event_type", "rows_to_delete"))

    print("\nC) recommendation_events a supprimer (strictement recommend_visit hors arnaud-huard)")
    rows_c = sorted(plan["recommendation_events"].items(), key=lambda x: (-x[1], x[0]))
    print_table(rows_c, ("card_slug::event_type", "rows_to_delete"))

    total = (
        sum(plan["card_visits"].values())
        + sum(plan["card_events"].values())
        + sum(plan["recommendation_events"].values())
    )
    print(f"\nTOTAL LIGNES CIBLEES: {total}")


def apply_cleanup(db, plan: Dict[str, Dict[str, int]], explicit_targets: List[str]) -> None:
    if DRY_RUN:
        print("\nDRY_RUN=True -> aucune suppression executee.")
        return

    print("\nDRY_RUN=False -> suppression en cours...")

    # card_visits
    if table_exists(db, "card_visits"):
        for slug in plan["card_visits"].keys():
            db.query(CardVisit).filter(CardVisit.slug == slug).delete(synchronize_session=False)

    # card_events (visit_from_recommendation uniquement)
    if table_exists(db, "card_events"):
        for key in plan["card_events"].keys():
            slug, event_type = key.split("::", 1)
            db.query(CardEvent).filter(
                and_(CardEvent.slug == slug, CardEvent.event_type == event_type)
            ).delete(synchronize_session=False)

    # recommendation_events (recommend_visit uniquement, jamais arnaud-huard)
    if table_exists(db, "recommendation_events"):
        for key in plan["recommendation_events"].keys():
            card_slug, event_type = key.split("::", 1)
            db.query(RecommendationEvent).filter(
                and_(
                    RecommendationEvent.card_slug == card_slug,
                    RecommendationEvent.event_type == event_type,
                    RecommendationEvent.card_slug != PROTECTED_RECOMMENDATION_SLUG,
                )
            ).delete(synchronize_session=False)

    db.commit()
    print("Suppression terminee et committee.")


def diagnostics_after(db) -> None:
    print_section("DIAGNOSTIC APRES EXECUTION")
    print(f"Mode d'execution: {'DRY_RUN' if DRY_RUN else 'REAL_DELETE'}")

    visits_count = (
        (db.query(func.count(CardVisit.id)).scalar() or 0)
        if table_exists(db, "card_visits")
        else 0
    )
    card_events_count = (
        (db.query(func.count(CardEvent.id)).scalar() or 0)
        if table_exists(db, "card_events")
        else 0
    )
    rec_events_count = (
        (db.query(func.count(RecommendationEvent.id)).scalar() or 0)
        if table_exists(db, "recommendation_events")
        else 0
    )

    print(f"card_visits total: {visits_count}")
    print(f"card_events total: {card_events_count}")
    print(f"recommendation_events total: {rec_events_count}")

    if table_exists(db, "recommendation_events"):
        arnaud_count = (
            db.query(func.count(RecommendationEvent.id))
            .filter(RecommendationEvent.card_slug == PROTECTED_RECOMMENDATION_SLUG)
            .scalar()
            or 0
        )
    else:
        arnaud_count = 0
    print(
        f"recommendation_events pour {PROTECTED_RECOMMENDATION_SLUG}: {arnaud_count}"
    )


def main() -> None:
    explicit_targets = parse_target_slugs()
    print_section("SMARTCARD ANALYTICS CLEANUP")
    print(f"DRY_RUN={DRY_RUN}")

    db = SessionLocal()
    try:
        diagnostics_before(db)
        plan = collect_deletion_plan(db, explicit_targets)
        print_deletion_plan(plan, explicit_targets)
        apply_cleanup(db, plan, explicit_targets)
        diagnostics_after(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
