# backend/app/routers/site_analytics.py

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from html import escape
from typing import Any, DefaultDict, Dict, List, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SiteAnalyticsEvent
from app.schemas import SiteAnalyticsEventIn
from app.utils.admin_auth import require_admin_http_basic
from app.utils.rate_limit import rate_limit_by_ip

router_api = APIRouter(prefix="/api/site-analytics", tags=["site-analytics"])
router_pages = APIRouter(tags=["site-analytics"])


def _utc_day_start() -> datetime:
    now = datetime.utcnow()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _path_key_expr():
    p = SiteAnalyticsEvent.path
    return case(
        (func.instr(p, "?") > 0, func.substr(p, 1, func.instr(p, "?") - 1)),
        else_=p,
    )


def _normalize_optional(v: str | None, max_len: int) -> str | None:
    if v is None:
        return None
    s = v.strip()
    if not s:
        return None
    return s[:max_len]


def _src_label(utm_s: Any, utm_m: Any, utm_c: Any, src_s: Any) -> str:
    parts: List[str] = []
    for x in (utm_s, utm_m, utm_c):
        t = (str(x).strip() if x is not None else "")[:200]
        if t:
            parts.append(t)
    if parts:
        return "utm:" + " / ".join(parts)
    s = (str(src_s).strip() if src_s is not None else "")[:200]
    if s:
        return "src:" + s
    return "direct"


def _coalesce_source_display(utm_s: Any, utm_m: Any, utm_c: Any, src_s: Any) -> str:
    return _src_label(utm_s, utm_m, utm_c, src_s)


@router_api.post("/event", status_code=204)
def record_site_event(
    payload: SiteAnalyticsEventIn,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(rate_limit_by_ip(120, 60)),
):
    ua_raw = request.headers.get("user-agent") or ""
    ua = ua_raw[:256] if ua_raw else None

    row = SiteAnalyticsEvent(
        domain=_normalize_optional(payload.domain, 255) or "",
        path=_normalize_optional(payload.path, 1024) or "",
        page_type=payload.page_type,
        event_type=payload.event_type,
        source=_normalize_optional(payload.source, 255),
        referrer=_normalize_optional(payload.referrer, 512),
        utm_source=_normalize_optional(payload.utm_source, 255),
        utm_medium=_normalize_optional(payload.utm_medium, 255),
        utm_campaign=_normalize_optional(payload.utm_campaign, 255),
        lang=_normalize_optional(payload.lang, 16),
        target=_normalize_optional(payload.target, 512),
        visitor_id=_normalize_optional(payload.visitor_id, 80),
        user_agent=ua,
    )
    db.add(row)
    db.commit()
    return Response(status_code=204)


def _count_events(
    db: Session,
    since: datetime,
    event_type: str,
) -> int:
    n = (
        db.query(func.count(SiteAnalyticsEvent.id))
        .filter(
            SiteAnalyticsEvent.created_at >= since,
            SiteAnalyticsEvent.event_type == event_type,
        )
        .scalar()
    )
    return int(n or 0)


def _top_pages(
    db: Session, d7: datetime, d30: datetime
) -> List[Tuple[str, str, str, int, int]]:
    pk = _path_key_expr()
    rows7 = (
        db.query(
            SiteAnalyticsEvent.domain,
            pk.label("path_key"),
            func.coalesce(SiteAnalyticsEvent.lang, "").label("lang"),
            func.count(SiteAnalyticsEvent.id),
        )
        .filter(
            SiteAnalyticsEvent.event_type == "page_view",
            SiteAnalyticsEvent.created_at >= d7,
        )
        .group_by(SiteAnalyticsEvent.domain, pk, SiteAnalyticsEvent.lang)
        .all()
    )
    rows30 = (
        db.query(
            SiteAnalyticsEvent.domain,
            pk.label("path_key"),
            func.coalesce(SiteAnalyticsEvent.lang, "").label("lang"),
            func.count(SiteAnalyticsEvent.id),
        )
        .filter(
            SiteAnalyticsEvent.event_type == "page_view",
            SiteAnalyticsEvent.created_at >= d30,
        )
        .group_by(SiteAnalyticsEvent.domain, pk, SiteAnalyticsEvent.lang)
        .all()
    )
    m7: Dict[Tuple[str, str, str], int] = {}
    for dom, pkey, lang, cnt in rows7:
        m7[(str(dom), str(pkey), str(lang or ""))] = int(cnt)
    m30: Dict[Tuple[str, str, str], int] = {}
    for dom, pkey, lang, cnt in rows30:
        m30[(str(dom), str(pkey), str(lang or ""))] = int(cnt)
    keys = set(m7.keys()) | set(m30.keys())
    out: List[Tuple[str, str, str, int, int]] = []
    for dom, pkey, lang in sorted(
        keys, key=lambda k: (-m30.get(k, 0), -m7.get(k, 0), k[0], k[1])
    ):
        c7 = m7.get((dom, pkey, lang), 0)
        c30 = m30.get((dom, pkey, lang), 0)
        out.append(
            (
                dom,
                pkey,
                lang if lang else "—",
                c7,
                c30,
            )
        )
    return out[:80]


