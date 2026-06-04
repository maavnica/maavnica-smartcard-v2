-- Carte fondateur : thème Maavnica Premium + contenus cibles
-- À exécuter une fois sur la base de production / staging.
-- N’affecte que le slug arnaud-huard.

UPDATE cards
SET
  visual_theme = 'maavnica',
  display_name = 'Arnaud Huard',
  job_title = 'FONDATEUR MAAVNICA',
  city = 'AUXERRE',
  hero_title = 'Transformez vos recommandations en clients',
  hero_text = 'Le bouche-à-oreille devient enfin mesurable.',
  form_title = 'Demander ma SmartCard'
WHERE lower(slug) = 'arnaud-huard';
