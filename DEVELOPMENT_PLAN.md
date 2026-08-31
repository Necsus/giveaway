# Plan de développement

Plan minimal pour obtenir rapidement un giveaway utilisable dans OBS.

> Avancement actuel : moteur métier, persistance SQLite, restauration au démarrage, API FastAPI, diffusion WebSocket, overlay minimal et pilotage depuis le chat Twitch avec OAuth terminés. Les tests automatisés sont volontairement reportés pour le moment.

## 1. État du giveaway

- [x] Définir les états : `HIDDEN`, `WAITING`, `OPEN` et `WINNER`.
- [x] Conserver le nom du lot, les participants et le gagnant.
- [x] Empêcher plusieurs inscriptions avec le même identifiant Twitch.
- [x] Choisir le gagnant au hasard côté service.
- [x] Coordonner les transitions, SQLite et les diffusions WebSocket dans un service applicatif.
- [x] Protéger les commandes concurrentes avec un verrou asynchrone.

### Validation

- `!join` n'est accepté que dans l'état `OPEN`.
- Un viewer ne peut apparaître qu'une fois.
- `!pull` sans participant ne choisit aucun gagnant.
- `!stop` réinitialise l'état actif et masque l'overlay sans supprimer l'historique.

## 2. Commandes Twitch

- [x] Ajouter TwitchIO 3 aux dépendances du projet.
- [x] Écouter les messages d'un seul canal Twitch.
- [x] Parser les cinq commandes indépendamment du connecteur Twitch.
- [x] Réserver `!lot`, `!start`, `!pull` et `!stop` au streamer.
- [x] Implémenter `!lot <nom du lot>` pour afficher le lot en état `WAITING`.
- [x] Implémenter `!start` pour passer à l'état `OPEN`.
- [x] Implémenter `!join` pour ajouter le viewer courant.
- [x] Implémenter `!pull` pour fermer les inscriptions et afficher le gagnant.
- [x] Implémenter `!stop` pour réinitialiser et masquer l'overlay.
- [x] Définir les variables Twitch dans `.env.example` avec de fausses valeurs.
- [x] Charger et typer la configuration locale avec `pydantic-settings`.
- [x] Protéger le secret client avec `SecretStr`.
- [x] Injecter `Settings`, le gestionnaire de commandes et le connecteur Twitch dans le cycle de vie FastAPI.
- [x] Réaliser l'autorisation OAuth et conserver les tokens Twitch hors de Git.
- [ ] Corriger l'interaction des gestionnaires de signaux de l'adaptateur OAuth TwitchIO et d'Uvicorn lors de l'arrêt.

### Validation

- Un viewer ne peut pas exécuter une commande réservée au streamer.
- Les commandes produisent uniquement les transitions prévues.
- Aucun secret Twitch n'est envoyé au navigateur ni ajouté au dépôt.

## 3. Overlay OBS

- [x] Servir une page HTML utilisable comme source navigateur OBS.
- [x] Créer un squelette HTML avec des `id` stables : `giveaway`, `lot`, `status`, `participants` et `winner`.
- [x] Afficher ou masquer le conteneur selon l'état reçu.
- [x] Synchroniser l'overlay avec le service avec WebSocket.
- [x] Renvoyer l'état complet lorsque la source OBS se reconnecte.
- [x] Reconnecter automatiquement le JavaScript après une coupure.
- [x] Laisser toute la personnalisation visuelle au CSS personnalisé d'OBS.

### Validation

- `!lot test` affiche l'overlay avec le texte `test`.
- `!start` indique que les inscriptions sont ouvertes.
- Chaque `!join` valide met à jour les participants.
- `!pull` affiche un unique gagnant.
- `!stop` masque entièrement l'overlay.
- Le rechargement de la source OBS récupère l'état courant.

## 4. Administration et persistance

- [ ] Ajouter une page `/admin` protégée par authentification.
- [x] Lire et valider la configuration locale Twitch depuis `.env`.
- [ ] Lire, valider et écrire la future configuration administrable dans un fichier JSON non versionné.
- [x] Enregistrer les giveaways et leurs participants dans SQLite.
- [x] Garantir un seul giveaway actif et une seule inscription par utilisateur.
- [ ] Afficher un historique paginé depuis l'administration.
- [x] Restaurer un giveaway actif après le redémarrage du service.
- [ ] Déployer le service Python sur la DevBox et le publier uniquement dans le tailnet.

### Validation

- La configuration peut être modifiée depuis un PC autorisé.
- Les secrets ne sont jamais renvoyés en clair ni ajoutés au dépôt.
- Un giveaway terminé ou annulé reste consultable dans l'historique.
- Plusieurs PC peuvent charger le même overlay et recevoir le même état.

## 5. Vérification finale

Contrôles techniques déjà effectués manuellement : compilation Python, Ruff, BasedPyright, cycle métier avec SQLite, restauration des états `WAITING`, `OPEN` et `WINNER`, unicité des inscriptions et unicité du giveaway actif.

- [ ] Ajouter les tests automatisés lorsqu'ils seront réintroduits dans le périmètre.
- [x] Tester manuellement le parcours Twitch `!lot` → `!start` → `!join` → `!pull` → `!stop`.
- [ ] Tester les commandes reçues dans le mauvais ordre.
- [ ] Tester 0, 1 et plusieurs participants.
- [ ] Tester une double inscription.
- [ ] Tester le rechargement de l'overlay.
- [ ] Tester la configuration et l'historique depuis `/admin`.
- [ ] Documenter le lancement du service et l'ajout de la source dans OBS.

## MVP terminé

Le MVP est terminé lorsque le scénario suivant fonctionne sans modifier le code :

1. Le service Python démarre sur la DevBox et se connecte au canal Twitch configuré depuis `/admin`.
2. Les PC autorisés chargent l'overlay dans OBS via Tailscale, initialement masqué.
3. Le streamer envoie `!lot Clavier mécanique` : le lot apparaît en attente.
4. Le streamer envoie `!start` : les inscriptions ouvrent.
5. Les viewers s'inscrivent une seule fois avec `!join`.
6. Le streamer envoie `!pull` : un gagnant est choisi et affiché.
7. Le streamer envoie `!stop` : l'état actif est réinitialisé et l'overlay disparaît.
8. Le giveaway et ses participants restent consultables dans l'historique SQLite.
