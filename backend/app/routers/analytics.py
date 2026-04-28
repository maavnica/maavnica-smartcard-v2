# backend/app/routers/analytics.py

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, CardEvent, CardVisit, RecommendationEvent
from app.schemas import AnalyticsEventIn, AnalyticsVisitIn, RecommendationEventIn
from app.utils.recommender_display import (
    build_recommender_display_name,
    effective_recommender_label,
    normalize_recommender_part,
)
from app.utils.admin_auth import require_admin_http_basic
from app.utils.rate_limit import rate_limit_by_ip

router_api = APIRouter(prefix="/api/analytics", tags=["analytics"])
router_pages = APIRouter(tags=["analytics"])

_EVENT_COLUMNS = (
    "phone_click",
    "whatsapp_click",
    "google_review_click",
    "rdv_request",
    "recommend_click",
    "share_native_success",
    "share_copy_fallback",
)


def _utc_day_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _normalize_src_for_storage(v: str | None) -> str | None:
    if v is None:
        return None
    s = v.strip()
    return s if s else None


@router_api.post("/visit", status_code=204)
def record_visit(
    payload: AnalyticsVisitIn,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(180, 60)),
):
    src = _normalize_src_for_storage(payload.src)
    ref = _normalize_src_for_storage(payload.ref)
    rec = _normalize_src_for_storage(payload.rec)
    row = CardVisit(
        slug=payload.slug,
        source=src,
        ref=ref,
        rec=rec,
    )
    db.add(row)
    db.commit()
    return Response(status_code=204)


@router_api.post("/event", status_code=204)
def record_event(
    payload: AnalyticsEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(180, 60)),
):
    src = _normalize_src_for_storage(payload.src)
    ref = _normalize_src_for_storage(payload.ref)
    rec = _normalize_src_for_storage(payload.rec)
    row = CardEvent(
        slug=payload.slug,
        event_type=payload.event_type,
        source=src,
        ref=ref,
        rec=rec,
    )
    db.add(row)
    db.commit()
    return Response(status_code=204)


def _optional_recommender_part(value: Optional[str]) -> Optional[str]:
    t = normalize_recommender_part(value)
    return t if t else None


@router_api.post("/recommendation-event", status_code=204)
def record_recommendation_event(
    payload: RecommendationEventIn,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(180, 60)),
):
    fn = _optional_recommender_part(payload.recommender_first_name)
    ln = _optional_recommender_part(payload.recommender_last_name)
    display = build_recommender_display_name(payload.recommender_first_name, payload.recommender_last_name)
    row = RecommendationEvent(
        card_slug=payload.card_slug,
        referrer_id=payload.referrer_id,
        visitor_id=payload.visitor_id,
        event_type=payload.event_type,
        recommender_first_name=fn,
        recommender_last_name=ln,
        recommender_display_name=display,
    )
    db.add(row)
    db.commit()
    return Response(status_code=204)


def _visit_counts_since(
    db: Session, since: datetime
) -> Dict[str, int]:
    rows = (
        db.query(CardVisit.slug, func.count(CardVisit.id))
        .filter(CardVisit.created_at >= since)
        .group_by(CardVisit.slug)
        .all()
    )
    return {r[0]: int(r[1]) for r in rows}


def _event_counts_since(
    db: Session, since: datetime, event_types: Tuple[str, ...]
) -> Dict[Tuple[str, str], int]:
    rows = (
        db.query(CardEvent.slug, CardEvent.event_type, func.count(CardEvent.id))
        .filter(
            CardEvent.created_at >= since,
            CardEvent.event_type.in_(event_types),
        )
        .group_by(CardEvent.slug, CardEvent.event_type)
        .all()
    )
    return {(r[0], r[1]): int(r[2]) for r in rows}


def _total_events_since(db: Session, since: datetime) -> int:
    n = db.query(func.count(CardEvent.id)).filter(CardEvent.created_at >= since).scalar()
    return int(n or 0)


