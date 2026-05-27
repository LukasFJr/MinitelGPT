# AGENTS.md

Ce dépôt contient un projet "pont" entre un **Minitel** (liaison série) et **Claude** (API Anthropic).
Objectif : taper un prompt sur le Minitel, recevoir la réponse sur le Minitel (wrap 40 colonnes, pagination, throttling).

Modèles : **Claude Sonnet 4.6** (conversations), **Claude Haiku** (mise à jour mémoire via `/memory`).

## TL;DR (pour agents pressés)
- **API Anthropic officielle uniquement** (`ANTHROPIC_API_KEY`).
- **macOS** + **Python 3.10+** + **pyserial** + **anthropic**.
- Le Minitel visé est un **Minitel 1 (TRT / La Radiotechnique NFZ 201)** : pas de Fnct, pas de VT100, donc **texte simple** et robuste.
- Contraintes clés d'affichage : **40 colonnes**, `latin-1`, retours `\r\n`, throttling + pagination.

---

## Structure attendue du projet
> (Si elle n'existe pas encore, l'agent peut la créer, mais rester simple.)

- `minitel_gpt.py` : script principal (un seul fichier).
- `minitel_config.json` : config série persistée (port, baud, format, throttling, pagination).
- `history.json` : fenêtre de contexte roulante (20 derniers échanges).
- `chat_log.json` : journal permanent de tous les échanges (jamais tronqué).
- `system_profile.md` : instructions permanentes de l'assistant (créé automatiquement).
- `memory.md` : mémoire persistante mise à jour par `/memory` (créée automatiquement).

---

## Installation (macOS)
Créer un environnement virtuel et installer les dépendances minimales :

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install pyserial anthropic
```
