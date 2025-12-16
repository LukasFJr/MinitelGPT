#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
minitel_gpt.py — ChatGPT sur Minitel via API OpenAI officielle

Un seul fichier Python pour piloter un Minitel 1 (TRT / La Radiotechnique NFZ 201)
en liaison série et l'utiliser comme terminal de chat.

Usage:
    python minitel_gpt.py [--simulate] [--port PORT] [--debug] [--no-stream]

Dépendances:
    pip install pyserial openai
"""

import argparse
import json
import os
import sys
import time
import textwrap
from pathlib import Path
from typing import Optional, Generator, List, Dict, Any

# --- Configuration par défaut ---
DEFAULT_MODEL = "gpt-4o-mini"
WRAP_COLS = 40
PAGE_LINES = 18
LINE_DELAY_MS = 80
CHAR_DELAY_MS = 0  # 0 = désactivé
MAX_HISTORY_TURNS = 20
MAX_HISTORY_CHARS = 16000

# Clé API en dur (laisser vide pour utiliser OPENAI_API_KEY)
# ATTENTION: Ne pas committer avec une vraie clé si repo public!
HARDCODED_API_KEY = ""

# Fichiers de configuration/données
CONFIG_FILE = "minitel_config.json"
HISTORY_FILE = "history.json"
SYSTEM_PROFILE_FILE = "system_profile.txt"

# Profil système par défaut si system_profile.txt absent
DEFAULT_SYSTEM_PROMPT = """Tu es un assistant concis et utile.
Réponds en français.
Tes réponses seront affichées sur un Minitel (écran 40 colonnes).
Sois bref et va à l'essentiel."""

# Configurations série à tester (ordre de priorité)
SERIAL_CONFIGS = [
    {"baud": 1200, "bytesize": 7, "parity": "E", "stopbits": 1, "label": "1200 7E1"},
    {"baud": 4800, "bytesize": 7, "parity": "E", "stopbits": 1, "label": "4800 7E1"},
    {"baud": 1200, "bytesize": 8, "parity": "N", "stopbits": 1, "label": "1200 8N1"},
    {"baud": 4800, "bytesize": 8, "parity": "N", "stopbits": 1, "label": "4800 8N1"},
    {"baud": 9600, "bytesize": 7, "parity": "E", "stopbits": 1, "label": "9600 7E1"},
    {"baud": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "label": "9600 8N1"},
    {"baud": 300, "bytesize": 7, "parity": "E", "stopbits": 1, "label": "300 7E1"},
    {"baud": 2400, "bytesize": 7, "parity": "E", "stopbits": 1, "label": "2400 7E1"},
    {"baud": 1200, "bytesize": 7, "parity": "N", "stopbits": 1, "label": "1200 7N1"},
    {"baud": 4800, "bytesize": 7, "parity": "N", "stopbits": 1, "label": "4800 7N1"},
]


# ============================================================================
# Utilitaires
# ============================================================================

def sanitize_latin1(text: str) -> str:
    """Convertit le texte pour affichage latin-1, remplace les caractères non supportés."""
    return text.encode("latin-1", errors="replace").decode("latin-1")


def wrap_40(text: str, width: int = WRAP_COLS) -> List[str]:
    """Découpe le texte en lignes de max `width` colonnes, évite de couper les mots."""
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        wrapped = textwrap.wrap(paragraph, width=width, break_long_words=True, break_on_hyphens=True)
        lines.extend(wrapped if wrapped else [""])
    return lines


def log_debug(msg: str, debug_mode: bool = True):
    """Affiche un message de debug côté console Mac."""
    if debug_mode:
        print(f"[DEBUG] {msg}", file=sys.stderr)


def hexdump(data: bytes) -> str:
    """Retourne une représentation hexadécimale des données."""
    return " ".join(f"{b:02x}" for b in data)


# ============================================================================
# Classe ConfigStore
# ============================================================================

class ConfigStore:
    """Gère la sauvegarde/chargement de minitel_config.json."""

    def __init__(self, filepath: str = CONFIG_FILE):
        self.filepath = Path(filepath)
        self.data: Dict[str, Any] = {}

    def exists(self) -> bool:
        return self.filepath.exists()

    def load(self) -> Dict[str, Any]:
        if not self.exists():
            return {}
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Erreur lecture config: {e}", file=sys.stderr)
            self.data = {}
        return self.data

    def save(self, data: Optional[Dict[str, Any]] = None):
        if data is not None:
            self.data = data
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[ERREUR] Impossible de sauvegarder config: {e}", file=sys.stderr)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any):
        self.data[key] = value


