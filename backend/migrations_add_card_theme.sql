-- Migration idempotente : card_theme sur cards (classic | experience)
-- SQLite / Postgres : exécuter une fois ; le startup appelle aussi ensure_card_theme_column().

-- SQLite (si colonne absente) :
-- ALTER TABLE cards ADD COLUMN card_theme VARCHAR(32) NOT NULL DEFAULT 'classic';

-- Postgres (équivalent) :
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_theme VARCHAR(32) NOT NULL DEFAULT 'classic';
