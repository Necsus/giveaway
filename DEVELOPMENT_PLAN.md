# Plan de développement

Plan pour faire évoluer le giveaway mono-streamer actuel vers un service multi-streamer utilisable simultanément depuis plusieurs chaînes Twitch.

> Avancement actuel : le parcours complet fonctionne avec une identité bot et broadcaster configurée au démarrage. La priorité est désormais une administration OAuth mono-streamer : le bot global reste fixe, tandis que le streamer actif et son canal proviennent de la connexion à `/admin`. La cible multi-streamer simultanée viendra ensuite.

## Priorité active — administration mono-streamer dynamique

Cette étape rend une même installation utilisable successivement par différents streamers sans modifier sa configuration locale. Un seul streamer et un seul giveaway restent actifs à la fois.

### Répartition des rôles

- **DEV** : l'utilisateur conçoit et écrit le code, exécute les validations et explique ses choix.
- **IA** : l'IA explique les concepts, découpe le travail, fournit des indices et effectue la revue sans modifier le code source.
- Une seule tâche marquée **EN COURS** est travaillée à la fois.

### A. Identité persistante du streamer actif

- [x] **DEV** : ajouter le schéma SQLite minimal de `streamers` avec l'identifiant Twitch stable, le login, le nom affiché, l'état actif et les dates UTC.
- [x] **DEV** : garantir au niveau SQLite qu'un seul streamer peut être actif.
- [x] **DEV** : ajouter l'opération de persistance pour enregistrer ou actualiser le streamer actif.
- [x] **DEV** : ajouter l'opération de persistance pour charger le streamer actif.
- [x] **IA** : expliquer les identifiants stables, les contraintes SQLite et relire chaque modification.

#### Validation A

- La création répétée du même identifiant Twitch actualise son login et son nom affiché sans créer de doublon.
- Deux streamers ne peuvent pas être actifs simultanément.
- Aucun access token ni refresh token n'est enregistré dans SQLite.
- Un redémarrage permet de retrouver l'identité du streamer actif.

### B. Authentification web Twitch

- [x] **DEV** : ajouter la configuration fictive du redirect URI et du secret de session dans `.env.example`.
- [x] **DEV** : construire l'URL d'autorisation Twitch avec le scope streamer `channel:bot`.
- [x] **DEV** : créer un état OAuth aléatoire, expirant et à usage unique.
- [x] **DEV** : implémenter `GET /auth/twitch/login` avec une redirection vers Twitch.
- [x] **DEV** : échanger le code OAuth et valider le Client ID, l'identité et le scope auprès de Twitch.
- [x] **DEV** : récupérer le profil Twitch validé, notamment le nom affiché.
- [x] **DEV** : implémenter `GET /auth/twitch/callback` et y valider le `state` avant tout échange.
- [x] **DEV** : persister l'identité validée sans accepter de `broadcaster_id` venant du navigateur.
- [x] **DEV** : signer et vérifier une identité de session avec expiration et contenu minimal.
- [x] **DEV** : créer le cookie de session `HttpOnly`, `Secure` en production et `SameSite=Lax`.
- [x] **DEV** : ajouter `POST /auth/logout` et l'expiration de session.
- [x] **DEV** : ajouter une dépendance de session réutilisable qui refuse les cookies absents, invalides ou expirés.
- [x] **DEV** : protéger une première route `/api/admin/*` et vérifier qu'elle retourne `401` sans session valide.
- [x] **IA** : expliquer Authorization Code, CSRF, cookies signés et séparation entre session et tokens OAuth.

#### Validation B

- Un état OAuth absent, expiré ou déjà utilisé est refusé.
- La session contient uniquement une identité Twitch validée côté serveur.
- Les tokens et secrets ne sont ni envoyés au navigateur, ni écrits dans SQLite, ni journalisés.
- Une route `/api/admin/*` retourne `401` sans session valide.

### C. Bot fixe et canal dynamique