# ============================================================================
# Classe HistoryStore
# ============================================================================

class HistoryStore:
    """Gère l'historique local des conversations (history.json)."""

    def __init__(self, filepath: str = HISTORY_FILE, max_turns: int = MAX_HISTORY_TURNS,
                 max_chars: int = MAX_HISTORY_CHARS):
        self.filepath = Path(filepath)
        self.max_turns = max_turns
        self.max_chars = max_chars
        self.messages: List[Dict[str, str]] = []

    def load(self):
        if not self.filepath.exists():
            self.messages = []
            return
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.messages = data if isinstance(data, list) else []
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARN] Erreur lecture historique: {e}", file=sys.stderr)
            self.messages = []
        self._trim()

    def save(self):
        self._trim()
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.messages, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"[ERREUR] Impossible de sauvegarder historique: {e}", file=sys.stderr)

    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self._trim()

    def reset(self):
        self.messages = []
        if self.filepath.exists():
            try:
                self.filepath.unlink()
            except IOError:
                pass

    def get_messages(self) -> List[Dict[str, str]]:
        return list(self.messages)

    def _trim(self):
        # Limiter par nombre de tours (paires user/assistant)
        while len(self.messages) > self.max_turns * 2:
            self.messages.pop(0)
        # Limiter par taille totale
        total_chars = sum(len(m.get("content", "")) for m in self.messages)
        while total_chars > self.max_chars and self.messages:
            removed = self.messages.pop(0)
            total_chars -= len(removed.get("content", ""))


# ============================================================================
# Classe OpenAIClientWrapper
# ============================================================================

class OpenAIClientWrapper:
    """Wrapper pour l'API OpenAI avec support streaming et fallback."""

    def __init__(self, api_key: Optional[str] = None, debug: bool = False):
        self.debug = debug
        self.client = None
        self._init_client(api_key)

    def _init_client(self, api_key: Optional[str] = None):
        # Priorité: clé passée > HARDCODED > env var
        key = api_key or HARDCODED_API_KEY or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("Clé API OpenAI non trouvée. Définir OPENAI_API_KEY ou HARDCODED_API_KEY.")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=key)
            self._use_new_api = True
        except ImportError:
            # Fallback vers ancienne API si nécessaire
            try:
                import openai
                openai.api_key = key
                self._use_new_api = False
                self.client = openai
            except ImportError:
                raise ImportError("Module openai non installé. Exécuter: pip install openai")

    def call(self, messages: List[Dict[str, str]], model: str = DEFAULT_MODEL,
             stream: bool = True) -> Generator[str, None, None]:
        """
        Appelle l'API OpenAI et retourne un générateur de chunks de texte.
        Si stream=False, retourne le texte complet en un seul chunk.
        """
        max_retries = 3
        retry_delay = 2

        for attempt in range(max_retries):
            try:
                if self._use_new_api:
                    yield from self._call_new_api(messages, model, stream)
                else:
                    yield from self._call_legacy_api(messages, model, stream)
                return
            except Exception as e:
                error_str = str(e).lower()
                # Erreurs transitoires: retry
                if any(x in error_str for x in ["rate limit", "timeout", "connection", "503", "502"]):
                    if attempt < max_retries - 1:
                        if self.debug:
                            log_debug(f"Erreur transitoire, retry dans {retry_delay}s: {e}")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                # Erreur fatale ou dernier retry
                if self.debug:
                    log_debug(f"Erreur API OpenAI: {e}")
                yield f"[Erreur API: {type(e).__name__}]"
                return

    def _call_new_api(self, messages: List[Dict[str, str]], model: str,
                      stream: bool) -> Generator[str, None, None]:
        """Appel avec le nouveau SDK OpenAI (>=1.0)."""
        if stream:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        else:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False
            )
            if response.choices:
                yield response.choices[0].message.content or ""

    def _call_legacy_api(self, messages: List[Dict[str, str]], model: str,
                         stream: bool) -> Generator[str, None, None]:
        """Fallback pour anciennes versions du SDK."""
        if stream:
            response = self.client.ChatCompletion.create(
                model=model,
                messages=messages,
                stream=True
            )
            for chunk in response:
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                if "content" in delta:
                    yield delta["content"]
        else:
            response = self.client.ChatCompletion.create(
                model=model,
                messages=messages,
                stream=False
            )
            yield response["choices"][0]["message"]["content"]


# ============================================================================
# Classe SerialMinitel
# ============================================================================