def _sources_breakdown(db: Session, d7: datetime) -> List[Tuple[str, int, int, int, int, int]]:
    rows = (
        db.query(
            SiteAnalyticsEvent.utm_source,
            SiteAnalyticsEvent.utm_medium,
            SiteAnalyticsEvent.utm_campaign,
            SiteAnalyticsEvent.source,
            SiteAnalyticsEvent.event_type,
            func.count(SiteAnalyticsEvent.id),
        )
        .filter(SiteAnalyticsEvent.created_at >= d7)
        .group_by(
            SiteAnalyticsEvent.utm_source,
            SiteAnalyticsEvent.utm_medium,
            SiteAnalyticsEvent.utm_campaign,
            SiteAnalyticsEvent.source,
            SiteAnalyticsEvent.event_type,
        )
        .all()
    )
    merged: DefaultDict[str, Dict[str, int]] = defaultdict(
        lambda: {"visits": 0, "cta": 0, "demo": 0, "contact": 0, "affiliate": 0}
    )
    for utm_s, utm_m, utm_c, src_s, ev, cnt in rows:
        lbl = _src_label(utm_s, utm_m, utm_c, src_s)
        b = merged[lbl]
        c = int(cnt)
        evs = str(ev)
        if evs == "page_view":
            b["visits"] += c
        elif evs == "cta_click":
            b["cta"] += c
        elif evs == "demo_click":
            b["demo"] += c
        elif evs == "contact_click":
            b["contact"] += c
        elif evs == "affiliate_click":
            b["affiliate"] += c
    out_list: List[Tuple[str, int, int, int, int, int]] = []
    for lbl, b in merged.items():
        out_list.append(
            (
                lbl,
                b["visits"],
                b["cta"],
                b["demo"],
                b["contact"],
                b["affiliate"],
            )
        )
    out_list.sort(key=lambda r: (-(r[1] + r[2] + r[3] + r[4] + r[5]), r[0]))
    return out_list[:60]


