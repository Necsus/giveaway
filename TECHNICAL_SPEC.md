# Spécification technique

## 1. Objectif

Construire un service central de giveaway Twitch multi-streamer hébergé sur la DevBox. Plusieurs streamers peuvent s'authentifier avec Twitch et utiliser simultanément leur propre giveaway. Tous les PC autorisés par Tailscale pourront accéder :

- à un overlay OBS propre à chaque streamer ;
- à une page d'administration authentifiée avec Twitch ;
- à un historique strictement limité au streamer connecté.

Le service reste la source de vérité. OBS affiche l'état reçu mais ne gère ni les commandes Twitch, ni les permissions, ni le tirage. Une application Twitch et un compte bot dédié sont partagés par l'instance ; le Client ID et le Client Secret identifient l'application, pas le compte bot.

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

Le fonctionnement actuel reste mono-streamer, avec un bot global fixe et un seul streamer dynamique connecté par `/admin`. Le `broadcaster_id` autorisé et le canal écouté proviennent de l'identité Twitch persistée dans SQLite après validation OAuth, jamais du navigateur ni de la configuration globale. L'isolation de plusieurs streamers simultanés viendra après cette étape. Les tests automatisés sont reportés ; les contrôles actuels sont manuels et complétés par Ruff et BasedPyright.

### Étape intermédiaire retenue

```text
Bot global fixe (necsus_dev, par exemple)
                │
                │ EventSub ChatMessageSubscription
                │ user_id = bot global
                │ broadcaster_user_id = streamer actif
                ▼
Streamer connecté à /admin (fluffy, par exemple)
                │
                └── son chat pilote l'unique moteur de giveaway
```

Pour cette étape :

- un seul streamer peut être actif à la fois ;
- l'application Twitch, le Client ID, le Client Secret et le compte bot ne changent pas lors d'une connexion admin ;
- le bot est autorisé une fois avec `user:read:chat`, `user:write:chat` et `user:bot` ;
- le streamer connecté autorise l'application avec `channel:bot` ;
- seul l'identifiant Twitch stable obtenu par OAuth définit le broadcaster autorisé ;
- la déconnexion de la session web n'arrête ni le bot, ni le giveaway actif ;
- les tokens restent gérés par TwitchIO et ne sont jamais enregistrés dans les tables métier.

## 2. Architecture retenue

```text
Application Twitch + bot dédié global
                  │
          EventSub multi-canaux
                  │
                  ▼
┌──────────────────────────────────────────────────────┐
│ Service Python / FastAPI sur la DevBox               │
│                                                      │
│ Streamer A ─ moteur A ─ historique A ─ /overlay/A   │
│ Streamer B ─ moteur B ─ historique B ─ /overlay/B   │
│                                                      │
│ /admin ─ authentification Twitch ─ session signée   │
└──────────────────────────────────────────────────────┘
                  │
           réseau Tailscale
                  ▼
          OBS et navigateurs
```

### Choix techniques

- **Langage serveur** : Python 3.
- **Serveur HTTP** : FastAPI avec Uvicorn.
- **Temps réel** : WebSocket natif de FastAPI.
- **Accès Twitch** : connecteur Python isolé du reste de l'application avec TwitchIO 3.
- **Frontend** : HTML et JavaScript natif, sans framework.
- **Configuration locale** : `.env` chargé et validé avec `pydantic-settings` ; valeurs réelles jamais versionnées.
- **Configuration globale** : fichier JSON local pour le bot dédié et les valeurs par défaut.
- **Configuration par streamer** : SQLite, indexée par identifiant Twitch stable.
- **Historique** : SQLite, toujours filtré par streamer.
- **Accès réseau** : Tailscale uniquement.
- **Déploiement** : service systemd déclaré dans la configuration NixOS.

## 3. Accès depuis les PC

Le service écoute localement sur la DevBox, par exemple :

```text
http://127.0.0.1:8000
```

Tailscale Serve publie ensuite ce service uniquement dans le tailnet avec une URL HTTPS, par exemple :

```text
https://devbox.<tailnet>.ts.net/overlay/<login_twitch>
https://devbox.<tailnet>.ts.net/admin
```

La fonctionnalité Tailscale Funnel ne doit pas être activée : elle rendrait le service accessible publiquement sur Internet.

### Source navigateur OBS

Chaque streamer utilise une URL dérivée de son login Twitch :

```text
https://devbox.<tailnet>.ts.net/overlay/<login_twitch>
```