def _recommendation_contacts_since(db: Session, since: datetime) -> Dict[str, int]:
    rows = (
        db.query(RecommendationEvent.card_slug, func.count(RecommendationEvent.id))
        .filter(
            RecommendationEvent.created_at >= since,
            RecommendationEvent.event_type == "recommend_contact",
        )
        .group_by(RecommendationEvent.card_slug)
        .all()
    )
    return {str(r[0]): int(r[1]) for r in rows}


def _build_card_metrics(
    slugs: List[str],
    visit_counts: Dict[str, int],
    event_counts: Dict[Tuple[str, str], int],
    recommendation_counts: Dict[str, int],
) -> Dict[str, Dict[str, int]]:
    metrics: Dict[str, Dict[str, int]] = {}
    for slug in slugs:
        phone = event_counts.get((slug, "phone_click"), 0)
        whatsapp = event_counts.get((slug, "whatsapp_click"), 0)
        google = event_counts.get((slug, "google_review_click"), 0)
        demande = event_counts.get((slug, "rdv_request"), 0)
        reco = recommendation_counts.get(slug, 0)
        partage = event_counts.get((slug, "share_native_success"), 0) + event_counts.get(
            (slug, "share_copy_fallback"), 0
        )
        contact = phone + whatsapp + demande
        visibilite = google + partage
        actions = phone + whatsapp + google + demande + reco + partage
        status = "inactif"
        if contact > 0:
            status = "performante"
        elif actions > 0:
            status = "actif"
        metrics[slug] = {
            "visites": visit_counts.get(slug, 0),
            "actions": actions,
            "contact": contact,
            "visibilite": visibilite,
            "status": status,
            "phone": phone,
            "whatsapp": whatsapp,
            "google": google,
            "demande": demande,
            "reco": reco,
            "partage": partage,
        }
    return metrics


def _traffic_sources_30d(db: Session, d30: datetime) -> List[Tuple[str, int]]:
    src_expr = func.coalesce(
        func.nullif(func.trim(func.coalesce(CardVisit.source, "")), ""),
        "direct",
    )
    rows = (
        db.query(src_expr, func.count(CardVisit.id))
        .filter(CardVisit.created_at >= d30)
        .group_by(src_expr)
        .all()
    )
    out = [(str(r[0]), int(r[1])) for r in rows]
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def _affiliates_30d(db: Session, d30: datetime) -> List[Tuple[str, int, int]]:
    """
    Performance par affilié (paramètre ref) sur 30 jours.
    visites = lignes card_visits avec ref renseigné
    actions = lignes card_events avec ref renseigné
    """
    v_rows = (
        db.query(CardVisit.ref, func.count(CardVisit.id))
        .filter(
            CardVisit.created_at >= d30,
            CardVisit.ref.isnot(None),
            CardVisit.ref != "",
        )
        .group_by(CardVisit.ref)
        .all()
    )
    e_rows = (
        db.query(CardEvent.ref, func.count(CardEvent.id))
        .filter(
            CardEvent.created_at >= d30,
            CardEvent.ref.isnot(None),
            CardEvent.ref != "",
        )
        .group_by(CardEvent.ref)
        .all()
    )
    visits_by_ref: Dict[str, int] = {str(r[0]): int(r[1]) for r in v_rows}
    actions_by_ref: Dict[str, int] = {str(r[0]): int(r[1]) for r in e_rows}
    all_refs = set(visits_by_ref) | set(actions_by_ref)
    out: List[Tuple[str, int, int]] = []
    for ref in all_refs:
        out.append(
            (
                ref,
                visits_by_ref.get(ref, 0),
                actions_by_ref.get(ref, 0),
            )
        )
    out.sort(key=lambda row: (-row[1], row[0]))
    return out


def _recommender_display_labels_30d(db: Session, d30: datetime) -> Dict[str, str]:
    rows = (
        db.query(
            RecommendationEvent.referrer_id,
            func.max(RecommendationEvent.recommender_display_name),
        )
        .filter(
            RecommendationEvent.created_at >= d30,
            RecommendationEvent.recommender_display_name.isnot(None),
        )
        .group_by(RecommendationEvent.referrer_id)
        .all()
    )
    out: Dict[str, str] = {}
    for rid, dname in rows:
        label = (str(dname).strip() if dname else "") or ""
        if label:
            out[str(rid)] = label
    return out


