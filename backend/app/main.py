from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .routers import public, cards
from .database import Base, engine, SessionLocal
from . import models


# ============================================================
# CONFIG ADMIN (simple, pour prototype)
# ============================================================

ADMIN_PASSWORD = "maavnica2025"
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"


# ============================================================
# INIT BASE DE DONNÉES
# ============================================================

# Création des tables si elles n'existent pas
Base.metadata.create_all(bind=engine)


def init_default_user() -> None:
    """
    Crée un utilisateur "owner" par défaut si la table users est vide.
    Utile pour lier les cartes à user_id = 1.
    """
    db = SessionLocal()
    try:
        existing = db.query(models.User).first()
        if not existing:
            user = models.User(
                email="owner@maavnica.com",
                password_hash="changeme",  # à remplacer plus tard par un vrai hash
            )
            db.add(user)
            db.commit()
            print("[INIT] Default user created with email=owner@maavnica.com")
        else:
            print("[INIT] Default user already exists (id=%s)" % existing.id)
    finally:
        db.close()


init_default_user()


# ============================================================
# INSTANCE FASTAPI
# ============================================================

app = FastAPI(
    title="Maavnica SmartCard API",
    version="1.0.0",
)


# ============================================================
# CORS
# ============================================================

origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:8000",
    "https://maavnica-smartcard-v2.onrender.com",
    "https://maavnica-smartcard-v2-1.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessions pour l'authentification admin
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# ============================================================
# DOSSIERS STATIC & FRONTEND
# ============================================================

# backend/app/main.py -> parents[2] = dossier racine du projet
BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

# S'assure que le dossier static existe (sinon FastAPI râle)
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Fichiers statiques (CSS des thèmes, images, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# Routers API
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# ============================================================
# ROUTE ROOT (PING)
# ============================================================

@app.get("/")
def root():
    return {"message": "Maavnica SmartCard API is running"}


# ============================================================
# LOGIN ADMIN (SIMPLE MOT DE PASSE)
# ============================================================

LOGIN_PAGE_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>Connexion admin – Maavnica SmartCard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
</head>
<body style="font-family: system-ui; background:#F3F4F6; margin:0;">
  <div style="max-width:360px; margin:80px auto; background:white;
       padding:24px; border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,0.12);">
    <h2 style="margin:0 0 8px;">Connexion admin</h2>
    <p style="margin:0 0 16px; color:#6B7280; font-size:14px;">
      Entrez le mot de passe pour accéder à l'espace d'administration.
    </p>
    <form method="POST">
      <input type="password" name="password" placeholder="Mot de passe"
        style="width:100%; padding:10px; border-radius:8px; border:1px solid #D1D5DB; margin-bottom:12px;" />
      <button type="submit"
        style="width:100%; padding:10px; border:none; border-radius:999px;
               background:#2563EB; color:white; font-weight:600;">
        Se connecter
      </button>
    </form>
  </div>
</body>
</html>
"""


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(LOGIN_PAGE_HTML)


@app.post("/login")
def login(password: str = Form(...), request: Request = None):
    if password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/login", status_code=302)


# ============================================================
# PAGES FRONTEND (ADMIN + CARTE PUBLIQUE)
# ============================================================

@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card(slug: str):
    """
    Sert la page publique de la SmartCard.
    Le slug est utilisé côté JS pour appeler /api/public/cards/{slug}.
    """
    html_path = FRONTEND_DIR / "public-card" / "index.html"
    return FileResponse(str(html_path))


@app.get("/admin", response_class=HTMLResponse)
def serve_admin(request: Request):
    """
    Sert l'interface d'administration (une seule page statique).
    Protection simple par session.
    """
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)

    html_path = FRONTEND_DIR / "admin" / "index.html"
    return FileResponse(str(html_path))