Toutes les sources OBS utilisant cette URL partagent l'état de ce streamer, sans recevoir celui des autres. Un changement de login Twitch change l'URL de l'overlay. Chaque installation OBS peut appliquer son propre **CSS personnalisé**.

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
│   ├── configuration_store.py      # lecture et écriture atomique du JSON
│   ├── database.py                 # connexion et initialisation SQLite
│   ├── history.py                  # persistance et restauration de l'historique
│   └── twitch.py                   # OAuth, EventSub et écoute Twitch
└── web/
    ├── websocket.py                # connexions et diffusion de l'état
    ├── routes/
    │   ├── overlay.py              # page et WebSocket de l'overlay
    │   ├── admin.py                # page et API d'administration protégée
    │   └── auth.py                 # OAuth Twitch et session web
    └── static/
        ├── overlay.html            # squelette de l'overlay
        ├── overlay.js              # réception et rendu de l'état
        ├── admin.html              # interface d'administration
        └── admin.js                # logique d'administration

.env.example                  # modèle versionné avec valeurs fictives
requirements.txt              # dépendances Python épinglées

data/
├── settings.json           # configuration administrable non versionnée
└── giveaway.sqlite3        # base non versionnée
```

Cette arborescence est indicative. Les règles métier doivent rester indépendantes de FastAPI, Twitch et SQLite afin de pouvoir être testées simplement.

## 5. Modèle d'état

L'overlay suit quatre états :

```text
HIDDEN --!galot--> WAITING --!gastart--> OPEN --!gapull--> WINNER
   ^                   |                     |                  |
   └-------------------┴------ !gastop -------┴------------------┘
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
| `!galot <nom>` | `HIDDEN` | Crée le giveaway et passe à `WAITING`. |
| `!gastart` | `WAITING` | Passe à `OPEN`. |
| `!join` | `OPEN` | Ajoute le viewer s'il n'est pas déjà inscrit. |
| `!gapull` | `OPEN` | Ferme les inscriptions, choisit un gagnant et passe à `WINNER`. |
| `!gastop` | `WAITING`, `OPEN` ou `WINNER` | Archive l'état courant puis repasse à `HIDDEN`. |

Règles complémentaires :

