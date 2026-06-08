# backend/app/main.py

import logging
import os
import re
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware



# Routes API
from app.routers import public, cards
from app.schemas import _ALLOWED_VISUAL_THEMES
from app.utils.public_slug import sanitize_public_slug
from app.routers import analytics as analytics_router
from app.routers import site_analytics as site_analytics_router
from app.routers import business as business_router
from app.routers.stripe_webhook import router as stripe_webhook_router
from app.routers.checkout import router as checkout_router
from app.routers.upload import router as upload_router
from app.routers.contact import router as contact_router
from app.routers.affiliate_kit import router as affiliate_kit_router




# ------------------------------------------------------------
# Paths (robuste local + Render)
# ------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent        # .../backend/app
BACKEND_DIR = APP_DIR.parent                    # .../backend
STATIC_DIR = BACKEND_DIR / "static"             # .../backend/static

# Fallback si tu lances depuis la racine d'un mono-repo (ancien layout)
if not STATIC_DIR.exists():
    # .../maavnica-smartcard/static
    STATIC_DIR = BACKEND_DIR.parent / "static"

# Dossier uploads (avatar) : créé au démarrage pour être prêt (local + Render)
UPLOADS_DIR = STATIC_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Version query-string pour og-default.jpg (cache busting Facebook / Twitter)
OG_DEFAULT_IMAGE_VERSION = "3"

# Landing marketing (source dans le dépôt, sans dupliquer index.html dans backend/static)
LANDING_DIR = BACKEND_DIR.parent / "landing"
LANDING_INDEX = LANDING_DIR / "index.html"


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")

_public_card_log = logging.getLogger(__name__)

_PUBLIC_CARD_V3_FILES = (
    "index_v3.html",
    "v3.css",
    "v3-layout.css",
    "public-card-runtime.js",
)


def _read_card_theme_from_db(card, db) -> str:
    """Lit card_theme (ORM + repli SQL si besoin)."""
    if card is None:
        return "classic"
    raw = getattr(card, "card_theme", None)
    if raw is not None and str(raw).strip():
        theme = str(raw).strip().lower()
        if theme in ("classic", "experience"):
            return theme
    try:
        from sqlalchemy import text

        row = db.execute(
            text("SELECT card_theme FROM cards WHERE id = :cid"),
            {"cid": card.id},
        ).first()
        if row and row[0] is not None and str(row[0]).strip():
            theme = str(row[0]).strip().lower()
            if theme in ("classic", "experience"):
                return theme
    except Exception:
        _public_card_log.debug(
            "card_theme_sql_fallback_failed slug=%s",
            getattr(card, "slug", "?"),
            exc_info=True,
        )
    return "classic"


def _resolve_visual_theme(
    card,
    db=None,
    *,
    slug: Optional[str] = None,
) -> str:
    """
    Univers visuel FR (body data-theme). Défaut : wellness-soft.
    La base SQL fait foi (write_card_visual_theme) — pas l’ORM potentiellement périmé.
    """
    from app.database import read_card_visual_theme, read_card_visual_theme_by_slug

    default = "wellness-soft"
    if db is not None and slug:
        sql_slug = read_card_visual_theme_by_slug(db, slug)
        if sql_slug and sql_slug in _ALLOWED_VISUAL_THEMES:
            return sql_slug
    if db is not None and card is not None:
        cid = getattr(card, "id", None)
        if cid is not None:
            sql_id = read_card_visual_theme(db, cid)
            if sql_id and sql_id in _ALLOWED_VISUAL_THEMES:
                return sql_id
    if card is not None:
        raw = getattr(card, "visual_theme", None) if hasattr(card, "visual_theme") else None
        if raw is not None and str(raw).strip():
            theme = str(raw).strip().lower()
            if theme in _ALLOWED_VISUAL_THEMES:
                return theme
    return default


_BODY_TAG_RE = re.compile(r"<body\b([^>]*)>", re.IGNORECASE)
_BODY_DATA_THEME_ATTR_RE = re.compile(
    r'data-theme\s*=\s*["\'][^"\']*["\']',
    re.IGNORECASE,
)
# Pendant la phase de développement SmartCard, on privilégie la fraîcheur des assets au cache navigateur.
PUBLIC_ASSET_VERSION = "2026-06-02-mobile-layout-fix"

