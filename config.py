import os
from pathlib import Path

# Configuration is read from environment variables:
#   TELEGRAM_TOKEN=123456789:your_bot_token_here
#   ALLOWED_TELEGRAM_USER_ID=123456789
#   NIRCMD_PATH=C:\path\to\nircmd.exe


def _read_optional_int(env_name: str) -> int | None:
    raw_value = os.getenv(env_name, "").strip()
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        return None


def _get_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA", "").strip()
    if local_app_data:
        data_dir = Path(local_app_data) / "TelegramLocalAssistant"
    else:
        data_dir = Path.home() / ".telegram-local-assistant"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


DATA_DIR: Path = _get_data_dir()
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "").strip()
FUZZY_MATCH_THRESHOLD: float = 0.6
MAX_FUZZY_RESULTS: int = 3
WHATSAPP_PATH: str = os.getenv("WHATSAPP_PATH", "").strip()
ALLOWED_ACTION_CATEGORIES: list[str] = [
    "app",
    "media",
    "system",
    "message",
    "power",
    "clipboard",
    "browser",
    "window",
    "filesystem",
    "status",
    "macro",
]

ALLOWED_TELEGRAM_USER_ID: int | None = _read_optional_int("ALLOWED_TELEGRAM_USER_ID")

HOME_DIR: Path = Path.home()
LOG_FILE: str = str(DATA_DIR / "assistant.log")
APPS_CACHE_FILE: Path = DATA_DIR / "apps_cache.json"
NIRCMD_PATH: str = os.getenv("NIRCMD_PATH", "nircmd.exe").strip() or "nircmd.exe"

DEFAULT_BROWSER: str = os.getenv("DEFAULT_BROWSER", "chrome").strip().lower() or "chrome"

ALLOWED_APPS: dict[str, str] = {
    "chrome":      "chrome.exe",
    "notepad":     "notepad.exe",
    "calculator":  "calc.exe",
    "explorer":    "explorer.exe",
    "cmd":         "cmd.exe",
    "word":        "WINWORD.EXE",
    "excel":       "EXCEL.EXE",
    "vscode":      "Code.exe",
    "code":        "Code.exe",
    "spotify":     "Spotify.exe",
    "vlc":         "vlc.exe",
    "discord":     "Discord.exe",
    "whatsapp":    "WhatsApp.exe",
}

ALARM_SOUND: str = "alarm.wav"  # place in project root