- [x] **DEV** : conserver l'identité et les scopes du bot global indépendamment du streamer actif.
- [x] **DEV** : retirer la souscription EventSub statique construite avec le broadcaster configuré au démarrage.
- [x] **DEV** : ajouter au bot une opération dynamique qui enregistre le token streamer dans TwitchIO et souscrit au chat.
- [x] **DEV** : construire `ChatMessageSubscription` avec `broadcaster_user_id` égal au streamer et `user_id` égal au bot.
- [x] **DEV** : appeler l'abonnement dynamique après le callback OAuth sans exposer les tokens.
- [x] **DEV** : supprimer ou désactiver l'ancien abonnement lors d'un changement de streamer et ignorer tout événement d'un autre canal.
- [x] **DEV** : rendre l'autorisation des commandes de gestion dépendante de l'identifiant du streamer actif.
- [x] **DEV** : restaurer l'abonnement du streamer actif au redémarrage.
- [x] **IA** : expliquer la distinction application, bot, broadcaster, token et abonnement EventSub.

#### Validation C

Avec `fluffy` comme streamer actif et `necsus_dev` comme bot :

- le bot reçoit les messages du chat de `fluffy` ;
- seul `fluffy` peut utiliser `!galot`, `!gastart`, `!gapull` et `!gastop` ;
- les viewers du canal peuvent utiliser `!join` ;
- les messages d'une ancienne chaîne ne modifient pas le giveaway.

### D. Première page d'administration

- [x] **DEV** : créer `/admin` et afficher un bouton **Se connecter avec Twitch** sans session.
- [x] **DEV** : afficher après connexion l'avatar, le nom, le login, le streamer actif et le bot global.
- [x] **DEV** : afficher séparément l'état de la session et l'état de l'abonnement au chat.
- [x] **DEV** : afficher l'URL OBS actuelle avec une action de copie.
- [x] **DEV** : ajouter le bouton de déconnexion sans arrêter le bot ni désactiver le streamer.
- [x] **IA** : relire l'accessibilité, les états d'erreur et l'absence de secrets dans le frontend.
- [x] **IA** : appliquer un design sombre, minimaliste et responsive à la page d'administration, sans dépendance frontend externe.

#### Validation D

- La page distingue clairement une session déconnectée, connectée et une connexion Twitch dégradée.
- Une déconnexion ferme la session web mais ne coupe pas le giveaway en cours.
- Recharger la page restaure correctement l'affichage depuis la session.

### E. Nettoyage des chemins remplacés

Le nettoyage suit toujours l'ordre **remplacer, valider, puis supprimer** afin de ne pas perdre l'autorisation du bot ni l'accès au chat pendant la migration.

#### Nettoyage lié à A — identité persistante

- [x] **DEV** : retirer les anciennes variables d'environnement du streamer de `Settings`, de `.env.example` et du bootstrap JSON.
- [x] **DEV** : retirer les anciens champs streamer de la configuration globale lorsque SQLite est devenue l'unique source de son identité.

#### Nettoyage lié à B — authentification web

- [x] **DEV** : fournir et valider `/auth/twitch/bot/login` comme mécanisme unique d'autorisation initiale du bot global.
- [x] **DEV** : supprimer le pilotage de l'adaptateur OAuth local TwitchIO et démarrer TwitchIO sans cet adaptateur.
- [x] **DEV** : supprimer du README et de la spécification le tunnel SSH et les anciennes instructions d'autorisation locale.
- [x] **DEV** : utiliser `/auth/twitch/callback` comme callback HTTPS unique, avec des états distincts pour les flux bot et streamer.

#### Nettoyage lié à C — canal dynamique

- [x] **DEV** : construire les abonnements EventSub uniquement à partir du streamer actif chargé depuis SQLite.
- [x] **DEV** : supprimer les branches de compatibilité avec l'ancien broadcaster statique.
- [x] **DEV** : supprimer les anciennes souscriptions de chat lors d'un changement de streamer et restaurer uniquement la souscription active.

#### Nettoyage lié à D — administration

- [x] **DEV** : supprimer les réponses, routes et éléments frontend temporaires remplacés pendant la construction de `/admin`.
- [x] **DEV** : vérifier qu'aucun ancien réglage streamer n'est affiché ou accepté par l'administration.
- [x] **DEV** : supprimer les références mortes du code et actualiser la documentation.

#### Validation du nettoyage

- Une recherche globale ne trouve plus les anciens noms de variables d'environnement ni l'ancien callback local.
- Le démarrage normal ne dépend plus d'un broadcaster statique dans `.env` ou `settings.json`.
- Le bot global peut être autorisé puis restauré après suppression de l'ancien adaptateur.
- Il existe un seul callback HTTPS et une seule source de vérité SQLite pour l'identité streamer.

## 1. Socle mono-streamer terminé