- `!galot`, `!gastart`, `!gapull` et `!gastop` sont réservées au broadcaster du canal où la commande est reçue ;
- l'autorisation est vérifiée avec l'identifiant Twitch, pas avec le nom affiché ;
- `!galot` est refusé si un giveaway est déjà visible ;
- `!gapull` est refusé lorsqu'aucun participant n'est inscrit ;
- le gagnant est choisi une seule fois côté serveur avec `secrets.choice` ;
- un verrou asynchrone protège `!join`, `!gapull` et `!gastop` contre les traitements concurrents ;
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
GET /ws/overlay/{login_twitch}
```

À chaque connexion, le serveur résout le login Twitch, rattache la connexion au gestionnaire WebSocket de ce streamer et envoie immédiatement son état complet. Les mises à jour suivantes utilisent le même format afin d'éviter plusieurs protocoles différents.

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

Le serveur conserve les connexions actives par streamer et supprime proprement les clients déconnectés. Une source OBS rechargée retrouve immédiatement l'état du streamer ciblé, sans diffusion croisée entre les chaînes.

## 9. Administration Twitch

### Première étape mono-streamer dynamique

La première livraison conserve un moteur, un historique et un overlay uniques. La connexion admin choisit le streamer actif dont le chat est écouté par le bot global. Une connexion avec un autre compte remplace explicitement le streamer actif et son abonnement, sans transformer encore le service en plateforme multi-streamer simultanée.

Le premier tableau de bord affiche uniquement l'identité Twitch, le bot global, l'état de l'abonnement au chat, l'URL OBS et la déconnexion. Les réglages et l'historique administratif restent des étapes ultérieures.

### Authentification Twitch

La page `/admin` présente un bouton **Se connecter avec Twitch**. Le parcours OAuth demande au streamer l'autorisation `channel:bot`, récupère son identifiant Twitch stable, met à jour son login et son nom affiché, puis crée une session signée.

Le compte bot dédié est autorisé une seule fois avec `user:read:chat`, `user:write:chat` et `user:bot`. Chaque streamer autorise ensuite ce bot sur sa propre chaîne. Les tokens restent gérés par TwitchIO et ne sont jamais copiés dans SQLite ni envoyés au navigateur.

L'accès réseau Tailscale constitue la première barrière. Tout membre du tailnet peut tenter une authentification Twitch et créer son espace. Une session valide reste obligatoire pour toutes les routes administratives.

### Pages et endpoints cibles

| Méthode | Chemin | Usage |
|---|---|---|
| `GET` | `/admin` | Affiche le bouton Twitch ou l'espace du streamer connecté. |
| `GET` | `/auth/twitch/login` | Démarre OAuth streamer avec un état anti-CSRF. |
| `GET` | `/auth/twitch/bot/login` | Autorise ou réautorise le bot global configuré. |
| `GET` | `/auth/twitch/callback` | Valide le flux OAuth bot ou streamer à partir de l'état à usage unique. |
| `POST` | `/auth/logout` | Ferme la session. |
| `GET` | `/api/admin/settings` | Lit les réglages du streamer connecté. |
| `PUT` | `/api/admin/settings` | Valide et enregistre ses réglages. |
| `GET` | `/api/admin/history` | Liste paginée de ses giveaways uniquement. |
| `GET` | `/api/admin/history/{id}` | Retourne un giveaway s'il lui appartient. |
| `GET` | `/health` | Vérifie que le service répond. |

### Session et isolation

- cookie signé `HttpOnly`, `Secure` et `SameSite=Lax` pour permettre le retour OAuth ;
- état OAuth aléatoire, court et à usage unique pour prévenir le CSRF ;
- identifiant Twitch de session utilisé dans chaque requête SQL ;
- aucune confiance accordée à un `broadcaster_id` fourni par le navigateur ;
- un giveaway d'un autre streamer retourne `404`, afin de ne pas révéler son existence ;
- déconnexion et expiration de session prises en charge.

### Paramètres par streamer

- activation de son connecteur et de ses abonnements ;
- préfixe des commandes, `!` par défaut ;
- login Twitch actualisé lors de chaque connexion ;
- futures préférences d'affichage et de conservation de l'historique.

L'identifiant Twitch du streamer provient uniquement d'OAuth et n'est pas modifiable depuis le formulaire.

## 10. Configuration

### Configuration locale actuelle

Le développement local utilise un fichier `.env` à la racine, chargé par `pydantic-settings`. Il contient les secrets, le callback HTTPS, les identifiants globaux du bot et le chemin du fichier JSON. L'identité streamer n'y figure plus. Les réglages globaux servent à initialiser `settings.json` lorsque celui-ci n'existe pas encore.

Le Client Secret est représenté avec `SecretStr`. Le fichier `.env` réel reste ignoré par Git et ne doit jamais être lu, affiché ou journalisé. `.env.example` documente les noms attendus avec des valeurs fictives. Les access tokens et refresh tokens ne sont pas saisis manuellement : ils sont obtenus par les parcours OAuth FastAPI, confiés à TwitchIO, sauvegardés dans `.tio.tokens.json` et rechargés au démarrage. Ce fichier est ignoré par Git et ne doit jamais être lu, affiché ou partagé.

`Settings` et `ConfigurationStore` sont créés dans le cycle de vie FastAPI. Si le JSON est absent, une configuration initiale est construite depuis `.env` puis enregistrée. Lors des démarrages suivants, le JSON validé devient prioritaire pour les réglages non secrets. Le gestionnaire de commandes et le connecteur TwitchIO utilisent cette configuration effective.

Le bot global est autorisé depuis `/auth/twitch/bot/login` avec `user:read:chat`, `user:write:chat` et `user:bot`. Le callback HTTPS `/auth/twitch/callback` valide que l'identité obtenue correspond au `bot_id` configuré, puis demande à TwitchIO de sauvegarder immédiatement le token. Le même callback traite le flux streamer `channel:bot` avec un état OAuth distinct.

### Configuration JSON administrable

Le modèle Pydantic version 2, le stockage JSON atomique et leur injection dans le cycle de vie FastAPI sont implémentés. Le JSON est limité à la configuration globale du bot ; l'identité du streamer actif est déjà stockée dans SQLite.

Emplacement local par défaut :

```text
data/settings.json
```

Emplacement cible pour le service NixOS :

```text
/var/lib/giveaway/settings.json
```

Structure globale actuelle :

```json
{
  "version": 2,
  "twitch": {
    "enabled": true,
    "bot_id": "123456",
    "owner_id": "123456",
    "bot_login": "mon_bot"
  },
  "commands": {
    "prefix": "!"
  }
}
```

Le JSON contient uniquement les réglages globaux non secrets du bot dédié. Le Client ID, le Client Secret et le secret de signature des sessions restent dans `.env`. Les tokens OAuth restent sous la responsabilité exclusive de TwitchIO dans `.tio.tokens.json`. Les identités et préférences des streamers sont stockées dans SQLite.

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

### Table `streamers` cible

| Colonne | Type | Description |
|---|---|---|
| `twitch_user_id` | TEXT, clé primaire | Identifiant Twitch stable obtenu par OAuth. |
| `login` | TEXT, unique | Login Twitch utilisé dans l'URL d'overlay. |
| `display_name` | TEXT | Nom affiché actualisé à la connexion. |
| `profile_image_url` | TEXT | URL publique de l'avatar actualisée à la connexion. |
| `enabled` | INTEGER | Active ou désactive les abonnements du streamer ; une contrainte partielle limite cette valeur à un seul streamer pendant l'étape mono-streamer dynamique. |
| `command_prefix` | TEXT | Préfixe de commandes propre au streamer. |
| `created_at` | TEXT | Date UTC de création de l'espace. |
| `updated_at` | TEXT | Dernière actualisation OAuth ou administrative. |

Les access tokens et refresh tokens ne sont pas stockés dans cette table. Pendant l'étape intermédiaire, un index unique partiel sur une expression constante avec `WHERE enabled = 1` garantit qu'un seul streamer est actif. Cette contrainte sera remplacée lorsque les runtimes multi-streamers seront implémentés.

### Table `giveaways`

| Colonne | Type | Description |
|---|---|---|
| `id` | TEXT, clé primaire | UUID du giveaway. |
| `broadcaster_id` | TEXT, clé étrangère | Propriétaire du giveaway, référence `streamers.twitch_user_id`. |
| `lot` | TEXT | Nom du lot. |
| `status` | TEXT | `WAITING`, `OPEN`, `WINNER`, `COMPLETED` ou `CANCELLED`. |
| `created_at` | TEXT | Date UTC de `!galot`. |
| `opened_at` | TEXT, nullable | Date UTC de `!gastart`. |
| `drawn_at` | TEXT, nullable | Date UTC de `!gapull`. |
| `stopped_at` | TEXT, nullable | Date UTC de `!gastop`. |
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

Une contrainte unique sur `(giveaway_id, twitch_user_id)` empêche les doubles inscriptions au niveau de la base. L'index unique partiel actuel, global, devra être remplacé par un index sur `broadcaster_id` garantissant au plus un giveaway `WAITING`, `OPEN` ou `WINNER` par streamer. Plusieurs streamers pourront ainsi avoir un giveaway actif simultanément.

### Utilisation

- SQLite fonctionne en mode WAL ;
- les clés étrangères sont activées ;
- les transitions et inscriptions utilisent des transactions ;
- les dates sont enregistrées en UTC ;
- au démarrage, le service recharge au plus un giveaway actif par streamer ;
- `!gapull` enregistre le statut `WINNER` tant que le résultat reste affiché ;
- `!gastop` transforme `WINNER` en `COMPLETED`, ou `WAITING`/`OPEN` en `CANCELLED`, puis masque l'overlay sans supprimer l'historique ;
- les migrations de schéma sont versionnées et exécutées au démarrage.

État actuel : le schéma mono-streamer utilise encore une unicité globale. La migration devra créer `streamers`, rattacher les données existantes au streamer de bootstrap, ajouter `giveaways.broadcaster_id`, remplacer l'index global et versionner le schéma sans perdre l'historique. Le mode WAL reste également à ajouter avant le déploiement.

## 12. Cycle de démarrage

1. Charger les secrets globaux depuis `.env` et la configuration du bot depuis `settings.json`.
2. Ouvrir SQLite et exécuter les migrations versionnées.
3. Charger tous les streamers autorisés et leurs réglages.
4. Restaurer au plus un giveaway actif par streamer.
5. Construire un registre de moteurs, services et gestionnaires WebSocket indexé par identifiant Twitch.
6. Charger les tokens OAuth gérés par TwitchIO.
7. Connecter le bot global et rétablir les abonnements EventSub de chaque streamer actif.
8. Démarrer les routes HTTP, OAuth, administratives et les overlays contextualisés.

Étape intermédiaire active : charger au plus un streamer actif, démarrer le bot global avec ses propres tokens, puis créer l'abonnement EventSub de ce streamer. OAuth dans FastAPI doit pouvoir remplacer cet abonnement dynamiquement. Le registre de runtimes multi-streamers reste une évolution ultérieure.

Si Twitch est indisponible, l'administration et l'historique doivent rester accessibles. Le service tente une reconnexion avec un délai progressif plafonné.

## 13. Performance, charge et résilience

### Mesures de référence

Un test local isolé, sans Twitch ni cycle de vie applicatif, a donné les résultats suivants sur la DevBox :

- 5 000 requêtes `GET /health`, concurrence 100 : aucune erreur, environ 6 875 requêtes/s ;
- latence HTTP p95 : environ 17 ms ;
- 300 connexions WebSocket ouvertes simultanément : aucune erreur ;
- processus de développement : environ 79 Mio de RAM ;
- limite souple actuelle : 1 024 descripteurs de fichiers.

Ces mesures valident uniquement le coût des routes simples. Elles ne constituent pas une garantie de capacité pour SQLite, TwitchIO, les diffusions d'état ou le futur fonctionnement multi-streamer.

### Diffusion WebSocket

La diffusion séquentielle actuelle est bloquante : 100 clients prenant chacun 10 ms produisent environ une seconde de latence. La cible doit :

- sortir la diffusion du verrou métier ;
- utiliser une file bornée par streamer, avec remplacement par l'état le plus récent ;
- envoyer aux connexions en parallèle ;
- imposer un délai maximal d'envoi ;
- supprimer les clients lents ou déconnectés ;
- itérer sur un instantané stable des connexions ;
- limiter les connexions par streamer et la taille des messages entrants ;
- utiliser une reconnexion exponentielle avec jitter dans le navigateur.

L'événement d'overlay ne doit contenir que l'état, le lot, le nombre de participants et le gagnant. La liste complète des participants est réservée à une API administrative paginée. À titre de comparaison, l'instantané actuel atteint environ 126 Kio avec 10 000 participants.

### SQLite et cohérence

Les écritures SQLite synchrones ne doivent pas bloquer la boucle événementielle. La cible utilise un accès asynchrone ou une file d'écriture dédiée, avec :

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
```

