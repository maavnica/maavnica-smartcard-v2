-- Migration idempotente : visual_theme sur cards (univers data-theme FR)
-- Valeurs : wellness-soft | artisan | real-estate | corporate | maavnica
-- Le startup appelle aussi ensure_visual_theme_column().

-- SQLite (manuel) :
-- ALTER TABLE cards ADD COLUMN visual_theme VARCHAR(32) NOT NULL DEFAULT 'wellness-soft';

-- PostgreSQL :
-- ALTER TABLE cards ADD COLUMN IF NOT EXISTS visual_theme VARCHAR(32) NOT NULL DEFAULT 'wellness-soft';
