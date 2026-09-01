# Twitch Giveaway Overlay

Overlay de giveaway pour Twitch, affiché dans OBS comme source navigateur et piloté directement depuis le chat.

> Le parcours Twitch complet est fonctionnel pour un streamer. La prochaine évolution vise plusieurs streamers simultanés, authentifiés avec Twitch et isolés par chaîne.

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
| `!lot <lot>` | Streamer | Prépare le lot et affiche l’overlay. |
| `!start` | Streamer | Ouvre les inscriptions. |
| `!join` | Viewer | Inscrit le viewer une seule fois. |
| `!pull` | Streamer | Ferme les inscriptions et tire un gagnant. |
| `!stop` | Streamer | Termine le giveaway et masque l’overlay. |

```text
HIDDEN --!lot--> WAITING --!start--> OPEN --!pull--> WINNER
   ^                 |                  |                |
   └-----------------┴----- !stop ------┴----------------┘
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

Sur le tailnet, MagicDNS permet par exemple d’utiliser `http://forge:8000/overlay`.

## Autorisation Twitch

L’application créée dans la console Twitch doit déclarer cette URL de redirection :

```text
http://localhost:4343/oauth/callback
```

Pour autoriser ou réautoriser un compte :

1. définir temporairement `TWITCH_OAUTH_ENABLED=true` ;
2. démarrer le service ;
3. transmettre le port depuis une DevBox distante si nécessaire :

   ```bash
   ssh -L 4343:127.0.0.1:4343 utilisateur@devbox
   ```

4. ouvrir l’URL OAuth avec les scopes adaptés ;
5. remettre `TWITCH_OAUTH_ENABLED=false` après l’autorisation.

Le mode mono-streamer actuel peut utiliser un compte unique avec `user:read:chat`, `user:write:chat`, `user:bot` et `channel:bot`. La cible multi-streamer utilisera un bot dédié autorisé une fois, puis `channel:bot` pour chaque streamer connecté.

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
