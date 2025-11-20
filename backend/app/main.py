from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

from .routers import public, cards
from .database import Base, engine

# -------------------------------------------------------------------
# CONFIG ADMIN SIMPLE
# -------------------------------------------------------------------
ADMIN_PASSWORD = "maavnica2025"
SESSION_SECRET_KEY = "MAAVNICA_SUPER_SECRET_2025_CHANGE_ME"

# -------------------------------------------------------------------
# INIT DB
# -------------------------------------------------------------------
Base.metadata.create_all(bind=engine)

# -------------------------------------------------------------------
# APP FASTAPI
# -------------------------------------------------------------------
app = FastAPI(
    title="Maavnica SmartCard API",
    version="1.0.0"
)

# -------------------------------------------------------------------
# CORS (NÉCESSAIRE POUR RENDER)
# -------------------------------------------------------------------
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://maavnica-smartcard-v2-1.onrender.com",   # TON FRONT RENDER
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,      # OK en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# MIDDLEWARE SESSIONS (POUR LOGIN ADMIN)
# -------------------------------------------------------------------
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# -------------------------------------------------------------------
# ROUTERS API
# -------------------------------------------------------------------
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])

# -------------------------------------------------------------------
# PATHS FRONTEND / STATIC
# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR / "static"
FRONTEND_DIR = BASE_DIR / "frontend"

STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# -------------------------------------------------------------------
# ROUTES API DE TEST
# -------------------------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Maavnica SmartCard API is running"}

# -------------------------------------------------------------------
# LOGIN ADMIN – PAGES
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
        request.session["is_admin"] = True
        return RedirectResponse("/admin", status_code=302)

    return RedirectResponse("/login", status_code=302)

# -------------------------------------------------------------------
# ROUTES FRONTEND HTML
# -------------------------------------------------------------------
@app.get("/c/{slug}", response_class=HTMLResponse)
def serve_card_page(slug: str):
    html_path = FRONTEND_DIR / "public-card" / "index.html"
    return FileResponse(str(html_path))


@app.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    # sécurité simple
    if not request.session.get("is_admin"):
        return RedirectResponse("/login", status_code=302)

    html_path = FRONTEND_DIR / "admin" / "index.html"
    return FileResponse(str(html_path))


@app.get("/smartcard", response_class=HTMLResponse)
def smartcard_landing():
    html_path = FRONTEND_DIR / "landing" / "index.html"
    return FileResponse(str(html_path))


