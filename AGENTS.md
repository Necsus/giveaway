# Instructions pour les agents IA

## Protection des variables d’environnement

- Ne jamais lire, ouvrir, afficher, rechercher, analyser ou transmettre le contenu du fichier `.env`.
- Ne jamais utiliser une commande ou un outil susceptible d’afficher le contenu de `.env`, même partiellement.
- Utiliser exclusivement `.env.example` pour connaître les variables d’environnement attendues par le projet.
- Considérer toutes les valeurs de `.env` comme des secrets, même lorsqu’elles semblent inoffensives.
- Ne jamais copier de valeur réelle depuis `.env` vers le code, la documentation, les journaux, les tests ou une réponse adressée à l’utilisateur.
- Il est permis de vérifier si `.env` existe, à condition de ne jamais en lire le contenu ni ses métadonnées sensibles.
- Si une opération nécessite une valeur absente de `.env.example`, demander à l’utilisateur de fournir une valeur fictive ou d’ajouter lui-même la variable appropriée à `.env.example`.
