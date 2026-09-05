# Twitch Giveaway Overlay

Overlay de giveaway pour Twitch, affiché dans OBS comme source navigateur et piloté directement depuis le chat.

> Le parcours Twitch complet est fonctionnel avec un bot global fixe et un streamer actif choisi dynamiquement depuis `/admin` avec Twitch OAuth. Le giveaway est isolé sous `overlay.necsus.dev/plugins/giveaway` et sa source OBS est protégée par une clé révocable. Plusieurs plugins et streamers simultanés viendront ensuite.

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
| `!gapull` | Streamer | Ferme les inscriptions au premier tirage, puis ajoute un gagnant inédit. |
| `!gastop` | Streamer | Termine le giveaway et masque l’overlay. |

```text
HIDDEN --!galot--> WAITING --!gastart--> OPEN --!gapull--> WINNER
   ^                   |                    |                  |
   └-------------------┴------ !gastop -----┴------------------┘
```

Dans l'état `WINNER`, chaque nouveau `!gapull` ajoute un gagnant qui n'a pas encore gagné le lot, jusqu'à épuisement des participants ou `!gastop`.

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

## Cible plateforme et multi-streamer

La future architecture prévoit :

- `overlay.necsus.dev` comme domaine commun à tous les plugins ;
- un namespace `/plugins/<plugin>` qui isole les routes, API, fichiers statiques et WebSockets ;
- une application Twitch et un compte bot dédié partagés par l'instance ;
- une connexion à `/admin` avec Twitch OAuth pour chaque streamer ;
- un moteur, un historique et des WebSockets isolés par identifiant Twitch ;
- des giveaways simultanés sur plusieurs chaînes ;
- une URL OBS protégée propre au couple streamer/plugin ;
- un historique filtré exclusivement avec l'identité de la session.

Pour le giveaway, l'URL actuelle est `https://overlay.necsus.dev/plugins/giveaway/overlay#<clé-OBS>`. Un futur plugin utilisera son propre espace, par exemple `/plugins/chat`, sans partager sa clé avec le giveaway.

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
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Sous PowerShell, utilise `\.venv\Scripts\Activate.ps1` et `Copy-Item .env.example .env`.

| URL | Usage |
|---|---|
| `http://127.0.0.1:8000/health` | État du service |
| `http://127.0.0.1:8000/admin` | Administration Twitch |
| `http://127.0.0.1:8000/docs` | Documentation OpenAPI |

Sur le réseau local, Nginx publie le service sur `https://overlay.necsus.dev` et relaie HTTP ainsi que WebSocket vers Uvicorn. Le DNS public résout ce nom vers l'adresse privée `192.168.1.112` ; aucun port n'est redirigé depuis Internet. Le certificat Let's Encrypt est obtenu par challenge DNS-01 Cloudflare et renouvelé par ACME sous NixOS. Tailscale Serve reste utilisable séparément sur son adresse privée.

Les anciennes routes `/overlay`, `/api/state` et `/ws/overlay`, le virtual host, le certificat et le DNS `giveaway.necsus.dev` ont été supprimés après validation du domaine et des routes canoniques.

| URL HTTPS locale actuelle | Usage |
|---|---|
| `https://overlay.necsus.dev/health` | État du service |
| `https://overlay.necsus.dev/admin` | Administration Twitch |
| `https://overlay.necsus.dev/plugins/giveaway/overlay#<clé-OBS>` | Overlay canonique protégé par une clé |

## Autorisation Twitch

Le callback canonique déclaré dans Twitch et utilisé par l'application est :

```text
https://overlay.necsus.dev/auth/twitch/callback
```

Le parcours complet a été validé sur le nouveau domaine. Le bot global et le streamer utilisent ce callback unique, avec des états OAuth distincts, courts et à usage unique.

Pour autoriser ou réautoriser le bot configuré :

1. démarrer le service avec Twitch activé ;
2. ouvrir `https://overlay.necsus.dev/auth/twitch/bot/login` ;
3. se connecter avec le compte bot configuré ;
4. accepter `user:read:chat`, `user:write:chat` et `user:bot`.

Le callback refuse toute identité différente du `bot_id` configuré et TwitchIO sauvegarde immédiatement le token dans son stockage local ignoré par Git. Le streamer ouvre ensuite `/admin` et accorde `channel:bot`. Les tokens OAuth ne sont jamais stockés dans SQLite ni envoyés au navigateur.

## OBS

Le plugin giveaway utilise désormais une URL protégée semblable à :

```text
https://overlay.necsus.dev/plugins/giveaway/overlay#<clé-OBS>
```

La clé OBS est une capacité de lecture longue durée distincte de la session Twitch. Elle est propre au couple streamer/plugin, stockée uniquement sous forme de hash et régénérable depuis `/admin`. Une rotation crée une nouvelle clé et invalide immédiatement l'ancien lien sans affecter les autres plugins. Dans le mode mono-streamer actuel, connecter un compte Twitch différent ferme aussi les sources OBS de l'ancien streamer.

Le fragment n'est pas transmis dans la requête HTTP. Le JavaScript l'envoie comme premier message WebSocket ; aucun état n'est diffusé avant validation. Une clé absente ou invalide ferme la connexion avec le code `1008`. Les anciennes routes `/overlay`, `/ws/overlay` et `/api/state` n'existent plus.

Le document expose les identifiants CSS suivants :

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
- les secrets OAuth ne sont jamais envoyés au navigateur ;
- l'accès OBS limite chaque clé aux données de rendu du plugin concerné ;
- aucune clé OBS n'est placée dans une query string ni stockée en clair côté serveur ;
- aucune route HTTP publique ne permet de piloter le giveaway.

## Documentation

- [`TECHNICAL_SPEC.md`](./docs/TECHNICAL_SPEC.md) : architecture et choix techniques ;
- [`DEVELOPMENT_PLAN.md`](./docs/DEVELOPMENT_PLAN.md) : avancement du MVP ;
- [`CHAT_OVERLAY_PLAN.md`](./docs/CHAT_OVERLAY_PLAN.md) : plan de développement de l'overlay de chat.

## Licence

Distribué sous licence [MIT](./LICENSE).
