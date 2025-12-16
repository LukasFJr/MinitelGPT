# MinitelGPT

## Pourquoi je ne peux pas modifier les fichiers ?
Dans certains échanges précédents, l'assistant a expliqué le code sans l'écrire. Les raisons les plus fréquentes sont :
- **Pas de droits en écriture** : le dépôt est peut‑être cloné en lecture seule ou dans un répertoire protégé.
- **Instructions contradictoires** : des consignes (AGENTS.md, description de tâche) peuvent interdire de modifier le dépôt.
- **Oubli d'initialiser le dépôt** : sans dépôt Git ou sans branche active, les changements ne peuvent pas être suivis ou validés.
- **Clôture anticipée** : la session a été terminée avant d'écrire sur le disque.

## Comment corriger la situation
- Vérifie que le répertoire est accessible en écriture (ex. `chmod -R u+w .` ou relancer le conteneur avec des droits suffisants).
- Assure‑toi d'être sur une branche Git active et commitable (`git status`, `git branch`).
- Supprime ou adapte les consignes qui empêchent la modification si elles existent (fichiers `AGENTS.md`, instructions de tâche).
- Laisse l'assistant exécuter les commandes de création/édition et `git commit` lorsque c'est attendu.

## Notes
Ce dépôt est prêt à recevoir les fichiers du script Minitel ↔ OpenAI. Ajoute ou modifie les fichiers ici dès que les conditions ci‑dessus sont remplies.