Une transition ne doit jamais rester appliquée uniquement en mémoire si SQLite échoue. Les opérations doivent être transactionnelles ou restaurer explicitement l'état précédent. Les requêtes d'historique sont paginées et indexées au minimum sur `(broadcaster_id, created_at)`.

### Processus et supervision

Tant que les moteurs, le bot et les connexions WebSocket sont conservés en mémoire, Uvicorn doit utiliser un seul worker. Plusieurs workers créeraient des états divergents. Une montée horizontale nécessiterait une source d'état et un bus de diffusion partagés.

La tâche TwitchIO doit être supervisée : ses exceptions sont journalisées immédiatement, une reconnexion progressive est tentée et son état alimente un endpoint de disponibilité. Les contrôles HTTP sont séparés en :

- `live` : le processus et la boucle événementielle répondent ;
- `ready` : SQLite est accessible et les composants requis sont opérationnels.

Le futur service systemd définit `LimitNOFILE=65536`, redémarre automatiquement après un crash et réduit les access logs en production. Des métriques doivent suivre le nombre de WebSockets, la latence de diffusion, les commandes, les erreurs SQLite et l'état Twitch.

### Critères avant exposition à une charge importante

- 10 000 participants ne font pas grossir le message d'overlay au-delà de quelques Kio ;
- un client lent ne retarde pas les commandes ni les autres overlays ;
- 500 WebSockets simultanés restent stables ;
- une panne SQLite ne désynchronise jamais la mémoire ;
- une panne TwitchIO est détectée et récupérée sans arrêter FastAPI ;
- des tests de charge couvrent au moins deux streamers actifs simultanément.

