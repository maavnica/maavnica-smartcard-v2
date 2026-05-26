# SmartCard V3 — Guide d’utilisation

## Principe `card_theme`

Chaque carte possède un champ **`card_theme`** :

| Valeur | Rendu public (FR) |
|--------|-------------------|
| `classic` (défaut) | `index.html` — carte actuelle |
| `experience` | `index_v3.html` — V3 premium apaisée |

Les cartes existantes restent en **`classic`** tant qu’elles ne sont pas basculées explicitement.

L’URL publique ne change pas : **`/c/{slug}`**.

## Activer la V3 sur une carte

### Via l’admin

1. Ouvrir `/admin`
2. Éditer la carte
3. **Thème carte** → **Experience V3**
4. Enregistrer

### Via script CLI

Depuis la racine du dépôt :

```bash
python scripts/set_card_theme.py demo2 experience
```

## Revenir au classique

Admin → **Thème carte** → **Classique**, ou :

```bash
python scripts/set_card_theme.py demo2 classic
```

## Fichiers V3

- `backend/static/public-card/index_v3.html`
- `backend/static/public-card/v3-layout.css`
- `backend/static/public-card/v3.css`
- `backend/static/public-card/public-card-runtime.js`

Régénération après évolution du script inline du classic :

```bash
python tools/build_public_card_v3.py
```

## Pilote recommandé

Activer **`experience`** uniquement sur **`demo2`** pour validation, puis étendre progressivement.

Ne pas basculer `demo`, `demo3`, `arnaud-huard` tant que le pilote n’est pas validé.

## Tests à faire (checklist)

- [ ] `/c/demo2` — rendu V3 (crème / sauge, mobile)
- [ ] `/c/demo2?admin_view=1` — badge prévisualisation, pas de double comptage
- [ ] `/c/demo2?r=test` — bannière recommandation si configurée
- [ ] Visite analytics (consentement `all`)
- [ ] Appeler, WhatsApp, avis Google, devis, partage, recommandation, QR
- [ ] `/c/demo`, `/c/demo3`, `/c/arnaud-huard` — toujours classic
- [ ] Rollback `classic` sur demo2

## Migration progressive

1. Valider V3 sur `demo2`
2. Activer carte par carte (clients pilotes)
3. Itérer sur `v3.css` sans toucher au classic
4. Option future : affiner le DOM V3 pour alléger `v3-layout.css`

Voir aussi : [smartcard_v3_migration_plan.md](./smartcard_v3_migration_plan.md)