_PUBLIC_CARD_STATIC_ASSET_RE = re.compile(
    r"(/static/(?:public-card/[\w.\-]+|maavnica-consent\.js|service-worker\.js))"
    r'(?:\?v=[^"\'>\s]+)?',
    re.IGNORECASE,
)

_PUBLIC_CARD_DEV_NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _inject_public_card_visual_theme(html: str, visual_theme: str) -> str:
    """Injecte ou remplace data-theme sur <body> (valeur validée)."""
    safe = visual_theme if visual_theme in _ALLOWED_VISUAL_THEMES else "wellness-soft"
    match = _BODY_TAG_RE.search(html)
    if not match:
        return html
    attrs = match.group(1)
    if _BODY_DATA_THEME_ATTR_RE.search(attrs):
        new_attrs = _BODY_DATA_THEME_ATTR_RE.sub(
            f'data-theme="{safe}"',
            attrs,
            count=1,
        )
    else:
        new_attrs = f'{attrs.rstrip()} data-theme="{safe}"'
    return html[: match.start()] + f"<body{new_attrs}>" + html[match.end() :]


def _inject_public_card_asset_cache_version(html: str) -> str:
    """Réécrit ?v= sur tous les CSS/JS public-card (cache-bust global après déploiement)."""
    return _PUBLIC_CARD_STATIC_ASSET_RE.sub(
        rf"\1?v={PUBLIC_ASSET_VERSION}",
        html,
    )


def _is_public_card_dev_static_path(path: str) -> bool:
    """Assets SmartCard publics : pas de cache long en phase de développement."""
    return (
        path.startswith("/static/public-card/")
        or path == "/static/maavnica-consent.js"
        or path == "/static/service-worker.js"
    )


def _log_public_card_v3_assets() -> None:
    pub = STATIC_DIR / "public-card"
    for name in _PUBLIC_CARD_V3_FILES:
        path = pub / name
        if not path.is_file():
            _public_card_log.warning("PUBLIC_CARD_V3_ASSET_MISSING file=%s", path)


def _fr_public_card_seo_strings(seo: Optional[Dict[str, Any]]) -> tuple[str, str, str, str]:
    """Titres et descriptions FR pour le HTML initial (crawlers sans exécution JS)."""
    if not seo:
        return (
            "Maavnica SmartCard – Carte publique",
            "Carte professionnelle Maavnica. Contact rapide, avis clients et recommandations.",
            "Maavnica SmartCard",
            "Contact direct, avis clients et recommandation simplifiée.",
        )
    name = (seo.get("name") or "").strip()
    job = (seo.get("job") or "").strip()
    city = (seo.get("city") or "").strip()

    if job and city and name:
        title = f"{job} à {city} | {name}"
        meta_desc = (
            f"{name}, {job} à {city}. Contact rapide, avis clients et recommandations."
        )
        og_title = f"{job} à {city} recommandé par ses clients | {name}"
    elif job and name:
        title = f"{job} | {name}"
        meta_desc = f"{name}, {job}. Contact rapide, avis clients et recommandations."
        og_title = f"{job} recommandé par ses clients | {name}"
    elif name and city:
        title = f"{name} | Maavnica"
        meta_desc = f"{name} à {city}. Contact rapide, avis clients et recommandations."
        og_title = f"{name} | Maavnica"
    elif name:
        title = f"{name} | Maavnica"
        meta_desc = f"{name}. Contact rapide, avis clients et recommandations."
        og_title = f"{name} | Maavnica"
    else:
        title = "Maavnica SmartCard – Carte publique"
        meta_desc = (
            "Carte professionnelle Maavnica. Contact rapide, avis clients et recommandations."
        )
        og_title = "Maavnica SmartCard"

    if name:
        og_desc = (
            f"Découvrez {name}. Contact direct, avis clients et recommandation simplifiée."
        )
    else:
        og_desc = (
            "Découvrez cette carte professionnelle. Contact direct, avis clients "
            "et recommandation simplifiée."
        )

    return title, meta_desc, og_title, og_desc


