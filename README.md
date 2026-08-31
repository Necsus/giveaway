# Twitch Giveaway Overlay

Overlay minimaliste de giveaway pour Twitch, affiché dans OBS comme **source navigateur** et piloté depuis le chat.

> État du projet : socle local fonctionnel. Le moteur, SQLite, FastAPI, le WebSocket et l'overlay minimal sont implémentés. La connexion Twitch, l'administration et le déploiement restent à réaliser.

## Objectif

Permettre au streamer de préparer un lot, d'ouvrir les inscriptions, de tirer un gagnant puis de masquer l'overlay, uniquement avec des commandes Twitch.

## État actuel

Le socle suivant est disponible :

- moteur avec les états `HIDDEN`, `WAITING`, `OPEN` et `WINNER` ;
- inscriptions uniques par identifiant Twitch et tirage avec `secrets.choice` ;
- service applicatif protégé contre les commandes concurrentes par un verrou asynchrone ;
- historique SQLite des giveaways et des participants ;
- restauration d'un giveaway actif après un redémarrage ;
- API FastAPI avec `/health`, `/api/state`, `/overlay` et `/ws/overlay` ;
- overlay HTML/JavaScript minimal, mise à jour par WebSocket et reconnexion automatique ;
- prise en charge simultanée de plusieurs connexions d'overlay.

Restent notamment à réaliser :

- la connexion au chat Twitch et le contrôle des permissions ;
- la configuration JSON ;
- l'authentification et l'interface `/admin` ;
- la consultation de l'historique ;
- le déploiement NixOS et la publication privée avec Tailscale.

Aucune route non authentifiée ne permet actuellement de piloter le giveaway. Tant que le connecteur Twitch n'est pas ajouté, l'overlay reçoit donc son état initial mais aucun utilisateur ne peut déclencher les commandes depuis le chat.

## Commandes

| Commande | Utilisateur | Effet |
|---|---|---|
| `!lot <nom du lot>` | Streamer | Affiche l'overlay avec le nom du lot et le place en attente. Exemple : `!lot Clavier mécanique`. |
| `!start` | Streamer | Ouvre les inscriptions et commence à prendre en compte les `!join`. |
| `!join` | Viewer | Inscrit le viewer au giveaway ouvert. Un viewer ne peut s'inscrire qu'une fois. |
| `!pull` | Streamer | Ferme les inscriptions, tire un participant au hasard et affiche le gagnant. |
| `!stop` | Streamer | Annule le giveaway en cours, réinitialise son état et masque l'overlay. |

Les commandes de gestion (`!lot`, `!start`, `!pull` et `!stop`) sont réservées au streamer. Son autorisation doit être vérifiée à partir de son identifiant Twitch.

## Déroulement

1. Le streamer prépare le giveaway avec `!lot <nom du lot>` : l'overlay devient visible et reste en attente.
2. Il envoie `!start` : les viewers peuvent alors s'inscrire avec `!join`.
3. Il envoie `!pull` : les inscriptions ferment et le gagnant est affiché.
4. Il envoie `!stop` : le giveaway est annulé ou terminé, puis l'overlay est masqué.

## États

```text
MASQUÉ --!lot--> EN ATTENTE --!start--> INSCRIPTIONS OUVERTES --!pull--> GAGNANT
   ^                    |                         |                         |
   └--------------------┴-------- !stop ----------┴-------------------------┘
```

- **Masqué** : aucun giveaway n'est affiché.
- **En attente** : le lot est visible, mais `!join` est ignoré.
- **Inscriptions ouvertes** : les `!join` sont acceptés.
- **Gagnant** : les inscriptions sont fermées et le résultat est affiché.

## Overlay OBS

Le HTML reste un simple squelette sémantique avec des `id` stables pour les éléments utiles, par exemple :

- `#giveaway` : conteneur principal à afficher ou masquer ;
- `#lot` : nom du lot ;
- `#status` : état courant ;
- `#participants` : liste ou nombre de participants ;
- `#winner` : nom du gagnant.

Le projet ne fournit pas de thème visuel élaboré. La personnalisation (couleurs, polices, dimensions, placements et animations) est réalisée avec le champ **CSS personnalisé** de la source navigateur OBS.

## Architecture minimale

```text
Chat Twitch
    │
    ▼
Service Python sur la DevBox
- écoute les commandes
- vérifie les permissions
- conserve l'état et l'historique
- fournit l'administration
- choisit le gagnant
    │
    ▼
Overlay HTML dans OBS
```

Le service est la source de vérité. L'overlay affiche uniquement l'état reçu et ne choisit jamais le gagnant.

## Périmètre du MVP

- écouter les commandes d'un seul canal Twitch ;
- gérer les cinq commandes décrites ci-dessus ;
- empêcher les inscriptions en double ;
- choisir aléatoirement un gagnant parmi les inscrits ;
- synchroniser l'état avec les overlays OBS du réseau Tailscale ;
- fournir un HTML minimal avec des `id` faciles à cibler depuis le CSS OBS ;
- modifier la configuration depuis `/admin` et la stocker en JSON ;
- enregistrer l'historique des giveaways dans SQLite.

Ne font pas partie du MVP : les avatars Twitch, les thèmes intégrés, les sons, la gestion de plusieurs chaînes et la pondération des chances.

## Développement local

Prérequis : Python 3.11 ou plus récent et PowerShell. Le développement actuel utilise Python 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Le service local est ensuite disponible sur :

| URL | Usage |
|---|---|
| `http://127.0.0.1:8000/health` | État de santé du service. |
| `http://127.0.0.1:8000/api/state` | Instantané JSON du giveaway courant. |
| `http://127.0.0.1:8000/overlay` | Page destinée à la source navigateur OBS. |
| `http://127.0.0.1:8000/docs` | Documentation OpenAPI générée par FastAPI. |
| `ws://127.0.0.1:8000/ws/overlay` | WebSocket utilisé par l'overlay. |

La base locale est créée dans `data/giveaway.sqlite3` et n'est pas versionnée. Les dates sont stockées en UTC ; l'administration les affichera plus tard dans le fuseau `Europe/Paris`.

## Sécurité

- Les jetons et secrets Twitch restent côté service et ne sont jamais versionnés.
- Les commandes de gestion sont refusées si leur auteur n'est pas le streamer attendu.
- Le gagnant est choisi côté service, indépendamment d'un éventuel effet visuel ajouté dans OBS.

## Documentation

- [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) : architecture, stockage, administration et déploiement sur la DevBox ;
- [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) : étapes minimales de réalisation du MVP.

## Licence

À définir.
