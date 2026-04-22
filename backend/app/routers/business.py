from __future__ import annotations

from datetime import datetime
from html import escape
from typing import List

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card
from app.routers.cards import _computed_status, _days_remaining
from app.utils.admin_auth import require_admin_http_basic

router_pages = APIRouter(tags=["business"])

_NON_EXPIRING_PLANS = {"demo", "lifetime"}
_ALLOWED_FILTERS = {"all", "active", "expired", "trial", "solo", "business", "demo", "lifetime"}
_ALLOWED_SORTS = {"expiring_soon", "expiring_far", "created_new", "created_old", "company_az"}


def _format_plan(plan_type: str | None) -> str:
    return (plan_type or "demo").strip().lower()


def _format_expiration_label(plan_type: str, expires_at) -> str:
    if plan_type in _NON_EXPIRING_PLANS:
        return "Sans expiration"
    if not expires_at:
        return "—"
    return expires_at.strftime("%d/%m/%Y")


def _normalize_filter(filter_value: str | None) -> str:
    v = (filter_value or "all").strip().lower()
    return v if v in _ALLOWED_FILTERS else "all"


def _normalize_sort(sort_value: str | None) -> str:
    v = (sort_value or "expiring_soon").strip().lower()
    return v if v in _ALLOWED_SORTS else "expiring_soon"


def _matches_filter(plan_type: str, status: str, filter_value: str) -> bool:
    if filter_value == "all":
        return True
    if filter_value in {"active", "expired"}:
        return status == filter_value
    return plan_type == filter_value


def _apply_sort(cards: List[Card], sort_value: str) -> List[Card]:
    if sort_value == "created_new":
        return sorted(cards, key=lambda c: c.created_at or datetime.min, reverse=True)
    if sort_value == "created_old":
        return sorted(cards, key=lambda c: c.created_at or datetime.min)
    if sort_value == "company_az":
        return sorted(cards, key=lambda c: (c.company_name or "").strip().lower())
    if sort_value == "expiring_far":
        # Les cartes sans expiration restent en bas pour garder la lisibilité.
        return sorted(
            cards,
            key=lambda c: (
                c.expires_at is None,
                0 if c.expires_at is None else -c.expires_at.timestamp(),
            ),
        )
    # expiring_soon par défaut
    return sorted(
        cards,
        key=lambda c: (
            c.expires_at is None,
            c.expires_at.timestamp() if c.expires_at else float("inf"),
        ),
    )