def _recommendation_referrers_30d(db: Session, d30: datetime) -> List[Tuple[str, str, int, int]]:
    visit_rows = (
        db.query(
            RecommendationEvent.card_slug,
            RecommendationEvent.referrer_id,
            func.count(RecommendationEvent.id),
        )
        .filter(
            RecommendationEvent.created_at >= d30,
            RecommendationEvent.event_type == "recommend_visit",
        )
        .group_by(RecommendationEvent.card_slug, RecommendationEvent.referrer_id)
        .all()
    )
    contact_rows = (
        db.query(
            RecommendationEvent.card_slug,
            RecommendationEvent.referrer_id,
            func.count(RecommendationEvent.id),
        )
        .filter(
            RecommendationEvent.created_at >= d30,
            RecommendationEvent.event_type == "recommend_contact",
        )
        .group_by(RecommendationEvent.card_slug, RecommendationEvent.referrer_id)
        .all()
    )

    visits_by_key: Dict[Tuple[str, str], int] = {
        (str(r[0]), str(r[1])): int(r[2]) for r in visit_rows
    }
    contacts_by_key: Dict[Tuple[str, str], int] = {
        (str(r[0]), str(r[1])): int(r[2]) for r in contact_rows
    }
    all_keys = set(visits_by_key) | set(contacts_by_key)
    out: List[Tuple[str, str, int, int]] = []
    for card_slug, referrer_id in all_keys:
        out.append(
            (
                card_slug,
                referrer_id,
                visits_by_key.get((card_slug, referrer_id), 0),
                contacts_by_key.get((card_slug, referrer_id), 0),
            )
        )
    out.sort(key=lambda row: (-row[2], row[0], row[1]))
    return out


def _top_referrers_30d(db: Session, d30: datetime) -> List[Tuple[str, int, int, int]]:
    rows = (
        db.query(
            RecommendationEvent.referrer_id,
            RecommendationEvent.event_type,
            func.count(RecommendationEvent.id),
        )
        .filter(
            RecommendationEvent.created_at >= d30,
            RecommendationEvent.referrer_id.isnot(None),
            RecommendationEvent.referrer_id != "",
            RecommendationEvent.event_type.in_(
                ("recommend_link_created", "recommend_visit", "recommend_contact")
            ),
        )
        .group_by(RecommendationEvent.referrer_id, RecommendationEvent.event_type)
        .all()
    )
    metrics_by_referrer: Dict[str, Dict[str, int]] = {}
    for referrer_id, event_type, count_val in rows:
        ref = str(referrer_id)
        if ref not in metrics_by_referrer:
            metrics_by_referrer[ref] = {
                "recommend_link_created": 0,
                "recommend_visit": 0,
                "recommend_contact": 0,
            }
        metrics_by_referrer[ref][str(event_type)] = int(count_val)

    out: List[Tuple[str, int, int, int]] = []
    for referrer_id, metrics in metrics_by_referrer.items():
        out.append(
            (
                referrer_id,
                metrics["recommend_link_created"],
                metrics["recommend_visit"],
                metrics["recommend_contact"],
            )
        )

    out.sort(key=lambda row: (-row[3], -row[2], -row[1], row[0]))
    return out


