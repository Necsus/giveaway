# Plan de développement — Overlay de chat Twitch

## 1. Objectif

Ajouter un second plugin OBS affichant en temps réel le chat du streamer actif, indépendamment du giveaway.

URL cible :

```text
https://overlay.necsus.dev/plugins/chat/overlay#<clé-OBS-chat>
```

Le plugin `chat` possède sa propre clé d'accès, sa propre route WebSocket et sa propre source navigateur OBS. Il réutilise les mécanismes communs de la plateforme, sans partager la clé ni le cycle de vie du plugin `giveaway`.

## 2. Critère de fin global

Une source navigateur OBS dédiée et authentifiée affiche les messages du chat Twitch du streamer actif en temps réel, sans perturber les commandes ni l'overlay du giveaway. Une rotation de la clé du chat invalide uniquement les connexions du chat.

## 3. Décisions d'architecture

### Décisions retenues

- créer un plugin indépendant sous `/plugins/chat` ;
- utiliser une clé OBS propre au couple `(streamer, chat)` ;
- conserver deux sources navigateur OBS séparées pour permettre leur placement indépendant ;
- distribuer chaque message Twitch vers deux traitements indépendants : commandes et affichage du chat ;
- ne pas persister l'historique du chat dans SQLite pour la première version ;
- conserver une fenêtre bornée de messages uniquement dans le navigateur ;
- échapper le contenu par construction en utilisant les propriétés textuelles du DOM, jamais du HTML provenant du chat ;
- maintenir un seul worker Uvicorn tant que les connexions et l'état restent en mémoire.

### Hors périmètre initial

- overlay composite regroupant plusieurs plugins dans une même page ;
- configuration visuelle complète depuis l'administration ;
- historique persistant et recherche dans le chat ;
- modération ou envoi de messages depuis l'overlay ;
- rendu natif des emotes, badges, réponses et Cheers ;
- fonctionnement multi-streamer simultané ;
- framework générique de plugins avant qu'un besoin commun concret soit identifié.

## 4. Décisions produit à confirmer avant l'implémentation

Définir explicitement :

1. si les commandes telles que `!join` sont affichées ou filtrées ;
2. si les messages du bot global sont affichés ;
3. le nombre maximal de messages visibles ;
4. la durée de présence d'un message ;
5. le comportement visuel attendu : défilement vertical, apparition en bas et disparition progressive ;
6. les données de la première version : pseudo et texte uniquement, ou couleur Twitch également.

Valeurs minimales proposées pour démarrer :

- afficher tous les messages, commandes comprises ;
- afficher les messages du bot comme les autres ;
- conserver au maximum 30 messages ;
- retirer chaque message après 60 secondes ;
- afficher les nouveaux messages en bas ;
- limiter la première version au nom affiché et au texte.

## 5. Flux de données cible

```text
EventSub Twitch
      │
      ▼
GiveawayTwitchBot.event_message
      │
      ├──> GiveawayCommandHandler
      │       └── transitions du giveaway
      │
      └──> ChatOverlayService
              └── publication non bloquante
                      └── ChatConnectionManager
                              └── WebSocket authentifié
                                      └── source navigateur OBS
```

Le contrôle du broadcaster actif reste effectué avant les deux traitements. Une erreur d'affichage ou un client OBS lent ne doit pas empêcher le traitement d'une commande.

## 6. Contrat de message initial

Le serveur envoie un événement par message reçu, plutôt qu'un instantané contenant tout l'historique :

```json
{
  "type": "chat.message",
  "data": {
    "message_id": "identifiant-Twitch",
    "twitch_user_id": "123456",
    "login": "viewer",
    "display_name": "Viewer",
    "text": "Bonjour !",
    "received_at": "2026-01-01T12:00:00+00:00"
  }
}
```

Contraintes :

- aucune donnée OAuth ou clé OBS dans les événements ;
- taille maximale du texte contrôlée côté serveur ;
- format JSON versionnable si le rendu des emotes est ajouté plus tard ;
- `message_id` utilisable pour éviter un doublon après une reconnexion, s'il est disponible ;
- aucune interprétation HTML du champ `text`.