- [x] Définir les états `HIDDEN`, `WAITING`, `OPEN` et `WINNER`.
- [x] Gérer `!galot`, `!gastart`, `!join`, `!gapull` et `!gastop`.
- [x] Réserver les commandes de gestion au broadcaster.
- [x] Empêcher les doubles inscriptions.
- [x] Choisir le gagnant côté serveur avec `secrets.choice`.
- [x] Persister et restaurer l'état avec SQLite.
- [x] Synchroniser plusieurs overlays avec WebSocket.
- [x] Connecter TwitchIO avec OAuth et EventSub.
- [x] Charger les secrets depuis `.env`.
- [x] Valider et écrire atomiquement `settings.json`.
- [x] Injecter la configuration dans le cycle de vie FastAPI.
- [x] Tester manuellement le parcours Twitch complet dans OBS.

### Évolution planifiée — plusieurs gagnants pour un même lot

- [x] Remplacer le gagnant unique par une collection ordonnée de gagnants.
- [x] Faire du premier `!gapull` la fermeture définitive des inscriptions pour le lot courant et le tirage du premier gagnant.
- [x] Autoriser de nouveaux `!gapull` dans l'état `WINNER` jusqu'à `!gastop`.
- [x] Exclure des tirages suivants tous les utilisateurs ayant déjà gagné ce lot.
- [x] Refuser proprement un nouveau tirage lorsque tous les participants ont déjà gagné.
- [x] Persister l'ordre de tous les gagnants et le restaurer après redémarrage.
- [x] Afficher la liste des gagnants dans l'overlay et les événements WebSocket.

#### Validation des tirages multiples

- Les inscriptions restent ouvertes jusqu'au premier `!gapull`, puis sont définitivement fermées pour ce lot.
- Chaque `!gapull` accepté ajoute un gagnant qui n'a encore jamais gagné ce lot.
- Les tirages peuvent continuer autant que nécessaire jusqu'à `!gastop` ou jusqu'à épuisement des participants.
- Un redémarrage conserve tous les gagnants déjà tirés et leur ordre.
- `!gastop` archive le lot avec l'ensemble de ses gagnants.

## 2. Stabilisation sous charge

- [ ] Retirer la liste complète des participants des événements WebSocket de l'overlay.
- [ ] Exposer les participants uniquement dans une API administrative paginée.
- [ ] Sortir les diffusions WebSocket du verrou métier.
- [ ] Utiliser une file bornée par streamer qui conserve uniquement l'état le plus récent.
- [ ] Envoyer aux overlays en parallèle avec un délai maximal par connexion.
- [ ] Déconnecter les clients trop lents ou défaillants.
- [ ] Remplacer la liste de participants en mémoire par une structure indexée par identifiant Twitch.
- [ ] Passer SQLite en mode WAL avec `busy_timeout`.
- [ ] Retirer les écritures SQLite synchrones de la boucle événementielle.
- [ ] Garantir la cohérence entre l'état mémoire et SQLite lors d'un échec.
- [ ] Superviser la tâche TwitchIO et ajouter une reconnexion progressive.
- [ ] Distinguer les contrôles de santé `live` et `ready`.
- [ ] Ajouter un backoff exponentiel avec jitter à la reconnexion de l'overlay.
- [ ] Limiter la taille et le nombre des connexions WebSocket.
- [ ] Configurer `LimitNOFILE=65536` dans le futur service NixOS.
- [ ] Désactiver ou réduire les access logs en production.

### Validation de charge

- 10 000 participants ne font pas grossir le message d'overlay au-delà de quelques Kio.
- Un overlay lent ne retarde ni une commande Twitch ni les autres overlays.
- 500 connexions WebSocket simultanées restent stables sans fuite de descripteurs.
- Une erreur SQLite ne laisse jamais l'état mémoire diverger de la base.
- La perte de TwitchIO est visible dans `ready` et déclenche une reconnexion.
- Le service fonctionne avec un seul worker Uvicorn tant que l'état reste en mémoire.

## 3. Modèle multi-streamer

- [ ] Ajouter une table `streamers` indexée par identifiant Twitch.
- [ ] Ajouter `broadcaster_id` aux giveaways existants.
- [ ] Rattacher l'historique actuel au streamer de bootstrap sans perte de données.
- [ ] Remplacer l'unicité globale par un giveaway actif maximum par streamer.
- [ ] Ajouter des migrations SQLite versionnées.
- [ ] Déplacer les réglages propres aux streamers du JSON vers SQLite.
- [ ] Limiter le JSON aux réglages globaux non secrets du bot dédié.

