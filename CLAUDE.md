# CLAUDE.md

## Project Overview

MinitelGPT is a Python bridge that connects a vintage Minitel terminal to OpenAI's chat API. Users type prompts on a physical Minitel 1 (TRT / La Radiotechnique NFZ 201) and receive AI responses directly on the terminal display.

## Tech Stack

- **Language**: Python 3.10+
- **Dependencies**: `pyserial`, `openai`
- **Platform**: macOS (primary), should work on Linux
- **Hardware**: Minitel 1 + USB-to-DIN5 serial cable (FTDI-based recommended)

## Project Structure

```
MinitelGPT/
├── minitel_gpt.py       # Main application (single-file architecture)
├── system_profile.txt   # Custom system prompt (optional)
├── minitel_config.json  # Serial config (auto-generated, gitignored)
├── history.json         # Conversation history (auto-generated, gitignored)
├── README.md            # User documentation (French)
└── AGENTS.md            # Agent guidelines
```

## Key Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install pyserial openai
export OPENAI_API_KEY="sk-..."

# Run with real Minitel
python minitel_gpt.py

# Test without hardware
python minitel_gpt.py --simulate

# Debug mode (shows RX bytes)
python minitel_gpt.py --debug

# Specify port directly
python minitel_gpt.py --port /dev/cu.usbserial-1234

# Disable streaming
python minitel_gpt.py --no-stream
```

## Architecture Notes

### Display Constraints
- **40 columns** max width (Minitel screen limitation)
- **latin-1** encoding only (no UTF-8)
- Line endings: `\r\n` (Videotex compatible)
- **Throttling**: Configurable delays to prevent character loss
- **Pagination**: Every ~18 lines, pause for keypress

### Key Classes in `minitel_gpt.py`
- `ConfigStore` - Manages `minitel_config.json`
- `HistoryStore` - Manages `history.json` with trimming
- `OpenAIClientWrapper` - API calls with streaming and retry logic
- `SerialMinitel` - Serial port communication
- `SimulatedMinitel` - Stdin/stdout mock for testing

### Serial Configuration
The script auto-tests multiple serial configs at first launch:
- 1200/4800/9600 baud
- 7E1, 8N1, 7N1 formats
- User confirms when text is readable on Minitel

### Slash Commands (in-app)
- `/help` - Show commands
- `/clear` - Clear screen
- `/quit` - Exit
- `/reset` - Reconfigure serial
- `/model [name]` - View/change model (default: gpt-4o-mini)
- `/debug` - Toggle RX debug
- `/history_reset` - Clear conversation history
- `/nopage` - Toggle pagination
- `/throttle N` - Set line delay in ms

## Development Guidelines

1. **Keep it single-file**: The entire application lives in `minitel_gpt.py`
2. **Minitel-first**: Always consider 40-column display and latin-1 encoding
3. **No scraping**: Only use official OpenAI API
4. **Robust serial**: Handle connection issues gracefully
5. **Test with --simulate**: Verify logic without hardware

## Common Issues

- **No display**: Check DIN-5 cable, run `/reset` to reconfigure
- **Garbled text**: Wrong serial format, let auto-config retry
- **Character loss**: Increase throttling via `/throttle`
- **Echo issues**: Some Minitel models echo locally