class SerialMinitel:
    """Gère la communication série avec le Minitel."""

    def __init__(self, port: str, baud: int = 1200, bytesize: int = 7,
                 parity: str = "E", stopbits: int = 1,
                 line_delay_ms: int = LINE_DELAY_MS,
                 char_delay_ms: int = CHAR_DELAY_MS,
                 debug: bool = False):
        self.port = port
        self.baud = baud
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.line_delay_ms = line_delay_ms
        self.char_delay_ms = char_delay_ms
        self.debug = debug
        self.serial = None
        self._pagination_enabled = True

    def open(self) -> bool:
        try:
            import serial
            parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                bytesize=self.bytesize,
                parity=parity_map.get(self.parity, serial.PARITY_EVEN),
                stopbits=self.stopbits,
                timeout=0.5,
                write_timeout=2
            )
            return True
        except Exception as e:
            if self.debug:
                log_debug(f"Erreur ouverture port {self.port}: {e}")
            return False

    def close(self):
        if self.serial and self.serial.is_open:
            try:
                self.serial.close()
            except Exception:
                pass

    def reopen(self) -> bool:
        self.close()
        return self.open()

    def is_open(self) -> bool:
        return self.serial is not None and self.serial.is_open

    def write(self, text: str):
        """Écrit du texte brut sur le Minitel (encodage latin-1)."""
        if not self.is_open():
            return
        data = sanitize_latin1(text).encode("latin-1", errors="replace")
        if self.char_delay_ms > 0:
            for byte in data:
                self.serial.write(bytes([byte]))
                time.sleep(self.char_delay_ms / 1000.0)
        else:
            self.serial.write(data)

    def writeln(self, line: str = ""):
        """Écrit une ligne puis retour chariot."""
        self.write(line + "\r\n")
        if self.line_delay_ms > 0:
            time.sleep(self.line_delay_ms / 1000.0)

    def clear(self):
        """Efface l'écran (form feed ou faux clear)."""
        # Essayer form feed
        self.write("\x0c")
        time.sleep(0.1)
        # Fallback: envoyer des lignes vides
        # (le form feed devrait marcher sur la plupart des Minitel)

    def fake_clear(self, lines: int = 24):
        """Faux clear: envoie beaucoup de retours ligne."""
        for _ in range(lines):
            self.writeln()

    def read_byte(self, timeout: float = 0.5) -> Optional[int]:
        """Lit un octet du Minitel."""
        if not self.is_open():
            return None
        old_timeout = self.serial.timeout
        self.serial.timeout = timeout
        try:
            data = self.serial.read(1)
            if data:
                byte = data[0]
                if self.debug:
                    log_debug(f"RX: 0x{byte:02x} ({repr(chr(byte)) if 32 <= byte < 127 else '?'})")
                return byte
            return None
        finally:
            self.serial.timeout = old_timeout

    def read_line(self, timeout: float = 60.0, echo: bool = True) -> Optional[str]:
        """
        Lit une ligne jusqu'à Entrée.
        Gère backspace (0x08 et 0x7f) et différentes formes de retour ligne.
        """
        if not self.is_open():
            return None

        buffer = []
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            byte = self.read_byte(timeout=0.1)
            if byte is None:
                continue

            # Entrée: \r (0x0d) ou \n (0x0a)
            if byte in (0x0d, 0x0a):
                # Consommer un éventuel \n suivant un \r
                next_byte = self.read_byte(timeout=0.05)
                if next_byte is not None and next_byte not in (0x0d, 0x0a):
                    # Remettre le byte dans le buffer? Non, on l'ignore pour simplifier
                    pass
                if echo:
                    self.writeln()
                return "".join(buffer)

            # Backspace: 0x08 ou 0x7f
            if byte in (0x08, 0x7f):
                if buffer:
                    buffer.pop()
                    if echo:
                        # Effacer le caractère à l'écran: backspace + espace + backspace
                        self.write("\x08 \x08")
                continue

            # Caractère imprimable
            if 32 <= byte < 127:
                char = chr(byte)
                buffer.append(char)
                if echo:
                    self.write(char)
            elif byte >= 128:
                # Caractères étendus latin-1
                try:
                    char = bytes([byte]).decode("latin-1")
                    buffer.append(char)
                    if echo:
                        self.write(char)
                except Exception:
                    pass

        return "".join(buffer) if buffer else None

    def wait_keypress(self, timeout: float = 300.0) -> Optional[int]:
        """Attend qu'une touche soit pressée."""
        return self.read_byte(timeout=timeout)

    def set_pagination(self, enabled: bool):
        self._pagination_enabled = enabled

    def is_pagination_enabled(self) -> bool:
        return self._pagination_enabled


