# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# 👉 Routes API (on n’utilise plus "admin" ici)
from app.routers import public, cards

# --------------------------------------------------------------------
# Config de base
# --------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Maavnica SmartCard API")

# CORS (à ajuster plus tard si besoin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # on ouvrira plus finement ensuite
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------

# Petite route de test (racine)
@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Maavnica SmartCard API is running"}

# Routes publiques (ex : /c/{slug})
app.include_router(public.router, prefix="", tags=["public"])

# Routes API pour gérer les cartes (POST /api/cards, etc.)
app.include_router(cards.router, prefix="/api", tags=["cards"])

# --------------------------------------------------------------------
# Fichiers statiques (admin front, etc.)
# --------------------------------------------------------------------

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """
    Redirige /admin vers la page d’admin statique.
    Si ton fichier est ailleurs, adapte simplement l’URL.
    """
    return RedirectResponse(url="/static/admin/index.html")
    # Exemple alternatif :
    # return RedirectResponse(url="/static/admin.html")



