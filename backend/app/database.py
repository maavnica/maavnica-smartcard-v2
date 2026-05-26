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


def ensure_card_owner_share_key_column() -> None:
    """
    Ajoute owner_share_key (nullable) si absente, puis remplit les cartes sans clé.
    PostgreSQL : ADD COLUMN IF NOT EXISTS (idempotent, robuste prod / introspection).
    Backfill en SQL brut pour éviter toute requête ORM avant que la colonne soit réelle.
    """
    from sqlalchemy import inspect, text
    import secrets

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return

    dialect = engine.dialect.name
    if dialect == "postgresql":
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE cards ADD COLUMN IF NOT EXISTS owner_share_key VARCHAR(128)"
                )
            )
    else:
        existing = {c["name"] for c in insp.get_columns("cards")}
        if "owner_share_key" not in existing:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE cards ADD COLUMN owner_share_key VARCHAR(128)")
                )

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                "SELECT id FROM cards WHERE owner_share_key IS NULL OR owner_share_key = ''"
            )
        ).fetchall()
        for row in rows:
            cid = row[0]
            key = secrets.token_urlsafe(10)
            conn.execute(
                text("UPDATE cards SET owner_share_key = :k WHERE id = :id"),
                {"k": key, "id": cid},
            )


def ensure_owner_share_key_column() -> None:
    """Alias historique — conservé pour compatibilité des imports."""
    ensure_card_owner_share_key_column()


def ensure_quote_recommendation_columns() -> None:
    """Ajoute source_type / referrer_id sur quotes si colonnes manquantes."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("quotes"):
        return
    existing = {c["name"] for c in insp.get_columns("quotes")}
    statements = []
    if "source_type" not in existing:
        statements.append("ALTER TABLE quotes ADD COLUMN source_type VARCHAR(32)")
    if "referrer_id" not in existing:
        statements.append("ALTER TABLE quotes ADD COLUMN referrer_id VARCHAR(128)")
    if "recommender_first_name" not in existing:
        statements.append("ALTER TABLE quotes ADD COLUMN recommender_first_name VARCHAR(80)")
    if "recommender_last_name" not in existing:
        statements.append("ALTER TABLE quotes ADD COLUMN recommender_last_name VARCHAR(80)")
    if "recommender_display_name" not in existing:
        statements.append("ALTER TABLE quotes ADD COLUMN recommender_display_name VARCHAR(200)")
    for stmt in statements:
        with engine.begin() as conn:
            conn.execute(text(stmt))


def ensure_recommendation_event_display_columns() -> None:
    """Ajoute prénom / nom / libellé affiché sur recommendation_events si manquant."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("recommendation_events"):
        return
    existing = {c["name"] for c in insp.get_columns("recommendation_events")}
    statements = []
    if "recommender_first_name" not in existing:
        statements.append("ALTER TABLE recommendation_events ADD COLUMN recommender_first_name VARCHAR(80)")
    if "recommender_last_name" not in existing:
        statements.append("ALTER TABLE recommendation_events ADD COLUMN recommender_last_name VARCHAR(80)")
    if "recommender_display_name" not in existing:
        statements.append("ALTER TABLE recommendation_events ADD COLUMN recommender_display_name VARCHAR(200)")
    for stmt in statements:
        with engine.begin() as conn:
            conn.execute(text(stmt))


def ensure_card_plan_columns() -> None:
    """Ajoute plan_type / expires_at sur cards si colonnes manquantes."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    statements = []
    if "plan_type" not in existing:
        statements.append("ALTER TABLE cards ADD COLUMN plan_type VARCHAR(32) NOT NULL DEFAULT 'demo'")
    if "expires_at" not in existing:
        dialect = engine.dialect.name
        if dialect == "sqlite":
            statements.append("ALTER TABLE cards ADD COLUMN expires_at DATETIME")
        else:
            statements.append("ALTER TABLE cards ADD COLUMN expires_at TIMESTAMP")
    for stmt in statements:
        with engine.begin() as conn:
            conn.execute(text(stmt))


def ensure_card_region_column() -> None:
    """Ajoute region sur cards si colonne manquante (default fr)."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    if "region" in existing:
        return

    dialect = engine.dialect.name
    if dialect == "sqlite":
        stmt = "ALTER TABLE cards ADD COLUMN region VARCHAR(16) NOT NULL DEFAULT 'fr'"
    else:
        stmt = "ALTER TABLE cards ADD COLUMN region VARCHAR(16) NOT NULL DEFAULT 'fr'"
    with engine.begin() as conn:
        conn.execute(text(stmt))


def ensure_card_city_column() -> None:
    """Ajoute city sur cards si colonne manquante (nullable)."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    if "city" in existing:
        return

    stmt = "ALTER TABLE cards ADD COLUMN city VARCHAR(120)"
    with engine.begin() as conn:
        conn.execute(text(stmt))


def ensure_card_theme_column() -> None:
    """Ajoute card_theme sur cards si colonne manquante (default classic)."""
    from sqlalchemy import inspect, text

    try:
        insp = inspect(engine)
    except Exception:
        return
    if not insp.has_table("cards"):
        return
    existing = {c["name"] for c in insp.get_columns("cards")}
    if "card_theme" in existing:
        return

    dialect = engine.dialect.name
    if dialect == "sqlite":
        stmt = (
            "ALTER TABLE cards ADD COLUMN card_theme VARCHAR(32) "
            "NOT NULL DEFAULT 'classic'"
        )
    else:
        stmt = (
            "ALTER TABLE cards ADD COLUMN card_theme VARCHAR(32) "
            "NOT NULL DEFAULT 'classic'"
        )
    with engine.begin() as conn:
        conn.execute(text(stmt))


