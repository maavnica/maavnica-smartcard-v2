from __future__ import annotations

from html import escape
from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card
from app.routers.cards import _computed_status, _days_remaining
from app.utils.admin_auth import require_admin_http_basic

router_pages = APIRouter(tags=["business"])

_NON_EXPIRING_PLANS = {"demo", "lifetime"}


def _format_plan(plan_type: str | None) -> str:
    return (plan_type or "demo").strip().lower()


def _format_expiration_label(plan_type: str, expires_at) -> str:
    if plan_type in _NON_EXPIRING_PLANS:
        return "Sans expiration"
    if not expires_at:
        return "—"
    return expires_at.strftime("%d/%m/%Y")


def _build_business_dashboard_html(db: Session) -> str:
    cards = db.query(Card).order_by(Card.created_at.desc()).all()

    total_cards = len(cards)
    active_cards = 0
    expired_cards = 0
    active_trials = 0
    demo_lifetime_cards = 0
    expiring_7 = 0
    expiring_30 = 0

    rows_html: List[str] = []
    for card in cards:
        plan_type = _format_plan(card.plan_type)
        status = _computed_status(card)
        days_remaining = _days_remaining(card)
        company_name = card.company_name or "—"
        expiration_label = _format_expiration_label(plan_type, card.expires_at)

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
            "Aucune carte en base.</td></tr>"
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
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_http_basic),
):
    html = _build_business_dashboard_html(db)
    return HTMLResponse(content=html)