## 14. Déploiement NixOS

Le déploiement doit être déclaratif :

- environnement Python reproductible avec un flake Nix ;
- utilisateur système dédié, sans shell interactif ;
- répertoire d'état `/var/lib/giveaway` ;
- unité systemd avec redémarrage automatique et `LimitNOFILE=65536` ;
- un seul worker Uvicorn tant que l'état reste en mémoire ;
- service applicatif lié à `127.0.0.1` ;
- publication HTTPS privée avec Tailscale Serve ;
- journaux applicatifs accessibles avec `journalctl` et access logs réduits ;
- sauvegarde périodique du JSON et de SQLite.

Le service ne doit pas ouvrir de port public sur Internet et ne doit pas modifier SSH, Tailscale ou le pare-feu en dehors de la configuration NixOS prévue.

## 15. Journalisation

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
- états OAuth anti-CSRF ;
- secret de signature ou contenu des cookies de session ;
- contenu complet de la configuration secrète.

## 16. Tests minimaux

Les tests automatisés décrits ci-dessous restent l'objectif avant la fin du MVP, mais leur mise en place est volontairement reportée. Les contrôles actuellement exécutés sont : compilation Python, Ruff, BasedPyright et scénarios manuels en mémoire ou avec SQLite.

### Tests unitaires