@router_pages.get("/admin/site-analytics", response_class=HTMLResponse, include_in_schema=False)
def site_analytics_dashboard(
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_http_basic),
):
    now = datetime.utcnow()
    today0 = _utc_day_start()
    d7 = now - timedelta(days=7)
    d30 = now - timedelta(days=30)

    visits_today = _count_events(db, today0, "page_view")
    visits_7 = _count_events(db, d7, "page_view")
    visits_30 = _count_events(db, d30, "page_view")
    cta_7 = _count_events(db, d7, "cta_click")
    demo_7 = _count_events(db, d7, "demo_click")
    contact_7 = _count_events(db, d7, "contact_click")
    aff_7 = _count_events(db, d7, "affiliate_click")

    top_pages = _top_pages(db, d7, d30)
    sources = _sources_breakdown(db, d7)

    recent_rows = (
        db.query(SiteAnalyticsEvent)
        .order_by(SiteAnalyticsEvent.id.desc())
        .limit(100)
        .all()
    )

    def tr_pages(cells: List[str]) -> str:
        return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"

    pages_html: List[str] = []
    for dom, pkey, lang, c7, c30 in top_pages[:40]:
        pages_html.append(
            tr_pages(
                [
                    escape(dom),
                    f"<code>{escape(pkey)}</code>",
                    escape(lang),
                    str(c7),
                    str(c30),
                ]
            )
        )
    if not pages_html:
        pages_html.append(
            '<tr><td colspan="5" class="muted">Aucune page vue enregistrée.</td></tr>'
        )

    src_html: List[str] = []
    for lbl, v, cta, demo, contact, aff in sources:
        src_html.append(
            tr_pages(
                [
                    escape(lbl),
                    str(v),
                    str(cta),
                    str(demo),
                    str(contact),
                    str(aff),
                ]
            )
        )
    if not src_html:
        src_html.append(
            '<tr><td colspan="6" class="muted">Aucune donnée sur 7 jours.</td></tr>'
        )

    recent_html: List[str] = []
    for ev in recent_rows:
        src_disp = _coalesce_source_display(
            ev.utm_source,
            ev.utm_medium,
            ev.utm_campaign,
            ev.source,
        )
        raw_path = ev.path or ""
        disp_path = raw_path.split("?", 1)[0] if "?" in raw_path else raw_path
        recent_html.append(
            tr_pages(
                [
                    escape(ev.created_at.strftime("%Y-%m-%d %H:%M") + " UTC"),
                    escape(ev.domain or ""),
                    f"<code>{escape(disp_path[:80])}</code>",
                    escape(ev.event_type),
                    escape(src_disp),
                    escape((ev.target or "")[:120]),
                ]
            )
        )
    if not recent_html:
        recent_html.append(
            '<tr><td colspan="6" class="muted">Aucun événement.</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Analytics site / landing</title>
  <style>
    :root {{
      --bg0:#0c1220; --bg1:#111827; --line:rgba(148,163,184,.2);
      --text:#e5e7eb; --muted:#94a3b8; --accent:#38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      color: var(--text);
      background: linear-gradient(165deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1180px; margin: 0 auto; padding: 28px 18px 56px; }}
    h1 {{ font-size: 1.45rem; margin: 0 0 8px; font-weight: 700; }}
    .sub {{ color: var(--muted); font-size: 14px; margin: 0 0 22px; line-height: 1.45; }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 28px;
    }}
    .kpi {{
      background: rgba(15,23,42,.72);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px;
    }}
    .kpi .lbl {{ font-size: 11px; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); }}
    .kpi .val {{ font-size: 1.35rem; font-weight: 700; margin-top: 6px; }}
    section {{ margin-bottom: 32px; }}
    section h2 {{
      font-size: 15px;
      margin: 0 0 12px;
      color: var(--accent);
      font-weight: 650;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      background: rgba(15,23,42,.55);
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: hidden;
    }}
    th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ background: rgba(2,6,23,.45); font-weight: 600; color: #cbd5e1; }}
    tr:last-child td {{ border-bottom: none; }}
    td:nth-child(n+4) {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .sources td:nth-child(n+2) {{ text-align: right; }}
    .muted {{ color: var(--muted); }}
    .nav-top {{ margin-bottom: 18px; font-size: 14px; }}
    .nav-top a {{ color: var(--accent); }}
    code {{ font-size: 12px; }}
    @media (max-width: 720px) {{
      table {{ display: block; overflow-x: auto; white-space: nowrap; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="nav-top">
      <a href="/admin/analytics">Analytics cartes</a>
      ·
      <a href="/admin">Admin</a>
    </div>
    <h1>Analytics site / acquisition</h1>
    <p class="sub">
      Trafic landing, sources, CTA et clics démo — données séparées de l’analytics des cartes publiques
      (<code>/c/…</code>).
    </p>

    <div class="kpi-grid">
      <div class="kpi"><div class="lbl">Visites aujourd’hui</div><div class="val">{visits_today}</div></div>
      <div class="kpi"><div class="lbl">Visites 7 jours</div><div class="val">{visits_7}</div></div>
      <div class="kpi"><div class="lbl">Visites 30 jours</div><div class="val">{visits_30}</div></div>
      <div class="kpi"><div class="lbl">CTA 7 jours</div><div class="val">{cta_7}</div></div>
      <div class="kpi"><div class="lbl">Démo 7 jours</div><div class="val">{demo_7}</div></div>
      <div class="kpi"><div class="lbl">Contact 7 jours</div><div class="val">{contact_7}</div></div>
      <div class="kpi"><div class="lbl">Affiliation 7 jours</div><div class="val">{aff_7}</div></div>
    </div>

    <section>
      <h2>Pages les plus vues</h2>
      <table>
        <thead><tr>
          <th>Domaine</th><th>Page</th><th>Langue</th><th>Visites 7j</th><th>Visites 30j</th>
        </tr></thead>
        <tbody>{"".join(pages_html)}</tbody>
      </table>
    </section>

    <section>
      <h2>Sources (7 jours)</h2>
      <table class="sources">
        <thead><tr>
          <th>Source / UTM</th><th>Visites</th><th>CTA</th><th>Démo</th><th>Contact</th><th>Affiliation</th>
        </tr></thead>
        <tbody>{"".join(src_html)}</tbody>
      </table>
    </section>

    <section>
      <h2>Événements récents</h2>
      <table>
        <thead><tr>
          <th>Date</th><th>Domaine</th><th>Page</th><th>Event</th><th>Source</th><th>Cible</th>
        </tr></thead>
        <tbody>{"".join(recent_html)}</tbody>
      </table>
    </section>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)
