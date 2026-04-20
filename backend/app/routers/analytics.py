# backend/app/routers/analytics.py

from __future__ import annotations

from datetime import datetime, timedelta
from html import escape
from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, CardEvent, CardVisit
from app.schemas import AnalyticsEventIn, AnalyticsVisitIn
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
    "share_click",
    "share_native_opened",
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


def _recommendation_codes_30d(db: Session, d30: datetime) -> List[Tuple[str, int, int]]:
    """
    Performance par code de recommandation (paramètre rec) sur 30 jours.
    visites = lignes card_visits avec rec renseigné
    actions = lignes card_events avec rec renseigné
    """
    v_rows = (
        db.query(CardVisit.rec, func.count(CardVisit.id))
        .filter(
            CardVisit.created_at >= d30,
            CardVisit.rec.isnot(None),
            CardVisit.rec != "",
        )
        .group_by(CardVisit.rec)
        .all()
    )
    e_rows = (
        db.query(CardEvent.rec, func.count(CardEvent.id))
        .filter(
            CardEvent.created_at >= d30,
            CardEvent.rec.isnot(None),
            CardEvent.rec != "",
        )
        .group_by(CardEvent.rec)
        .all()
    )
    visits_by_rec: Dict[str, int] = {str(r[0]): int(r[1]) for r in v_rows}
    actions_by_rec: Dict[str, int] = {str(r[0]): int(r[1]) for r in e_rows}
    all_recs = set(visits_by_rec) | set(actions_by_rec)
    out: List[Tuple[str, int, int]] = []
    for rec_val in all_recs:
        out.append(
            (
                rec_val,
                visits_by_rec.get(rec_val, 0),
                actions_by_rec.get(rec_val, 0),
            )
        )
    out.sort(key=lambda row: (-row[1], row[0]))
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

    vc7 = _visit_counts_since(db, d7)
    vc30 = _visit_counts_since(db, d30)
    ev7 = _event_counts_since(db, d7, _EVENT_COLUMNS)

    traffic = _traffic_sources_30d(db, d30)
    affiliates = _affiliates_30d(db, d30)
    recommendations = _recommendation_codes_30d(db, d30)

    def ev(slug: str, kind: str) -> int:
        return ev7.get((slug, kind), 0)

    slugs = sorted(slugs_all, key=lambda s: (-vc7.get(s, 0), s))

    rows_html: List[str] = []
    for slug in slugs:
        rows_html.append(
            "<tr>"
            f"<td><code>{escape(slug)}</code></td>"
            f"<td style=\"text-align:right\">{vc7.get(slug, 0)}</td>"
            f"<td style=\"text-align:right\">{vc30.get(slug, 0)}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'phone_click')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'whatsapp_click')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'google_review_click')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'rdv_request')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'recommend_click')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'share_click')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'share_native_opened')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'share_native_success')}</td>"
            f"<td style=\"text-align:right\">{ev(slug, 'share_copy_fallback')}</td>"
            "</tr>"
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="12" style="color:rgba(229,231,235,.65)">'
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

    reco_html: List[str] = []
    for rec_val, v_cnt, a_cnt in recommendations:
        reco_html.append(
            f"<tr><td><code>{escape(rec_val)}</code></td>"
            f"<td style=\"text-align:right\">{v_cnt}</td>"
            f"<td style=\"text-align:right\">{a_cnt}</td></tr>"
        )
    if not reco_html:
        reco_html.append(
            '<tr><td colspan="3" style="color:rgba(229,231,235,.65)">'
            "Aucun paramètre <code>rec</code> sur 30 jours.</td></tr>"
        )

    table_aff = (
        "<table><thead><tr>"
        "<th>ref (affilié)</th><th>Visites</th><th>Actions</th>"
        "</tr></thead><tbody>"
        + "".join(affiliate_html)
        + "</tbody></table>"
    )

    table_reco = (
        "<table><thead><tr>"
        "<th>rec</th><th>Visites</th><th>Actions</th>"
        "</tr></thead><tbody>"
        + "".join(reco_html)
        + "</tbody></table>"
    )

    kpi = f"""
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Visites aujourd’hui</div><div class="kpi-val">{int(visits_today)}</div></div>
      <div class="kpi"><div class="kpi-label">Visites 7 jours</div><div class="kpi-val">{int(visits_7)}</div></div>
      <div class="kpi"><div class="kpi-label">Visites 30 jours</div><div class="kpi-val">{int(visits_30)}</div></div>
      <div class="kpi"><div class="kpi-label">Actions 7 jours</div><div class="kpi-val">{actions_7}</div></div>
    </div>
    """

    table_cards = (
        "<table><thead><tr>"
        "<th>Slug</th><th>Visites 7j</th><th>Visites 30j</th>"
        "<th>phone</th><th>whatsapp</th><th>Google</th><th>demande</th><th>reco</th>"
        "<th>partage</th><th>share open</th><th>share ok</th><th>copie fallback</th>"
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
    .kpi-label {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
    .kpi-val {{ font-size: 26px; font-weight: 700; color: #fff; }}
    section {{ margin-bottom: 32px; }}
    h2 {{ font-size: 18px; margin: 0 0 12px; font-weight: 600; }}
    table {{
      width: 100%; border-collapse: collapse; background: var(--card);
      border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
    }}
    th, td {{ padding: 10px 12px; text-align: left; font-size: 13px; border-bottom: 1px solid var(--line); }}
    th {{ background: rgba(15,23,42,.65); color: rgba(229,231,235,.92); font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
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
        Basé sur le paramètre d’URL <code>ref</code> (ex. <code>/c/demo2?ref=paul</code>).
      </p>
      {table_aff}
    </section>
    <section>
      <h2>RECOMMANDATIONS (30 jours)</h2>
      <p class="sub" style="margin-top:-4px;margin-bottom:12px;font-size:13px;">
        Basé sur le paramètre d’URL <code>rec</code> (ex. partage avec <code>?src=recommend&amp;rec=julie123</code>).
      </p>
      {table_reco}
    </section>
    <p class="sub"><a href="/admin">← Retour admin cartes</a></p>
  </div>
</body>
</html>"""


@router_pages.get("/admin/analytics", response_class=HTMLResponse, include_in_schema=False)
def analytics_dashboard_page(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_http_basic),
):
    html = _build_dashboard_html(db)
    return HTMLResponse(content=html)
