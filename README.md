# Telegram Local Assistant

A Windows-only Telegram bot that lets you control your laptop from your phone using messages sent to a telegram bot.

## 1. Project Title

**Telegram Local Assistant**

## 2. Project Overview

Telegram Local Assistant is a Telegram-based desktop automation tool for Windows. You send text commands to a Telegram bot, and the bot turns them into laptop actions such as opening apps, pressing keys, sending WhatsApp messages, taking screenshots, checking system status, and more.

### What it does
- Opens, switches to, and closes desktop applications.
- Searches for files inside your home directory.
- Controls screen brightness and, if available, system volume.
- Types text and presses ordered key sequences like `enter`, `ctrl+c`, and `alt+tab`.
- Sends WhatsApp messages or opens a WhatsApp chat.
- Opens URLs, searches Google and YouTube, and runs app shortcuts.
- Shows battery, Wi-Fi, IP address, CPU, RAM, and disk usage.
- Creates folders, moves files, and works with the clipboard.
- Takes screenshots and sends them back to Telegram.
- Runs simple macros such as `work mode`, `study mode`, and `meeting mode`.

### Problem it solves
This project removes the need to sit in front of the laptop for common actions. Instead of walking back to your computer just to open an app, check a status value, or send a message, you can issue the command from Telegram on your phone.

### Real-world use case
You can use it when:
- your laptop is across the room
- your laptop is connected to a TV or external monitor
- you want to trigger repetitive desktop actions remotely
- you need a quick way to launch apps or send a message without touching the keyboard

## 3. Tech Stack

### Programming language
- Python 3.14

### Core libraries
- `python-telegram-bot` for Telegram bot handling
- `psutil` for process and system information
- `pyautogui` for keyboard input and screenshot fallback
- `pywinauto` for Windows UI automation and window focus
- `pygetwindow` for locating and managing windows
- `screen-brightness-control` for display brightness
- `rapidfuzz` for fuzzy matching app names and stuff

### Built-in/system tools
- Windows shell and PowerShell
- Windows clipboard APIs
- Windows process management
- Windows startup folder for auto-launch

### Support files
- `requirements.txt` for Python dependencies
- `startup.bat` for easy manual or startup-folder launching

## 4. Installation Guide

### 4.1 Prerequisites

Install these first:

- Python: [official download](https://www.python.org/downloads/)
- Git: [official download](https://git-scm.com/downloads)
- Windows 10 or Windows 11
- Telegram account
- Telegram Bot token from [BotFather](https://t.me/BotFather)

Optional, but recommended for full functionality:

- WhatsApp Desktop installed locally
- `nircmd.exe` if you want reliable volume control

### 4.2 Environment Setup

Clone the repository:

```bash
git clone <repo_url>
cd <project_folder>
```

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.3 Configuration

Set the Telegram token as an environment variable:

```powershell
setx TELEGRAM_TOKEN "123456789:your_bot_token_here"
```

Optional but strongly recommended: restrict access to your own Telegram user ID.

```powershell
setx ALLOWED_TELEGRAM_USER_ID "123456789"
```

Optional: if WhatsApp is installed in a non-standard location, point the bot to it.

```powershell
setx WHATSAPP_PATH "C:\Path\To\WhatsApp.exe"
```

Optional: if you want volume control, set the location of `nircmd.exe`.

```powershell
setx NIRCMD_PATH "C:\Tools\nircmd.exe"
```

Important:
- Close and reopen your terminal after using `setx`.
- Do not share your Telegram token publicly.

## 5. How to Run

From the project folder:

```powershell
python main.py
```

If you want to use the Windows startup helper:

```powershell
startup.bat
```

To auto-start on login:
1. Press `Win + R`
2. Type `shell:startup`
3. Copy or create a shortcut to `startup.bat` in that folder

## 6. How It Works

The bot uses a simple but strict pipeline:

1. Telegram sends a message to the bot.
2. `bot.py` receives the message.
3. `InputValidator.sanitize()` cleans the raw text.
4. `router.py` passes the text into the parser.
5. `intent_parser.py` converts text into a structured action.
6. `validator.py` checks the action name, arguments, and policy rules.
7. `actions.py` looks up the matching handler in the action registry.
8. The handler performs the Windows automation work.
9. The result is logged and returned to Telegram.

This design keeps the project predictable and safer than a free-form natural language assistant.

## 7. Project Structure

```text
main.py              # Entry point and dependency bootstrap
bot.py               # Telegram polling, routing, confirmations, replies
router.py            # Adapter from parser output to action format
intent_parser.py     # Rule-based command parsing
validator.py         # Safety checks and audit logging
actions.py           # Windows automation handlers and action registry
whatsapp_handler.py  # WhatsApp launch/chat/message automation
app_discovery.py     # Discovers installed apps and caches them
fuzzy_match.py       # Approximate matching for app names
key_sequence.py      # Ordered key-sequence parser
config.py            # Environment settings and app allowlist
startup.bat          # Windows startup helper
requirements.txt     # Python dependency list
```

## 8. Supported Commands

Examples of commands you can send to the bot:

- `open chrome`
- `open whatsapp`
- `close spotify`
- `find resume`
- `set brightness to 70`
- `type hello world`
- `press enter`
- `press ctrl+c, alt+tab, enter`
- `alarm in 5 minutes`
- `system info`
- `screenshot`
- `message John Hey! on whatsapp`
- `copy selected text`
- `paste clipboard`
- `set clipboard to hello`
- `open url https://example.com`
- `search google python telegram bot`
- `search youtube lofi music`
- `lock system`
- `sleep system`
- `shutdown system`
- `restart system`
- `sign out`
- `battery status`
- `wifi status`
- `ip address`
- `open downloads`
- `create folder notes`
- `move file report.pdf to downloads`
- `chrome new tab`
- `vscode command palette`
- `spotify next`
- `work mode`
- `study mode`
- `meeting mode`

## 9. Command Categories

### App control
- Open, close, and switch to apps
- Fuzzy app matching when you misspell a name

### Typing and keyboard automation
- Type plain text
- Press ordered shortcuts
- Use comma-separated sequences

### Messaging
- Open WhatsApp chats
- Send WhatsApp messages

### System actions
- Lock, sleep, shutdown, restart, and sign out
- Check battery, network, and IP address

### Browser actions
- Open URLs
- Search Google or YouTube

### File actions
- Find files
- Create folders
- Move files within the home directory

### Productivity actions
- Clipboard read/write
- Media controls
- Window controls
- Macros

## 10. Safety Notes

This bot can control a real laptop, so treat it like a remote admin tool.

- Set `ALLOWED_TELEGRAM_USER_ID` so only your Telegram account can use it.
- Do not publish your token in screenshots or commits.
- Be careful with `shutdown`, `restart`, `sleep`, and `move file` commands.
- The project is designed to stay inside your home directory for file operations.

## 11. Troubleshooting

### The bot exits with a Telegram token error
Make sure `TELEGRAM_TOKEN` is set correctly in your environment.

### WhatsApp commands open the app but do not message
- Make sure WhatsApp Desktop is installed and logged in.
- Confirm the contact name exists in WhatsApp.
- If needed, set `WHATSAPP_PATH`.

### Volume commands do not work
- Install `nircmd.exe`
- Set `NIRCMD_PATH`

### Screenshot fails
- Use the bot from an active Windows desktop session.
- Make sure the user session is unlocked and interactive.

### App names do not open correctly
- Try the exact app name from the help list.
- Use `open chrome` or `switch to vscode`.
- Fuzzy matching may ask you to choose from several matches.

## 12. Development Notes

- The project is intentionally rule-based instead of AI-generated at runtime.
- `ACTION_REGISTRY` is the central place where new capabilities are registered.
- `ActionGuard` is the main place to add safety checks for new actions.
- `intent_parser.py` is the main place to add new commands or phrase patterns.
- `actions.py` is where you implement the actual Windows automation behavior.

## 13. Suggested Next Improvements

- Split `actions.py` into smaller modules.
- Replace runtime dependency auto-installation with a one-time setup script.
- Move secrets out of `config.py` and require environment variables only.
- Add automated tests for parser, validator, and key-sequence parsing.
- Add a proper PDF export step for documentation builds.

## 14. License

No license file is currently included. Add one before publishing the project publicly.
