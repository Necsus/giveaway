# Spécification technique

## 1. Objectif

Construire un service central de giveaway Twitch hébergé sur la DevBox. Tous les PC autorisés par Tailscale pourront accéder :

- à l'overlay utilisé comme source navigateur OBS ;
- à une page d'administration pour modifier la configuration ;
- à l'historique des giveaways.

Le service reste la source de vérité. OBS affiche l'état reçu mais ne gère ni les commandes Twitch, ni les permissions, ni le tirage.

### État d'implémentation

Le socle local est actuellement opérationnel :

- moteur d'état et règles des cinq actions métier ;
- parseur des commandes et contrôle des permissions par identifiant Twitch ;
- modèle de configuration `.env` typé avec `pydantic-settings` et `SecretStr` ;
- connecteur TwitchIO 3 avec OAuth, abonnement EventSub et écoute du chat ;
- injection de la configuration et du connecteur dans le cycle de vie FastAPI ;
- service applicatif avec verrou asynchrone ;
- schéma SQLite, persistance des transitions et restauration au démarrage ;
- FastAPI avec routes de santé, état JSON, overlay et WebSocket ;
- gestion de plusieurs connexions WebSocket ;
- overlay HTML/JavaScript sans thème avec reconnexion automatique.

Ne sont pas encore implémentés : la configuration administrable en JSON, l'authentification, `/admin`, les API d'historique, le déploiement NixOS et Tailscale. Les tests automatisés sont reportés ; les contrôles actuels sont manuels et complétés par Ruff et BasedPyright.

## 2. Architecture retenue

```text
                         Chat Twitch
                              │
                              ▼
┌──────────────────────────────────────────────────────┐
│ DevBox NixOS                                         │
│                                                      │
│ Service Python / FastAPI                             │
│ ├── connexion au chat Twitch                        │
│ ├── moteur du giveaway                              │
│ ├── API HTTP et WebSocket                           │
│ ├── page /admin                                     │
│ ├── configuration JSON                              │
│ └── historique SQLite                               │
└──────────────────────────────────────────────────────┘
                │                         │
                │ réseau Tailscale        │ réseau Tailscale
                ▼                         ▼
        OBS sur un PC              Navigateur d'administration
        /overlay                   /admin
```

### Choix techniques

- **Langage serveur** : Python 3.
- **Serveur HTTP** : FastAPI avec Uvicorn.
- **Temps réel** : WebSocket natif de FastAPI.
- **Accès Twitch** : connecteur Python isolé du reste de l'application avec TwitchIO 3.
- **Frontend** : HTML et JavaScript natif, sans framework.
- **Configuration locale** : `.env` chargé et validé avec `pydantic-settings` ; valeurs réelles jamais versionnées.
- **Configuration administrable cible** : fichier JSON local à la DevBox.
- **Historique** : SQLite.
- **Accès réseau** : Tailscale uniquement.
- **Déploiement** : service systemd déclaré dans la configuration NixOS.

## 3. Accès depuis les PC

Le service écoute localement sur la DevBox, par exemple :

```text
http://127.0.0.1:8000
```

Tailscale Serve publie ensuite ce service uniquement dans le tailnet avec une URL HTTPS, par exemple :

```text
https://devbox.<tailnet>.ts.net/overlay
https://devbox.<tailnet>.ts.net/admin
```

La fonctionnalité Tailscale Funnel ne doit pas être activée : elle rendrait le service accessible publiquement sur Internet.

### Source navigateur OBS

Chaque PC équipé d'OBS utilise la même URL :

```text
https://devbox.<tailnet>.ts.net/overlay
```

Chaque installation OBS peut appliquer son propre **CSS personnalisé**. L'état du giveaway reste commun à toutes les sources connectées.

## 4. Structure logique du service

