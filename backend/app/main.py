# backend/app/main.py

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from starlette.staticfiles import StaticFiles

# ⬇️ Import des routes API
from routers import public, admin  # public = cartes publiques /c/{slug}, admin = API d’admin


# --- Config de base ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
# Si ton dossier "static" est à la racine du projet (comme avant sur Render) :
STATIC_DIR = BASE_DIR.parent / "static"

app = FastAPI(
    title="Maavnica SmartCard API",
    description="Backend Maavnica SmartCard (cartes publiques + admin).",
    version="2.0.0",
)


# --- CORS (pour que le front / Swagger puisse appeler l’API sans blocage) ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Tu pourras restreindre plus tard si tu veux
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Healthcheck simple -----------------------------------------------------

@app.get("/", tags=["default"])
async def root():
    """
    Petit endpoint de santé pour vérifier que l'API tourne.
    """
    return {"message": "Maavnica SmartCard API is running"}


# --- Inclusion des routers --------------------------------------------------

# Routes publiques (cartes, feedback, devis, etc.)
# → /api/public/...
app.include_router(public.router, prefix="/api/public", tags=["public"])

# Routes d’admin API (CRUD cartes, feedbacks, etc.)
# → /api/admin/...
# (le router admin a un prefix="/admin", donc chemin final = /api/admin/...)
app.include_router(admin.router, prefix="/api", tags=["admin"])


# --- Fichiers statiques & page admin ---------------------------------------

# On sert le dossier /static (CSS, JS, admin.html, etc.)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/admin", include_in_schema=False)
async def serve_admin():
    """
    Redirige /admin vers la page statique d’admin.
    Adapte le chemin si ton fichier a un autre nom / emplacement.
    """
    return RedirectResponse(url="/static/admin/index.html")
    # Si ton fichier est /static/admin.html → mets "/static/admin.html"



