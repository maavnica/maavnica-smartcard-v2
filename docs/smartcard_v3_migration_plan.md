# SmartCard V3 — Plan de migration progressive

## Objectif

Introduire une expérience publique **premium, apaisée et mobile-first** (V3) **carte par carte**, sans modifier l’URL `/c/{slug}` ni casser l’existant (classic).

## Fichiers impactés

| Fichier | Rôle |
|---------|------|
| `backend/static/public-card/index.html` | Template **classic** (inchangé, JS inline conservé) |
| `backend/static/public-card/index_v3.html` | Template **experience** |
| `backend/static/public-card/v3-layout.css` | Structure DOM (extrait du classic) |
| `backend/static/public-card/v3.css` | Surcharges visuelles premium V3 |
| `backend/static/public-card/public-card-runtime.js` | Logique carte (extrait du classic + garde V3) |
| `backend/app/main.py` | Routage conditionnel `/c/{slug}` + SEO FR |
| `backend/app/models.py` | Colonne `card_theme` |
| `backend/app/schemas.py` | `classic` \| `experience` |
| `backend/app/database.py` | `ensure_card_theme_column()` |
| `backend/migrations_add_card_theme.sql` | Référence SQL manuelle |
| `backend/static/admin/index.html` + `app.js` | Select « Thème carte » |
| `scripts/set_card_theme.py` | Bascule CLI |
| `tools/build_public_card_v3.py` | Régénère V3 depuis `index.html` |

## Route et données

- **URL publique** : `/c/{slug}` (identique).
- **API données** : `GET /api/public/cards/{slug}` (+ `?r=`, `?o=`).
- **Choix template** (serveur, région FR uniquement) :
  - `card_theme == "experience"` → `index_v3.html`
  - sinon → `index.html`
  - `region == "latam"` → `index_latam.html` (pas de V3 pour l’instant).

## IDs / classes critiques (ne pas supprimer)

Le runtime s’appuie sur ~70 `getElementById`, notamment :

`btn-call`, `btn-whatsapp`, `btn-google-review`, `btn-primary-demande-contact`, `btn-cta-recommander`, `btn-share-card-main`, `qr-image`, `quote-*`, `panel-*`, `acc-trigger-*`, `recommend-identity-modal`, `toast`, `person-name`, `company-name`, `hero-*`, `premium-load-layer`, etc.

La V3 conserve le **même DOM** ; seuls les CSS et le template HTML diffèrent.

## Analytics & recommandation

- `POST /api/analytics/visit`, `/event`, `/recommendation-event`
- Consentement : `maavnica_consent` via `maavnica-consent.js`
- `?r=` : attribution recommandation (inchangé)
- `?admin_view=1` : mode prévisualisation interne (inchangé)

## Risques

| Risque | Mitigation |
|--------|------------|
| Divergence JS classic / runtime V3 | Régénérer via `tools/build_public_card_v3.py` après changements majeurs du script inline |
| Carte LATAM en experience | Ignorée : LATAM reste sur `index_latam.html` |
| Colonne `card_theme` absente en prod | `ensure_card_theme_column()` au startup |
| Régression OG / SEO | Injection FR identique sur les deux templates |
| Activation V3 sur toutes les cartes | Défaut `classic` ; bascule admin ou script par slug |

## Éléments à ne pas toucher

- Route `/c/{slug}` et routes API existantes
- `index.html` classic (pas de suppression)
- Landing Maavnica / SmartCard
- Tables analytics, `recommendation_events`
- Admin hors champ « Thème carte »

## Stratégie retenue

1. Couche **experience** parallèle (`index_v3.html` + CSS).
2. Flag **`card_theme`** en base (`classic` par défaut).
3. Routage serveur conditionnel.
4. Pilote sur **`demo2`** uniquement après validation.
5. Extension progressive slug par slug.

## Rollback

1. Admin : Thème carte → **Classique**, ou  
   `python scripts/set_card_theme.py <slug> classic`
2. Aucun redéploiement de template requis : la route ressert `index.html` immédiatement.
3. Les fichiers V3 peuvent rester en place sans effet.

## Tests obligatoires

- `/c/demo2` en `experience` → présence `smartcard-v3`, `v3.css`
- `/c/demo2` en `classic` → pas de V3
- `/c/demo`, `/c/demo3`, `/c/arnaud-huard` → classic par défaut
- `?admin_view=1`, `?r=test` sur demo2 experience
- Clics téléphone, WhatsApp, Google, partage, reco, QR (manuel)
- Tests auto : `backend/tests/test_public_slug.py`