```text
app/
├── main.py                         # assemblage et création de FastAPI
├── core/
│   ├── environment.py              # configuration secrète et bootstrap depuis .env
│   └── configuration.py            # modèle de configuration administrable
├── domain/
│   └── giveaway.py                 # règles, états et objets métier purs
├── application/
│   ├── commands.py                 # parsing, permissions et dispatch des commandes
│   └── service.py                  # orchestration des cas d'usage
├── infrastructure/
│   ├── database.py                 # connexion et initialisation SQLite
│   ├── history.py                  # persistance et restauration de l'historique
│   └── twitch.py                   # OAuth, EventSub et écoute Twitch
└── web/
    ├── websocket.py                # connexions et diffusion de l'état
    ├── routes/                     # extraction future des routes de main.py
    │   ├── overlay.py              # page et WebSocket de l'overlay, à créer
    │   └── admin.py                # administration protégée, à créer
    └── static/
        ├── overlay.html            # squelette de l'overlay
        ├── overlay.js              # réception et rendu de l'état
        ├── admin.html              # interface d'administration, à créer
        └── admin.js                # logique d'administration, à créer

.env.example                  # modèle versionné avec valeurs fictives
requirements.txt              # dépendances Python épinglées

data/
├── settings.json           # future configuration administrable non versionnée
└── giveaway.sqlite3        # base non versionnée
```

Cette arborescence est indicative. Les règles métier doivent rester indépendantes de FastAPI, Twitch et SQLite afin de pouvoir être testées simplement.

## 5. Modèle d'état

L'overlay suit quatre états :

```text
HIDDEN --!lot--> WAITING --!start--> OPEN --!pull--> WINNER
   ^                 |                   |                |
   └-----------------┴------ !stop ------┴----------------┘
```

| État | Overlay | Inscriptions | Description |
|---|---|---|---|
| `HIDDEN` | Masqué | Refusées | Aucun giveaway visible. |
| `WAITING` | Visible | Refusées | Le lot est annoncé, mais les inscriptions ne sont pas ouvertes. |
| `OPEN` | Visible | Acceptées | Les viewers peuvent utiliser `!join`. |
| `WINNER` | Visible | Refusées | Le gagnant est affiché. |

L'état actif contient au minimum :

```json
{
  "state": "OPEN",
  "giveaway_id": "uuid",
  "lot": "Clavier mécanique",
  "participants": [
    {
      "twitch_user_id": "123456",
      "login": "viewer",
      "display_name": "Viewer"
    }
  ],
  "winner": null
}
```

## 6. Règles des commandes

| Commande | État requis | Résultat |
|---|---|---|
| `!lot <nom>` | `HIDDEN` | Crée le giveaway et passe à `WAITING`. |
| `!start` | `WAITING` | Passe à `OPEN`. |
| `!join` | `OPEN` | Ajoute le viewer s'il n'est pas déjà inscrit. |
| `!pull` | `OPEN` | Ferme les inscriptions, choisit un gagnant et passe à `WINNER`. |
| `!stop` | `WAITING`, `OPEN` ou `WINNER` | Archive l'état courant puis repasse à `HIDDEN`. |

Règles complémentaires :

- `!lot`, `!start`, `!pull` et `!stop` sont réservées au broadcaster configuré ;
- l'autorisation est vérifiée avec l'identifiant Twitch, pas avec le nom affiché ;
- `!lot` est refusé si un giveaway est déjà visible ;
- `!pull` est refusé lorsqu'aucun participant n'est inscrit ;
- le gagnant est choisi une seule fois côté serveur avec `secrets.choice` ;
- un verrou asynchrone protège `!join`, `!pull` et `!stop` contre les traitements concurrents ;
- chaque transition valide déclenche une sauvegarde SQLite et une diffusion WebSocket.

## 7. Overlay HTML

L'overlay reste volontairement sans thème. Il fournit des éléments avec des identifiants stables :

```html
<main id="giveaway" hidden>
  <div id="lot"></div>
  <div id="status"></div>
  <div id="participants"></div>
  <div id="winner"></div>
</main>
```

Le JavaScript de l'overlay :

1. ouvre le WebSocket ;
2. reçoit un instantané complet de l'état ;
3. met à jour le texte et les attributs du DOM ;
4. masque `#giveaway` dans l'état `HIDDEN` ;
5. tente automatiquement de se reconnecter en cas de coupure.

Aucun secret, tirage ou contrôle de permission ne se trouve dans le frontend.

## 8. Protocole WebSocket

### Endpoint