# ============================================================================
# Classe SimulatedMinitel
# ============================================================================

class SimulatedMinitel:
    """
    Simule un Minitel via stdin/stdout pour tester sans matériel.
    Implémente la même interface que SerialMinitel.
    """

    def __init__(self, line_delay_ms: int = 0, debug: bool = False):
        self.line_delay_ms = line_delay_ms
        self.debug = debug
        self._pagination_enabled = True
        self._is_open = False

    def open(self) -> bool:
        self._is_open = True
        return True

    def close(self):
        self._is_open = False

    def reopen(self) -> bool:
        return self.open()

    def is_open(self) -> bool:
        return self._is_open

    def write(self, text: str):
        print(sanitize_latin1(text), end="", flush=True)

    def writeln(self, line: str = ""):
        print(sanitize_latin1(line))
        if self.line_delay_ms > 0:
            time.sleep(self.line_delay_ms / 1000.0)

    def clear(self):
        # En mode simulé, on affiche juste des lignes vides
        print("\n" * 5)

    def fake_clear(self, lines: int = 24):
        print("\n" * lines)

    def read_byte(self, timeout: float = 0.5) -> Optional[int]:
        # En mode simulé, on lit un caractère de stdin
        import select
        if select.select([sys.stdin], [], [], timeout)[0]:
            char = sys.stdin.read(1)
            if char:
                return ord(char)
        return None

    def read_line(self, timeout: float = 60.0, echo: bool = True) -> Optional[str]:
        try:
            line = input()
            return line
        except EOFError:
            return None
        except KeyboardInterrupt:
            return None

    def wait_keypress(self, timeout: float = 300.0) -> Optional[int]:
        return self.read_byte(timeout=timeout)

    def set_pagination(self, enabled: bool):
        self._pagination_enabled = enabled

    def is_pagination_enabled(self) -> bool:
        return self._pagination_enabled


# ============================================================================
# Auto-configuration série
# ============================================================================

def list_serial_ports() -> List[str]:
    """Liste les ports série disponibles, préférant /dev/cu.* sur macOS."""
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        # Filtrer pour macOS: préférer cu.* (pas tty.*)
        cu_ports = [p.device for p in ports if "/dev/cu." in p.device]
        other_ports = [p.device for p in ports if "/dev/cu." not in p.device]
        return cu_ports + other_ports
    except ImportError:
        print("[ERREUR] pyserial non installé. Exécuter: pip install pyserial", file=sys.stderr)
        return []


