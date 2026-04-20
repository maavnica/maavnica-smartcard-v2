# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware



# Routes API
from app.routers import public, cards
from app.routers import analytics as analytics_router
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

# Landing marketing (source dans le dépôt, sans dupliquer index.html dans backend/static)
LANDING_DIR = BACKEND_DIR.parent / "landing"
LANDING_INDEX = LANDING_DIR / "index.html"


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")


@app.on_event("startup")
def _create_db_tables():
    """Crée les tables manquantes (ex. analytics) sans migration lourde."""
    import app.models  # noqa: F401 — enregistre les modèles sur le metadata
    from app.database import (
        Base,
        engine,
        ensure_card_hero_columns,
        ensure_card_identity_columns,
        ensure_enable_recommendation_column,
        ensure_recommendation_code_column,
    )

    Base.metadata.create_all(bind=engine)
    ensure_card_hero_columns()
    ensure_card_identity_columns()
    ensure_enable_recommendation_column()
    ensure_recommendation_code_column()


app.include_router(public.router)
app.include_router(cards.router)
app.include_router(stripe_webhook_router)
app.include_router(checkout_router)



class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Cache: immutable pour les assets statiques, no-store pour le reste
        if request.url.path.startswith("/static/"):
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
async def serve_public_card(slug: str):
    """
    Affiche la carte publique pour un slug donné.
    Le template est statique ; le JS récupère le slug via l'URL et charge les données via l'API.
    """
    file_path = STATIC_DIR / "public-card" / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Public card template not found")
    return FileResponse(path=str(file_path), media_type="text/html; charset=utf-8")









