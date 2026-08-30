# Plan de développement

Plan minimal pour obtenir rapidement un giveaway utilisable dans OBS.

## 1. État du giveaway

- [ ] Définir les états : `HIDDEN`, `WAITING`, `OPEN` et `WINNER`.
- [ ] Conserver le nom du lot, les participants et le gagnant.
- [ ] Empêcher plusieurs inscriptions avec le même identifiant Twitch.
- [ ] Choisir le gagnant au hasard côté service.

### Validation

- `!join` n'est accepté que dans l'état `OPEN`.
- Un viewer ne peut apparaître qu'une fois.
- `!pull` sans participant ne choisit aucun gagnant.
- `!stop` réinitialise l'état actif et masque l'overlay sans supprimer l'historique.

## 2. Commandes Twitch

- [ ] Écouter les messages d'un seul canal Twitch.
- [ ] Réserver `!lot`, `!start`, `!pull` et `!stop` au streamer.
- [ ] Implémenter `!lot <nom du lot>` pour afficher le lot en état `WAITING`.
- [ ] Implémenter `!start` pour passer à l'état `OPEN`.
- [ ] Implémenter `!join` pour ajouter le viewer courant.
- [ ] Implémenter `!pull` pour fermer les inscriptions et afficher le gagnant.
- [ ] Implémenter `!stop` pour réinitialiser et masquer l'overlay.
- [ ] Charger les identifiants Twitch depuis le fichier JSON non versionné.

### Validation

- Un viewer ne peut pas exécuter une commande réservée au streamer.
- Les commandes produisent uniquement les transitions prévues.
- Aucun secret Twitch n'est envoyé au navigateur ni ajouté au dépôt.

## 3. Overlay OBS

- [ ] Servir une page HTML utilisable comme source navigateur OBS.
- [ ] Créer un squelette HTML avec des `id` stables : `giveaway`, `lot`, `status`, `participants` et `winner`.
- [ ] Afficher ou masquer le conteneur selon l'état reçu.
- [ ] Synchroniser l'overlay avec le service, par exemple avec WebSocket.
- [ ] Renvoyer l'état complet lorsque la source OBS se reconnecte.
- [ ] Laisser toute la personnalisation visuelle au CSS personnalisé d'OBS.

### Validation

- `!lot test` affiche l'overlay avec le texte `test`.
- `!start` indique que les inscriptions sont ouvertes.
- Chaque `!join` valide met à jour les participants.
- `!pull` affiche un unique gagnant.
- `!stop` masque entièrement l'overlay.
- Le rechargement de la source OBS récupère l'état courant.

## 4. Administration et persistance

- [ ] Ajouter une page `/admin` protégée par authentification.
- [ ] Lire, valider et écrire la configuration dans un fichier JSON non versionné.
- [ ] Enregistrer les giveaways et leurs participants dans SQLite.
- [ ] Afficher un historique paginé depuis l'administration.
- [ ] Restaurer un giveaway actif après le redémarrage du service.
- [ ] Déployer le service Python sur la DevBox et le publier uniquement dans le tailnet.

### Validation

- La configuration peut être modifiée depuis un PC autorisé.
- Les secrets ne sont jamais renvoyés en clair ni ajoutés au dépôt.
- Un giveaway terminé ou annulé reste consultable dans l'historique.
- Plusieurs PC peuvent charger le même overlay et recevoir le même état.

## 5. Vérification finale

- [ ] Tester le parcours `!lot` → `!start` → `!join` → `!pull` → `!stop`.
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