def run_serial_autoconfig(debug: bool = False) -> Optional[Dict[str, Any]]:
    """
    Assistant interactif de configuration série.
    Teste plusieurs configurations jusqu'à validation par l'utilisateur.
    """
    print("\n" + "=" * 60)
    print("   ASSISTANT DE CONFIGURATION SERIE MINITEL")
    print("=" * 60)

    # 1. Détection des ports
    ports = list_serial_ports()
    if not ports:
        print("\n[ERREUR] Aucun port série détecté.")
        print("\nCauses possibles:")
        print("  - Câble USB non branché")
        print("  - Driver FTDI/CH340 non installé")
        print("  - Permission refusée sur le port")
        print("\nSolutions:")
        print("  1. Brancher le câble USB-série")
        print("  2. Installer le driver FTDI: https://ftdichip.com/drivers/")
        print("  3. Sur macOS, vérifier: ls /dev/cu.*")
        print("\nAppuie sur Entrée pour rescanner ou Ctrl+C pour quitter...")
        try:
            input()
            return run_serial_autoconfig(debug)
        except KeyboardInterrupt:
            return None

    # 2. Sélection du port
    print(f"\n{len(ports)} port(s) série détecté(s):\n")
    for i, port in enumerate(ports):
        print(f"  [{i + 1}] {port}")
    print(f"\n  [R] Rescanner les ports")
    print(f"  [Q] Quitter")

    while True:
        choice = input("\nChoisis un port (numéro): ").strip().lower()
        if choice == "r":
            return run_serial_autoconfig(debug)
        if choice == "q":
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(ports):
                selected_port = ports[idx]
                break
        except ValueError:
            pass
        print("Choix invalide.")

    print(f"\nPort sélectionné: {selected_port}")
    print("\n" + "-" * 40)
    print("Test des configurations série...")
    print("Regarde l'écran du Minitel!")
    print("-" * 40)

    # 3. Test des configurations
    import serial

    for config in SERIAL_CONFIGS:
        label = config["label"]
        print(f"\n[TEST] {label}...", end=" ", flush=True)

        try:
            parity_map = {"N": serial.PARITY_NONE, "E": serial.PARITY_EVEN, "O": serial.PARITY_ODD}
            ser = serial.Serial(
                port=selected_port,
                baudrate=config["baud"],
                bytesize=config["bytesize"],
                parity=parity_map.get(config["parity"], serial.PARITY_EVEN),
                stopbits=config["stopbits"],
                timeout=0.5,
                write_timeout=2
            )
        except Exception as e:
            print(f"ERREUR ouverture: {e}")
            continue

        # Envoyer message de test
        test_msg = f"\r\nTEST {label}\r\n"
        test_msg += "SI TU LIS CECI\r\n"
        test_msg += "TAPE y PUIS ENTREE\r\n"
        test_msg += "> "

        try:
            ser.write(test_msg.encode("latin-1"))
            time.sleep(0.1)
        except Exception as e:
            print(f"ERREUR écriture: {e}")
            ser.close()
            continue

        # Attendre réponse 'y'
        print("En attente de 'y'...", end=" ", flush=True)
        start_time = time.time()
        buffer = b""

        while (time.time() - start_time) < 6:  # 6 secondes timeout
            try:
                data = ser.read(1)
                if data:
                    if debug:
                        print(f"[RX: 0x{data[0]:02x}]", end=" ", flush=True)
                    buffer += data
                    # Chercher 'y' ou 'Y' suivi d'un retour
                    if b"y" in buffer.lower() or b"Y" in buffer:
                        # Attendre un peu pour le retour ligne
                        time.sleep(0.3)
                        extra = ser.read(10)
                        buffer += extra

                        if any(c in buffer for c in [b"\r", b"\n", b"y", b"Y"]):
                            print("OK!")
                            ser.close()

                            # Configuration validée
                            result = {
                                "port": selected_port,
                                "baud": config["baud"],
                                "bytesize": config["bytesize"],
                                "parity": config["parity"],
                                "stopbits": config["stopbits"],
                                "line_delay_ms": LINE_DELAY_MS,
                                "char_delay_ms": CHAR_DELAY_MS,
                                "model": DEFAULT_MODEL,
                                "page_lines": PAGE_LINES,
                            }

                            print("\n" + "=" * 40)
                            print("CONFIGURATION VALIDEE!")
                            print("=" * 40)
                            print(f"  Port: {selected_port}")
                            print(f"  Baud: {config['baud']}")
                            print(f"  Format: {config['label']}")
                            print("=" * 40)

                            return result
            except Exception:
                break

        print("pas de réponse")
        ser.close()

    # Aucune configuration n'a marché
    print("\n" + "=" * 60)
    print("AUCUNE CONFIGURATION N'A FONCTIONNE")
    print("=" * 60)
    print("\nDiagnostic:")
    print("-" * 40)
    print("1. MAUVAIS PORT")
    print("   -> Essaie un autre port si disponible")
    print()
    print("2. CABLE INCOMPATIBLE")
    print("   -> Le câble peut avoir une inversion RX/TX")
    print("   -> Ou des niveaux de tension incorrects")
    print("   -> Solution: câble 'spécial Minitel' basé FTDI")
    print()
    print("3. PRISE DIN-5 NON EXPLOITABLE")
    print("   -> Sur certains Minitel 1, la prise péri-")
    print("      informatique peut être non fonctionnelle")
    print()
    print("4. MINITEL ETEINT / EN VEILLE")
    print("   -> Vérifier que le Minitel est allumé")
    print()
    print("-" * 40)
    print("Pour débugger:")
    print("  1. Relance avec --debug")
    print("  2. Tape sur le clavier du Minitel")
    print("  3. Regarde si des octets RX arrivent")
    print()

    retry = input("Réessayer? [o/N] ").strip().lower()
    if retry == "o":
        return run_serial_autoconfig(debug)

    return None


# ============================================================================
# Fonctions d'affichage Minitel
# ============================================================================

def display_wrapped(minitel, text: str, page_lines: int = PAGE_LINES):
    """Affiche du texte avec wrap à 40 colonnes et pagination."""
    lines = wrap_40(text, WRAP_COLS)
    line_count = 0

    for line in lines:
        minitel.writeln(line)
        line_count += 1

        # Pagination
        if minitel.is_pagination_enabled() and line_count >= page_lines:
            minitel.writeln()
            minitel.write("-- suite (touche) --")
            minitel.wait_keypress(timeout=300)
            # Effacer le message "suite"
            minitel.write("\r" + " " * 22 + "\r")
            line_count = 0