```text
GET /ws/overlay
```

À chaque connexion, le serveur envoie immédiatement l'état complet. Les mises à jour suivantes utilisent le même format afin d'éviter plusieurs protocoles différents.

Exemple :

```json
{
  "type": "giveaway.state",
  "data": {
    "state": "WINNER",
    "giveaway_id": "a0c5...",
    "lot": "Clavier mécanique",
    "participant_count": 24,
    "participants": ["Viewer1", "Viewer2"],
    "winner": {
      "twitch_user_id": "123456",
      "display_name": "Viewer1"
    }
  }
}
```

Le serveur conserve la liste des connexions actives et supprime proprement les clients déconnectés. Une source OBS rechargée retrouve donc immédiatement l'état courant.

## 9. Administration

### Pages et endpoints

| Méthode | Chemin | Usage |
|---|---|---|
| `GET` | `/admin` | Interface de configuration. |
| `GET` | `/api/admin/settings` | Lit la configuration, avec secrets masqués. |
| `PUT` | `/api/admin/settings` | Valide et enregistre la configuration. |
| `GET` | `/api/admin/history` | Liste paginée des giveaways. |
| `GET` | `/api/admin/history/{id}` | Détail et participants d'un giveaway. |
| `GET` | `/health` | Vérifie que le service répond. |

### Paramètres administrables

- identifiant du broadcaster Twitch ;
- nom du canal Twitch ;
- identifiants nécessaires à la connexion Twitch ;
- préfixe des commandes, fixé par défaut à `!` ;
- activation ou désactivation du connecteur Twitch ;
- durée de conservation de l'historique, si une purge est ajoutée.

Une modification de la configuration Twitch provoque une reconnexion contrôlée du connecteur. La configuration invalide est refusée sans écraser la dernière version valide.

### Protection de `/admin`

Tailscale limite l'accès au réseau privé, mais la page d'administration doit également être protégée :

- mot de passe administrateur unique pour le MVP ;
- mot de passe stocké sous forme de hash, jamais en clair ;
- session dans un cookie `HttpOnly`, `Secure` et `SameSite=Strict` ;
- limitation des tentatives de connexion ;
- règles ACL Tailscale limitant `/admin` aux appareils ou utilisateurs autorisés lorsque cela est possible.

Les secrets Twitch sont masqués dans les réponses de l'API. Une valeur secrète vide dans le formulaire signifie « conserver la valeur existante ».

## 10. Configuration

### Configuration locale actuelle

Le développement local utilise un fichier `.env` à la racine, chargé par `pydantic-settings`. Le modèle `Settings` valide actuellement :

- l'activation du connecteur Twitch ;
- le Client ID et le Client Secret de l'application Twitch ;
- les identifiants du bot, du propriétaire et du broadcaster ;
- les logins du bot et du canal ;
- le préfixe des commandes, avec `!` par défaut.

Le Client Secret est représenté avec `SecretStr`. Le fichier `.env` réel reste ignoré par Git et ne doit jamais être lu, affiché ou journalisé. `.env.example` documente les noms attendus avec des valeurs fictives. Les access tokens et refresh tokens ne sont pas saisis manuellement : ils sont obtenus pendant le parcours OAuth TwitchIO, sauvegardés dans `.tio.tokens.json` et rechargés au démarrage. Ce fichier est ignoré par Git et ne doit jamais être lu, affiché ou partagé.

`Settings`, le gestionnaire de commandes et le connecteur TwitchIO sont créés dans le cycle de vie FastAPI. Le connecteur démarre uniquement lorsque `TWITCH_ENABLED` est actif. L'adaptateur OAuth est activé séparément avec `TWITCH_OAUTH_ENABLED` et reste désactivé en fonctionnement normal afin de ne pas interférer avec la gestion des signaux d'Uvicorn. Pour le développement distant, il écoute alors sur `localhost:4343` et peut être transmis avec un tunnel SSH. L'application Twitch déclare `http://localhost:4343/oauth/callback` comme URL de redirection.

### Configuration JSON cible

Emplacement proposé :

```text
/var/lib/giveaway/settings.json
```

Exemple de structure :

