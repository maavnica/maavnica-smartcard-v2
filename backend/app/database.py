import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# -------------------------------------------------------------------
# CONFIGURATION BASE DE DONNÉES
# -------------------------------------------------------------------
# En production (Render), on utilise la variable d'environnement DATABASE_URL,
# qui pointe vers PostgreSQL.
# En local (développement), si DATABASE_URL n'est pas définie,
# on retombe sur une base SQLite dans le dossier data/.
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render fournit souvent une URL en postgres://, SQLAlchemy attend postgresql://
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # Mode développement local : SQLite dans ./data/sql_app.db
    BASE_DIR = Path(__file__).resolve().parents[2]
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(exist_ok=True)
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'sql_app.db'}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Dépendance FastAPI pour obtenir une session DB par requête
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_card_hero_columns() -> None:
    """
    Ajoute hero_title / hero_text / hero_cta_text si la table `cards` existait déjà
    (create_all ne modifie pas les tables existantes — SQLite / PostgreSQL).
    """
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    statements = []
    if "hero_title" not in existing:
        statements.append("ALTER TABLE cards ADD COLUMN hero_title TEXT")
    if "hero_text" not in existing:
        statements.append("ALTER TABLE cards ADD COLUMN hero_text TEXT")
    if "hero_cta_text" not in existing:
        statements.append("ALTER TABLE cards ADD COLUMN hero_cta_text TEXT")
    for sql in statements:
        with engine.begin() as conn:
            conn.execute(text(sql))


