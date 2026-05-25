# MinitelGPT — ChatGPT sur Minitel (API OpenAI + série)

Un pont série entre un Minitel 1 (TRT / La Radiotechnique NFZ 201) et l'API OpenAI. Tu tapes un prompt sur le clavier du Minitel, la réponse s'affiche sur l'écran.

Pas de scraping du site ChatGPT : uniquement l'API officielle OpenAI.

---

## Fonctionnalités

**Ce que le script gère :**
- Saisie de prompt via le clavier du Minitel (liaison série)
- Envoi à l'API OpenAI et affichage de la réponse
- Wrap 40 colonnes, encodage latin-1
- Retours ligne `\r\n` compatibles Vidéotex
- Throttling pour éviter la perte de caractères
- Pagination ("— suite — appuie sur une touche")
- Auto-configuration série au premier lancement
- Historique local (`history.json`)
- Profil système local (`system_profile.txt`) pour personnaliser le style de l'assistant

**Limitations :**

Le script ne fait pas de graphismes Vidéotex, ne prétend pas être un terminal VT100/ANSI, et n'a pas accès à la mémoire de ton compte ChatGPT web (l'API OpenAI et le site web sont deux choses séparées).

---

## Matériel requis

- Minitel 1 première génération (TRT / La Radiotechnique NFZ 201)
- Câble USB ↔ DIN-5 "spécial Minitel" (généralement basé sur FTDI)
- macOS (environnement de test principal)

> **Note :** Le Minitel 1 est plus capricieux que les modèles 1B ou 2. Le script inclut un assistant d'auto-configuration, mais certains câbles mal câblés (inversions de signaux ou niveaux incorrects) peuvent rester problématiques même après configuration.

---

## Installation (macOS)

**1. Créer l'environnement Python**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pyserial openai
```

**2. Configurer la clé API OpenAI**
```bash
export OPENAI_API_KEY="sk-..."
```

**3. (Optionnel) Lister les ports série disponibles**
```bash
python -m serial.tools.list_ports
```

**4. Lancer le script**
```bash
python minitel_gpt.py
```

---

## Premier lancement : auto-configuration série

Au premier lancement (ou via `/reset`), le script :

1. Liste les ports disponibles (`/dev/cu.usbserial-*`, `/dev/cu.usbmodem*`)
2. Teste plusieurs combinaisons de baud rate et de format
3. Envoie un écran de test :
```
TEST 1200 7E1 : SI TU LIS CA, TAPE y PUIS ENTREE
```
4. Si tu tapes `y` + Entrée, la config est validée et sauvegardée dans `minitel_config.json`

Si rien ne s'affiche, laisse tourner — le script cycle automatiquement à travers toutes les combinaisons possibles.

---

## Utilisation

L'invite côté Minitel est `> `. Tape ton prompt, appuie sur Entrée, lis la réponse.

### Commandes disponibles

| Commande | Description |
|---|---|
| `/help` | Afficher l'aide |
| `/clear` | Effacer l'écran (ou faux clear si non supporté) |
| `/quit` | Quitter proprement |
| `/reset` | Relancer l'assistant de configuration série |
| `/model` | Changer de modèle (si supporté) |
| `/history_reset` | Effacer l'historique local |
| `/debug` | Afficher les octets RX bruts côté Mac (debug bas niveau) |

---

## Personnalisation

Pour personnaliser le comportement de l'assistant, crée un fichier `system_profile.txt` à la racine du projet :

```
Tu es un assistant direct, pragmatique, légèrement sarcastique si utile.
Réponds en français.
Pas de blabla.
Tu parles à Lukas.
```

Ce fichier est injecté comme message système à chaque requête. L'historique des échanges est stocké dans `history.json` et persiste entre les sessions.

---

## Fichiers générés

| Fichier | Rôle |
|---|---|
| `minitel_config.json` | Paramètres série, throttling, pagination |
| `history.json` | Historique local des échanges |
| `system_profile.txt` | Profil utilisateur (optionnel) |

À ajouter au `.gitignore` si le dépôt est public.

---

## Dépannage

**Rien ne s'affiche sur le Minitel**
- Vérifie la prise DIN-5 péri-informatique (pas la prise téléphonique)
- Laisse l'auto-config cycler jusqu'au bout
- Teste un autre port série si plusieurs sont disponibles
- Active `/debug` — si aucun octet RX ne remonte, le câble est probablement incompatible ou les niveaux sont inversés

**Caractères illisibles / hiéroglyphes**
- Mauvais format série (7E1 vs 8N1)
- Relancer `/reset`

**Entrée / backspace ne fonctionnent pas**
- Active `/debug` et vérifie la réception de `0x08`, `0x7f`, `\r`, `\n`
- Ajuster le mapping si nécessaire

**Pertes de caractères / texte qui saute**
- Augmenter le throttling dans `minitel_config.json`
- Préférer un affichage ligne par ligne

**Double affichage (écho local)**
- Certains Minitel font de l'écho local
- Le script doit tolérer ou filtrer selon le cas

---

## Roadmap

- UI Vidéotex plus complète (cadres, titres, positionnement du curseur)
- Saisie multi-lignes plus confortable
- Mini-apps : météo, RSS, now playing, etc.