Le serveur n'envoie pas les messages antérieurs lors d'une nouvelle connexion dans la première version. L'overlay repart vide après un rechargement OBS.

## 7. Étapes d'implémentation

### Étape 1 — Modèle de message indépendant de TwitchIO

Définir un objet applicatif minimal représentant un message de chat. La couche WebSocket ne doit pas dépendre directement de `twitchio.ChatMessage`.

Points à valider :

- conversion explicite depuis le payload TwitchIO ;
- champs obligatoires et valeurs de repli pour le login et le nom affiché ;
- limite de longueur documentée ;
- aucune donnée inutile transmise à OBS.

**Critère de fin :** un payload Twitch peut être transformé en message sérialisable sans dépendance TwitchIO dans la couche web.

### Étape 2 — Distribution depuis le connecteur Twitch

Après validation du broadcaster actif, transmettre le message au gestionnaire de commandes et au service de chat.

La diffusion vers OBS doit être isolée : une erreur ou une lenteur du chat ne doit pas empêcher `GiveawayCommandHandler` de traiter le même message.

Points à valider :

- une commande continue de modifier le giveaway ;
- le même message peut aussi être publié vers le chat selon la politique de filtrage retenue ;
- une erreur de publication est journalisée sans exposer le contenu sensible ni arrêter TwitchIO.

**Critère de fin :** les commandes existantes conservent exactement leur comportement avec ou sans client chat connecté.

### Étape 3 — Gestionnaire WebSocket dédié au chat

Créer un gestionnaire de connexions distinct de celui du giveaway. Les connexions doivent être associées au streamer, au plugin et à l'empreinte de la clé ayant servi à les authentifier.

Prévoir dès cette étape :

- itération sur un instantané des connexions ;
- suppression des clients déconnectés ;
- délai maximal d'envoi ;
- diffusion concurrente ou file bornée ;
- abandon d'un client trop lent plutôt que blocage de TwitchIO.

**Critère de fin :** plusieurs clients authentifiés reçoivent un message et un client lent ne bloque ni les autres clients ni les commandes.

### Étape 4 — Routes et authentification du plugin

Ajouter les endpoints canoniques :

| Méthode | Chemin | Usage |
|---|---|---|
| `GET` | `/plugins/chat/overlay` | Sert la page de l'overlay. |
| `WS` | `/plugins/chat/ws` | Authentifie puis diffuse les messages. |
| `GET` | `/api/admin/plugins/chat/overlay-access` | Retourne l'état de la clé, jamais sa valeur. |
| `POST` | `/api/admin/plugins/chat/overlay-access/rotate` | Génère une nouvelle clé et retourne une fois l'URL. |

Réutiliser le format d'authentification actuel :

```json
{
  "type": "overlay.authenticate",
  "token": "valeur-lue-depuis-le-fragment"
}
```

La résolution de la clé utilise le slug `chat`. Une clé du giveaway doit être refusée par le WebSocket du chat, et inversement.

**Critère de fin :** clé absente, invalide, expirée par rotation ou appartenant à un autre plugin → fermeture WebSocket avec le code `1008` et aucune donnée diffusée.

### Étape 5 — Overlay HTML et JavaScript minimal

Créer une page transparente et sans thème imposé, adaptée au CSS personnalisé d'OBS.

Structure DOM stable proposée :

```text
#chat
  #messages
    .chat-message
      .chat-author
      .chat-text
```

Responsabilités du navigateur :

- lire la clé depuis `window.location.hash` ;
- authentifier le WebSocket comme premier message ;
- reconnecter avec un délai progressif et du jitter ;
- ajouter chaque message avec `textContent` ;
- borner le nombre d'éléments DOM ;
- supprimer les messages arrivés à expiration ;
- vider l'affichage après un refus d'authentification ;
- permettre le style depuis le champ CSS personnalisé d'OBS.

**Critère de fin :** 30 messages successifs restent lisibles, le 31e supprime le plus ancien et aucun texte de chat ne peut injecter du HTML.

### Étape 6 — Administration

Ajouter une section Chat indépendante dans `/admin` avec :

