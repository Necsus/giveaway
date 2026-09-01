# Plan de développement

Plan pour faire évoluer le giveaway mono-streamer actuel vers un service multi-streamer utilisable simultanément depuis plusieurs chaînes Twitch.

> Avancement actuel : le parcours complet fonctionne pour un streamer avec FastAPI, TwitchIO, OAuth, SQLite, WebSocket et OBS. La cible multi-streamer décrite ci-dessous n'est pas encore implémentée.

## 1. Socle mono-streamer terminé

- [x] Définir les états `HIDDEN`, `WAITING`, `OPEN` et `WINNER`.
- [x] Gérer `!lot`, `!start`, `!join`, `!pull` et `!stop`.
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

- [ ] Déployer avec systemd dans la configuration NixOS.
- [ ] Publier uniquement dans le tailnet avec Tailscale Serve.
- [ ] Ajouter les tests unitaires et d'intégration.
- [ ] Tester deux streamers et plusieurs sources OBS simultanément.
- [ ] Documenter l'installation, OAuth, l'URL d'overlay et la récupération après incident.

## MVP multi-streamer terminé

Le MVP cible est terminé lorsque deux streamers connectés avec Twitch peuvent lancer simultanément des giveaways indépendants, utiliser chacun `/overlay/{login_twitch}` et consulter uniquement leur propre historique, avec un seul bot dédié partagé par l'instance.
