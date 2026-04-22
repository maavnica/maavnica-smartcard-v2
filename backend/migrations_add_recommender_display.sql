-- Recommandation : prénom / nom / libellé affiché (affichage + devis)
-- À exécuter si vous ne passez pas par le startup FastAPI (ensure_*).
-- SQLite / PostgreSQL : types compatibles.

ALTER TABLE recommendation_events ADD COLUMN recommender_first_name VARCHAR(80);
ALTER TABLE recommendation_events ADD COLUMN recommender_last_name VARCHAR(80);
ALTER TABLE recommendation_events ADD COLUMN recommender_display_name VARCHAR(200);

ALTER TABLE quotes ADD COLUMN recommender_first_name VARCHAR(80);
ALTER TABLE quotes ADD COLUMN recommender_last_name VARCHAR(80);
ALTER TABLE quotes ADD COLUMN recommender_display_name VARCHAR(200);