def _build_dashboard_html(db: Session) -> str:
    now = datetime.utcnow()
    today0 = _utc_day_start()
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    visits_today = (
        db.query(func.count(CardVisit.id)).filter(CardVisit.created_at >= today0).scalar() or 0
    )
    visits_7 = db.query(func.count(CardVisit.id)).filter(CardVisit.created_at >= d7).scalar() or 0
    visits_30 = (
        db.query(func.count(CardVisit.id)).filter(CardVisit.created_at >= d30).scalar() or 0
    )
    actions_7 = _total_events_since(db, d7)

    slugs_all = [r[0] for r in db.query(Card.slug).all()]

    vc_today = _visit_counts_since(db, today0)
    vc7 = _visit_counts_since(db, d7)
    vc30 = _visit_counts_since(db, d30)
    ev_today = _event_counts_since(db, today0, _EVENT_COLUMNS)
    ev7 = _event_counts_since(db, d7, _EVENT_COLUMNS)
    ev30 = _event_counts_since(db, d30, _EVENT_COLUMNS)
    reco_today = _recommendation_contacts_since(db, today0)
    reco7 = _recommendation_contacts_since(db, d7)
    reco30 = _recommendation_contacts_since(db, d30)

    traffic = _traffic_sources_30d(db, d30)
    affiliates = _affiliates_30d(db, d30)
    recommendation_referrers = _recommendation_referrers_30d(db, d30)
    top_referrers = _top_referrers_30d(db, d30)
    recommender_labels = _recommender_display_labels_30d(db, d30)

    slugs = sorted(slugs_all, key=lambda s: (-vc_today.get(s, 0), -vc7.get(s, 0), s))
    metrics_today = _build_card_metrics(slugs, vc_today, ev_today, reco_today)
    metrics_7 = _build_card_metrics(slugs, vc7, ev7, reco7)
    metrics_30 = _build_card_metrics(slugs, vc30, ev30, reco30)
    totals_today = {
        "visites": int(visits_today),
        "contact": sum(m["contact"] for m in metrics_today.values()),
        "visibilite": sum(m["visibilite"] for m in metrics_today.values()),
        "phone": sum(m["phone"] for m in metrics_today.values()),
        "whatsapp": sum(m["whatsapp"] for m in metrics_today.values()),
        "google": sum(m["google"] for m in metrics_today.values()),
        "demande": sum(m["demande"] for m in metrics_today.values()),
        "reco": sum(m["reco"] for m in metrics_today.values()),
        "partage": sum(m["partage"] for m in metrics_today.values()),
    }
    totals_today["actions"] = (
        totals_today["phone"]
        + totals_today["whatsapp"]
        + totals_today["google"]
        + totals_today["demande"]
        + totals_today["reco"]
        + totals_today["partage"]
    )
    conversion_today = (
        round((totals_today["actions"] / totals_today["visites"]) * 100)
        if totals_today["visites"] > 0
        else 0
    )
    if totals_today["visites"] == 0 and totals_today["actions"] == 0:
        business_summary = "Aucune activité aujourd’hui"
    else:
        business_summary = (
            f"{totals_today['visites']} visites aujourd’hui, "
            f"{totals_today['contact']} prises de contact, "
            f"{totals_today['reco']} recommandations"
        )
    if totals_today["visites"] == 0:
        performance_today = "aucun trafic"
        performance_label = "Aucune activité aujourd’hui"
        performance_class = "perf-none"
    elif totals_today["contact"] == 0:
        performance_today = "trafic sans conversion"
        performance_label = "Du trafic mais aucune prise de contact"
        performance_class = "perf-warn"
    elif conversion_today < 10:
        performance_today = "conversion faible"
        performance_label = "Conversion faible aujourd’hui"
        performance_class = "perf-warn"
    else:
        performance_today = "activité performante"
        performance_label = "Bonne activité aujourd’hui"
        performance_class = "perf-good"

    rows_html: List[str] = []
    for slug in slugs:
        m = metrics_today.get(slug, {})
        status_txt = m.get("status", "inactif")
        status_cls = "status-idle"
        if status_txt == "performante":
            status_cls = "status-perf"
        elif status_txt == "actif":
            status_cls = "status-active"
        rows_html.append(
            "<tr>"
            f"<td><code>{escape(slug)}</code></td>"
            f"<td style=\"text-align:right\" data-col=\"visites\">{m.get('visites', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"actions\">{m.get('actions', 0)}</td>"
            f"<td data-col=\"status\"><span class=\"status-pill {status_cls}\">{status_txt}</span></td>"
            f"<td style=\"text-align:right\" data-col=\"phone\">{m.get('phone', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"whatsapp\">{m.get('whatsapp', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"google\">{m.get('google', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"demande\">{m.get('demande', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"reco\">{m.get('reco', 0)}</td>"
            f"<td style=\"text-align:right\" data-col=\"partage\">{m.get('partage', 0)}</td>"
            "</tr>"
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="10" style="color:rgba(229,231,235,.65)">'
            "Aucune carte en base — créez une carte depuis l’admin.</td></tr>"
        )

    traffic_html: List[str] = []
    for label, cnt in traffic:
        traffic_html.append(
            f"<tr><td>{escape(label)}</td>"
            f"<td style=\"text-align:right\">{cnt}</td></tr>"
        )
    if not traffic_html:
        traffic_html.append(
            '<tr><td colspan="2" style="color:rgba(229,231,235,.65)">'
            "Aucune visite sur 30 jours.</td></tr>"
        )

    affiliate_html: List[str] = []
    for ref_val, v_cnt, a_cnt in affiliates:
        affiliate_html.append(
            f"<tr><td><code>{escape(ref_val)}</code></td>"
            f"<td style=\"text-align:right\">{v_cnt}</td>"
            f"<td style=\"text-align:right\">{a_cnt}</td></tr>"
        )
    if not affiliate_html:
        affiliate_html.append(
            '<tr><td colspan="3" style="color:rgba(229,231,235,.65)">'
            "Aucun paramètre <code>ref</code> sur 30 jours.</td></tr>"
        )

    reco_referrer_html: List[str] = []
    for card_slug, referrer_id, v_cnt, c_cnt in recommendation_referrers:
        raw_l = recommender_labels.get(referrer_id)
        disp_l = raw_l.strip() if raw_l else None
        who = escape(effective_recommender_label(disp_l, referrer_id))
        reco_referrer_html.append(
            f"<tr><td><code>{escape(card_slug)}</code></td>"
            f"<td>{who}</td>"
            f"<td style=\"text-align:right\">{v_cnt}</td>"
            f"<td style=\"text-align:right\">{c_cnt}</td></tr>"
        )
    if not reco_referrer_html:
        reco_referrer_html.append(
            '<tr><td colspan="4" style="color:rgba(229,231,235,.65)">'
            "Aucune recommandation tracée via <code>?r=...</code> sur 30 jours.</td></tr>"
        )

    top_referrers_html: List[str] = []
    for referrer_id, created_cnt, visit_cnt, contact_cnt in top_referrers:
        raw_t = recommender_labels.get(referrer_id)
        disp_t = raw_t.strip() if raw_t else None
        who = escape(effective_recommender_label(disp_t, referrer_id))
        top_referrers_html.append(
            f"<tr><td>{who}</td>"
            f"<td style=\"text-align:right\">{created_cnt}</td>"
            f"<td style=\"text-align:right\">{visit_cnt}</td>"
            f"<td style=\"text-align:right\">{contact_cnt}</td></tr>"
        )
    if not top_referrers_html:
        top_referrers_html.append(
            '<tr><td colspan="4" style="color:rgba(229,231,235,.65)">'
            "Aucun recommandant actif sur 30 jours.</td></tr>"
        )

    table_aff = (
        "<table><thead><tr>"
        "<th>ref (affilié)</th><th>Visites</th><th>Actions</th>"
        "</tr></thead><tbody>"
        + "".join(affiliate_html)
        + "</tbody></table>"
    )

    table_reco_referrer = (
        "<table><thead><tr>"
        "<th>Carte</th><th>Recommandant</th><th>Visites générées</th><th>Contacts générés</th>"
        "</tr></thead><tbody>"
        + "".join(reco_referrer_html)
        + "</tbody></table>"
    )

    table_top_referrers = (
        "<table><thead><tr>"
        "<th>Recommandant</th><th>Recommandations créées</th><th>Visites générées</th><th>Contacts générés</th>"
        "</tr></thead><tbody>"
        + "".join(top_referrers_html)
        + "</tbody></table>"
    )

    kpi = f"""
    <section>
      <h2>ACTIVITÉ DU JOUR</h2>
      <p class="business-summary">{business_summary}</p>
      <p class="performance-summary {performance_class}">{performance_label}</p>
      <div class="kpi-grid kpi-grid-today">
        <div class="kpi {'kpi-active' if totals_today['visites'] > 0 else 'kpi-idle'}"><div class="kpi-label">visites_today</div><div class="kpi-val">{totals_today['visites']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['actions'] > 0 else 'kpi-idle'}"><div class="kpi-label">actions_today</div><div class="kpi-val">{totals_today['actions']}</div></div>
        <div class="kpi {'kpi-active' if conversion_today > 0 else 'kpi-idle'}"><div class="kpi-label">conversion_today</div><div class="kpi-val">{conversion_today}%</div></div>
        <div class="kpi {'kpi-active' if totals_today['contact'] > 0 else 'kpi-idle'}"><div class="kpi-label">contact_today</div><div class="kpi-val">{totals_today['contact']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['visibilite'] > 0 else 'kpi-idle'}"><div class="kpi-label">visibilite_today</div><div class="kpi-val">{totals_today['visibilite']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['phone'] > 0 else 'kpi-idle'}"><div class="kpi-label">phone_today</div><div class="kpi-val">{totals_today['phone']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['whatsapp'] > 0 else 'kpi-idle'}"><div class="kpi-label">whatsapp_today</div><div class="kpi-val">{totals_today['whatsapp']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['google'] > 0 else 'kpi-idle'}"><div class="kpi-label">google_today</div><div class="kpi-val">{totals_today['google']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['demande'] > 0 else 'kpi-idle'}"><div class="kpi-label">demande_today</div><div class="kpi-val">{totals_today['demande']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['reco'] > 0 else 'kpi-idle'}"><div class="kpi-label">reco_today</div><div class="kpi-val">{totals_today['reco']}</div></div>
        <div class="kpi {'kpi-active' if totals_today['partage'] > 0 else 'kpi-idle'}"><div class="kpi-label">partage_today</div><div class="kpi-val">{totals_today['partage']}</div></div>
      </div>
      <p class="sub" style="margin-top:-12px;margin-bottom:2px;font-size:13px;">Recommandations aujourd’hui : <b>{totals_today['reco']}</b></p>
    </section>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Visites aujourd’hui</div><div class="kpi-val">{int(visits_today)}</div></div>
      <div class="kpi"><div class="kpi-label">Visites 7 jours</div><div class="kpi-val">{int(visits_7)}</div></div>
      <div class="kpi"><div class="kpi-label">Visites 30 jours</div><div class="kpi-val">{int(visits_30)}</div></div>
      <div class="kpi"><div class="kpi-label">Actions 7 jours</div><div class="kpi-val">{actions_7}</div></div>
    </div>
    """

    table_cards = (
        "<div class=\"period-switch\" id=\"period-switch\">"
        "<button class=\"period-btn is-active\" data-period=\"today\">Aujourd’hui</button>"
        "<button class=\"period-btn\" data-period=\"7d\">7 jours</button>"
        "<button class=\"period-btn\" data-period=\"30d\">30 jours</button>"
        "</div>"
        "<table id=\"cards-table\"><thead><tr>"
        "<th>Slug</th><th data-head=\"visites\">visites_today</th><th data-head=\"actions\">actions_today</th><th data-head=\"status\">status_today</th>"
        "<th>phone</th><th>whatsapp</th><th>Google</th><th>demande</th><th>reco</th>"
        "<th>partage</th>"
        "</tr></thead><tbody>"
        + "".join(rows_html)
        + "</tbody></table>"
    )

    table_src = (
        "<table><thead><tr><th>Source (src)</th><th>Visites 30j</th></tr></thead><tbody>"
        + "".join(traffic_html)
        + "</tbody></table>"
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SmartCard — Analytics</title>
  <style>
    :root {{
      --bg0:#050a13; --bg1:#070f1f; --card:#0b1222; --line:rgba(148,163,184,.18);
      --text:#e5e7eb; --muted:rgba(229,231,235,.72); --brand:#60a5fa; --ok:#22c55e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      color: var(--text);
      background: radial-gradient(1000px 600px at 20% 0%, rgba(30,58,138,.35), transparent 60%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1200px; margin: 0 auto; padding: 28px 18px 48px; }}
    .tag {{
      display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px;
      font-size: 12px; color: rgba(229,231,235,.85); border: 1px solid var(--line);
      background: rgba(2,6,23,.55);
    }}
    h1 {{ margin: 14px 0 8px; font-size: 30px; letter-spacing: -0.02em; }}
    .sub {{ color: var(--muted); font-size: 14px; max-width: 720px; margin-bottom: 22px; }}
    .kpi-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 28px;
    }}
    .kpi {{
      background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px;
      box-shadow: 0 8px 28px rgba(0,0,0,.35);
    }}
    .kpi-idle {{
      opacity: .72;
      border-color: rgba(148,163,184,.24);
    }}
    .kpi-active {{
      border-color: rgba(34,197,94,.48);
      box-shadow: 0 8px 28px rgba(34,197,94,.18);
    }}
    .kpi-label {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
    .kpi-val {{ font-size: 26px; font-weight: 700; color: #fff; }}
    .business-summary {{
      margin: 4px 0 12px;
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      color: rgba(229,231,235,.9);
      background: rgba(2,6,23,.38);
      font-size: 14px;
    }}
    .performance-summary {{
      margin: -4px 0 12px;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      display: inline-block;
    }}
    .perf-none {{
      color: rgba(229,231,235,.72);
      border-color: rgba(148,163,184,.28);
      background: rgba(148,163,184,.12);
    }}
    .perf-warn {{
      color: #fdba74;
      border-color: rgba(251,146,60,.4);
      background: rgba(251,146,60,.14);
    }}
    .perf-good {{
      color: #86efac;
      border-color: rgba(34,197,94,.4);
      background: rgba(34,197,94,.15);
    }}
    .period-switch {{
      display: flex;
      gap: 8px;
      margin: 0 0 12px;
      flex-wrap: wrap;
    }}
    .period-btn {{
      background: rgba(2,6,23,.55);
      color: var(--text);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 8px 12px;
      cursor: pointer;
      font-size: 12px;
    }}
    .period-btn.is-active {{
      border-color: rgba(96,165,250,.8);
      background: rgba(37,99,235,.22);
    }}
    section {{ margin-bottom: 32px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; font-weight: 600; }}
    table {{
      width: 100%; border-collapse: collapse; background: var(--card);
      border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
    }}
    th, td {{ padding: 10px 12px; text-align: left; font-size: 13px; border-bottom: 1px solid var(--line); }}
    th {{ background: rgba(15,23,42,.65); color: rgba(229,231,235,.92); font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
    .status-pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      border: 1px solid transparent;
    }}
    .status-active {{
      color: #86efac;
      border-color: rgba(34,197,94,.4);
      background: rgba(34,197,94,.15);
    }}
    .status-idle {{
      color: rgba(229,231,235,.7);
      border-color: rgba(148,163,184,.28);
      background: rgba(148,163,184,.12);
    }}
    .status-perf {{
      color: #86efac;
      border-color: rgba(34,197,94,.45);
      background: rgba(34,197,94,.2);
    }}
    code {{ font-family: ui-monospace, monospace; font-size: 12px; color: #93c5fd; }}
    a {{ color: #93c5fd; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="tag">Maavnica SmartCard — Analytics v1</div>
    <h1>Performance des cartes</h1>
    <p class="sub">
      Lecture seule — compteurs basés sur les visites <code>/c/&lt;slug&gt;</code> et les événements envoyés par la carte publique.
      Fuseau : UTC (dates « aujourd’hui » = jour UTC).
    </p>
    {kpi}
    <section>
      <h2>Performance par carte</h2>
      {table_cards}
    </section>
    <section>
      <h2>Sources de trafic (30 jours)</h2>
      {table_src}
    </section>
    <section>
      <h2>Affiliés (30 jours)</h2>
      <p class="sub" style="margin-top:-4px;margin-bottom:12px;font-size:13px;">
        Basé sur le paramètre d’URL <code>ref</code> (ex. <code>/c/demo?ref=paul</code>).
      </p>
      {table_aff}
    </section>
    <section>
      <h2>RECOMMANDATIONS TRAÇABLES (30 jours)</h2>
      <p class="sub" style="margin-top:-4px;margin-bottom:12px;font-size:13px;">
        Basé sur la table <code>recommendation_events</code> (chaîne de recommandation traçable).
        Colonne <b>Recommandant</b> : nom affiché si enregistré, sinon identifiant technique (<code>?r=…</code>) —
        les totaux restent groupés par cet identifiant, pas par le nom seul.
      </p>
      {table_reco_referrer}
    </section>
    <section>
      <h2>TOP RECOMMANDANTS (30 jours)</h2>
      <p class="sub" style="margin-top:-4px;margin-bottom:12px;font-size:13px;">
        Tri métier : contacts générés, puis visites générées, puis recommandations créées.
      </p>
      {table_top_referrers}
    </section>
    <p class="sub"><a href="/admin">← Retour admin cartes</a></p>
  </div>
  <script>
    (function initAnalyticsPeriodSwitch() {{
      const dataByPeriod = {{
        today: {metrics_today},
        "7d": {metrics_7},
        "30d": {metrics_30},
      }};
      const table = document.getElementById("cards-table");
      const switchBox = document.getElementById("period-switch");
      if (!table || !switchBox) return;
      const rows = Array.from(table.querySelectorAll("tbody tr"));
      const visitHead = table.querySelector('[data-head="visites"]');
      const actionHead = table.querySelector('[data-head="actions"]');
      const statusHead = table.querySelector('[data-head="status"]');
      function applyPeriod(period) {{
        const visitLabel = period === "today" ? "visites_today" : (period === "7d" ? "visites_7j" : "visites_30j");
        const actionLabel = period === "today" ? "actions_today" : (period === "7d" ? "actions_7j" : "actions_30j");
        const statusLabel = period === "today" ? "status_today" : (period === "7d" ? "status_7j" : "status_30j");
        if (visitHead) visitHead.textContent = visitLabel;
        if (actionHead) actionHead.textContent = actionLabel;
        if (statusHead) statusHead.textContent = statusLabel;
        rows.forEach((row) => {{
          const slug = row.querySelector("td code")?.textContent || "";
          const metric = (dataByPeriod[period] && dataByPeriod[period][slug]) || null;
          if (!metric) return;
          row.querySelector('[data-col="visites"]').textContent = metric.visites || 0;
          row.querySelector('[data-col="actions"]').textContent = metric.actions || 0;
          row.querySelector('[data-col="phone"]').textContent = metric.phone || 0;
          row.querySelector('[data-col="whatsapp"]').textContent = metric.whatsapp || 0;
          row.querySelector('[data-col="google"]').textContent = metric.google || 0;
          row.querySelector('[data-col="demande"]').textContent = metric.demande || 0;
          row.querySelector('[data-col="reco"]').textContent = metric.reco || 0;
          row.querySelector('[data-col="partage"]').textContent = metric.partage || 0;
          const statusBox = row.querySelector('[data-col="status"] .status-pill');
          if (statusBox) {{
            const status = metric.status || "inactif";
            statusBox.textContent = status;
            statusBox.classList.toggle("status-perf", status === "performante");
            statusBox.classList.toggle("status-active", status === "actif");
            statusBox.classList.toggle("status-idle", status === "inactif");
          }}
        }});
        switchBox.querySelectorAll(".period-btn").forEach((btn) => {{
          btn.classList.toggle("is-active", btn.dataset.period === period);
        }});
      }}
      switchBox.addEventListener("click", (e) => {{
        const btn = e.target.closest(".period-btn");
        if (!btn || !btn.dataset.period) return;
        applyPeriod(btn.dataset.period);
      }});
      applyPeriod("today");
    }})();
  </script>
</body>
</html>"""


@router_pages.get("/admin/analytics", response_class=HTMLResponse, include_in_schema=False)
def analytics_dashboard_page(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_http_basic),
):
    html = _build_dashboard_html(db)
    return HTMLResponse(content=html)
