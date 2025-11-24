from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text  # pour exécuter du SQL brut

from .routers import public, cards
from .database import Base, engine, get_db, SessionLocal
from . import models, schemas


# -------------------------------------------------------------------
# CONFIG ADMIN
# -------------------------------------------------------------------
ADMIN_PASSWORD = "maavnica2025"
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"


# -------------------------------------------------------------------
# INIT DB
# -------------------------------------------------------------------
Base.metadata.create_all(bind=engine)


def init_default_user():
    """Crée l'utilisateur owner@maavnica.com si la table users est vide."""
    db = SessionLocal()
    try:
        existing = db.query(models.User).first()
        if not existing:
            user = models.User(
                email="owner@maavnica.com",
                password_hash="changeme",
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


init_default_user()


# -------------------------------------------------------------------
# FASTAPI INSTANCE
# -------------------------------------------------------------------
app = FastAPI(
    title="Maavnica SmartCard API",
    version="1.0.0",
)


# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
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

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# -------------------------------------------------------------------
# STATIC FILES
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers API
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# -------------------------------------------------------------------
# ROUTE TEMPORAIRE : FIX TABLE CARDS (Render Free, pas de console SQL)
# -------------------------------------------------------------------
@app.get("/__fix/recreate-cards-table")
def recreate_cards_table(db: Session = Depends(get_db)):
    """
    ⚠️ Route TEMPORAIRE pour corriger l'erreur "column cards.theme does not exist".
    - Supprime la table cards si elle existe
    - Recrée les tables selon models.py

    À utiliser UNE FOIS, puis à supprimer du code.
    """
    try:
        # On supprime la table cards si présente
        db.execute(text("DROP TABLE IF EXISTS cards CASCADE;"))
        db.commit()
    except Exception as e:
        db.rollback()
        return {"status": "error", "details": str(e)}

    # On recrée les tables manquantes d'après les modèles
    Base.metadata.create_all(bind=engine)

    return {
        "status": "ok",
        "message": "Table 'cards' recréée avec les bonnes colonnes depuis models.py.",
    }


# -------------------------------------------------------------------
# ROOT
# -------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Maavnica SmartCard API is running"}


# -------------------------------------------------------------------
# LOGIN PAGE
# -------------------------------------------------------------------
@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse(
        """
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
    )


@app.post("/login")
def login(password: str = Form(...), request: Request = None):
    if password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/login", status_code=302)


# -------------------------------------------------------------------
# FRONTEND PAGES
# -------------------------------------------------------------------
@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card(slug: str):
    """Page publique de la SmartCard (/c/{slug})."""
    return FileResponse(str(FRONTEND_DIR / "public-card" / "index.html"))


@app.get("/admin", response_class=HTMLResponse)
def serve_admin(request: Request):
    """Mini back-office protégé par login simple."""
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)

    html_path = FRONTEND_DIR / "admin" / "index.html"
    return FileResponse(str(html_path))