```json
{
  "version": 1,
  "twitch": {
    "enabled": true,
    "bot_id": "123456",
    "owner_id": "654321",
    "broadcaster_id": "654321",
    "bot_login": "mon_bot",
    "channel_login": "ma_chaine"
  },
  "commands": {
    "prefix": "!"
  }
}
```

Le JSON contient uniquement les réglages non secrets modifiables depuis l'administration. Le Client ID, le Client Secret et le futur secret de bootstrap administrateur restent dans `.env`. Les tokens OAuth restent sous la responsabilité exclusive de TwitchIO dans `.tio.tokens.json`.

Contraintes :

- le fichier n'est jamais ajouté à Git ;
- il appartient à l'utilisateur système du service ;
- ses permissions sont limitées à `0600` ;
- les données sont validées avec un modèle Pydantic avant enregistrement ;
- l'écriture est atomique : fichier temporaire, synchronisation, puis renommage ;
- le fichier précédent est conservé comme sauvegarde lors d'une modification ;
- l'API ne renvoie jamais les tokens en clair.

Pour une version ultérieure, les secrets pourront être séparés du JSON et gérés avec `sops-nix` ou un mécanisme équivalent.

## 11. Historique SQLite

Emplacement proposé :

```text
/var/lib/giveaway/giveaway.sqlite3
```

### Table `giveaways`

| Colonne | Type | Description |
|---|---|---|
| `id` | TEXT, clé primaire | UUID du giveaway. |
| `lot` | TEXT | Nom du lot. |
| `status` | TEXT | `WAITING`, `OPEN`, `WINNER`, `COMPLETED` ou `CANCELLED`. |
| `created_at` | TEXT | Date UTC de `!lot`. |
| `opened_at` | TEXT, nullable | Date UTC de `!start`. |
| `drawn_at` | TEXT, nullable | Date UTC de `!pull`. |
| `stopped_at` | TEXT, nullable | Date UTC de `!stop`. |
| `winner_user_id` | TEXT, nullable | Identifiant Twitch du gagnant. |
| `winner_display_name` | TEXT, nullable | Nom affiché au moment du tirage. |

### Table `participants`

| Colonne | Type | Description |
|---|---|---|
| `id` | INTEGER, clé primaire | Identifiant local. |
| `giveaway_id` | TEXT | Référence vers `giveaways.id`. |
| `twitch_user_id` | TEXT | Identifiant Twitch stable. |
| `login` | TEXT | Login Twitch au moment de l'inscription. |
| `display_name` | TEXT | Nom affiché au moment de l'inscription. |
| `joined_at` | TEXT | Date UTC du `!join`. |

Une contrainte unique sur `(giveaway_id, twitch_user_id)` empêche les doubles inscriptions au niveau de la base. Un index unique partiel garantit également qu'une seule ligne peut avoir le statut `WAITING`, `OPEN` ou `WINNER`.

### Utilisation

- SQLite fonctionne en mode WAL ;
- les clés étrangères sont activées ;
- les transitions et inscriptions utilisent des transactions ;
- les dates sont enregistrées en UTC ;
- au démarrage, le service recharge le dernier giveaway dont le statut est `WAITING`, `OPEN` ou `WINNER` ;
- `!pull` enregistre le statut `WINNER` tant que le résultat reste affiché ;
- `!stop` transforme `WINNER` en `COMPLETED`, ou `WAITING`/`OPEN` en `CANCELLED`, puis masque l'overlay sans supprimer l'historique ;
- les migrations de schéma sont versionnées et exécutées au démarrage.

État actuel : les clés étrangères, les contraintes d'unicité, les dates UTC, l'enregistrement des transitions et la restauration sont implémentés. Le schéma est créé avec des instructions idempotentes `CREATE ... IF NOT EXISTS`. Le mode WAL et les migrations versionnées restent à ajouter avant le déploiement.

## 12. Cycle de démarrage

1. Charger et valider les secrets et paramètres Twitch depuis `.env` avec `Settings`.
2. Charger la future configuration administrable depuis `settings.json` lorsqu'elle sera disponible.
3. Ouvrir SQLite et appliquer les migrations.
4. Restaurer un éventuel giveaway actif.
5. Construire le service et le gestionnaire de commandes.
6. Démarrer l'API HTTP et le WebSocket.
7. Connecter le client Twitch si sa configuration est activée et valide.
8. Envoyer l'état restauré aux overlays qui se connectent.