def display_streaming(minitel, text_generator: Generator[str, None, None],
                      page_lines: int = PAGE_LINES) -> str:
    """
    Affiche du texte en streaming avec wrap progressif.
    Accumule dans un buffer et flush ligne par ligne.
    Retourne le texte complet.
    """
    full_text = ""
    buffer = ""
    line_count = 0
    current_line_len = 0

    for chunk in text_generator:
        full_text += chunk
        buffer += chunk

        # Traiter le buffer caractère par caractère
        while buffer:
            # Chercher un point de coupure naturel
            if "\n" in buffer:
                idx = buffer.index("\n")
                segment = buffer[:idx]
                buffer = buffer[idx + 1:]

                # Afficher le segment avec wrap
                if current_line_len + len(segment) <= WRAP_COLS:
                    minitel.write(segment)
                    current_line_len += len(segment)
                else:
                    # Wrap nécessaire
                    remaining = segment
                    while remaining:
                        space_left = WRAP_COLS - current_line_len
                        if len(remaining) <= space_left:
                            minitel.write(remaining)
                            current_line_len += len(remaining)
                            break
                        else:
                            # Trouver le dernier espace dans la zone disponible
                            cut_point = remaining[:space_left].rfind(" ")
                            if cut_point <= 0:
                                cut_point = space_left
                            minitel.write(remaining[:cut_point])
                            minitel.writeln()
                            line_count += 1
                            remaining = remaining[cut_point:].lstrip()
                            current_line_len = 0

                            # Pagination
                            if minitel.is_pagination_enabled() and line_count >= page_lines:
                                minitel.writeln()
                                minitel.write("-- suite (touche) --")
                                minitel.wait_keypress(timeout=300)
                                minitel.write("\r" + " " * 22 + "\r")
                                line_count = 0

                # Nouvelle ligne
                minitel.writeln()
                line_count += 1
                current_line_len = 0

                # Pagination
                if minitel.is_pagination_enabled() and line_count >= page_lines:
                    minitel.writeln()
                    minitel.write("-- suite (touche) --")
                    minitel.wait_keypress(timeout=300)
                    minitel.write("\r" + " " * 22 + "\r")
                    line_count = 0

            elif " " in buffer and len(buffer) > 10:
                # On a assez de texte avec un espace, on peut afficher
                idx = buffer.rfind(" ")
                segment = buffer[:idx]
                buffer = buffer[idx + 1:]

                # Wrap si nécessaire
                while segment:
                    space_left = WRAP_COLS - current_line_len
                    if len(segment) <= space_left:
                        minitel.write(segment + " ")
                        current_line_len += len(segment) + 1
                        break
                    else:
                        cut_point = segment[:space_left].rfind(" ")
                        if cut_point <= 0:
                            cut_point = space_left
                        minitel.write(segment[:cut_point])
                        minitel.writeln()
                        line_count += 1
                        segment = segment[cut_point:].lstrip()
                        current_line_len = 0

                        if minitel.is_pagination_enabled() and line_count >= page_lines:
                            minitel.writeln()
                            minitel.write("-- suite (touche) --")
                            minitel.wait_keypress(timeout=300)
                            minitel.write("\r" + " " * 22 + "\r")
                            line_count = 0
            else:
                # Pas assez de texte, attendre plus
                break

    # Flush le reste du buffer
    if buffer:
        while buffer:
            space_left = WRAP_COLS - current_line_len
            if len(buffer) <= space_left:
                minitel.write(buffer)
                break
            else:
                cut_point = buffer[:space_left].rfind(" ")
                if cut_point <= 0:
                    cut_point = space_left
                minitel.write(buffer[:cut_point])
                minitel.writeln()
                buffer = buffer[cut_point:].lstrip()
                current_line_len = 0

    minitel.writeln()
    return full_text


# ============================================================================
# Chargement du profil système
# ============================================================================

def load_system_prompt() -> str:
    """Charge le prompt système depuis system_profile.txt ou utilise le défaut."""
    profile_path = Path(SYSTEM_PROFILE_FILE)
    if profile_path.exists():
        try:
            content = profile_path.read_text(encoding="utf-8").strip()
            if content:
                return content
        except IOError:
            pass
    return DEFAULT_SYSTEM_PROMPT


# ============================================================================
# Boucle principale (shell)
# ============================================================================

