-- Migration: ajout note Google et nombre d'avis (v1 preuve sociale)
-- Note: ensure_google_rating_columns() dans app/database.py applique cette migration
-- automatiquement au démarrage (SQLite + PostgreSQL Render). Ce fichier reste une
-- référence manuelle si besoin.

-- SQLite
ALTER TABLE cards ADD COLUMN google_rating REAL;
ALTER TABLE cards ADD COLUMN google_review_count INTEGER;

-- PostgreSQL
ALTER TABLE cards ADD COLUMN IF NOT EXISTS google_rating DOUBLE PRECISION;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS google_review_count INTEGER;