def _inject_fr_public_card_head(html: str, seo: Optional[Dict[str, Any]]) -> str:
    title, meta_desc, og_title, og_desc = _fr_public_card_seo_strings(seo)
    html = re.sub(
        r"<title>[^<]*</title>",
        "<title>" + escape(title, quote=False) + "</title>",
        html,
        count=1,
    )
    html = re.sub(
        r'<meta name="description" content="[^"]*"\s*/>',
        '<meta name="description" content="' + escape(meta_desc, quote=True) + '" />',
        html,
        count=1,
    )
    html = re.sub(
        r'<meta property="og:title" content="[^"]*"\s*/>',
        '<meta property="og:title" content="' + escape(og_title, quote=True) + '" />',
        html,
        count=1,
    )
    html = re.sub(
        r'<meta property="og:description" content="[^"]*"\s*/>',
        '<meta property="og:description" content="' + escape(og_desc, quote=True) + '" />',
        html,
        count=1,
    )
    return html


def _public_card_base_url(request: Request) -> str:
    """URL publique absolue (prod, staging, local) — priorité à PUBLIC_BASE_URL."""
    explicit = (os.environ.get("PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if explicit:
        return explicit
    forwarded_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    scheme = forwarded_proto or request.url.scheme or "http"
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(
        ","
    )[0].strip()
    if not host:
        return str(request.base_url).rstrip("/")
    return f"{scheme}://{host}"


def _absolute_public_url(base: str, path_or_url: str) -> str:
    """Rend une URL d’asset absolue pour OG / Twitter (avatar relatif ou CDN)."""
    raw = (path_or_url or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return raw
    if raw.startswith("//"):
        return ("https:" if "https" in (base or "").lower() else "http:") + raw
    path = raw if raw.startswith("/") else "/" + raw
    return f"{base.rstrip('/')}{path}"


def _fr_public_og_image_url(base_url: str, slug_norm: str, card: Optional[Any]) -> str:
    """Image OG : arnaud-huard dédié, demo2 = visuel marketing (pas l’avatar), sinon avatar, sinon défaut."""
    slug_l = (slug_norm or "").strip().lower()
    if slug_l == "arnaud-huard":
        return f"{base_url}/static/og-arnaud-huard.jpg"
    if slug_l == "demo2":
        return f"{base_url}/static/og-default.jpg?v={OG_DEFAULT_IMAGE_VERSION}"
    avatar = ""
    if card is not None:
        avatar = (getattr(card, "avatar_url", None) or "").strip()
    if avatar:
        return _absolute_public_url(base_url, avatar)
    return f"{base_url}/static/og-default.jpg?v={OG_DEFAULT_IMAGE_VERSION}"


def _inject_fr_social_bundle(
    html: str,
    *,
    page_url: str,
    og_image_url: str,
    og_title: str,
    og_desc: str,
) -> str:
    """Une seule passe : canonical, OG image/url/type, Twitter — alignés sur og:title / og:description."""
    og_title_e = escape(og_title, quote=True)
    og_desc_e = escape(og_desc, quote=True)
    img_e = escape(og_image_url, quote=True)
    url_e = escape(page_url, quote=True)
    block = (
        f'  <link rel="canonical" href="{url_e}" />\n'
        f'  <meta property="og:image" id="seo-og-image" content="{img_e}" />\n'
        f'  <meta property="og:image:width" content="1200" />\n'
        f'  <meta property="og:image:height" content="630" />\n'
        f'  <meta property="og:type" content="website" />\n'
        f'  <meta property="og:url" content="{url_e}" />\n'
        f'  <meta name="twitter:card" content="summary_large_image" />\n'
        f'  <meta name="twitter:title" content="{og_title_e}" />\n'
        f'  <meta name="twitter:description" content="{og_desc_e}" />\n'
        f'  <meta name="twitter:image" content="{img_e}" />\n'
    )
    if "</head>" in html:
        return html.replace("</head>", block + "</head>", 1)
    return html


@app.on_event("startup")
def _create_db_tables():
    """Crée les tables manquantes (ex. analytics) sans migration lourde."""
    import app.models  # noqa: F401 — enregistre les modèles sur le metadata
    from app.database import (
        Base,
        engine,
        ensure_card_owner_share_key_column,
        ensure_card_hero_columns,
        ensure_card_identity_columns,
        ensure_enable_recommendation_column,
        ensure_quote_recommendation_columns,
        ensure_recommendation_code_column,
        ensure_recommendation_event_display_columns,
        ensure_card_plan_columns,
        ensure_card_region_column,
        ensure_card_city_column,
        ensure_card_theme_column,
        ensure_visual_theme_column,
    )

    Base.metadata.create_all(bind=engine)
    ensure_card_owner_share_key_column()
    ensure_card_hero_columns()
    ensure_card_identity_columns()
    ensure_enable_recommendation_column()
    ensure_recommendation_code_column()
    ensure_card_plan_columns()
    ensure_card_region_column()
    ensure_card_city_column()
    ensure_card_theme_column()
    ensure_visual_theme_column()
    ensure_quote_recommendation_columns()
    ensure_recommendation_event_display_columns()
    _log_public_card_v3_assets()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Cache : anti-cache pour les assets public-card (phase dev SmartCard) ;
        # immutable pour les autres statiques ; no-store pour le HTML /c/{slug} et l’API.
        path = request.url.path
        if _is_public_card_dev_static_path(path):
            for header, value in _PUBLIC_CARD_DEV_NO_CACHE_HEADERS.items():
                response.headers[header] = value
        elif path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        else:
            response.headers["Cache-Control"] = "no-store"

        return response


# CORS (ok pour proto/dev ; à restreindre ensuite)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://maavnica.com",
        "https://www.maavnica.com",
        "https://smartcard.maavnica.com",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)
app.add_middleware(SecurityHeadersMiddleware)


# ------------------------------------------------------------
# Landing marketing (racine)
# ------------------------------------------------------------
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    """Page d’accueil : landing/index.html (même fichier que dans le dossier landing/ du repo)."""
    if not LANDING_INDEX.is_file():
        raise HTTPException(status_code=404, detail="landing/index.html introuvable")
    return FileResponse(path=str(LANDING_INDEX), media_type="text/html; charset=utf-8")


# ------------------------------------------------------------
# API routers
# ------------------------------------------------------------
# API publique (lecture)
app.include_router(public.router, tags=["public"])

# API admin / cartes (CRUD + feedback + devis…)
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])