### Validation

- Deux streamers peuvent avoir chacun un giveaway actif.
- Les participants et gagnants restent rattachés au bon streamer.
- Une migration conserve l'historique mono-streamer existant.
- Un JSON ou une migration invalide n'écrase aucune donnée valide.

## 4. Runtimes et overlays isolés

- [ ] Créer un registre de moteurs et services indexé par identifiant Twitch.
- [ ] Restaurer un moteur actif par streamer au démarrage.
- [ ] Séparer les connexions WebSocket par streamer.
- [ ] Exposer `/overlay/{login_twitch}`.
- [ ] Exposer `/ws/overlay/{login_twitch}`.
- [ ] Résoudre le login vers l'identifiant Twitch stable.
- [ ] Actualiser le login après chaque authentification Twitch.

### Validation

- Une commande reçue sur la chaîne A ne modifie jamais l'état B.
- `/overlay/a` et `/overlay/b` affichent des giveaways indépendants.
- Plusieurs OBS peuvent suivre le même streamer.
- Un changement de login produit une nouvelle URL sans mélanger l'historique.

## 5. Bot global et EventSub multi-canaux

- [ ] Utiliser une application Twitch globale : Client ID et Client Secret ne représentent aucun compte utilisateur.
- [ ] Autoriser une seule fois un compte bot dédié avec `user:read:chat`, `user:write:chat` et `user:bot`.
- [ ] Autoriser chaque streamer avec `channel:bot`.
- [ ] Créer et supprimer dynamiquement les abonnements EventSub par streamer.
- [ ] Restaurer les abonnements des streamers actifs au redémarrage.
- [ ] Gérer les révocations et reconnexions sans arrêter FastAPI.

### Validation

- Le même bot reçoit les messages de plusieurs chaînes.
- Une révocation désactive uniquement le streamer concerné.
- Aucun token OAuth n'est stocké dans SQLite ou envoyé au navigateur.

## 6. Administration avec Twitch OAuth

- [ ] Ajouter un bouton **Se connecter avec Twitch** sur `/admin`.
- [ ] Implémenter `/auth/twitch/login` et `/auth/twitch/callback`.
- [ ] Utiliser un état OAuth aléatoire, court et à usage unique.
- [ ] Créer une session signée dans un cookie `HttpOnly`, `Secure` et `SameSite=Lax`.
- [ ] Ajouter la déconnexion et l'expiration de session.
- [ ] Autoriser la création d'un espace à tout membre ayant déjà accès au tailnet.
- [ ] Ne jamais accepter un `broadcaster_id` fourni par le navigateur comme identité.
- [ ] Permettre au streamer de modifier son préfixe et l'activation de son espace.

### Validation

- Un utilisateur non connecté ne peut pas appeler `/api/admin/*`.
- Le callback refuse un état OAuth absent, expiré ou déjà utilisé.
- La session contient l'identifiant Twitch validé côté serveur.
- Le login et le nom affiché sont actualisés à chaque connexion.

## 7. Historique isolé

- [ ] Paginer l'historique du streamer connecté.
- [ ] Afficher le détail et les participants d'un giveaway lui appartenant.
- [ ] Ajouter systématiquement le filtre `broadcaster_id` aux requêtes.
- [ ] Retourner `404` pour un giveaway appartenant à un autre streamer.

### Validation

- A ne voit jamais les giveaways de B.
- Modifier un identifiant dans une URL ne contourne pas l'isolation.
- Les giveaways terminés ou annulés restent consultables.

## 8. Déploiement et tests

- [ ] Déployer l'application avec systemd dans la configuration NixOS.
- [x] Publier le service en HTTPS sur le LAN avec Nginx lié à `192.168.1.112:443` et un certificat ACME DNS-01 Cloudflare, sans exposition Internet.
- [x] Conserver Tailscale Serve sur son adresse propre sans conflit avec l'écoute LAN.
- [ ] Ajouter les tests unitaires et d'intégration.
- [ ] Tester deux streamers et plusieurs sources OBS simultanément.
- [ ] Documenter l'installation complète, OAuth et la récupération après incident.

## MVP multi-streamer terminé

Le MVP cible est terminé lorsque deux streamers connectés avec Twitch peuvent lancer simultanément des giveaways indépendants, utiliser chacun `/overlay/{login_twitch}` et consulter uniquement leur propre historique, avec un seul bot dédié partagé par l'instance.
