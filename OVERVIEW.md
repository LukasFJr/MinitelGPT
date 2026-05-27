# MinitelGPT — Récapitulatif technique complet

> Généré à partir d'une lecture intégrale du dépôt.

---

## 1. Vue d'ensemble

`minitel_gpt.py` est un **script Python mono-fichier** (~1 570 lignes) qui fait office de pont entre :

- **Un Minitel 1 TRT / La Radiotechnique NFZ 201 (1982)** connecté via câble USB→DIN-5 FTDI
- **L'API Anthropic** (Claude Sonnet 4.6 pour les conversations, Claude Haiku pour la mémoire)

Flux d'une interaction :

```
Clavier Minitel
  → liaison série 1200 7E1 (RX)
    → buffer de saisie (read_line)
      → API Anthropic (streaming)
        → translittération ASCII 7 bits + wrap 40 colonnes
          → liaison série 1200 7E1 (TX)
            → écran Minitel
```

---

## 2. Contraintes hardware non négociables

| Paramètre | Valeur |
|---|---|
| Débit série | **1200 bauds uniquement** |
| Format | **7E1** (7 bits data, parité paire, 1 stop bit) |
| Colonnes écran | **40 max** |
| Lignes écran | 24 (18 utilisées avant pagination) |
| Encodage TX | **ASCII 7 bits** (le 8e bit = parité) |
| Encodage RX | ASCII 7 bits (tout octet ≥ 0x80 = bruit, ignoré) |
| Mode écran | Vidéotex — **pas d'ANSI/VT100/CSI** |
| Débit effectif | ~120 caractères/seconde |
| Chunk max sans saturation | ≤ 40 octets (~50 ms d'intervalle) |

---

## 3. Structure des fichiers

### Fichiers versionnés

| Fichier | Rôle |
|---|---|
| `minitel_gpt.py` | Script principal |
| `system_profile.txt` | Profil système d'origine (migré vers `system_profile.md` au runtime) |
| `CLAUDE.md` | Instructions pour Claude Code |
| `AGENTS.md` | Instructions pour agents IA |
| `README.md` | Documentation utilisateur |

### Fichiers générés au runtime (dans `.gitignore`)

| Fichier | Rôle | Tronqué ? |
|---|---|---|
| `minitel_config.json` | Port, baud, throttling, modèle, session courante | — |
| `history.json` | Fenêtre de contexte roulante | Oui (20 tours / 16 000 chars) |
| `sessions.json` | Toutes les sessions complètes | Non |
| `chat_log.json` | Journal permanent horodaté UTC | Non |
| `system_profile.md` | Instructions permanentes de l'assistant | — |
| `memory.md` | Mémoire persistante (mis à jour par Haiku via `/memory`) | — |

---

## 4. Constantes globales

```python
DEFAULT_MODEL      = "claude-sonnet-4-6"   # conversations
MEMORY_MODEL       = "claude-haiku-4-5-20251001"  # mise à jour mémoire
WRAP_COLS          = 40          # colonnes max Minitel
PAGE_LINES         = 18          # lignes avant pagination
LINE_DELAY_MS      = 80          # délai inter-ligne (ms)
CHAR_DELAY_MS      = 0           # délai inter-octet (0 = désactivé)
MAX_HISTORY_TURNS  = 20          # paires user/assistant conservées
MAX_HISTORY_CHARS  = 16000       # taille max de l'historique (chars)
```

`SERIAL_CONFIGS` ne contient **qu'une seule entrée** : `{"baud": 1200, "bytesize": 7, "parity": "E", "stopbits": 1}`. Aucune autre configuration n'est prévue.

---

## 5. Classes

### 5.1 `ConfigStore`

Persistance de `minitel_config.json`.

| Méthode | Rôle |
|---|---|
| `load()` | Charge le JSON, renvoie le dict |
| `save(data?)` | Écrit le JSON sur disque |
| `get(key, default)` | Accès à une clé |
| `set(key, value)` | Modification d'une clé |
| `exists()` | Vérifie l'existence du fichier |

**Clés importantes stockées :**
- `port`, `baud`, `bytesize`, `parity`, `stopbits`
- `model` (modèle courant)
- `line_delay_ms`, `char_delay_ms`
- `page_lines`
- `current_session_id`
- `last_memory_update` (ISO 8601 UTC, pour savoir jusqu'où Haiku a lu)

---

### 5.2 `HistoryStore`

Fenêtre de contexte roulante envoyée à l'API (`history.json`).

| Méthode | Rôle |
|---|---|
| `load()` | Charge + tronque |
| `save()` | Tronque + sauvegarde |
| `add(role, content, chat_log?)` | Ajoute un message, loggue dans `chat_log` si fourni |
| `reset()` | Vide et supprime le fichier |
| `load_from(messages)` | Remplace le contenu (reprise de session) |
| `get_messages()` | Copie de la liste pour l'API |
| `_trim()` | Élagage interne : par nombre de tours puis par taille |

**Logique de troncature** (`_trim`) :
1. Supprime les messages les plus anciens tant que `len(messages) > MAX_HISTORY_TURNS * 2`
2. Supprime ensuite tant que la somme des caractères dépasse `MAX_HISTORY_CHARS`

---

### 5.3 `ChatLogStore`

Journal permanent jamais tronqué (`chat_log.json`). Utilisé par `/memory`.

| Méthode | Rôle |
|---|---|
| `append(role, content)` | Ajoute une entrée avec timestamp UTC |
| `get_since(since_iso)` | Filtre les entrées postérieures à une date ISO |
| `_load_all()` | Lecture brute du fichier |

**Format d'une entrée :**
```json
{"timestamp": "2025-05-27T12:00:00+00:00", "role": "user", "content": "..."}
```

---

### 5.4 `SessionStore`

Historique complet de toutes les conversations (`sessions.json`).

| Méthode | Rôle |
|---|---|
| `load()` / `save()` | Sérialisation JSON |
| `create_session()` | Crée une session `sess_YYYYMMDD_HHMMSS` |
| `get_session(id)` | Recherche par ID |
| `update_session(id, messages)` | Met à jour les messages + titre (30 premiers chars du 1er message user) |
| `list_sessions()` | Tri par `updated_at` décroissant |
| `get_or_create_current(session_id)` | Reprend ou crée la session courante |
| `migrate_from_history(messages)` | Migration one-shot depuis `history.json` (si sessions vide) |

---

### 5.5 `AnthropicClientWrapper`

Wrapper autour du SDK `anthropic`.

| Méthode | Rôle |
|---|---|
| `_init_client(api_key?)` | Cherche la clé dans : arg → `HARDCODED_API_KEY` → `ANTHROPIC_API_KEY` |
| `call(messages, system_prompt, model, stream)` | Générateur de chunks texte, avec retry |
| `_call_streaming(...)` | Via `client.messages.stream()` |
| `_call_blocking(...)` | Via `client.messages.create()` |

**Retry logic :**
- 3 tentatives max
- Backoff exponentiel : 2s, 4s, 8s
- Déclenché sur : `rate limit`, `timeout`, `connection`, `503`, `502`, `overloaded`
- En cas d'échec définitif : yield `"[Erreur API: ...]"` (affiché sur le Minitel)

**Paramètres API fixes :** `max_tokens=1024` (non configurable)

---

### 5.6 `SerialMinitel`

Gestion de la liaison série réelle.

| Méthode | Rôle |
|---|---|
| `open()` | Ouvre le port avec `pyserial` |
| `close()` / `reopen()` | Ferme / rouvre |
| `write(text)` | Translittère en ASCII 7 bits puis envoie |
| `writeln(line)` | `write(line + "\r\n")` + délai `line_delay_ms` |
| `clear()` | Envoie `\x0c` (form feed Vidéotex) |
| `fake_clear(lines)` | Alternative : N retours ligne |
| `read_byte(timeout)` | Lit 1 octet (avec timeout temporaire) |
| `read_line(timeout, echo)` | Boucle sur `read_byte`, gère `\r`/`\n`, backspace `0x08`/`0x7F`, écho |
| `wait_keypress(timeout)` | Attend n'importe quelle touche |
| `set_pagination(bool)` / `is_pagination_enabled()` | Bascule pagination |

**Points d'attention `read_line` :**
- Ignore silencieusement tout octet ≥ 0x80 (bruit/erreur parité)
- Le `\n` suivant un `\r` est consommé mais pas remis dans le buffer (simplifié)
- Écho backspace = `\x08 \x08` (BS + espace + BS pour effacer le char à l'écran)

---

### 5.7 `SimulatedMinitel`

Même interface que `SerialMinitel`, mais via `stdin`/`stdout`. Permet de tester sans matériel.

- `write()` / `writeln()` → `print()` avec `to_ascii_7bit()`
- `read_line()` → `input()` (pas de gestion du timeout)
- `read_byte()` → `select.select([sys.stdin], ...)` avec timeout
- `clear()` → 5 lignes vides

---

## 6. Fonctions utilitaires

### `to_ascii_7bit(text) → str`

Pipeline de translittération obligatoire avant tout `serial.write()` :

1. Remplacement manuel via `_TRANSLIT_TABLE` (ligatures, monnaies, guillemets typographiques, flèches, exposants, etc.)
2. `unicodedata.normalize("NFKD", text)` — décompose les diacritiques
3. Filtre les marques combinantes (catégorie Unicode `Mn`)
4. `.encode("ascii", "replace").decode("ascii")` — remplace les restes par `?`

### `wrap_40(text, width=40) → List[str]`

Découpe un texte multi-lignes en respectant les mots. Utilise `textwrap.wrap()` avec `break_long_words=True`. Les paragraphes vides deviennent une ligne vide.

### `log_debug(msg, debug_mode)` / `hexdump(data)`

Outils de débogage vers `stderr`.

---

## 7. Fonctions d'affichage Minitel

### `display_wrapped(minitel, text, page_lines)`

Affichage bloquant d'un texte statique :
1. Appelle `wrap_40()` pour découper le texte
2. Envoie chaque ligne via `writeln()`
3. Toutes les `page_lines` lignes : affiche `-- suite (touche) --`, attend une touche, efface le message

### `display_streaming(minitel, text_generator, page_lines) → str`

Affichage progressif pendant le streaming Anthropic. C'est la fonction la plus complexe du projet.

**Stratégie de buffer :**
- Accumule les chunks du générateur dans `buffer`
- Priorité 1 : si `\n` dans le buffer → affiche jusqu'au `\n`, wrap si nécessaire, passe à la ligne
- Priorité 2 : si un espace est disponible et buffer > 10 chars → affiche jusqu'au dernier espace (mot complet)
- Sinon : attends plus de chunks

**Pagination :** vérifiée à chaque `writeln()` interne, même en streaming.

**Retour :** le texte complet accumulé (pour sauvegarde dans l'historique).

**Point d'attention :** le compteur `current_line_len` peut dériver si `write()` est appelé plusieurs fois sans `writeln()` — la logique suppose qu'il est mis à zéro à chaque retour ligne.

---

## 8. Gestion du profil et de la mémoire

### `_ensure_default_files()`

Crée au démarrage :
- `memory.md` vide si absent
- `system_profile.md` en essayant dans l'ordre : migration depuis `system_profile.txt`, puis `DEFAULT_SYSTEM_PROMPT`

### `load_system_prompt_combined() → str`

Concatène `system_profile.md` + (si non vide) `memory.md` sous la section `# Mémoire personnelle`. Ce prompt combiné est injecté en `system=` à chaque appel API.

### `_run_memory_update(anthropic_client, chat_log, config, debug)`

Appelé par la commande `/memory` :

1. Lit `memory.md` (mémoire actuelle)
2. Récupère les entrées de `chat_log.json` postérieures à `config["last_memory_update"]`
3. Formate la conversation pour Haiku
4. Appel **non-streaming** à Haiku avec le prompt : *"Met à jour la mémoire en Markdown…"*
5. Écrit la nouvelle `memory.md`
6. Met à jour `config["last_memory_update"]` avec l'heure courante UTC

---

## 9. Boucle principale `run_shell()`

Point d'entrée de l'interaction utilisateur. Tourne en boucle `while True`.

### Initialisation
1. Charge le modèle et `page_lines` depuis la config
2. Appelle `load_system_prompt_combined()`
3. Reprend ou crée la session courante via `SessionStore.get_or_create_current()`
4. Charge l'historique de la session dans `HistoryStore`
5. Affiche l'écran d'accueil (bannière `MINICLAUDE`)

### Boucle
```
> [read_line, timeout=3600s]
  → strip
  → si vide : continue
  → si commence par "/" : dispatch commande
  → sinon : appel API
```

### Commandes locales

| Commande | Action |
|---|---|
| `/help` | `show_help()` → `display_wrapped()` |
| `/clear` | `minitel.clear()` |
| `/quit` | `break` → retourne `"quit"` |
| `/reset` | retourne `"reset"` (signal à `main()` pour relancer l'autoconfig) |
| `/model [X]` | Affiche ou change le modèle en RAM + config |
| `/debug` | Toggle `debug_rx`, modifie `minitel.debug` si disponible |
| `/new` | Crée une nouvelle session, vide l'historique en RAM |
| `/chat` | Liste les 9 sessions les plus récentes, permet d'en charger une |
| `/history_reset` | `history.reset()` + vide la session courante dans `SessionStore` |
| `/memory` | `_run_memory_update()` + recharge le prompt système |
| `/nopage` | Toggle `minitel.set_pagination()` |
| `/throttle N` | Modifie `minitel.line_delay_ms` + config |

### Appel API
1. Construit `messages = history.get_messages() + [{"role": "user", "content": user_input}]`
2. Si streaming : `display_streaming()` avec générateur `anthropic_client.call()`
3. Si non-streaming : accumule les chunks + `display_wrapped()`
4. Sauvegarde dans `history` (avec log dans `chat_log`)
5. Sauvegarde dans `session_store` (non tronqué)

---

## 10. Point d'entrée `main()`

Arguments CLI :

| Argument | Effet |
|---|---|
| `--simulate` | Mode SimulatedMinitel (stdin/stdout) |
| `--port PORT` | Port série forcé (bypass autoconfig) |
| `--debug` | Active les logs RX/TX en `stderr` |
| `--no-stream` | Désactive le streaming (mode bloquant) |

### Séquence de démarrage (mode série)

```
Charger config + history + sessions
Créer fichiers par défaut
Migration one-shot history→sessions si nécessaire
Init AnthropicClientWrapper
Boucle principale :
  Si pas de config → run_serial_autoconfig()
  Ouvrir SerialMinitel
  run_shell()
    → si "reset" : effacer config, relancer la boucle
    → si "quit"  : sortir
```

### `run_serial_autoconfig(debug)`

1. Détecte les ports (`serial.tools.list_ports`), préfère `/dev/cu.*` sur macOS
2. Menu de sélection interactif (côté Mac, pas côté Minitel)
3. Ouvre le port en 1200 7E1
4. Envoie `"TEST 1200 7E1\r\nSI TU LIS CECI\r\nTAPE y PUIS ENTREE\r\n> "`
5. Attend `y` ou `Y` pendant 6 secondes
6. Si validé → sauvegarde la config complète et retourne le dict
7. Si aucune config ne marche → guide de diagnostic + option retry

---

## 11. Points d'attention et pièges

### Sérialisation ASCII 7 bits
- `to_ascii_7bit()` doit être appelée **avant tout** `serial.write()`. `SerialMinitel.write()` le fait systématiquement.
- `SimulatedMinitel.write()` appelle aussi `to_ascii_7bit()` pour cohérence de test.
- Les fichiers JSON/Markdown sont en UTF-8 — la contrainte ASCII ne s'applique **qu'à la sortie série**.

### Throttling
- `line_delay_ms=80` par défaut : 80 ms après chaque `\r\n`.
- `char_delay_ms=0` par défaut (désactivé). À activer si perte de chars persistante.
- En streaming, les chunks Anthropic arrivent vite. La fonction `display_streaming()` limite naturellement le débit en attendant les espaces.

### Pagination
- Bloquante : `wait_keypress(timeout=300)` — jusqu'à 5 minutes d'attente.
- Le message `-- suite (touche) --` fait 22 caractères, effacé par `\r` + 22 espaces + `\r`.
- Peut être désactivée via `/nopage`.

### Historique vs Sessions
- `history.json` = fenêtre tronquée envoyée à l'API (20 tours max).
- `sessions.json` = archive complète non tronquée pour navigation `/chat`.
- Les deux sont synchronisés à chaque échange dans `run_shell()`.

### Gestion de la clé API
- Ordre de priorité : argument → `HARDCODED_API_KEY` (vide par défaut) → `ANTHROPIC_API_KEY`.
- Si absente : `sys.exit(1)` avant même d'ouvrir le port série.

### Migration `system_profile.txt` → `.md`
- `_ensure_default_files()` migre automatiquement `system_profile.txt` (présent dans le repo) vers `system_profile.md` (ignoré par git) au premier lancement.

### Commande `/reset`
- Ne ferme pas proprement la session : retourne simplement `"reset"` à `main()`, qui supprime `minitel_config.json` et relance `run_serial_autoconfig()`.

### `max_tokens=1024`
- Limite fixe dans l'API. Des réponses longues seront coupées sans avertissement côté Minitel. À surveiller pour les requêtes complexes.

### Octet `\x0c` (form feed)
- Utilisé pour effacer l'écran. Peut ne pas fonctionner sur tous les Minitel 1. La méthode `fake_clear()` (N retours ligne) est disponible comme fallback mais n'est pas appelée automatiquement.

### `read_line()` et le byte "perdu"
- Après un `\r`, le code tente de consommer un éventuel `\n` (`read_byte(timeout=0.05)`). Si ce byte n'est pas `\r`/`\n`, il est **ignoré** (pas remis dans le buffer). Peut causer la perte d'un caractère si la frappe arrive très vite après l'Entrée.

---

## 12. Diagramme des flux de données

```
[system_profile.md] + [memory.md]
         │
         └──→ load_system_prompt_combined()
                        │
                        ▼
[Clavier Minitel] ──→ read_line()
                        │
                        ▼
               history.get_messages()
               + message user
                        │
                        ▼
         AnthropicClientWrapper.call()  ←── [API Anthropic]
                        │
              (générateur de chunks)
                        │
                        ▼
            display_streaming()
         [to_ascii_7bit + wrap_40 + throttle]
                        │
                        ▼
            [Écran Minitel 40 colonnes]
                        │
                        ▼
    history.add()  →  history.json
    chat_log.append() → chat_log.json
    session_store.update() → sessions.json
```

---

## 13. Commandes de test rapide

```bash
# Mode simulé (sans Minitel, sans câble)
python minitel_gpt.py --simulate

# Mode simulé sans streaming (utile pour debugger le wrap)
python minitel_gpt.py --simulate --no-stream

# Mode série avec port forcé
python minitel_gpt.py --port /dev/cu.usbserial-1234

# Mode debug (affiche octets RX en stderr)
python minitel_gpt.py --debug

# Lister les ports disponibles
python -m serial.tools.list_ports
```
