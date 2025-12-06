# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

# Import des routes API (à adapter si besoin)
from app.routers import public, cards


# --------------------------------------------------------------------
# Chemins de base
# --------------------------------------------------------------------

# Chemin du dossier app/  ->  .../maavnica-smartcard/backend/app
APP_DIR = Path(__file__).resolve().parent

# Racine du projet où se trouvent backend/, static/, landing/, etc.
# -> .../maavnica-smartcard
PROJECT_ROOT = APP_DIR.parents[1]

# Dossier static/ à la racine du projet
STATIC_DIR = PROJECT_ROOT / "static"


# --------------------------------------------------------------------
# Création de l'application FastAPI
# --------------------------------------------------------------------
app = FastAPI(title="Maavnica SmartCard API")


# --------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # on pourra restreindre plus tard
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
        "static_example": "/static/admin/html/index.html",
    }


# --------------------------------------------------------------------
# Inclusion des routers API
# --------------------------------------------------------------------
# Routes publiques (URL de cartes /c/{slug}, etc.)
app.include_router(public.router, prefix="", tags=["public"])

# Routes de gestion des cartes (création, liste…)
app.include_router(cards.router, prefix="/api", tags=["cards"])


# --------------------------------------------------------------------
# Fichiers statiques (admin, assets…)
# --------------------------------------------------------------------

# Monte le dossier "static" de la racine sur l’URL /static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """
    Redirige /admin vers l'interface admin statique.

    Fichier attendu :
        static/admin/index.html
    """
    return RedirectResponse(url="/static/admin/index.html")






