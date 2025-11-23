from pathlib import Path

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session

from .routers import public, cards
from .database import Base, engine, get_db, SessionLocal
from . import models, schemas

# -------------------------------------------------------------------
# CONFIG SIMPLE POUR LE LOGIN ADMIN
# -------------------------------------------------------------------
ADMIN_PASSWORD = "maavnica2025"  # à changer si tu veux
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"

# -------------------------------------------------------------------
# CREATION APP + DB
# -------------------------------------------------------------------
Base.metadata.create_all(bind=engine)


# -------------------------------------------------------------------
# AUTO-CREATION DE L'UTILISATEUR OWNER (ID = 1)
# -------------------------------------------------------------------
def init_default_user():
    db = SessionLocal()
    try:
        # Vérifie si un user existe déjà
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


# On initialise l’utilisateur par défaut
init_default_user()


# -------------------------------------------------------------------
# INSTANCE FASTAPI
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

# Sessions (login admin)
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# -------------------------------------------------------------------
# STATIC & FRONT
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

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
# LOGIN ADMIN
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
    return HTMLResponse(html)


@app.post("/login")
def login(password: str = Form(...), request: Request = None):
    if password == ADMIN_PASSWORD:
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)
    return RedirectResponse("/login", status_code=302)


# -------------------------------------------------------------------
# PAGES FRONT
# -------------------------------------------------------------------
@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card_page(slug: str):
    html_path = FRONTEND_DIR / "public-card" / "index.html"
    return FileResponse(str(html_path))


@app.get("/admin", response_class=HTMLResponse)
def serve_admin(request: Request):
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)
    html_path = FRONTEND_DIR / "admin" / "index.html"
    return FileResponse(str(html_path))


@app.get("/smartcard", response_class=HTMLResponse)
def smartcard_landing():
    html_path = FRONTEND_DIR / "landing" / "index.html"
    return FileResponse(str(html_path))


# -------------------------------------------------------------------
# ENDPOINTS COMPATIBILITÉ
# -------------------------------------------------------------------
@app.get("/api/by-slug/{slug}", response_model=schemas.CardOut, tags=["compat"])
def get_card_by_slug_compat(slug: str, db: Session = Depends(get_db)):
    card = db.query(models.Card).filter(models.Card.slug == slug).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@app.get("/api/{card_id}/feedback",
         response_model=list[schemas.FeedbackOut],
         tags=["compat"])
def list_feedback_compat(card_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Feedback)
        .filter(models.Feedback.card_id == card_id)
        .order_by(models.Feedback.created_at.desc())
        .all()
    )


@app.get("/api/{card_id}/quotes",
         response_model=list[schemas.QuoteOut],
         tags=["compat"])
def list_quotes_compat(card_id: int, db: Session = Depends(get_db)):
    return (
        db.query(models.Quote)
        .filter(models.Quote.card_id == card_id)
        .order_by(models.Quote.created_at.desc())
        .all()
    )





