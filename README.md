# Twitch Giveaway Overlay

Overlay de giveaway pour Twitch, affiché dans OBS comme source navigateur et piloté directement depuis le chat.

> Le parcours Twitch complet est fonctionnel avec un bot global fixe et un streamer actif choisi dynamiquement depuis `/admin` avec Twitch OAuth. Plusieurs streamers simultanés viendront ensuite.

## Fonctionnalités

- commandes Twitch reçues avec TwitchIO 3 et EventSub ;
- autorisation OAuth et rafraîchissement des tokens ;
- permissions de gestion réservées au broadcaster ;
- inscriptions uniques et tirage avec `secrets.choice` ;
- persistance et restauration avec SQLite ;
- API FastAPI et synchronisation des overlays par WebSocket ;
- overlay HTML minimal personnalisable avec le CSS d’OBS ;
- bootstrap `.env` et configuration JSON non secrète validés avec Pydantic.

## Commandes

| Commande | Accès | Effet |
|---|---|---|
| `!galot <lot>` | Streamer | Prépare le lot et affiche l’overlay. |
| `!gastart` | Streamer | Ouvre les inscriptions. |
| `!join` | Viewer | Inscrit le viewer une seule fois. |
| `!gapull` | Streamer | Ferme les inscriptions et tire un gagnant. |
| `!gastop` | Streamer | Termine le giveaway et masque l’overlay. |

```text
HIDDEN --!galot--> WAITING --!gastart--> OPEN --!gapull--> WINNER
   ^                   |                    |                  |
   └-------------------┴------ !gastop -----┴------------------┘
```

## Architecture

```text
app/
├── main.py             # assemblage FastAPI
├── core/               # environnement et configuration
├── domain/             # règles métier du giveaway
├── application/        # commandes et cas d’usage
├── infrastructure/     # SQLite et TwitchIO
└── web/                # routes, WebSocket et fichiers statiques
```

Le service est la source de vérité : l’overlay affiche l’état reçu et ne choisit jamais le gagnant.

## Étape active : administration mono-streamer

La première évolution conserve un seul giveaway actif, mais sépare les identités :

- le bot global reste fixe, par exemple `necsus_dev` ;
- le streamer se connecte sur `/admin`, par exemple `fluffy` ;
- son identifiant Twitch validé devient le `broadcaster_id` autorisé ;
- le bot global écoute le chat de ce streamer avec EventSub ;
- changer de streamer remplace l'unique canal actif.

Le tableau de bord affiche l'identité Twitch, le bot utilisé, l'état de l'abonnement au chat, l'URL OBS et la déconnexion.

## Cible multi-streamer

La future architecture prévoit :

- une application Twitch et un compte bot dédié partagés par l'instance ;
- une connexion à `/admin` avec Twitch OAuth pour chaque streamer ;
- un moteur, un historique et des WebSockets isolés par identifiant Twitch ;
- des giveaways simultanés sur plusieurs chaînes ;
- une URL OBS `/overlay/{login_twitch}` propre à chaque streamer ;
- un historique filtré exclusivement avec l'identité de la session.

Le Client ID et le Client Secret identifient l'application Twitch, pas le compte bot. Les détails et l'ordre de migration sont décrits dans la documentation technique et le plan de développement.

## Capacité et limites actuelles

Un test local isolé a traité 5 000 requêtes HTTP avec une concurrence de 100 sans erreur, ainsi que 300 connexions WebSocket simultanées. Ces résultats valident les routes de lecture simples, mais pas encore une charge multi-streamer complète.

Avant une mise en production avec du trafic, il reste notamment à :

- réduire les messages WebSocket pour ne plus diffuser toute la liste des participants ;
- isoler les clients lents avec des files bornées et des délais d'envoi ;
- passer SQLite en WAL et sortir ses écritures de la boucle asynchrone ;
- garantir la cohérence entre SQLite et l'état mémoire en cas d'erreur ;
- superviser TwitchIO, ajouter des contrôles `live`/`ready` et relever la limite de fichiers ouverts.

Le service doit rester sur **un seul worker Uvicorn** tant que les moteurs et WebSockets sont conservés en mémoire.

## Installation locale

Prérequis : Python 3.11 ou plus récent.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# Compléter .env avec les valeurs Twitch réelles.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Sous PowerShell, utilise `\.venv\Scripts\Activate.ps1` et `Copy-Item .env.example .env`.

| URL | Usage |
|---|---|
| `http://127.0.0.1:8000/health` | État du service |
| `http://127.0.0.1:8000/api/state` | État courant du giveaway |
| `http://127.0.0.1:8000/overlay` | Source navigateur OBS |
| `http://127.0.0.1:8000/docs` | Documentation OpenAPI |

Avec Tailscale Serve, le service est disponible en HTTPS privé, par exemple sur `https://forge.<tailnet>.ts.net/overlay`.

## Autorisation Twitch

L’application créée dans la console Twitch doit déclarer le callback HTTPS de l’administration, par exemple :

```text
https://forge.<tailnet>.ts.net/auth/twitch/callback
```

Le bot global et le streamer utilisent ce callback unique, avec des états OAuth distincts, courts et à usage unique.

Pour autoriser ou réautoriser le bot configuré :

1. démarrer le service avec Twitch activé ;
2. ouvrir `https://forge.<tailnet>.ts.net/auth/twitch/bot/login` ;
3. se connecter avec le compte bot configuré ;
4. accepter `user:read:chat`, `user:write:chat` et `user:bot`.

Le callback refuse toute identité différente du `bot_id` configuré et TwitchIO sauvegarde immédiatement le token dans son stockage local ignoré par Git. Le streamer ouvre ensuite `/admin` et accorde `channel:bot`. Les tokens OAuth ne sont jamais stockés dans SQLite ni envoyés au navigateur.

## OBS

Ajoute `/overlay` comme source navigateur dans le mode actuel. La cible multi-streamer utilisera `/overlay/{login_twitch}`. Le document expose les identifiants CSS suivants :

- `#giveaway`
- `#lot`
- `#status`
- `#participants`
- `#winner`

Le rendu visuel est défini dans le champ **CSS personnalisé** de la source OBS.

## Sécurité

- `.env` contient les valeurs réelles et ne doit jamais être versionné ou partagé ;
- `.env.example` contient uniquement des valeurs fictives ;
- `.tio.tokens.json` contient les tokens OAuth et reste hors de Git ;
- les secrets ne sont jamais envoyés au navigateur ;
- aucune route HTTP publique ne permet de piloter le giveaway.

## Documentation

- [`TECHNICAL_SPEC.md`](./TECHNICAL_SPEC.md) : architecture et choix techniques ;
- [`DEVELOPMENT_PLAN.md`](./DEVELOPMENT_PLAN.md) : avancement du MVP.

## Licence

Distribué sous licence [MIT](./LICENSE).
