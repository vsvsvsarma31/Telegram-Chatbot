"""
validator.py — Safety, validation, and logging layer for the local assistant.
"""

import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Any

from actions import ACTION_REGISTRY  # type: ignore
from config import ALLOWED_ACTION_CATEGORIES, LOG_FILE  # type: ignore
from key_sequence import parse_key_sequence  # type: ignore

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")
_APP_NAME_RE = re.compile(r"^[a-zA-Z0-9 ._()'&+\-]+$")
_CONTACT_RE = re.compile(r"^[a-zA-Z0-9 ._()'+\-]+$")
_FOLDER_NAME_RE = re.compile(r"^[^<>:\"/\\|?*]{1,80}$")

_ACTION_CATEGORY_MAP: dict[str, str] = {
    "open_app": "app",
    "switch_app": "window",
    "close_app": "app",
    "find_file": "system",
    "system_info": "system",
    "set_volume": "media",
    "volume_up": "media",
    "volume_down": "media",
    "mute": "media",
    "set_brightness": "media",
    "brightness_up": "media",
    "brightness_down": "media",
    "type_text": "system",
    "press_keys": "system",
    "media_play_pause": "media",
    "media_next": "media",
    "media_previous": "media",
    "set_alarm": "system",
    "screenshot": "system",
    "message": "message",
    "open_chat": "message",
    "lock_system": "power",
    "sleep_system": "power",
    "shutdown_system": "power",
    "restart_system": "power",
    "signout_system": "power",
    "copy_selected_text": "clipboard",
    "paste_clipboard": "clipboard",
    "set_clipboard": "clipboard",
    "show_clipboard": "clipboard",
    "open_url": "browser",
    "open_site": "browser",
    "search_google": "browser",
    "search_youtube": "browser",
    "window_minimize": "window",
    "window_maximize": "window",
    "window_alt_tab": "window",
    "battery_status": "status",
    "network_status": "status",
    "ip_address": "status",
    "device_status": "status",
    "open_downloads": "filesystem",
    "create_folder": "filesystem",
    "move_file": "filesystem",
    "app_shortcut": "app",
    "run_macro": "macro",
    "unknown": "system",
}


# ---------------------------------------------------------------------------
# 1. InputValidator
# ---------------------------------------------------------------------------

class InputValidator:
    """Sanitise and validate raw user input and individual fields."""

    @staticmethod
    def sanitize(text: str) -> str:
        """Trim input, collapse extra spaces, and drop control characters."""
        text = _CONTROL_CHARS_RE.sub("", text)
        text = " ".join(text.strip().split())
        return text[:300]

    @staticmethod
    def validate_app_name(name: str) -> tuple[bool, str]:
        """Allow common Windows app-name characters, max 60 chars."""
        if not name:
            return False, "App name is empty."
        if len(name) > 60:
            return False, "App name too long (max 60 chars)."
        if not _APP_NAME_RE.match(name):
            return False, "App name contains invalid characters."
        return True, "ok"

    @staticmethod
    def validate_contact(name: str) -> tuple[bool, str]:
        """Allow common contact-name and phone-number characters, max 80 chars."""
        if not name:
            return False, "Contact name is empty."
        if len(name) > 80:
            return False, "Contact name too long (max 80 chars)."
        if not _CONTACT_RE.match(name):
            return False, "Contact name contains invalid characters."
        return True, "ok"

    @staticmethod
    def validate_message_text(text: str) -> tuple[bool, str]:
        """Max 200 chars, no URLs."""
        if not text:
            return False, "Message text is empty."
        if len(text) > 200:
            return False, "Message too long (max 200 chars)."
        if _URL_RE.search(text):
            return False, "URLs are not allowed in messages."
        return True, "ok"

    @staticmethod
    def validate_simple_text(text: str, max_length: int = 200) -> tuple[bool, str]:
        if not text.strip():
            return False, "Text is empty."
        if len(text) > max_length:
            return False, f"Text is too long (max {max_length} characters)."
        return True, "ok"

    @staticmethod
    def validate_folder_name(name: str) -> tuple[bool, str]:
        if not name.strip():
            return False, "Folder name is empty."
        if not _FOLDER_NAME_RE.match(name.strip()):
            return False, "Folder name contains invalid characters."
        return True, "ok"


# ---------------------------------------------------------------------------
# 2. ActionGuard
# ---------------------------------------------------------------------------

