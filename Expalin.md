# Telegram Local Assistant — Complete Beginner's Guide

> **What you'll achieve:** Understand, run, and rebuild a Python bot that lets you control your Windows PC by sending messages on Telegram — opening apps, adjusting volume, taking screenshots, and more.

---

## 1. Introduction

### What Does It Do?

This project is a **Telegram bot that runs on your Windows computer**. You send it a text message from your phone or any device, and it executes commands on your PC — without you touching the keyboard.

**Examples of what you can say:**
- `open chrome` → Chrome opens on your PC
- `set volume to 40` → Volume changes immediately
- `screenshot` → Bot sends you a photo of your screen
- `alarm in 5 minutes` → An alarm sounds after 5 minutes
- `message John Hello! on whatsapp` → WhatsApp sends the message for you

### Real-World Use Case

You're in bed and forgot to close Spotify. You open Telegram on your phone and type `close spotify`. Done. No need to go back to your desk.

---

## 2. System Flow (Mental Model)

Here is exactly what happens from the moment you type a message to the moment your PC responds:

```
YOU (phone/Telegram app)
        |
        | "open chrome"
        v
[Telegram Servers]
        |
        | forwards message to your bot
        v
[bot.py]  ← Your PC is polling Telegram every few seconds
        |
        | passes text to router
        v
[router.py] → [intent_parser.py]
        |
        | returns: { action: "open_app", params: { app: "chrome" } }
        v
[validator.py]
        |
        | checks: Is this safe? Is the input clean?
        v
[actions.py]
        |
        | runs: handle_open_app({ app: "chrome" })
        |       → os.startfile("chrome.exe")
        v
[Chrome opens on your PC]
        |
        v
[bot.py sends reply back]
        |
        v
YOU receive: "OK: Opened chrome."
```

**Key insight:** Your PC stays connected to Telegram by constantly asking "any new messages?" (called *polling*). When a message arrives, this chain fires automatically.

---

## 3. Core Concepts

Only read what you need. These are brief.

### Telegram Bot Basics

- A Telegram bot is an account controlled by code, not a human.
- You create one via **BotFather** (a special Telegram account) — it gives you a **token** (a secret string like `123456:ABC...`).
- Your Python code uses this token to receive messages from users and send replies.
- The `python-telegram-bot` library handles all the networking for you.

### Environment Variables

- A way to store secrets (like your bot token) **outside your code**, so you never accidentally share them on GitHub.
- Set once in your terminal. Python reads them with `os.getenv("VARIABLE_NAME")`.
- Example: `setx TELEGRAM_TOKEN "123456:your_token_here"` (Windows)

### Windows Automation

The project uses several libraries to control Windows:

| Library | What it does |
|---|---|
| `os.startfile()` | Opens apps/files using their default program |
| `pyautogui` | Simulates keyboard and mouse input |
| `psutil` | Lists running processes, CPU/RAM/disk info |
| `pygetwindow` | Finds and focuses open windows |
| `screen_brightness_control` | Changes monitor brightness |
| `winsound` | Plays sounds (used for alarms) |
| `nircmd.exe` | External tool that controls system volume |

### Why Rule-Based Parsing (Not AI)?

This bot uses regex patterns to understand commands, not an AI model. Reasons:
- **Predictable:** `open chrome` always opens Chrome. An AI might misinterpret it.
- **Fast:** No API call, no latency.
- **Offline-capable:** Works without internet (except Telegram polling).
- **Safe:** You know exactly what inputs are accepted.

The trade-off: it won't understand anything it wasn't explicitly programmed to handle.

---

## 4. Setup (Exact Steps)

### Step 1 — Prerequisites

