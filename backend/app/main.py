from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from .routers import public, cards
from .database import Base, engine, get_db, SessionLocal
from . import models, schemas


# =============================================================
#  CONFIG ADMIN
# =============================================================

ADMIN_PASSWORD = "maavnica2025"  # change si besoin
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"


# =============================================================
#  INIT BDD
# =============================================================

Base.metadata.create_all(bind=engine)


def init_default_user():
    """Crée un utilisateur owner si aucun n'existe."""
    db = SessionLocal()
    try:
        existing = db.query(models.User).first()
        if not existing:
            user = models.User(
                email="owner@maavnica.com",
                password_hash="changeme"
            )
            db.add(user)
            db.commit()
    finally:
        db.close()


def ensure_theme_column():
    """
    Ajoute la colonne 'theme' si elle n'existe pas déjà.
    Utilise un ALTER TABLE silencieux.
    """
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE cards ADD COLUMN theme VARCHAR(50) NOT NULL DEFAULT 'apple';"
            ))
    except Exception:
        # colonne existe déjà → on ignore
        pass


# Lancements auto
init_default_user()
ensure_theme_column()


# =============================================================
#  APPLICATION FASTAPI
# =============================================================

app = FastAPI(
    title="Maavnica SmartCard API",
    version="1.0.0",
)


# =============================================================
#  CORS
# =============================================================

origins = [
    "http://localhost",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
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


# =============================================================
#  SESSIONS (ADMIN)
# =============================================================

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# =============================================================
#  STATIC & FRONT
# =============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# =============================================================
#  ROUTES API
# =============================================================

app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# =============================================================
#  ROUTE DE TEST
# =============================================================

@app.get("/")
def read_root():
    return {"message": "Maavnica SmartCard API is running"}


# =============================================================
#  LOGIN ADMIN
# =============================================================

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
    <body style="font-family: system-ui; background:#F3F4F6; margin:0;">
      <div style="max-width:360px; margin:80px auto; background:white;
           padding:24px; border-radius:16px; box-shadow:0 10px 30px rgba(15,23,42,0.12);">
        <h2 style="margin:0 0 8px;">Connexion admin</h2>
        <p style="margin:0 0 16px; color:#6B7280; font-size:14px;">
          Entrez le mot de passe pour accéder à l'espace d'administration.
        </p>
        <form method="POST">
          <input type="passwor





