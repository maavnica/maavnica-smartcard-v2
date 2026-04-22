-- Migration manuelle simple (SQLite / PostgreSQL)
-- Ajoute les colonnes de gestion d'expiration des cartes.
-- Note: l'application exécute déjà un garde-fou automatique au démarrage
-- via ensure_card_plan_columns(), ce script est utile pour migration explicite.

ALTER TABLE cards ADD COLUMN plan_type VARCHAR(32) NOT NULL DEFAULT 'demo';
ALTER TABLE cards ADD COLUMN expires_at TIMESTAMP NULL;