class ActionGuard:
    """Gate-checks an action dict before execution."""

    _ALLOWED_PLATFORMS = ("whatsapp", "wa")

    @staticmethod
    def check(action_dict: dict[str, Any]) -> tuple[bool, str]:
        """Return ``(True, 'ok')`` if the action is allowed, else ``(False, reason)``."""
        action_id: str = action_dict.get("action", "")

        # ── Whitelist check ──────────────────────────────────────────────
        if action_id not in ACTION_REGISTRY:
            return False, f"Unknown action '{action_id}'."

        # ── Category check ───────────────────────────────────────────────
        category = _ACTION_CATEGORY_MAP.get(action_id)
        if category and category not in ALLOWED_ACTION_CATEGORIES:
            return False, f"Action category '{category}' is disabled."

        # ── Per-action param validation ──────────────────────────────────
        if action_id in ("open_app", "close_app", "switch_app"):
            app = str(action_dict.get("app", action_dict.get("target", "")))
            ok, reason = InputValidator.validate_app_name(app)
            if not ok:
                return False, reason

        if action_id == "find_file":
            name = str(action_dict.get("name", ""))
            if len(name.strip()) < 2:
                return False, "Search text is too short."
            banned = ("..", "\\", "/", ":", '"', "<", ">", "|", "*", "?")
            for value in banned:
                if value in name:
                    return False, f"Invalid character in file search: '{value}'"

        if action_id in ("set_volume", "set_brightness"):
            level = action_dict.get("level")
            if not isinstance(level, (int, float)):
                return False, "Level must be a number."
            if not (0 <= float(level) <= 100):
                return False, "Level must be between 0 and 100."

        if action_id == "type_text":
            text = str(action_dict.get("text", ""))
            if not text.strip():
                return False, "No text provided."
            if len(text) > 500:
                return False, "Text is too long (max 500 characters)."

        if action_id == "press_keys":
            sequence = str(action_dict.get("sequence", ""))
            parsed, error = parse_key_sequence(sequence)
            if error:
                return False, error
            if not parsed:
                return False, "No key steps were parsed."

        if action_id in ("open_url", "open_site"):
            url_key = "url" if action_id == "open_url" else "site"
            value = str(action_dict.get(url_key, ""))
            ok, reason = InputValidator.validate_simple_text(value, 250)
            if not ok:
                return False, reason

        if action_id in ("search_google", "search_youtube"):
            query = str(action_dict.get("query", ""))
            ok, reason = InputValidator.validate_simple_text(query, 200)
            if not ok:
                return False, reason

        if action_id == "set_clipboard":
            text = str(action_dict.get("text", ""))
            ok, reason = InputValidator.validate_simple_text(text, 1000)
            if not ok:
                return False, reason

        if action_id == "set_alarm":
            seconds = action_dict.get("seconds")
            if not isinstance(seconds, int):
                return False, "Alarm time must be a whole number of seconds."
            if not (1 <= seconds <= 86400):
                return False, "Alarm time must be between 1 second and 24 hours."

        if action_id == "create_folder":
            name = str(action_dict.get("name", ""))
            ok, reason = InputValidator.validate_folder_name(name)
            if not ok:
                return False, reason
            location = str(action_dict.get("location", ""))
            if location:
                ok, reason = InputValidator.validate_simple_text(location, 80)
                if not ok:
                    return False, reason

        if action_id == "move_file":
            source = str(action_dict.get("source", ""))
            destination = str(action_dict.get("destination", ""))
            ok, reason = InputValidator.validate_simple_text(source, 260)
            if not ok:
                return False, "Source path is invalid."
            ok, reason = InputValidator.validate_simple_text(destination, 260)
            if not ok:
                return False, "Destination path is invalid."

        if action_id == "app_shortcut":
            app = str(action_dict.get("app", ""))
            command = str(action_dict.get("command", ""))
            ok, reason = InputValidator.validate_app_name(app)
            if not ok:
                return False, reason
            ok, reason = InputValidator.validate_simple_text(command, 80)
            if not ok:
                return False, reason

        if action_id == "run_macro":
            name = str(action_dict.get("name", ""))
            if name not in {"work mode", "study mode", "meeting mode"}:
                return False, "Unknown macro."

        if action_id == "message":
            contact = action_dict.get("contact", "")
            text = action_dict.get("text", "")
            platform = action_dict.get("platform", "").lower()

            ok, reason = InputValidator.validate_contact(contact)
            if not ok:
                return False, reason

            ok, reason = InputValidator.validate_message_text(text)
            if not ok:
                return False, reason

            if platform not in ActionGuard._ALLOWED_PLATFORMS:
                return False, f"Platform '{platform}' is not supported. Allowed: {list(ActionGuard._ALLOWED_PLATFORMS)}"

        if action_id == "open_chat":
            contact = action_dict.get("contact", "")
            platform = action_dict.get("platform", "").lower()

            ok, reason = InputValidator.validate_contact(contact)
            if not ok:
                return False, reason

            if platform not in ActionGuard._ALLOWED_PLATFORMS:
                return False, f"Platform '{platform}' is not supported. Allowed: {list(ActionGuard._ALLOWED_PLATFORMS)}"

        return True, "ok"


# ---------------------------------------------------------------------------
# 3. Logger
# ---------------------------------------------------------------------------

class ActionLogger:
    """Append-only action logger that rotates at 5 MB."""

    _handler: RotatingFileHandler | None = None
    _action_logger: logging.Logger | None = None

    @classmethod
    def _ensure_logger(cls) -> logging.Logger:
        if cls._action_logger is None:
            action_log = logging.getLogger("action_audit")
            action_log.setLevel(logging.INFO)
            action_log.propagate = False
            handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=5 * 1024 * 1024,  # 5 MB
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            action_log.addHandler(handler)
            cls._handler = handler
            cls._action_logger = action_log
        return cls._action_logger  # type: ignore

    @classmethod
    def log_action(
        cls,
        user_id: int | str,
        action_dict: dict[str, Any],
        result: str,
    ) -> None:
        """Write: timestamp | user_id | action | params | result."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action = action_dict.get("action", "unknown")
        params = {k: v for k, v in action_dict.items() if k != "action"}
        line = f"{ts} | {user_id} | {action} | {params} | {result}"
        cls._ensure_logger().info(line)