def _build_business_dashboard_html(
    db: Session,
    *,
    filter_value: str,
    search_query: str,
    sort_value: str,
) -> str:
    cards = db.query(Card).all()

    total_cards = len(cards)
    active_cards = 0
    expired_cards = 0
    active_trials = 0
    demo_lifetime_cards = 0
    expiring_7 = 0
    expiring_30 = 0

    filtered_cards: List[Card] = []
    search_q_norm = search_query.strip().lower()
    for card in cards:
        plan_type = _format_plan(card.plan_type)
        status = _computed_status(card)
        days_remaining = _days_remaining(card)

        if status == "active":
            active_cards += 1
        else:
            expired_cards += 1

        if plan_type == "trial" and status == "active":
            active_trials += 1
        if plan_type in _NON_EXPIRING_PLANS:
            demo_lifetime_cards += 1
        if status == "active" and days_remaining is not None and days_remaining <= 7:
            expiring_7 += 1
        if status == "active" and days_remaining is not None and days_remaining <= 30:
            expiring_30 += 1

        company_raw = card.company_name or ""
        slug_raw = card.slug or ""
        matches_search = (
            not search_q_norm
            or search_q_norm in company_raw.lower()
            or search_q_norm in slug_raw.lower()
        )
        if _matches_filter(plan_type, status, filter_value) and matches_search:
            filtered_cards.append(card)

    sorted_cards = _apply_sort(filtered_cards, sort_value)

    rows_html: List[str] = []
    for card in sorted_cards:
        plan_type = _format_plan(card.plan_type)
        status = _computed_status(card)
        days_remaining = _days_remaining(card)
        company_name = card.company_name or "—"
        expiration_label = _format_expiration_label(plan_type, card.expires_at)

        days_label = "—" if days_remaining is None else str(days_remaining)
        status_badge_class = "status-expired" if status == "expired" else "status-active"
        status_label = "Expirée" if status == "expired" else "Active"
        edit_href = f"/admin?slug={escape(card.slug)}"

        rows_html.append(
            "<tr>"
            f"<td><strong>{escape(company_name)}</strong></td>"
            f"<td><code>{escape(card.slug)}</code></td>"
            f"<td>{escape(plan_type)}</td>"
            f"<td>{escape(expiration_label)}</td>"
            f"<td><span class=\"status-badge {status_badge_class}\">{status_label}</span></td>"
            f"<td style=\"text-align:right\">{days_label}</td>"
            f"<td><a href=\"{edit_href}\">Editer</a></td>"
            "</tr>"
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="7" style="color:rgba(229,231,235,.7)">'
            "Aucune carte pour ce filtre/recherche.</td></tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>SmartCard — Dashboard Business</title>
  <style>
    :root {{
      --bg0:#050a13; --bg1:#070f1f; --card:#0b1222; --line:rgba(148,163,184,.18);
      --text:#e5e7eb; --muted:rgba(229,231,235,.72);
      --ok-bg:rgba(34,197,94,.18); --ok-fg:#86efac;
      --bad-bg:rgba(239,68,68,.16); --bad-fg:#fca5a5;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      color: var(--text);
      background: radial-gradient(1000px 600px at 20% 0%, rgba(30,58,138,.35), transparent 60%),
        linear-gradient(180deg, var(--bg0), var(--bg1));
      min-height: 100vh;
    }}
    .wrap {{ max-width: 1260px; margin: 0 auto; padding: 28px 18px 48px; }}
    .tag {{
      display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px;
      font-size: 12px; color: rgba(229,231,235,.85); border: 1px solid var(--line);
      background: rgba(2,6,23,.55);
    }}
    h1 {{ margin: 14px 0 8px; font-size: 30px; letter-spacing: -0.02em; }}
    .sub {{ color: var(--muted); font-size: 14px; max-width: 760px; margin-bottom: 22px; }}
    .kpi-grid {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 28px;
    }}
    .kpi {{
      background: var(--card); border: 1px solid var(--line); border-radius: 16px; padding: 16px 18px;
      box-shadow: 0 8px 28px rgba(0,0,0,.35);
    }}
    .kpi-label {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
    .kpi-val {{ font-size: 26px; font-weight: 700; color: #fff; }}
    .filters {{
      margin-bottom: 14px; display:grid; grid-template-columns: 1fr 1fr 1fr auto; gap:10px;
      align-items:end;
    }}
    .filters label {{ font-size: 12px; color: var(--muted); display:block; margin-bottom: 4px; }}
    .filters input, .filters select {{
      width: 100%; background: var(--card); color: var(--text); border: 1px solid var(--line);
      border-radius: 10px; padding: 9px 10px; font-size: 13px;
    }}
    .filters button, .filters a {{
      background: rgba(96,165,250,.2); color: #bfdbfe; border: 1px solid rgba(96,165,250,.4);
      border-radius: 10px; padding: 9px 12px; font-size: 13px; text-decoration: none;
      display: inline-flex; align-items: center; justify-content: center;
    }}
    .table-meta {{ margin: 8px 0 10px; color: var(--muted); font-size: 12px; }}
    @media (max-width: 980px) {{
      .filters {{ grid-template-columns: 1fr; }}
    }}
    table {{
      width: 100%; border-collapse: collapse; background: var(--card);
      border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
    }}
    th, td {{ padding: 10px 12px; text-align: left; font-size: 13px; border-bottom: 1px solid var(--line); }}
    th {{ background: rgba(15,23,42,.65); color: rgba(229,231,235,.92); font-weight: 600; }}
    tr:last-child td {{ border-bottom: none; }}
    .status-badge {{
      display:inline-flex; padding:3px 8px; border-radius:999px; font-size:12px; font-weight:600;
      border:1px solid transparent;
    }}
    .status-active {{ background:var(--ok-bg); color:var(--ok-fg); border-color:rgba(34,197,94,.35); }}
    .status-expired {{ background:var(--bad-bg); color:var(--bad-fg); border-color:rgba(239,68,68,.30); }}
    code {{ font-family: ui-monospace, monospace; font-size: 12px; color: #93c5fd; }}
    a {{ color: #93c5fd; }}
    .top-links {{ margin-bottom: 14px; display:flex; gap:14px; flex-wrap:wrap; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="tag">Maavnica SmartCard — Dashboard Business v1</div>
    <h1>Pilotage commercial des cartes</h1>
    <p class="sub">
      Vue globale des cartes, plans et expirations. Données calculées côté serveur en UTC à partir des cartes existantes.
    </p>
    <div class="top-links">
      <a href="/admin">Retour admin cartes</a>
      <a href="/admin/analytics">Voir analytics</a>
    </div>
    <div class="kpi-grid">
      <div class="kpi"><div class="kpi-label">Total cartes</div><div class="kpi-val">{total_cards}</div></div>
      <div class="kpi"><div class="kpi-label">Cartes actives</div><div class="kpi-val">{active_cards}</div></div>
      <div class="kpi"><div class="kpi-label">Cartes expirées</div><div class="kpi-val">{expired_cards}</div></div>
      <div class="kpi"><div class="kpi-label">Trials en cours</div><div class="kpi-val">{active_trials}</div></div>
      <div class="kpi"><div class="kpi-label">Demo / Lifetime</div><div class="kpi-val">{demo_lifetime_cards}</div></div>
      <div class="kpi"><div class="kpi-label">Expire sous 7 jours</div><div class="kpi-val">{expiring_7}</div></div>
      <div class="kpi"><div class="kpi-label">Expire sous 30 jours</div><div class="kpi-val">{expiring_30}</div></div>
    </div>
    <form method="get" action="/admin/business" class="filters">
      <div>
        <label for="filter">Filtre</label>
        <select id="filter" name="filter">
          <option value="all" {"selected" if filter_value == "all" else ""}>Toutes</option>
          <option value="active" {"selected" if filter_value == "active" else ""}>Active</option>
          <option value="expired" {"selected" if filter_value == "expired" else ""}>Expired</option>
          <option value="trial" {"selected" if filter_value == "trial" else ""}>Trial</option>
          <option value="solo" {"selected" if filter_value == "solo" else ""}>Solo</option>
          <option value="business" {"selected" if filter_value == "business" else ""}>Business</option>
          <option value="demo" {"selected" if filter_value == "demo" else ""}>Demo</option>
          <option value="lifetime" {"selected" if filter_value == "lifetime" else ""}>Lifetime</option>
        </select>
      </div>
      <div>
        <label for="q">Recherche (entreprise ou slug)</label>
        <input id="q" name="q" type="text" value="{escape(search_query)}" placeholder="Ex. plomberie ou jules-card" />
      </div>
      <div>
        <label for="sort">Tri</label>
        <select id="sort" name="sort">
          <option value="expiring_soon" {"selected" if sort_value == "expiring_soon" else ""}>Expiration la plus proche</option>
          <option value="expiring_far" {"selected" if sort_value == "expiring_far" else ""}>Expiration la plus lointaine</option>
          <option value="created_new" {"selected" if sort_value == "created_new" else ""}>Création la plus récente</option>
          <option value="created_old" {"selected" if sort_value == "created_old" else ""}>Création la plus ancienne</option>
          <option value="company_az" {"selected" if sort_value == "company_az" else ""}>Entreprise A→Z</option>
        </select>
      </div>
      <div style="display:flex; gap:8px; align-items:end;">
        <button type="submit">Appliquer</button>
        <a href="/admin/business">Reset</a>
      </div>
    </form>
    <div class="table-meta">{len(sorted_cards)} carte(s) affichée(s) sur {total_cards}.</div>
    <table>
      <thead>
        <tr>
          <th>Carte / entreprise</th>
          <th>Slug</th>
          <th>Plan</th>
          <th>Expiration</th>
          <th>Statut</th>
          <th>Jours restants</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {"".join(rows_html)}
      </tbody>
    </table>
  </div>
</body>
</html>"""


@router_pages.get("/admin/business", response_class=HTMLResponse, include_in_schema=False)
def business_dashboard_page(
    filter: str = Query("all"),
    q: str = Query(""),
    sort: str = Query("expiring_soon"),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_http_basic),
):
    filter_value = _normalize_filter(filter)
    sort_value = _normalize_sort(sort)
    html = _build_business_dashboard_html(
        db,
        filter_value=filter_value,
        search_query=q,
        sort_value=sort_value,
    )
    return HTMLResponse(content=html)
