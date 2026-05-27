# CLAUDE.md

Guide pour Claude Code travaillant sur **MinitelGPT** — pont série entre un Minitel 1 et l'API Anthropic.

---

## Vue d'ensemble

Script unique (`minitel_gpt.py`) qui :
- Lit les frappes clavier du Minitel sur le port série
- Envoie le prompt à l'API Anthropic (Claude Sonnet 4.6)
- Streame la réponse sur l'écran du Minitel (40 colonnes, pagination, throttling)
- Maintient un historique roulant (`history.json`), un journal permanent (`chat_log.json`), des sessions (`sessions.json`)
- Profil système (`system_profile.md`) + mémoire persistante (`memory.md`) mise à jour via `/memory` (Claude Haiku)

Dépendances : `pyserial`, `anthropic`. Python 3.10+. macOS principal.

---

## Minitel Hardware Constraints

> **CES CONTRAINTES SONT NON NÉGOCIABLES.** Le terminal cible est un **Minitel 1 La Radiotechnique 9 NFZ 201 (1982)**. Tout code écrit pour ce projet DOIT les respecter. Toute proposition qui les viole doit être rejetée d'office.

### Liaison série

- **1200 bauds uniquement.** Pas de 4800, pas de 9600, pas d'autres vitesses.
- **Format 7E1 :** 7 bits de données, parité paire (even), 1 stop bit. Pas de 8N1.
- **Interface TTL 5V** via prise DIN-5 péri-informatique (pas la prise téléphonique).
- **Connexion Mac :** câble USB→DIN FTDI, apparaît comme `/dev/tty.usbserial-*` ou `/dev/cu.usbserial-*` (préférer `cu.*` côté écriture sur macOS).
- **L'autoconfig ne doit pas itérer sur d'autres baud rates ni d'autres formats.** Si la liaison ne fonctionne pas en 1200 7E1, c'est un problème de câblage, pas de paramètres.

### Affichage

- **40 colonnes × 24 lignes**, point final. Wrap strict à 40 caractères, jamais dépasser.
- **Mode Vidéotex uniquement.** Interdit : séquences `\x1b[...` (ANSI/CSI), codes VT100, escape sequences couleur.
- **Pas de positionnement curseur arbitraire**, pas de `clear screen` ANSI. Le form feed `\x0c` (Vidéotex CLEAR/HOME) est toléré.
- **Encodage 7 bits ASCII bas uniquement.** Pas d'UTF-8, pas de latin-1, pas d'accents natifs. Les accents doivent être **translittérés** (`é`→`e`, `è`→`e`, `à`→`a`, `ç`→`c`, `œ`→`oe`, `î`→`i`, `ô`→`o`, `ù`→`u`, etc.).
- **Débit effectif : ~120 caractères/seconde** (1200 baud / 10 bits par caractère 7E1).

### Implications pour le code

- **Wrap strict à 40 colonnes** sur tout texte renvoyé par l'API Claude avant écriture série. Pas de découpe en plein milieu d'un mot sauf si le mot dépasse 40 caractères.
- **Translittération ASCII 7 bits obligatoire** avant tout `serial.write()`. Préférer `unicodedata.normalize('NFKD', s).encode('ascii', 'ignore')` + remplacements manuels (`œ`→`oe`, `æ`→`ae`, etc.).
- **Jamais encoder en `latin-1`** pour la sortie série — le 8e bit est utilisé par la parité.
- **Pas d'envoi en bloc.** Streamer la réponse Claude caractère par caractère ou par petits chunks (≤ 40 caractères / 1 ligne). Le `display_streaming` doit flusher progressivement.
- **Délai inter-chunk ~50 ms** pour ne pas saturer le buffer série du Minitel. À 1200 baud, écrire ≥ 60 octets d'un coup risque de déborder.
- **Prompt système** doit instruire Claude : « Pas d'accents. Pas de caractères spéciaux Unicode. Réponses courtes (chaque caractère coûte ~8 ms d'affichage). »

### Touches clavier reçues du Minitel

- 7 bits ASCII uniquement en réception aussi. Tout octet > 0x7F en RX est du bruit / une erreur de parité — ignorer.
- Entrée : `\r` (0x0D) ou `\n` (0x0A).
- Backspace : `0x08` ou `0x7F`.
- Pas de touches de fonction Fnct exploitables sur le Minitel 1 NFZ 201 — ne pas dépendre de codes ≥ 0x80 ni de séquences SEP.

---

## Modèles Anthropic

- **Conversations :** `claude-sonnet-4-6`
- **Mise à jour mémoire (`/memory`) :** `claude-haiku-4-5-20251001`
- Toujours via le SDK officiel `anthropic` Python, clé via `ANTHROPIC_API_KEY`.

---

## Structure du projet

| Fichier | Rôle |
|---|---|
| `minitel_gpt.py` | Script principal (un seul fichier) |
| `minitel_config.json` | Config série persistée (port, baud, format, throttling, pagination) |
| `history.json` | Fenêtre de contexte roulante (20 derniers échanges) |
| `sessions.json` | Toutes les sessions (non tronquées, navigation `/chat`) |
| `chat_log.json` | Journal global horodaté (pour `/memory`) |
| `system_profile.md` | Instructions permanentes assistant |
| `memory.md` | Mémoire persistante |

Tous générés au runtime et listés dans `.gitignore`.

---

## Commandes shell (côté Minitel)

`/help` `/clear` `/quit` `/new` `/chat` `/reset` `/model [X]` `/debug` `/history_reset` `/memory` `/nopage` `/throttle <ms>`

---

## Tests / lancement

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install pyserial anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
python minitel_gpt.py            # mode série
python minitel_gpt.py --simulate # mode stdin/stdout (pas de Minitel)
python minitel_gpt.py --debug    # affiche les octets RX
```

---

## Règles d'édition pour Claude Code

- **Ne jamais** ajouter de baud rate autre que 1200 ni de format autre que 7E1 dans `SERIAL_CONFIGS` ou les defaults.
- **Ne jamais** encoder la sortie série en `latin-1` ou `utf-8`. Toujours ASCII 7 bits après translittération.
- **Ne jamais** émettre d'`\x1b` (ESC) sur le port série.
- **Ne jamais** dépasser 40 colonnes par ligne sur le Minitel.
- Garder `minitel_gpt.py` mono-fichier sauf demande explicite contraire.
- Les fichiers JSON / Markdown locaux peuvent rester en `utf-8` (lecture/écriture disque) — la contrainte ASCII 7 bits ne s'applique qu'à la **sortie série**.
