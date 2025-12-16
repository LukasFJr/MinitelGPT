# AGENTS.md

Ce dépôt contient un projet “pont” entre un **Minitel** (liaison série) et un modèle de chat via **API OpenAI** (sans scraping du site web).  
Objectif : taper un prompt sur le Minitel, recevoir la réponse sur le Minitel (wrap 40 colonnes, pagination, throttling).

## TL;DR (pour agents pressés)
- **Ne pas** automatiser / scrapper `chat.openai.com`. **API officielle uniquement**.
- **macOS** + **Python 3.10+** + **pyserial** + **openai**.
- Le Minitel visé est un **Minitel 1 (TRT / La Radiotechnique NFZ 201)** : pas de Fnct, pas de VT100, donc **texte simple** et robuste.
- Contraintes clés d’affichage : **40 colonnes**, `latin-1`, retours `\r\n`, throttling + pagination.

---

## Structure attendue du projet
> (Si elle n’existe pas encore, l’agent peut la créer, mais rester simple.)

- `minitel_gpt.py` : script principal (un seul fichier si possible).
- `minitel_config.json` : config série persistée (port, baud, format, throttling, pagination).
- `history.json` : historique local de conversation (optionnel mais recommandé).
- `system_profile.txt` : prompt système local pour personnaliser l’assistant (optionnel mais recommandé).

---

## Installation (macOS)
Créer un environnement virtuel et installer les dépendances minimales :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pyserial openai
