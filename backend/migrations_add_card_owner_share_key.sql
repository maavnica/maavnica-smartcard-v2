-- Clé mode propriétaire (?o=) sur cards — idempotent PostgreSQL
ALTER TABLE cards ADD COLUMN IF NOT EXISTS owner_share_key VARCHAR(128);
