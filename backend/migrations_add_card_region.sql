-- Ajout region sur cards (default FR)
ALTER TABLE cards ADD COLUMN region VARCHAR(16) NOT NULL DEFAULT 'fr';
