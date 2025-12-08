# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Routes API
from app.routers import public, cards


# --------------------------------------------------------------------
# Chemins de base
# --------------------------------------------------------------------

# .../maavnica-smartcard/backend/app
APP_DIR = Path(__file__).resolve().parent

# .../maavnica-smartcard
PROJECT_ROOT = APP_DIR.parents[1]

# .../maavnica-smartcard/static
STATIC_DIR = PROJECT_ROOT / "static"


# --------------------------------------------------------------------
# Application FastAPI
# --------------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")


# --------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # à restreindre plus tard si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------
# Routes simples
# --------------------------------------------------------------------
@app.get("/", include_in_schema=False)
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
# (si public.py expose d'autres endpoints API)
app.include_router(public.router, prefix="", tags=["public"])

# Gestion des cartes (création, update, feedback, devis…)
# => /api/cards/...
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# --------------------------------------------------------------------
# Fichiers statiques (admin, carte publique, assets…)
# --------------------------------------------------------------------
# Monte le dossier "static" à la racine sur /static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """
    Redirige /admin vers l'interface d'administration statique.

    Fichier :
        static/admin/index.html
    """
    return RedirectResponse(url="/static/admin/index.html")


@app.get("/c/{slug}", include_in_schema=False)
async def serve_public_card(slug: str):
    """
    Affiche la carte publique pour un slug donné.

    On sert toujours le même fichier :
        static/public-card/index.html

    Le JS dans ce fichier peut utiliser le slug présent dans l'URL
    (window.location.pathname) pour appeler l'API :
        GET /api/cards/by-slug/{slug}
    """
    file_path = STATIC_DIR / "public-card" / "index.html"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Public card template not found")

    html = file_path.read_text(encoding="utf-8")
    return HTMLResponse(html)







