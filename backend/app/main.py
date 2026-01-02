# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

# Routes API
from app.routers import public, cards


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


# ------------------------------------------------------------
# App
# ------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


# ------------------------------------------------------------
# Health / Root
# ------------------------------------------------------------
@app.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root():
    return {
        "message": "Maavnica SmartCard API is running",
        "admin_url": "/admin",
        "static_admin": "/static/admin/index.html",
        "public_example": "/c/example-slug",
    }


# ------------------------------------------------------------
# API routers
# ------------------------------------------------------------
# API publique (lecture)
app.include_router(public.router, tags=["public"])

# API admin / cartes (CRUD + feedback + devis…)
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


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









