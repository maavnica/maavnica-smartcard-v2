# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Routes API
from app.routers import public, cards


# --------------------------------------------------------------------
# Chemins de base
# --------------------------------------------------------------------

# .../maavnica-smartcard/backend/app
APP_DIR = Path(__file__).resolve().parent

# .../maavnica-smartcard
PROJECT_ROOT = APP_DIR.parents[1]

# .../maavnica-smartcard/backend/static
STATIC_DIR = PROJECT_ROOT / "backend" / "static"


# --------------------------------------------------------------------
# Application FastAPI
# --------------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Sécurité basique (safe)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Évite des comportements étranges en webview / QR
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"

        # Cache maîtrisé
        path = request.url.path
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
        else:
            response.headers["Cache-Control"] = "no-store"

        return response


# --------------------------------------------------------------------
# CORS (ok pour dev / prototype ; à restreindre ensuite)
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


# --------------------------------------------------------------------
# Routes simples
# --------------------------------------------------------------------
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    return {
        "message": "Maavnica SmartCard API is running",
        "admin_url": "/admin",
        "public_example": "/c/example-slug",
        "static_admin": "/static/admin/index.html",
    }


# --------------------------------------------------------------------
# Inclusion des routers API
# --------------------------------------------------------------------
# API publique (lecture)
# => /api/public/...
app.include_router(public.router, tags=["public"])

# API admin / cartes (CRUD + feedback + devis…)
# => /api/cards/...
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# --------------------------------------------------------------------
# Fichiers statiques (admin, carte publique, assets…)
# --------------------------------------------------------------------
# Monte le dossier "static" à la racine sur /static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """Sert directement l'interface d'administration statique."""
    file_path = STATIC_DIR / "admin" / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Admin UI not found")
    return FileResponse(path=str(file_path), media_type="text/html; charset=utf-8")


# IMPORTANT: les scanners QR / webviews font souvent un HEAD avant GET
@app.api_route("/c/{slug}", methods=["GET", "HEAD"], include_in_schema=False)
async def serve_public_card(slug: str):
    """
    Affiche la carte publique pour un slug donné.

    On sert toujours le template :
        static/public-card/index.html

    Le JS du template récupère le slug depuis l'URL et charge les données via API.
    """
    file_path = STATIC_DIR / "public-card" / "index.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Public card template not found")

    # FileResponse gère mieux les headers, le cache, et HEAD automatiquement
    return FileResponse(path=str(file_path), media_type="text/html; charset=utf-8")









