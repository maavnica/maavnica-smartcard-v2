-- Migration: ajout note Google et nombre d'avis (v1 preuve sociale)
-- À exécuter une fois sur la base existante.

-- SQLite
ALTER TABLE cards ADD COLUMN google_rating REAL;
ALTER TABLE cards ADD COLUMN google_review_count INTEGER;

-- PostgreSQL (si besoin, décommenter et adapter)
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS google_rating DOUBLE PRECISION;
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS google_review_count INTEGER;