- **Python 3.10+** installed and on PATH.
  - Verify: open a terminal and run `python --version`
  - If you see `Python 3.10.x` or higher, you're good.
  - Download from [python.org](https://python.org) if needed. Check "Add Python to PATH" during install.

- **Git** (optional, for cloning). Or just download the ZIP from GitHub.

- **nircmd.exe** — needed for volume control only.
  - Download from [nirsoft.net/utils/nircmd.html](https://www.nirsoft.net/utils/nircmd.html)
  - Place it somewhere on your PC and note the full path (e.g., `C:\Tools\nircmd.exe`)

### Step 2 — Get the Code

```bash
# Option A: with git
git clone https://github.com/your-repo/telegram-local-assistant.git
cd telegram-local-assistant

# Option B: without git
# Download ZIP → extract → open that folder in terminal
```

### Step 3 — Create a Virtual Environment

A virtual environment keeps this project's packages isolated from the rest of your system.

```bash
# In the project folder:
python -m venv venv

# Activate it (Windows):
venv\Scripts\activate

# You should now see (venv) at the start of your terminal prompt.
```

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs: `python-telegram-bot`, `psutil`, `pyautogui`, `screen-brightness-control`, `rapidfuzz`, `pygetwindow`, `pywinauto`, and `requests`.

> **Note:** `main.py` also auto-installs missing packages on startup. But doing it manually first is cleaner.

### Step 5 — Create a Telegram Bot

1. Open Telegram and search for **BotFather**.
2. Send `/newbot`
3. Follow the prompts — choose a name and username.
4. BotFather gives you a token like: `7123456789:AAFx-xxxxxxxxxxxxxxxxxxxxxx`
5. **Copy and save this token.** You only see it once (though you can retrieve it again from BotFather with `/mybots`).

### Step 6 — Find Your Telegram User ID

You need this to restrict the bot to only respond to you.

1. Search for **userinfobot** on Telegram.
2. Send `/start`.
3. It replies with your numeric ID, e.g., `Id: 987654321`.

### Step 7 — Set Environment Variables

Open a terminal **as Administrator** (right-click → Run as administrator):

```bat
setx TELEGRAM_TOKEN "7123456789:AAFx-xxxxxxxxxxxxxxxxxxxxxx"
setx ALLOWED_TELEGRAM_USER_ID "987654321"
setx NIRCMD_PATH "C:\Tools\nircmd.exe"
```

> **Critical:** Close and reopen your terminal after running `setx`. Windows only loads new env vars in new terminal sessions.

Verify they were set:

```bat
echo %TELEGRAM_TOKEN%
echo %ALLOWED_TELEGRAM_USER_ID%
```

### Step 8 — (Optional) Configure Allowed Apps

Open `config.py`. Find `ALLOWED_APPS` and check that the apps you want to control are listed. You can add entries:

```python
ALLOWED_APPS: dict[str, str] = {
    "chrome":    "chrome.exe",
    "notepad":   "notepad.exe",
    "spotify":   "Spotify.exe",
    # Add your app:
    "paint":     "mspaint.exe",
}
```

The key is what you type in Telegram. The value is the executable name (or full path).

---

## 5. Run & Verify

### Start the Bot

```bash
# Make sure your venv is activated (you should see (venv) in the prompt)
python main.py
```

### Expected Output

```
2024-01-15 10:30:00 [INFO] __main__: Starting local AI assistant...
2024-01-15 10:30:01 [INFO] bot: Bot is polling for updates...
```

The bot is now running. It will keep running until you press `Ctrl+C`.

### Test It

1. Open Telegram on your phone or another device.
2. Find your bot (search by its username).
3. Send: `/start`
4. You should receive a reply listing all available commands.
5. Send: `system info`
6. You should receive CPU, RAM, and disk usage of your PC.

### Auto-Start on Boot (Optional)

1. Press `Win+R`, type `shell:startup`, press Enter.
2. Create a shortcut to `startup.bat` in that folder.
3. Windows will now run the bot every time you log in.

---

## 6. Code Walkthrough

Here is what each file does and how they connect.

### `main.py` — The Entry Point

**Role:** Starts everything.

- Checks that all required packages are installed (auto-installs missing ones).
- Sets up logging to both the terminal and a log file (`assistant.log`).
- Calls `bot.run()` to start the Telegram bot.
- Catches errors and prints helpful setup messages.

**Connects to:** `bot.py`, `config.py`

---

### `config.py` — Central Configuration

**Role:** One place for all settings.

- Reads env variables (`TELEGRAM_TOKEN`, `ALLOWED_TELEGRAM_USER_ID`, etc.).
- Defines `ALLOWED_APPS` (what apps the bot can open/close).
- Defines `HOME_DIR`, log file path, fuzzy match settings.

**Connects to:** Almost every other file imports from here.

---

### `bot.py` — The Telegram Interface

**Role:** Handles all Telegram communication.

- Creates the Telegram `Application` and registers two handlers:
  - `/start` command → sends the help message.
  - Any text message → routes through the full pipeline.
- Manages **pending states**:
  - `pending_confirmations`: waits for "yes/no" before dangerous actions (shutdown, move file, etc.).
  - `pending_choices`: waits for a number when fuzzy app matching returns multiple results.
- Sends replies back (text or photo for screenshots).

**The message handler pipeline:**
```
raw message
  → InputValidator.sanitize()     # clean the input
  → router.get_intent()           # figure out what they want
  → ActionGuard.check()           # is it safe to do?
  → action.handler()              # do it
  → ActionLogger.log_action()     # write to log file
  → reply to user
```

**Connects to:** `router.py`, `validator.py`, `actions.py`, `config.py`

---

### `router.py` — The Adapter

**Role:** Bridges the parser output to the format `bot.py` expects.

- Calls `intent_parser.parse(text)`.
- Remaps generic action names: `"open"` → `"open_app"`, `"close"` → `"close_app"`, `"find"` → `"find_file"`.
- Returns a clean `{ "action": "...", "params": {...} }` dict.
- Returns `{ "action": "unknown", "params": {} }` if nothing matched.

**Connects to:** `intent_parser.py`

---

### `intent_parser.py` — The Brain (Pattern Matching)

**Role:** Turns plain text into structured intents using regex.

- Contains ~50 compiled regex patterns (one per command type).
- Each pattern extracts the relevant parts of the command.
- Returns a dict with `action` and any parameters, or `None` if nothing matched.

**Example:**
```python
# Pattern:
_VOLUME_SET_RE = re.compile(r"^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:%)?$", re.IGNORECASE)

# Input: "set volume to 65"
# Match group 1: "65"
# Returns: {"action": "set_volume", "level": 65}
```

**Connects to:** Only called by `router.py`

---

### `validator.py` — The Safety Layer

**Role:** Prevents bad, dangerous, or malformed input from reaching the action handlers.

Three classes:

- **`InputValidator`**: Cleans raw text (strips control chars, trims whitespace). Validates app names, contact names, URLs, folder names, and message text individually.
- **`ActionGuard`**: Checks the parsed intent dict — is the action registered? Is the category allowed? Are the parameters valid (e.g., volume 0–100)?
- **`ActionLogger`**: Writes every action and its result to a rotating log file. Useful for debugging.

**Connects to:** `bot.py` (guard and logger), `actions.py` (imports `ACTION_REGISTRY` to check valid actions)

---

### `actions.py` — The Executor

**Role:** Actually performs the commands. This is where your PC gets controlled.

- Defines an `Action` dataclass: `{ id, description, requires_confirmation, handler }`.
- Contains one `handle_*` function per action (e.g., `handle_open_app`, `handle_set_volume`).
- Registers all actions in `ACTION_REGISTRY` (a dict mapping action ID → Action).

**Key helper functions used internally:**
- `_run_powershell()` — runs PowerShell scripts (used for clipboard, screenshots, network info)
- `_tap_virtual_key()` — sends media key presses (play/pause/next/prev)
- `_focus_app_window()` — finds and brings a window to the front
- `_capture_screenshot()` — tries PowerShell first, falls back to pyautogui

**Connects to:** Called by `bot.py`. Imports from `config.py`, `fuzzy_match.py`, `whatsapp_handler.py`

---

### Supporting Files

| File | Role |
|---|---|
| `app_discovery.py` | Scans Start Menu and Program Files for installed apps. Caches results for 24 hours in `apps_cache.json`. |
| `fuzzy_match.py` | Uses `rapidfuzz` to find the closest app name when an exact match fails. Returns top N results above a similarity threshold. |
| `key_sequence.py` | Parses compound key instructions like `ctrl+c, then enter x3` into steps pyautogui can execute. |
| `whatsapp_handler.py` | Launches WhatsApp Desktop and automates sending messages using `pywinauto` keyboard simulation. |

---

## 7. Example Flow: "open chrome"

Let's trace exactly what happens, file by file.

**You send:** `open chrome`

```
bot.py → handle_message()
  ├─ InputValidator.sanitize("open chrome")
  │    → "open chrome"  (no change, already clean)
  │
  ├─ router.get_intent("open chrome")
  │    └─ intent_parser.parse("open chrome")
  │         → _OPEN_RE matches: target = "chrome"
  │         → returns { "action": "open", "target": "chrome" }
  │    └─ router remaps "open" → "open_app"
  │    → returns { "action": "open_app", "params": { "app": "chrome" } }
  │
  ├─ ActionGuard.check({ "action": "open_app", "app": "chrome" })
  │    → "open_app" is in ACTION_REGISTRY ✓
  │    → category "app" is in ALLOWED_ACTION_CATEGORIES ✓
  │    → "chrome" passes validate_app_name() ✓
  │    → returns (True, "ok")
  │
  ├─ ACTION_REGISTRY["open_app"].requires_confirmation → False
  │    (no "confirm?" prompt needed)
  │
  ├─ _execute_action("open_app", { "app": "chrome" }, chat_id)
  │    └─ actions.handle_open_app({ "app": "chrome" })
  │         → _normalize_app_name("chrome") → "chrome"
  │         → "chrome" is in ALLOWED_APPS → path = "chrome.exe"
  │         → _launch("chrome", "chrome.exe")
  │              → _open_path("chrome.exe")
  │                   → os.startfile("chrome.exe")  ← Chrome opens!
  │         → returns "OK: Opened chrome."
  │
  ├─ ActionLogger.log_action(user_id, {...}, "OK: Opened chrome.")
  │    → writes to assistant.log
  │
  └─ update.message.reply_text("OK: Opened chrome.")
       → You receive the reply on Telegram
```

---

## 8. Add a New Command

**Goal:** Add a command `open notepad++` that opens Notepad++.

### Step 1 — Add to `ALLOWED_APPS` in `config.py`

```python
ALLOWED_APPS: dict[str, str] = {
    # ... existing apps ...
    "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
}
```

That's actually all you need for this case — `handle_open_app` already handles it via `ALLOWED_APPS`.

---

**Goal:** Add a completely new command: `clear clipboard`

### Step 1 — Add a regex pattern in `intent_parser.py`

```python
# Near the top with other patterns:
_CLEAR_CLIPBOARD_RE = re.compile(r"^clear\s+clipboard$", re.IGNORECASE)
```

### Step 2 — Add the parse case in `intent_parser.py`

Inside the `parse()` function, add (before the final `return None`):

```python
if _CLEAR_CLIPBOARD_RE.match(text):
    return {"action": "clear_clipboard"}
```

### Step 3 — Add the handler in `actions.py`

```python
def handle_clear_clipboard(params: dict) -> str:
    del params
    if _set_clipboard_text(""):
        return "OK: Clipboard cleared."
    return "Error: Could not clear the clipboard."
```

### Step 4 — Register the action in `ACTION_REGISTRY` (bottom of `actions.py`)

```python
"clear_clipboard": Action(
    id="clear_clipboard",
    description="Clear the clipboard",
    requires_confirmation=False,
    handler=handle_clear_clipboard,
),
```

### Step 5 — Add to category map in `validator.py`

```python
_ACTION_CATEGORY_MAP: dict[str, str] = {
    # ... existing entries ...
    "clear_clipboard": "clipboard",
}
```

**Done.** No other files need to change. Test by sending `clear clipboard` to your bot.

---

## 9. Common Errors

| Error | Cause | Fix |
|---|---|---|
| `ConfigurationError: Missing Telegram bot token` | `TELEGRAM_TOKEN` env var not set | Run `setx TELEGRAM_TOKEN "..."` and restart terminal |
| `ConfigurationError: Invalid Telegram bot token` | Token format is wrong | Token must contain `:` — get a fresh one from BotFather |
| `Access denied for this Telegram account.` | Your user ID is wrong or not set | Check `ALLOWED_TELEGRAM_USER_ID` matches what userinfobot returned |
| `Error: Could not set volume. Is nircmd installed?` | nircmd not found | Set `NIRCMD_PATH` env var to full path of `nircmd.exe` |
| `Error: No app matching 'x' was found` | App not in `ALLOWED_APPS` and not discovered | Add it to `ALLOWED_APPS` in `config.py` |
| `ModuleNotFoundError: No module named 'telegram'` | venv not activated, or deps not installed | Run `venv\Scripts\activate`, then `pip install -r requirements.txt` |
| Bot receives messages but does nothing | User ID filter blocking you | Temporarily set `ALLOWED_TELEGRAM_USER_ID` to empty to test, then fix the correct ID |
| `Error: Could not set brightness` | `screen-brightness-control` can't access your monitor | Only works with supported display hardware; desktop monitors often unsupported |

---

## 10. Rebuild Guide

Build it from scratch, step by step. Start minimal, then expand.

### Phase 1: One-Command Bot (< 50 lines)

This bot receives one message and responds. No actions yet.

```python
# minimal_bot.py
import os
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN", "")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    if text.lower() == "ping":
        await update.message.reply_text("pong")
    else:
        await update.message.reply_text(f"You said: {text}")

app = Application.builder().token(TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT, handle))
app.run_polling()
```

Run it: `python minimal_bot.py`
Send `ping` on Telegram → receive `pong`.

---

### Phase 2: Add One Real Action

Add system info:

```python
import psutil

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (update.message.text or "").strip().lower()
    if text == "system info":
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        reply = f"CPU: {cpu}%\nRAM: {mem.percent}%"
        await update.message.reply_text(reply)
    else:
        await update.message.reply_text("Unknown command.")
```

---

### Phase 3: Separate Parsing from Handling

Move command detection out of the handler:

```python
def parse(text: str) -> dict | None:
    if text.lower() == "system info":
        return {"action": "system_info"}
    if text.lower().startswith("open "):
        app = text[5:].strip()
        return {"action": "open_app", "app": app}
    return None

async def handle(update, context):
    intent = parse(update.message.text or "")
    if intent is None:
        await update.message.reply_text("Unknown command.")
        return
    if intent["action"] == "system_info":
        # ... handle it
    elif intent["action"] == "open_app":
        os.startfile(intent["app"] + ".exe")
        await update.message.reply_text(f"Opened {intent['app']}")
```

---

### Phase 4: Add a Registry Pattern

Instead of `if/elif` chains:

```python
def handle_system_info(params):
    cpu = psutil.cpu_percent(interval=1)
    return f"CPU: {cpu}%"

def handle_open_app(params):
    import subprocess
    subprocess.Popen(params["app"] + ".exe", shell=True)
    return f"Opened {params['app']}"

REGISTRY = {
    "system_info": handle_system_info,
    "open_app":    handle_open_app,
}

async def handle(update, context):
    intent = parse(update.message.text or "")
    if not intent:
        await update.message.reply_text("Unknown.")
        return
    handler_fn = REGISTRY.get(intent["action"])
    result = handler_fn({k: v for k, v in intent.items() if k != "action"})
    await update.message.reply_text(result)
```

From here you can keep adding:
- More patterns to `parse()`
- More handlers to `REGISTRY`
- Validation before calling handlers
- Logging after calling handlers

That is exactly the structure of the full project.

---

## 11. Exercises

These will deepen your understanding. Each is small and focused.

1. **Add a new app.** Add `mspaint` (MS Paint) to `ALLOWED_APPS` in `config.py`. Test with `open paint`.

2. **Add a new command.** Add `what time is it` → bot replies with the current time. You'll need: a regex in `intent_parser.py`, a handler in `actions.py`, a registry entry, and a category in `validator.py`.

3. **Read the log.** After sending a few commands, open `assistant.log` (find its path by printing `config.LOG_FILE`). What do you see? What does each column mean?

4. **Trigger fuzzy matching.** Type `open sptify` (intentional typo). What does the bot reply? Trace the code path through `handle_open_app` → `fuzzy_find` → the response.

5. **Add confirmation to a new action.** Create a `delete_temp` command that runs `del /q /f /s %TEMP%\*`. Set `requires_confirmation=True`. Test that the bot asks for `yes` before executing.

6. **Break and fix the parser.** In `intent_parser.py`, comment out the `_VOLUME_SET_RE` block. Send `set volume to 50`. What happens? Restore it. What does this teach you about the system's fallback behavior?

7. **Rebuild Phase 1–4** from the Rebuild Guide above without looking. Start from a blank file. This is the most valuable exercise.

---

*Guide complete. All code references are from the actual project files. No steps were skipped.*
