"""
Helpers for parsing and validating ordered keyboard actions.
"""

import re
from typing import Any

import pyautogui  # type: ignore

_STEP_SPLIT_RE = re.compile(r"\s*(?:,|\bthen\b)\s*", re.IGNORECASE)
_COUNT_RE = re.compile(r"^(?P<body>.+?)(?:\s*(?:x|\*)\s*(?P<count>\d{1,2}))?$", re.IGNORECASE)

_ALIASES = {
    "backspace": "backspace",
    "bksp": "backspace",
    "break": "pause",
    "caps": "capslock",
    "capslock": "capslock",
    "ctrl": "ctrl",
    "control": "ctrl",
    "del": "delete",
    "delete": "delete",
    "down": "down",
    "end": "end",
    "enter": "enter",
    "esc": "esc",
    "escape": "esc",
    "home": "home",
    "ins": "insert",
    "insert": "insert",
    "left": "left",
    "menu": "apps",
    "option": "alt",
    "pagedown": "pagedown",
    "page down": "pagedown",
    "pageup": "pageup",
    "page up": "pageup",
    "pgdn": "pagedown",
    "pgup": "pageup",
    "printscreen": "printscreen",
    "prtsc": "printscreen",
    "return": "enter",
    "right": "right",
    "shift": "shift",
    "space": "space",
    "spacebar": "space",
    "tab": "tab",
    "up": "up",
    "win": "win",
    "windows": "win",
}

_KEY_NAMES = set(pyautogui.KEYBOARD_KEYS)


def _normalize_token(token: str) -> str | None:
    value = " ".join(token.strip().lower().split())
    if not value:
        return None
    value = _ALIASES.get(value, value)
    return value if value in _KEY_NAMES else None


def _split_combo(text: str) -> list[str]:
    compact = re.sub(r"\s*\+\s*", "+", text.strip().lower())
    if "+" in compact:
        return [part for part in compact.split("+") if part]

    normalized = " ".join(compact.split())
    if normalized in _ALIASES:
        return [normalized]

    words = normalized.split()
    if len(words) > 1:
        normalized_words = [_normalize_token(word) for word in words]
        if all(normalized_words):
            return words
    return [normalized]


def parse_key_sequence(raw: str) -> tuple[list[dict[str, Any]] | None, str | None]:
    """Parse raw key instructions into executable steps."""
    text = raw.strip()
    if not text:
        return None, "No key sequence provided."
    if len(text) > 200:
        return None, "Key sequence is too long."

    parts = [part.strip() for part in _STEP_SPLIT_RE.split(text) if part.strip()]
    if not parts:
        return None, "No key sequence provided."
    if len(parts) > 20:
        return None, "Too many key steps (max 20)."

    steps: list[dict[str, Any]] = []

    for part in parts:
        lowered = part.lower()
        if lowered.startswith("text:") or lowered.startswith("type:"):
            prefix, payload = part.split(":", 1)
            del prefix
            payload = payload.strip()
            if not payload:
                return None, "Text step cannot be empty."
            steps.append(
                {
                    "kind": "write",
                    "text": payload,
                    "label": f"text:{payload}",
                }
            )
            continue

        match = _COUNT_RE.match(part)
        if not match:
            return None, f"Invalid key step: '{part}'"

        count = int(match.group("count") or "1")
        if count < 1 or count > 20:
            return None, f"Repeat count out of range in '{part}'"

        raw_keys = _split_combo(match.group("body"))
        keys: list[str] = []
        labels: list[str] = []

        for token in raw_keys:
            normalized = _normalize_token(token)
            if normalized is None:
                return None, f"Unsupported key '{token}'"
            keys.append(normalized)
            labels.append(normalized)

        if len(keys) > 5:
            return None, f"Too many keys in combination '{part}'"

        steps.append(
            {
                "kind": "keys",
                "keys": keys,
                "count": count,
                "label": "+".join(labels),
            }
        )

    return steps, None
