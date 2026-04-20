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


def ensure_card_identity_columns() -> None:
    """Ajoute display_name, business_name, job_title, form_title si colonnes manquantes."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    statements = []
    for col, sql in (
        ("display_name", "ALTER TABLE cards ADD COLUMN display_name TEXT"),
        ("business_name", "ALTER TABLE cards ADD COLUMN business_name TEXT"),
        ("job_title", "ALTER TABLE cards ADD COLUMN job_title TEXT"),
        ("form_title", "ALTER TABLE cards ADD COLUMN form_title TEXT"),
    ):
        if col not in existing:
            statements.append(sql)
    for stmt in statements:
        with engine.begin() as conn:
            conn.execute(text(stmt))


def ensure_enable_recommendation_column() -> None:
    """Ajoute enable_recommendation (défaut false) si colonne manquante."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    if "enable_recommendation" in existing:
        return
    dialect = engine.dialect.name
    if dialect == "sqlite":
        sql = "ALTER TABLE cards ADD COLUMN enable_recommendation BOOLEAN NOT NULL DEFAULT 0"
    else:
        sql = "ALTER TABLE cards ADD COLUMN enable_recommendation BOOLEAN NOT NULL DEFAULT false"
    with engine.begin() as conn:
        conn.execute(text(sql))


def ensure_recommendation_code_column() -> None:
    """Ajoute recommendation_code (nullable) si colonne manquante."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    if "recommendation_code" in existing:
        return
    dialect = engine.dialect.name
    if dialect == "sqlite":
        sql = "ALTER TABLE cards ADD COLUMN recommendation_code VARCHAR(64)"
    else:
        sql = "ALTER TABLE cards ADD COLUMN recommendation_code VARCHAR(64)"
    with engine.begin() as conn:
        conn.execute(text(sql))