def show_help(minitel):
    """Affiche l'aide des commandes."""
    help_text = """COMMANDES DISPONIBLES:
/help    - Cette aide
/clear   - Effacer ecran
/quit    - Quitter
/reset   - Reconfigurer serie
/model   - Voir/changer modele
/model X - Changer pour X
/debug   - Toggle debug RX
/history_reset - Effacer historique
/nopage  - Toggle pagination
/throttle N - Delai lignes (ms)
"""
    display_wrapped(minitel, help_text)


def run_shell(minitel, openai_client: OpenAIClientWrapper,
              config: ConfigStore, history: HistoryStore,
              debug: bool = False, stream: bool = True):
    """Boucle principale du shell Minitel."""

    model = config.get("model", DEFAULT_MODEL)
    page_lines = config.get("page_lines", PAGE_LINES)
    system_prompt = load_system_prompt()
    debug_rx = debug

    minitel.clear()
    time.sleep(0.2)
    minitel.writeln("=" * 40)
    minitel.writeln("  MINITEL-GPT")
    minitel.writeln("  Tape /help pour les commandes")
    minitel.writeln("=" * 40)
    minitel.writeln()

    while True:
        try:
            # Afficher le prompt
            minitel.write("> ")
            user_input = minitel.read_line(timeout=3600, echo=True)

            if user_input is None:
                continue

            user_input = user_input.strip()
            if not user_input:
                continue

            # Commandes locales
            if user_input.startswith("/"):
                cmd_parts = user_input.split(maxsplit=1)
                cmd = cmd_parts[0].lower()
                arg = cmd_parts[1] if len(cmd_parts) > 1 else ""

                if cmd == "/help":
                    show_help(minitel)

                elif cmd == "/clear":
                    minitel.clear()
                    time.sleep(0.1)
                    # Si le clear ne marche pas, faire un faux clear
                    # (l'utilisateur peut relancer /clear si besoin)

                elif cmd == "/quit":
                    minitel.writeln("Au revoir!")
                    break

                elif cmd == "/reset":
                    minitel.writeln("Relance config serie...")
                    return "reset"  # Signal pour relancer l'autoconfig

                elif cmd == "/model":
                    if arg:
                        model = arg.strip()
                        config.set("model", model)
                        config.save()
                        minitel.writeln(f"Modele: {model}")
                    else:
                        minitel.writeln(f"Modele actuel: {model}")

                elif cmd == "/debug":
                    debug_rx = not debug_rx
                    if debug_rx:
                        minitel.writeln("Debug RX actif")
                        print("[DEBUG] Mode debug RX activé - les octets seront affichés en console",
                              file=sys.stderr)
                    else:
                        minitel.writeln("Debug RX desactive")
                    if hasattr(minitel, "debug"):
                        minitel.debug = debug_rx

                elif cmd == "/history_reset":
                    history.reset()
                    minitel.writeln("Historique efface")

                elif cmd == "/nopage":
                    current = minitel.is_pagination_enabled()
                    minitel.set_pagination(not current)
                    if minitel.is_pagination_enabled():
                        minitel.writeln("Pagination activee")
                    else:
                        minitel.writeln("Pagination desactivee")

                elif cmd == "/throttle":
                    if arg:
                        try:
                            ms = int(arg)
                            minitel.line_delay_ms = ms
                            config.set("line_delay_ms", ms)
                            config.save()
                            minitel.writeln(f"Delai: {ms}ms")
                        except ValueError:
                            minitel.writeln("Usage: /throttle <ms>")
                    else:
                        minitel.writeln(f"Delai actuel: {minitel.line_delay_ms}ms")

                else:
                    minitel.writeln(f"Commande inconnue: {cmd}")

                continue

            # Envoi à OpenAI
            minitel.writeln()

            # Construire les messages
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(history.get_messages())
            messages.append({"role": "user", "content": user_input})

            try:
                if stream:
                    response_text = display_streaming(
                        minitel,
                        openai_client.call(messages, model=model, stream=True),
                        page_lines=page_lines
                    )
                else:
                    response_text = ""
                    for chunk in openai_client.call(messages, model=model, stream=False):
                        response_text += chunk
                    display_wrapped(minitel, response_text, page_lines=page_lines)

                # Sauvegarder dans l'historique
                history.add("user", user_input)
                history.add("assistant", response_text)
                history.save()

            except Exception as e:
                minitel.writeln()
                minitel.writeln("Erreur API. Reessaie.")
                if debug_rx:
                    print(f"[ERREUR] {type(e).__name__}: {e}", file=sys.stderr)

            minitel.writeln()

        except KeyboardInterrupt:
            minitel.writeln()
            minitel.writeln("Ctrl+C detecte.")
            break

    return "quit"


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MinitelGPT - ChatGPT sur Minitel via API OpenAI"
    )
    parser.add_argument("--simulate", action="store_true",
                        help="Mode simulation (stdin/stdout au lieu de série)")
    parser.add_argument("--port", type=str, default=None,
                        help="Port série à utiliser (ex: /dev/cu.usbserial-1234)")
    parser.add_argument("--debug", action="store_true",
                        help="Activer le mode debug (affiche les octets RX)")
    parser.add_argument("--no-stream", action="store_true",
                        help="Désactiver le streaming (récupère la réponse complète)")
    args = parser.parse_args()

    # Initialiser les stores
    config = ConfigStore()
    history = HistoryStore()

    # Charger l'historique
    history.load()

    # Initialiser le client OpenAI
    try:
        openai_client = OpenAIClientWrapper(debug=args.debug)
    except Exception as e:
        print(f"[ERREUR] Impossible d'initialiser OpenAI: {e}", file=sys.stderr)
        print("\nVérifiez que OPENAI_API_KEY est défini:", file=sys.stderr)
        print("  export OPENAI_API_KEY='sk-...'", file=sys.stderr)
        sys.exit(1)

    # Mode simulation
    if args.simulate:
        print("=" * 50)
        print("MODE SIMULATION (stdin/stdout)")
        print("Tape tes prompts, /help pour les commandes")
        print("=" * 50)
        print()

        minitel = SimulatedMinitel(debug=args.debug)
        minitel.open()

        # Créer une config par défaut pour le mode simulation
        config.data = {
            "port": "SIMULATE",
            "model": DEFAULT_MODEL,
            "page_lines": PAGE_LINES,
            "line_delay_ms": 0,
        }

        try:
            run_shell(minitel, openai_client, config, history,
                      debug=args.debug, stream=not args.no_stream)
        except KeyboardInterrupt:
            print("\nAu revoir!")
        finally:
            minitel.close()
            history.save()
        return

    # Mode série
    while True:
        # Charger ou créer la configuration
        if args.port:
            # Port spécifié en argument
            config.data = config.load()
            config.data["port"] = args.port
            if "baud" not in config.data:
                config.data["baud"] = 1200
            if "bytesize" not in config.data:
                config.data["bytesize"] = 7
            if "parity" not in config.data:
                config.data["parity"] = "E"
            if "stopbits" not in config.data:
                config.data["stopbits"] = 1
        elif not config.exists():
            # Pas de config, lancer l'assistant
            result = run_serial_autoconfig(debug=args.debug)
            if result is None:
                print("\nConfiguration annulée. Utilise --simulate pour tester sans Minitel.")
                sys.exit(0)
            config.data = result
            config.save()
        else:
            config.load()

        # Vérifier qu'on a un port
        port = config.get("port")
        if not port:
            result = run_serial_autoconfig(debug=args.debug)
            if result is None:
                sys.exit(0)
            config.data = result
            config.save()
            port = config.get("port")

        # Ouvrir le port série
        minitel = SerialMinitel(
            port=port,
            baud=config.get("baud", 1200),
            bytesize=config.get("bytesize", 7),
            parity=config.get("parity", "E"),
            stopbits=config.get("stopbits", 1),
            line_delay_ms=config.get("line_delay_ms", LINE_DELAY_MS),
            char_delay_ms=config.get("char_delay_ms", CHAR_DELAY_MS),
            debug=args.debug
        )

        if not minitel.open():
            print(f"[ERREUR] Impossible d'ouvrir {port}", file=sys.stderr)
            print("Vérifie que le câble est branché et que le port existe.", file=sys.stderr)
            print("\nPorts disponibles:")
            for p in list_serial_ports():
                print(f"  - {p}")
            print()
            retry = input("Relancer la configuration? [O/n] ").strip().lower()
            if retry != "n":
                config.data = {}
                continue
            sys.exit(1)

        print(f"[INFO] Connecté sur {port} ({config.get('baud')} baud)")
        print("[INFO] Ctrl+C pour quitter")

        try:
            result = run_shell(minitel, openai_client, config, history,
                               debug=args.debug, stream=not args.no_stream)

            if result == "reset":
                minitel.close()
                config.data = {}
                if config.filepath.exists():
                    config.filepath.unlink()
                continue
            else:
                break

        except KeyboardInterrupt:
            print("\n[INFO] Ctrl+C - Fermeture...")
        finally:
            minitel.close()
            history.save()

    print("[INFO] Au revoir!")


if __name__ == "__main__":
    main()