# Upload avatar (admin)
app.include_router(upload_router, prefix="/api/upload", tags=["upload"])

# Contact landing (SmartCard)
app.include_router(contact_router)

# Kit affilié (outil interne, clé admin)
app.include_router(affiliate_kit_router)

# Analytics (API + page /admin/analytics)
app.include_router(analytics_router.router_api)
app.include_router(analytics_router.router_pages)
# Analytics site / landing (isolé des cartes)
app.include_router(site_analytics_router.router_api)
app.include_router(site_analytics_router.router_pages)
app.include_router(business_router.router_pages)


# ------------------------------------------------------------
# Static files
# ------------------------------------------------------------
if not STATIC_DIR.exists():
    # Important : on échoue clairement si Render ne voit pas les fichiers
    raise RuntimeError(f"STATIC_DIR not found: {STATIC_DIR}")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ------------------------------------------------------------
# Admin UI
# ------------------------------------------------------------
@app.api_route("/admin", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_admin():
    """Sert directement l'interface d'administration statique."""
    file_path = STATIC_DIR / "admin" / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(path=str(file_path), media_type="text/html; charset=utf-8")


# ------------------------------------------------------------
# Public card (QR)
# ------------------------------------------------------------
@app.api_route("/c/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_public_card(request: Request, slug: str):
    """
    Affiche la carte publique pour un slug donné.
    Le template est statique ; le JS récupère le slug via l'URL et charge les données via l'API.
    Choix FR vs LATAM : colonne Card.region (voir aussi ensure_card_region_column au startup).
    """
    from sqlalchemy import func

    from app.database import SessionLocal
    from app.models import Card

    path_classic = STATIC_DIR / "public-card" / "index.html"
    path_latam = STATIC_DIR / "public-card" / "index_latam.html"
    file_path = path_classic
    slug_norm = sanitize_public_slug(slug)
    card_region_log = "n/a"
    template_served = "classic"
    seo_fr: Optional[Dict[str, Any]] = None
    fr_db_card: Optional[Card] = None
    resolved_visual_theme = "wellness-soft"
    visual_theme_orm: Optional[str] = None
    visual_theme_sql_slug: Optional[str] = None
    visual_theme_sql_id: Optional[str] = None
    card_id_log: Optional[int] = None

    db = SessionLocal()
    try:
        card = (
            db.query(Card)
            .filter(func.lower(Card.slug) == slug_norm.lower())
            .first()
        )
        if slug_norm and card is not None and slug != slug_norm:
            target = f"/c/{slug_norm}"
            q = request.url.query
            if q:
                target = f"{target}?{q}"
            return RedirectResponse(url=target, status_code=301)
        if card:
            card_region_log = (getattr(card, "region", None) or "fr").strip().lower()
            fr_db_card = card

            # Architecture figée: LATAM dédié, tout le reste sur base FR classique.
            if card_region_log == "latam":
                file_path = path_latam
                template_served = "latam"
            else:
                template_served = "classic"

            dn = (getattr(card, "display_name", None) or "").strip()
            cn = (getattr(card, "company_name", None) or "").strip()
            seo_fr = {
                "name": dn or cn,
                "job": (getattr(card, "job_title", None) or "").strip(),
                "city": (getattr(card, "city", None) or "").strip(),
            }
            card_id_log = card.id
            raw_orm = (
                getattr(card, "visual_theme", None)
                if hasattr(card, "visual_theme")
                else None
            )
            visual_theme_orm = (
                str(raw_orm).strip().lower() if raw_orm is not None else None
            )
            from app.database import read_card_visual_theme, read_card_visual_theme_by_slug

            visual_theme_sql_slug = read_card_visual_theme_by_slug(db, slug_norm)
            visual_theme_sql_id = read_card_visual_theme(db, card.id)
            resolved_visual_theme = _resolve_visual_theme(
                card, db, slug=slug_norm
            )
    finally:
        db.close()

    injected_visual_theme = (
        resolved_visual_theme
        if resolved_visual_theme in _ALLOWED_VISUAL_THEMES
        else "wellness-soft"
    )

    # Log diagnostic (Render) : valeurs ORM vs SQL vs injection finale.
    _public_card_log.warning(
        "PUBLIC_CARD_RENDER slug=%s card_id=%s region=%s template=%s "
        "visual_theme_orm=%s visual_theme_sql_slug=%s visual_theme_sql_id=%s "
        "visual_theme_resolved=%s visual_theme_injected=%s",
        slug_norm,
        card_id_log,
        card_region_log,
        file_path.name,
        visual_theme_orm,
        visual_theme_sql_slug,
        visual_theme_sql_id,
        resolved_visual_theme,
        injected_visual_theme,
    )

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Public card template not found")

    if template_served == "latam":
        return FileResponse(path=str(file_path), media_type="text/html; charset=utf-8")

    # Thème visuel toujours injecté ; SEO/OG en best-effort (ne pas renvoyer le HTML brut).
    html = file_path.read_text(encoding="utf-8")
    html = _inject_public_card_visual_theme(html, injected_visual_theme)
    html = _inject_public_card_asset_cache_version(html)
    try:
        html = _inject_fr_public_card_head(html, seo_fr)
        _, _, og_title, og_desc = _fr_public_card_seo_strings(seo_fr)
        base_url = _public_card_base_url(request)
        page_url = f"{base_url}/c/{slug_norm}"
        og_image_url = _fr_public_og_image_url(base_url, slug_norm, fr_db_card)
        html = _inject_fr_social_bundle(
            html,
            page_url=page_url,
            og_image_url=og_image_url,
            og_title=og_title,
            og_desc=og_desc,
        )
    except Exception:
        _public_card_log.exception("public_card og_injection_failed slug=%s", slug_norm)
    return HTMLResponse(
        content=html,
        media_type="text/html; charset=utf-8",
        headers=_PUBLIC_CARD_DEV_NO_CACHE_HEADERS,
    )









