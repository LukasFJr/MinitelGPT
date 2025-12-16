# MinitelGPT — ChatGPT sur Minitel (API OpenAI + série)

Un pont **Minitel → Python → API OpenAI → Minitel**.

Tu tapes un prompt sur un **Minitel 1** (TRT / La Radiotechnique **NFZ 201**),
la réponse s’affiche directement sur l’écran du Minitel.

👉 Pas de scraping du site ChatGPT : **API OpenAI officielle uniquement**.

---

## Ce que ça fait (et ce que ça ne fait pas)

### ✅ Fait

* Saisie d’un prompt via le clavier du Minitel (liaison série)
* Envoi du prompt à l’API OpenAI
* Affichage de la réponse sur le Minitel
* **Wrap 40 colonnes**, encodage **latin-1**
* Retours ligne `\r\n` compatibles Vidéotex
* **Throttling** (évite la perte de caractères)
* **Pagination** (“— suite — appuie sur une touche”)
* **Auto-configuration série** au premier lancement
* Historique local (`history.json`)
* Profil système local (`system_profile.txt`) pour personnaliser le style

### ❌ Ne fait pas

* Pas de “vraie vidéo”
* Pas de VT100 / ANSI / terminal moderne
* Pas d’accès à la *Memory* de ton compte ChatGPT web
  (l’API n’y a pas accès automatiquement)

---

## Matériel requis

* **Minitel 1** première génération
  (TRT / La Radiotechnique **NFZ 201**)
* **Câble USB ↔ DIN-5 “spécial Minitel”**
  (souvent basé sur FTDI)
* macOS (environnement de test principal)

> ⚠️ Le Minitel 1 est plus capricieux que les modèles 1B / 2.
> Le script inclut un assistant d’auto-config, mais certains câbles
> mal câblés (inversion / niveaux) peuvent poser problème.

---

## Installation (macOS)

### 1) Créer l’environnement Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pyserial openai
```

### 2) Ajouter la clé API OpenAI

Méthode recommandée :

```bash
export OPENAI_API_KEY="sk-..."
```

### 3) (Optionnel) Lister les ports série

```bash
python -m serial.tools.list_ports
```

### 4) Lancer le script

```bash
python minitel_gpt.py
```

---

## Premier lancement : auto-configuration série

Au premier lancement (ou via la commande `/reset`), le script :

1. Liste les ports série (`/dev/cu.usbserial-*`, `/dev/cu.usbmodem*`)
2. Teste plusieurs configurations (baud + format)
3. Envoie un écran de test :

   ```
   TEST 1200 7E1 : SI TU LIS CA, TAPE y PUIS ENTREE
   ```
4. Si tu tapes `y` + Entrée, la configuration est validée et sauvegardée dans :

```
minitel_config.json
```

> Si rien ne s’affiche : laisse tourner, il teste automatiquement
> toutes les configurations possibles.

---

## Utilisation côté Minitel

* Invite : `> `
* Tape ton prompt
* Appuie sur **Entrée**
* Lis la réponse affichée

### Commandes disponibles

* `/help` : affiche l’aide
* `/clear` : efface l’écran (ou faux clear si non supporté)
* `/quit` : quitter proprement
* `/reset` : relancer l’assistant série
* `/model` : changer de modèle (si supporté)
* `/history_reset` : effacer l’historique local
* `/debug` : afficher les octets RX côté Mac (debug bas niveau)

---

## Personnalisation (style ChatGPT “perso”, mais local)

L’API OpenAI ne réutilise pas la mémoire du compte web.
On fait donc simple, propre et stable.

### `system_profile.txt`

Crée un fichier `system_profile.txt` à la racine du projet.

Exemple :

```txt
Tu es un assistant direct, pragmatique, légèrement sarcastique si utile.
Réponds en français.
Pas de blabla.
Tu parles à Lukas.
```

Ce fichier est injecté comme **message système** à chaque requête.

### Historique local

* Fichier : `history.json`
* Permet de conserver un contexte entre les sessions
* Stockage local uniquement

---

## Fichiers générés

* `minitel_config.json`
  → paramètres série, throttling, pagination
* `history.json`
  → historique local des échanges
* `system_profile.txt`
  → profil utilisateur (optionnel)

👉 À ajouter au `.gitignore` si le dépôt est public.

---

## Dépannage (symptômes → solutions)

### Rien ne s’affiche sur le Minitel

* Vérifie la **prise DIN-5 péri-informatique**
* Laisse l’auto-config tester toutes les configs
* Teste un autre port série si plusieurs existent
* Active `/debug`
* Si aucun octet RX : câble incompatible ou inversion de niveaux

### Caractères illisibles / hiéroglyphes

* Mauvais format série (`7E1` vs `8N1`)
* Relancer `/reset`

### Entrée / backspace ne fonctionnent pas

* Active `/debug`
* Vérifie la réception de `0x08`, `0x7f`, `\r`, `\n`
* Ajuste le mapping si nécessaire

### Texte qui saute / pertes de caractères

* Augmente le throttling dans `minitel_config.json`
* Préfère un affichage ligne par ligne

### Double affichage (écho)

* Certains Minitel font de l’écho local
* Le script doit tolérer ou filtrer l’écho selon le cas

---

## Roadmap (si tu veux pousser le vice)

* UI plus “Vidéotex” (cadres, titres, curseur)
* Mode multi-lignes plus confortable
* Mini-apps : météo, RSS, now playing, etc.
