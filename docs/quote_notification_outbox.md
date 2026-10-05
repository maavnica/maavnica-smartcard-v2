# Notifications de devis

## Routage

Chaque demande de devis et son entrée d'outbox sont créées dans la même
transaction. Le destinataire est figé dans l'ordre suivant :

1. `cards.notification_email` (privé) ;
2. `cards.email_pro` (repli public).

`notification_email` n'est jamais rendu dans l'API publique ni dans la carte.
L'e-mail du prospect est uniquement placé dans `Reply-To`.

## États et reprises

- `pending` : prêt à envoyer à partir de `next_attempt_at` ;
- `processing` : réservé par une lease temporaire ;
- `sent` : succès confirmé ;
- `failed` : échec connu après épuisement des tentatives ;
- `unknown` : résultat ambigu, sans relance automatique.

La lease est commitée avant l'appel réseau. Une instance interrompue libère
implicitement le travail à l'expiration de `processing_until`. Les workers
PostgreSQL utilisent également `FOR UPDATE SKIP LOCKED` lors de la prise de
lease.

Le processeur n'est pas lancé dans une boucle mémoire par le serveur web :

```bash
python -m app.jobs.process_notification_outbox --limit 50
```

Cette commande est prévue pour un Cron Render partageant les mêmes variables
d'environnement et la même base. Le Cron n'est pas créé automatiquement.

Les endpoints manuels, protégés par `Authorization: Bearer <ADMIN_API_KEY>`,
sont :

- `GET /api/admin/notification-outbox`
- `POST /api/admin/notification-outbox/process`
- `POST /api/admin/notification-outbox/{id}/retry`

Une entrée `unknown` exige `confirm_unknown=true` pour être replacée en
`pending`.

## Idempotence et résultats ambigus

Brevo reçoit la même clé UUID lors des répétitions d'une notification.
L'application n'accorde qu'une fenêtre conservatrice de 15 minutes à cette
protection. Après cette fenêtre, une relance explicite peut créer un doublon.

Un HTTP 4xx/5xx Brevo clairement reçu autorise le fallback SMTP. Un timeout ou
une exception sans réponse HTTP passe la notification en `unknown` et
n'active pas SMTP, car Brevo peut déjà avoir accepté le message.

SMTP ne fournit pas d'idempotence de bout en bout. Un timeout SMTP est donc
également `unknown`. L'objectif est la traçabilité et l'absence de perte
silencieuse, pas une promesse incorrecte d'exactement-une-fois.

Si `SMTP_HOST` utilise l'infrastructure Brevo, le fallback SMTP change de
transport mais pas de fournisseur ; il ne constitue pas une redondance de
fournisseur.

## Confidentialité

Les logs ne contiennent ni adresse complète, ni contenu de demande, ni secret.
Les diagnostics d'outbox sont assainis avant stockage. Les réponses admin ne
retournent pas le destinataire.

## Recette de production

Les erreurs Brevo (400, 500, timeout, exception) sont testées uniquement avec
des mocks. Ne jamais invalider la clé Brevo de production.

Le test réel est limité à une carte Maavnica de test, avec
`notification_email` configuré vers Gmail direct. Vérifier :

- le délai de réception ;
- l'expéditeur Brevo vérifié ;
- le `Reply-To` du prospect de test ;
- les en-têtes de réception, qui ne doivent montrer aucun passage par OVH.
