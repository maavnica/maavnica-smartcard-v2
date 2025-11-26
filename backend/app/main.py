from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

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
    "https://maavnica-smartcard-client.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sessions (cookies signés)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)


# -------------------------------------------------------------------
# STATIC FILES
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

# /static -> pour thèmes, qrcodes, CSS/JS admin, etc.
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Routers API
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])


# -------------------------------------------------------------------
# ROOT
# -------------------------------------------------------------------
@app.get("/", response_class=JSONResponse)
def root():
    return {"message": "Maavnica SmartCard API is running"}


# -------------------------------------------------------------------
# LOGIN PAGE
# -------------------------------------------------------------------
LOGIN_HTML = """
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
def login_page(request: Request):
    # Si déjà loggé, on renvoie vers /admin
    if request.session.get("is_admin"):
        return RedirectResponse("/admin", status_code=302)
    return HTMLResponse(LOGIN_HTML)


@app.post("/login")
def login(password: str = Form(...), request: Request = None):
    if password == ADMIN_PASSWORD:
        # on pose le flag dans la session
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)

    # mot de passe faux -> on efface l’éventuelle session
    request.session.pop("is_admin", None)
    return RedirectResponse("/login", status_code=302)


@app.get("/logout")
def logout(request: Request):
    request.session.pop("is_admin", None)
    return RedirectResponse("/login", status_code=302)


# -------------------------------------------------------------------
# FRONTEND PAGES
# -------------------------------------------------------------------
@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card(slug: str):
    """
    Délivre la carte publique. Le HTML est générique et charge les données
    via /api/public/cards/{slug}.
    """
    card_html = FRONTEND_DIR / "public-card" / "index.html"
    if not card_html.exists():
        raise HTTPException(status_code=500, detail="Fichier de carte introuvable.")
    return FileResponse(str(card_html))


@app.get("/admin", response_class=HTMLResponse)
def serve_admin(request: Request):
    """
    Page d'admin PROTÉGÉE par mot de passe.
    Si 'is_admin' n'est pas présent dans la session, on redirige vers /login.
    """
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)

    html_path = FRONTEND_DIR / "admin" / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="Admin HTML introuvable.")
    return FileResponse(str(html_path))


