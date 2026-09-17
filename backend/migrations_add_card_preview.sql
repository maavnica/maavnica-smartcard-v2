-- Migration additive (SQLite / PostgreSQL) — mode carte preview.
-- Non destructive : colonnes nullable / défaut false, aucune donnée existante modifiée.
-- Le démarrage de l’application appelle aussi ensure_card_preview_columns().

-- PostgreSQL
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS is_preview BOOLEAN NOT NULL DEFAULT false;
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS preview_origin VARCHAR(64);
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS preview_expires_at TIMESTAMP;

-- SQLite (exécuter une fois ; DEFAULT 0 = false)
-- ALTER TABLE cards ADD COLUMN is_preview BOOLEAN NOT NULL DEFAULT 0;
-- ALTER TABLE cards ADD COLUMN preview_origin VARCHAR(64);
-- ALTER TABLE cards ADD COLUMN preview_expires_at DATETIME;
