# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# Routes API
from app.routers import public, cards

# --------------------------------------------------------------------
# Chemins de base
# --------------------------------------------------------------------

# /opt/render/project/src/backend/app
BASE_DIR = Path(__file__).resolve().parent

# /opt/render/project/src  (racine du projet)
PROJECT_ROOT = BASE_DIR.parent.parent

# /opt/render/project/src/static  (là où se trouve ton dossier "static")
STATIC_DIR = PROJECT_ROOT / "static"

app = FastAPI(title="Maavnica SmartCard API")

# --------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # on affinera plus tard si besoin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Maavnica SmartCard API is running"}

# Routes publiques (ex : /c/{slug})
app.include_router(public.router, prefix="", tags=["public"])

# Routes API pour gérer les cartes (POST /api/cards, GET /api/cards/{slug}, etc.)
app.include_router(cards.router, prefix="/api", tags=["cards"])

# --------------------------------------------------------------------
# Fichiers statiques (front admin, etc.)
# --------------------------------------------------------------------

# Monte le dossier static/ à l’URL /static
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """
    Redirige /admin vers la page d’admin statique.
    Vérifie que ton fichier existe bien sous static/admin/index.html.
    """
    return RedirectResponse(url="/static/admin/index.html")