- état configuré ou non ;
- date de dernière rotation ;
- bouton de génération/rotation ;
- URL affichée une seule fois après génération ;
- action explicite de copie ;
- avertissement indiquant que la rotation déconnecte les sources chat existantes.

La rotation du chat ne doit pas fermer les connexions du giveaway. Cela implique de ne pas utiliser une déconnexion globale par streamer lorsque plusieurs plugins partagent le processus.

**Critère de fin :** les deux URLs OBS peuvent être générées et tournées séparément depuis l'administration.

### Étape 7 — Validation manuelle puis tests automatisés

Scénario manuel minimal :

1. générer les clés du giveaway et du chat ;
2. ouvrir les deux overlays dans deux clients distincts ;
3. envoyer un message normal et vérifier son affichage ;
4. envoyer `!join` et vérifier le comportement produit retenu ainsi que le giveaway ;
5. ouvrir un client chat lent ou interrompu ;
6. vérifier que les commandes continuent de fonctionner ;
7. tourner la clé chat ;
8. vérifier que le chat est déconnecté mais que le giveaway reste connecté ;
9. vérifier qu'une clé giveaway est refusée sur `/plugins/chat/ws` ;
10. recharger OBS et vérifier la reconnexion avec la nouvelle clé.

Tests automatisés cibles :

- sérialisation du modèle de message ;
- filtrage selon la politique produit ;
- authentification obligatoire avant toute diffusion ;
- isolation des clés entre `chat` et `giveaway` ;
- rotation indépendante des clés ;
- diffusion à plusieurs clients ;
- suppression d'un client déconnecté ou lent ;
- échappement du contenu côté navigateur ;
- maintien du traitement des commandes si la diffusion chat échoue.

**Critère de fin :** le scénario manuel complet passe et les comportements de sécurité et d'isolation sont couverts par des tests.

## 8. Fichiers probablement concernés

Cette liste décrit les zones attendues, sans imposer la conception finale :

```text
app/
├── application/
│   └── chat.py                         # modèle/service applicatif éventuel
├── infrastructure/
│   └── twitch.py                       # distribution des messages entrants
└── web/
    ├── routes/
    │   └── chat_overlay.py             # page et WebSocket du chat
    ├── websocket.py                    # extraction prudente du commun
    └── static/plugins/chat/
        ├── overlay.html
        └── overlay.js
```

Les routes administratives et l'assemblage dans `app/main.py` seront également concernés. La table `overlay_access_keys` supporte déjà plusieurs `plugin_slug` et ne devrait pas nécessiter une nouvelle table.

Ne pas extraire immédiatement un framework générique de plugins. Commencer par identifier les duplications réelles entre `giveaway` et `chat`, puis extraire seulement l'authentification et la gestion de connexion qui possèdent les mêmes invariants.

## 9. Risques et garde-fous

| Risque | Garde-fou |
|---|---|
| Un client OBS lent bloque TwitchIO | File bornée, délai d'envoi et déconnexion du client lent. |
| Croissance illimitée du DOM | Nombre et durée de vie des messages bornés. |
| Injection HTML depuis le chat | Utilisation exclusive de `textContent`. |
| Une clé donne accès à plusieurs plugins | Résolution obligatoire avec le `plugin_slug`. |
| Rotation chat coupe le giveaway | Gestionnaires et déconnexions ciblés par plugin. |
| Duplication excessive du code giveaway | Extraction limitée aux invariants réellement communs. |
| Perte des messages pendant une reconnexion | Acceptée en V1 ; pas d'historique serveur. |
| Emotes mal rendues en texte brut | Limitation documentée, enrichissement reporté. |

## 10. Ordre recommandé

1. confirmer les six décisions produit ;
2. définir le contrat de message ;
3. distribuer les événements Twitch sans régression des commandes ;
4. construire et sécuriser le WebSocket du chat ;
5. réaliser l'overlay minimal ;
6. ajouter la gestion de clé dans l'administration ;
7. valider l'isolation avec le giveaway ;
8. seulement ensuite envisager couleurs, badges, emotes et paramètres visuels.

La première tranche verticale doit rester petite : **un message texte Twitch apparaît dans une source OBS authentifiée, tandis que le giveaway continue de fonctionner normalement**.