État actuel : les étapes SQLite, restauration, service, API et WebSocket sont en place. Le modèle `Settings` est validé séparément mais n'est pas encore injecté dans ce cycle de démarrage.

Si Twitch est indisponible, l'administration et l'historique doivent rester accessibles. Le service tente une reconnexion avec un délai progressif plafonné.

## 13. Déploiement NixOS

Le déploiement doit être déclaratif :

- environnement Python reproductible avec un flake Nix ;
- utilisateur système dédié, sans shell interactif ;
- répertoire d'état `/var/lib/giveaway` ;
- unité systemd avec redémarrage automatique ;
- service applicatif lié à `127.0.0.1` ;
- publication HTTPS privée avec Tailscale Serve ;
- journaux accessibles avec `journalctl` ;
- sauvegarde périodique du JSON et de SQLite.

Le service ne doit pas ouvrir de port public sur Internet et ne doit pas modifier SSH, Tailscale ou le pare-feu en dehors de la configuration NixOS prévue.

## 14. Journalisation

Les journaux doivent contenir :

- démarrage et arrêt du service ;
- connexion et reconnexion Twitch ;
- commandes administratives acceptées ou refusées ;
- transitions d'état ;
- nombre d'inscriptions ;
- connexions WebSocket ;
- erreurs de base de données et de configuration.

Ils ne doivent jamais contenir :

- tokens OAuth ;
- mot de passe administrateur ;
- cookies de session ;
- contenu complet de la configuration secrète.

## 15. Tests minimaux

Les tests automatisés décrits ci-dessous restent l'objectif avant la fin du MVP, mais leur mise en place est volontairement reportée. Les contrôles actuellement exécutés sont : compilation Python, Ruff, BasedPyright et scénarios manuels en mémoire ou avec SQLite.

### Tests unitaires

- transitions entre les quatre états ;
- permissions broadcaster/viewer ;
- parseur des cinq commandes ;
- refus des commandes dans le mauvais état ;
- double `!join` ;
- `!pull` avec 0, 1 et plusieurs participants ;
- unicité et conservation du gagnant ;
- chargement et validation de `.env` sans exposition des secrets ;
- validation et écriture atomique du futur JSON administrable.

### Tests d'intégration

- enregistrement d'un cycle complet dans SQLite ;
- restauration après redémarrage ;
- réception de l'état initial par WebSocket ;
- diffusion d'une modification à plusieurs overlays ;
- modification valide et invalide depuis `/admin` ;
- protection des routes administratives.

### Scénario final

1. La DevBox démarre le service automatiquement.
2. Un PC du tailnet ouvre `/admin` et configure Twitch.
3. Plusieurs PC chargent `/overlay` dans OBS.
4. `!lot test` affiche le même lot partout.
5. `!start` ouvre les inscriptions.
6. Les `!join` valides sont enregistrés une seule fois.
7. `!pull` affiche le même gagnant partout.
8. Le giveaway apparaît dans l'historique.
9. `!stop` masque tous les overlays sans supprimer cet historique.

## 16. Ordre d'implémentation

1. [x] Moteur d'état, hors tests automatisés reportés.
2. [x] Base SQLite et restauration de l'état, hors migrations versionnées et WAL.
3. [x] API FastAPI et WebSocket de l'overlay.
4. [x] Overlay HTML/JavaScript minimal.
5. [x] Parseur de commandes et configuration locale `.env` typée.
6. [x] Dépendances TwitchIO et `pydantic-settings` épinglées.
7. [x] Injection de `Settings` dans le cycle de vie FastAPI.
8. [x] Autorisation OAuth et connexion au chat Twitch.
9. [ ] Configuration JSON, authentification et interface `/admin`.
10. [ ] Consultation de l'historique.
11. [ ] Déploiement NixOS et publication Tailscale.
12. [ ] Tests automatisés et essais depuis plusieurs PC et plusieurs sources OBS.