- transitions entre les quatre états ;
- permissions broadcaster/viewer ;
- parseur des cinq commandes ;
- refus des commandes dans le mauvais état ;
- double `!join` ;
- `!gapull` avec 0, 1 et plusieurs participants ;
- unicité et conservation du gagnant ;
- chargement et validation de `.env` sans exposition des secrets ;
- validation et écriture atomique du JSON global ;
- résolution d'un runtime par identifiant Twitch ;
- isolation des commandes, états et WebSockets entre streamers.

### Tests d'intégration

- enregistrement d'un cycle complet dans SQLite ;
- restauration après redémarrage ;
- réception de l'état initial par WebSocket ;
- diffusion d'une modification à plusieurs overlays ;
- authentification Twitch, état OAuth anti-CSRF et session signée ;
- création et actualisation d'un streamer à la connexion ;
- historique filtré par le streamer de session ;
- refus d'accès au giveaway d'un autre streamer ;
- deux giveaways actifs simultanés sur deux chaînes ;
- absence de diffusion croisée entre leurs overlays ;
- charge HTTP et WebSocket avec suivi des erreurs et latences ;
- client WebSocket lent pendant une rafale de commandes ;
- panne SQLite injectée pendant chaque transition ;
- arrêt et reconnexion du client TwitchIO.

### Scénario final

1. La DevBox démarre le bot dédié et restaure les streamers autorisés.
2. Les streamers A et B ouvrent `/admin` depuis le tailnet et se connectent avec Twitch.
3. Chacun autorise le bot sur sa chaîne et obtient son URL `/overlay/<login_twitch>`.
4. Les deux streamers lancent simultanément un giveaway différent.
5. Les commandes et participants de A ne modifient jamais l'état de B.
6. Chaque overlay reçoit uniquement les mises à jour de son streamer.
7. Chaque administration affiche uniquement son propre historique.
8. Après redémarrage, les deux états actifs et abonnements sont restaurés.
9. Un changement de login Twitch actualise l'identité et produit la nouvelle URL d'overlay.

## 17. Ordre d'implémentation

1. [x] Moteur d'état, hors tests automatisés reportés.
2. [x] Base SQLite et restauration de l'état, hors migrations versionnées et WAL.
3. [x] API FastAPI et WebSocket de l'overlay.
4. [x] Overlay HTML/JavaScript minimal.
5. [x] Parseur de commandes et configuration locale `.env` typée.
6. [x] Dépendances TwitchIO et `pydantic-settings` épinglées.
7. [x] Injection de `Settings` dans le cycle de vie FastAPI.
8. [x] Autorisation OAuth et connexion au chat Twitch.
9. [x] Modèle et stockage atomique de la configuration JSON mono-streamer.
10. [x] Table SQLite et persistance d'un streamer actif unique.
11. [x] Authentification Twitch dans FastAPI, état OAuth et session signée.
12. [x] Souscription dynamique du bot global au chat du streamer actif.
13. [x] Première page `/admin` : identité, bot, état du chat, URL OBS et déconnexion.
14. [ ] Réduction des payloads et diffusion WebSocket non bloquante avec backpressure.
15. [ ] SQLite WAL, accès non bloquant et cohérence transactionnelle mémoire/base.
16. [ ] Supervision TwitchIO, santé `live`/`ready` et limites de ressources.
17. [ ] Migrations SQLite versionnées et rattachement des données existantes à un streamer.
18. [ ] Registre de runtimes isolés par streamer et overlays `/overlay/{login}`.
19. [ ] Extension de l'administration et de l'historique filtrés par streamer.
20. [ ] Abonnements EventSub simultanés pour plusieurs streamers.
21. [ ] Déploiement NixOS et publication Tailscale.
22. [ ] Tests automatisés multi-streamer, charge et essais depuis plusieurs OBS.
