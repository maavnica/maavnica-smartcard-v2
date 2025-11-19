from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .routers import public, cards
from .database import Base, engine

# -------------------------------------------------------------------
# CONFIG SIMPLE POUR LE LOGIN ADMIN
# -------------------------------------------------------------------
ADMIN_PASSWORD = "maavnica2025"  # à changer si tu veux
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"  # chaîne longue = mieux


# -------------------------------------------------------------------
# CREATION APP + DB
# -------------------------------------------------------------------
# Création des tables au démarrage (une fois, si elles n'existent pas)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Maavnica SmartCard API", version="1.0.0")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import cards  # et les autres routers si tu en as
# ...

app = FastAPI(
    title="Maavnica SmartCard API",
)

# 👇 Autoriser le front Render + localhost
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://maavnica-smartcard-v2-1.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# routes
app.include_router(cards.router, prefix="/api")


# Middleware de session (pour savoir si l'admin est connecté)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Chemins de base
BASE_DIR = Path(__file__).resolve().parents[2]   # dossier "maavnica-smartcard"
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Fichiers statiques (pour les QR codes notamment)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routes API
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# -------------------------------------------------------------------
# ROUTE DE TEST
# -------------------------------------------------------------------
@app.get("/")
def read_root():
  return {"message": "Maavnica SmartCard API is running"}


# -------------------------------------------------------------------
# LOGIN ADMIN SIMPLE
# -------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page():
    html = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
      <meta charset="UTF-8" />
      <title>Connexion admin – Maavnica SmartCard</title>
      <meta name="viewport" content="width=device-width, initial-scale=1" />
    </head>
    <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background:#F3F4F6; margin:0;">
      <div style="max-width:360px; margin:80px auto; background:white; padding:24px; border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,0.12);">
        <h2 style="margin-top:0; margin-bottom:8px; font-size:22px;">Connexion admin</h2>
        <p style="margin-top:0; margin-bottom:16px; color:#6B7280; font-size:14px;">
          Entrez le mot de passe pour accéder à l'espace d'administration.
        </p>
        <form method="POST">
          <input type="password" name="password" placeholder="Mot de passe"
                 style="width:100%; padding:10px 12px; border-radius:8px; border:1px solid #D1D5DB; font-size:14px; box-sizing:border-box; margin-bottom:12px;" />
          <button type="submit"
                  style="width:100%; padding:10px 16px; border:none; border-radius:999px; background:#2563EB; color:white; font-weight:600; cursor:pointer;">
            Se connecter
          </button>
        </form>
      </div>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.post("/login")
def login(password: str = Form(...), request: Request = None):
    if password == ADMIN_PASSWORD:
        # On marque l'utilisateur comme connecté dans la session
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)

    # Mot de passe incorrect -> on revient sur la page de login
    return RedirectResponse("/login", status_code=302)


# -------------------------------------------------------------------
# PAGES FRONT
# -------------------------------------------------------------------
# Servir la SmartCard publique
@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card_page(slug: str):
    """
    Renvoie la page HTML publique. Le JS récupère le slug depuis l'URL.
    """
    html_path = FRONTEND_DIR / "public-card" / "index.html"
    return FileResponse(str(html_path))


# Servir le mini back-office (protégé par login)
@app.get("/admin", response_class=HTMLResponse)
def serve_admin(request: Request):
    # Si pas connecté -> redirection vers /login
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)

    html_path = FRONTEND_DIR / "admin" / "index.html"
    return FileResponse(str(html_path))


# Landing page Maavnica SmartCard
@app.get("/smartcard", response_class=HTMLResponse)
def smartcard_landing():
    html_path = FRONTEND_DIR / "landing" / "index.html"
    return FileResponse(str(html_path))

