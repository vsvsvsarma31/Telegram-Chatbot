"""
Pure rule-based intent parser for the local assistant.
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_OPEN_DOWNLOADS_RE = re.compile(r"^(?:open\s+downloads|downloads)$", re.IGNORECASE)
_OPEN_URL_RE = re.compile(
    r"^(?:open\s+url|go\s+to|browse)\s+(https?://\S+|www\.\S+)$",
    re.IGNORECASE,
)
_OPEN_SITE_RE = re.compile(r"^(?:open\s+site|site)\s+(.+)$", re.IGNORECASE)
_SEARCH_GOOGLE_RE = re.compile(r"^(?:search\s+google|google)\s+(.+)$", re.IGNORECASE)
_SEARCH_YOUTUBE_RE = re.compile(r"^(?:search\s+youtube|youtube)\s+(.+)$", re.IGNORECASE)
_CREATE_FOLDER_RE = re.compile(
    r"^(?:create|make)\s+folder\s+(.+?)(?:\s+in\s+(.+))?$",
    re.IGNORECASE,
)
_MOVE_FILE_RE = re.compile(
    r"^(?:move|relocate)\s+file\s+(.+?)\s+to\s+(.+)$",
    re.IGNORECASE,
)
_SET_CLIPBOARD_RE = re.compile(
    r"^(?:set\s+clipboard(?:\s+to)?|clipboard\s+set)\s+(.+)$",
    re.IGNORECASE,
)
_COPY_SELECTED_RE = re.compile(
    r"^(?:copy\s+selected(?:\s+text)?|copy\s+selection)$",
    re.IGNORECASE,
)
_PASTE_CLIPBOARD_RE = re.compile(
    r"^(?:paste(?:\s+clipboard)?)$",
    re.IGNORECASE,
)
_SHOW_CLIPBOARD_RE = re.compile(
    r"^(?:show\s+clipboard|clipboard\s+show|get\s+clipboard)$",
    re.IGNORECASE,
)
_LOCK_RE = re.compile(r"^(?:lock(?:\s+system|\s+laptop|\s+pc)?)$", re.IGNORECASE)
_SLEEP_RE = re.compile(r"^(?:sleep(?:\s+system|\s+laptop|\s+pc)?)$", re.IGNORECASE)
_SHUTDOWN_RE = re.compile(r"^(?:shutdown(?:\s+system|\s+laptop|\s+pc)?)$", re.IGNORECASE)
_RESTART_RE = re.compile(r"^(?:restart(?:\s+system|\s+laptop|\s+pc)?)$", re.IGNORECASE)
_SIGNOUT_RE = re.compile(
    r"^(?:sign\s*out|log\s*out|logout|signout)$",
    re.IGNORECASE,
)
_BATTERY_RE = re.compile(
    r"^(?:battery(?:\s+status)?|battery\s+percent)$",
    re.IGNORECASE,
)
_NETWORK_RE = re.compile(
    r"^(?:network(?:\s+status)?|wifi(?:\s+status)?|wi[- ]?fi(?:\s+status)?)$",
    re.IGNORECASE,
)
_IP_RE = re.compile(r"^(?:ip(?:\s+address)?|local\s+ip)$", re.IGNORECASE)
_STATUS_RE = re.compile(
    r"^(?:device\s+status|battery\s+and\s+network|network\s+and\s+battery)$",
    re.IGNORECASE,
)
_MEDIA_PLAY_RE = re.compile(
    r"^(?:play\s*pause|play/pause|toggle\s+playback|media\s+play|media\s+pause|pause\s+music|play\s+music)$",
    re.IGNORECASE,
)
_MEDIA_NEXT_RE = re.compile(
    r"^(?:next\s+track|skip\s+track|media\s+next)$",
    re.IGNORECASE,
)
_MEDIA_PREV_RE = re.compile(
    r"^(?:previous\s+track|prev(?:ious)?\s+track|media\s+previous)$",
    re.IGNORECASE,
)
_WINDOW_MINIMIZE_RE = re.compile(
    r"^(?:minimize(?:\s+window)?|minimise(?:\s+window)?)$",
    re.IGNORECASE,
)
_WINDOW_MAXIMIZE_RE = re.compile(
    r"^(?:maximize(?:\s+window)?|maximise(?:\s+window)?)$",
    re.IGNORECASE,
)
_WINDOW_ALT_TAB_RE = re.compile(
    r"^(?:alt\s*tab|switch\s+window|next\s+window)$",
    re.IGNORECASE,
)
_SWITCH_APP_RE = re.compile(r"^(?:switch\s+to|focus)\s+(.+)$", re.IGNORECASE)
_OPEN_CHAT_RE = re.compile(
    r"^(?:open|show|focus)\s+(?P<contact>.+?)\s+chat(?:\s+on\s+(?P<platform>\S+))?$",
    re.IGNORECASE,
)
_OPEN_CHAT_WITH_RE = re.compile(
    r"^(?:open|show|focus)\s+chat(?:\s+with)?\s+(?P<contact>.+?)(?:\s+on\s+(?P<platform>\S+))?$",
    re.IGNORECASE,
)
_MESSAGE_RE = re.compile(
    r"^(?:message|msg|send(?:\s+a?\s*message)?)\s+"
    r"(?P<contact>\S+)\s+"
    r"(?P<text>.+?)\s+"
    r"on\s+(?P<platform>\S+)$",
    re.IGNORECASE,
)
_WA_SHORTHAND_RE = re.compile(
    r"^(?:whatsapp|wa)\s+(?P<contact>\S+)\s+(?P<text>.+)$",
    re.IGNORECASE,
)
_SCREENSHOT_RE = re.compile(
    r"^(?:screenshot|take\s+screenshot|snap|capture\s+screen|send\s+screenshot)$",
    re.IGNORECASE,
)
_OPEN_RE = re.compile(r"^(?:open|launch|start|run)\s+(.+)$", re.IGNORECASE)
_CLOSE_RE = re.compile(r"^(?:close|quit|exit|kill|stop)\s+(.+)$", re.IGNORECASE)
_FIND_RE = re.compile(r"^(?:find|locate|look\s+for)\s+(.+)$", re.IGNORECASE)
_VOLUME_SET_RE = re.compile(
    r"^(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:%)?$",
    re.IGNORECASE,
)
_VOLUME_UP_RE = re.compile(r"^volume\s+up$", re.IGNORECASE)
_VOLUME_DOWN_RE = re.compile(r"^volume\s+down$", re.IGNORECASE)
_MUTE_RE = re.compile(r"^(?:mute|unmute|toggle\s+mute)$", re.IGNORECASE)
_BRIGHTNESS_SET_RE = re.compile(
    r"^(?:set\s+)?brightness\s+(?:to\s+)?(\d{1,3})(?:%)?$",
    re.IGNORECASE,
)
_BRIGHTNESS_UP_RE = re.compile(r"^(?:brightness\s+up|brighter)$", re.IGNORECASE)
_BRIGHTNESS_DOWN_RE = re.compile(
    r"^(?:brightness\s+down|dimmer|dim\s+screen)$",
    re.IGNORECASE,
)
_TYPE_RE = re.compile(r"^type\s+(.+)$", re.IGNORECASE)
_PRESS_RE = re.compile(r"^(?:press|key|keys|hotkey|shortcut)\s+(.+)$", re.IGNORECASE)
_ALARM_RE = re.compile(
    r"^alarm\s+(?:in\s+)?(\d+)\s*(second|minute|hour|day)s?$",
    re.IGNORECASE,
)
_SYSINFO_RE = re.compile(
    r"^(?:system\s+info|sysinfo|cpu|ram|disk|specs)$",
    re.IGNORECASE,
)
_MACRO_RE = re.compile(r"^(work|study|meeting)\s+mode$", re.IGNORECASE)
_APP_SHORTCUT_RE = re.compile(
    r"^(?P<app>chrome|spotify|whatsapp|vs\s*code|vscode|code)\s+(?P<command>.+)$",
    re.IGNORECASE,
)


def _normalize_app_name(value: str) -> str:
    lowered = " ".join(value.strip().lower().split())
    if lowered in {"vs code", "code"}:
        return "vscode"
    if lowered in {"wa", "whatsapp desktop"}:
        return "whatsapp"
    return lowered


def parse(text: str) -> dict[str, Any] | None:
    """Parse *text* into a structured intent dict, or return None."""
    text = text.strip()
    if not text:
        return None

    match = _SET_CLIPBOARD_RE.match(text)
    if match:
        return {"action": "set_clipboard", "text": match.group(1).strip()}

    if _COPY_SELECTED_RE.match(text):
        return {"action": "copy_selected_text"}

    if _PASTE_CLIPBOARD_RE.match(text):
        return {"action": "paste_clipboard"}

    if _SHOW_CLIPBOARD_RE.match(text):
        return {"action": "show_clipboard"}

    if _OPEN_DOWNLOADS_RE.match(text):
        return {"action": "open_downloads"}

    match = _OPEN_URL_RE.match(text)
    if match:
        return {"action": "open_url", "url": match.group(1).strip()}

    match = _OPEN_SITE_RE.match(text)
    if match:
        return {"action": "open_site", "site": match.group(1).strip()}

    match = _SEARCH_YOUTUBE_RE.match(text)
    if match:
        return {"action": "search_youtube", "query": match.group(1).strip()}

    match = _SEARCH_GOOGLE_RE.match(text)
    if match:
        return {"action": "search_google", "query": match.group(1).strip()}

    match = _CREATE_FOLDER_RE.match(text)
    if match:
        return {
            "action": "create_folder",
            "name": match.group(1).strip(),
            "location": (match.group(2) or "").strip(),
        }

    match = _MOVE_FILE_RE.match(text)
    if match:
        return {
            "action": "move_file",
            "source": match.group(1).strip(),
            "destination": match.group(2).strip(),
        }

    if _LOCK_RE.match(text):
        return {"action": "lock_system"}

    if _SLEEP_RE.match(text):
        return {"action": "sleep_system"}

    if _SHUTDOWN_RE.match(text):
        return {"action": "shutdown_system"}

    if _RESTART_RE.match(text):
        return {"action": "restart_system"}

    if _SIGNOUT_RE.match(text):
        return {"action": "signout_system"}

    if _STATUS_RE.match(text):
        return {"action": "device_status"}

    if _BATTERY_RE.match(text):
        return {"action": "battery_status"}

    if _NETWORK_RE.match(text):
        return {"action": "network_status"}

    if _IP_RE.match(text):
        return {"action": "ip_address"}

    if _MEDIA_PLAY_RE.match(text):
        return {"action": "media_play_pause"}

    if _MEDIA_NEXT_RE.match(text):
        return {"action": "media_next"}

    if _MEDIA_PREV_RE.match(text):
        return {"action": "media_previous"}

    if _WINDOW_MINIMIZE_RE.match(text):
        return {"action": "window_minimize"}

    if _WINDOW_MAXIMIZE_RE.match(text):
        return {"action": "window_maximize"}

    if _WINDOW_ALT_TAB_RE.match(text):
        return {"action": "window_alt_tab"}

    match = _SWITCH_APP_RE.match(text)
    if match:
        return {"action": "switch_app", "app": _normalize_app_name(match.group(1))}

    match = _OPEN_CHAT_RE.match(text)
    if match:
        return {
            "action": "open_chat",
            "contact": match.group("contact").strip(),
            "platform": (match.group("platform") or "whatsapp").lower(),
        }

    match = _OPEN_CHAT_WITH_RE.match(text)
    if match:
        return {
            "action": "open_chat",
            "contact": match.group("contact").strip(),
            "platform": (match.group("platform") or "whatsapp").lower(),
        }

    match = _MESSAGE_RE.match(text)
    if match:
        return {
            "action": "message",
            "contact": match.group("contact"),
            "text": match.group("text").strip(),
            "platform": match.group("platform").lower(),
        }

    match = _WA_SHORTHAND_RE.match(text)
    if match:
        return {
            "action": "message",
            "contact": match.group("contact"),
            "text": match.group("text").strip(),
            "platform": "whatsapp",
        }

    if _SCREENSHOT_RE.match(text):
        return {"action": "screenshot"}

    match = _APP_SHORTCUT_RE.match(text)
    if match:
        return {
            "action": "app_shortcut",
            "app": _normalize_app_name(match.group("app")),
            "command": " ".join(match.group("command").strip().lower().split()),
        }

    match = _OPEN_RE.match(text)
    if match:
        return {"action": "open", "target": match.group(1).strip()}

    match = _CLOSE_RE.match(text)
    if match:
        return {"action": "close", "target": match.group(1).strip()}

    match = _FIND_RE.match(text)
    if match:
        return {"action": "find", "name": match.group(1).strip()}

    match = _VOLUME_SET_RE.match(text)
    if match:
        return {"action": "set_volume", "level": int(match.group(1))}
    if _VOLUME_UP_RE.match(text):
        return {"action": "volume_up"}
    if _VOLUME_DOWN_RE.match(text):
        return {"action": "volume_down"}
    if _MUTE_RE.match(text):
        return {"action": "mute"}

    match = _BRIGHTNESS_SET_RE.match(text)
    if match:
        return {"action": "set_brightness", "level": int(match.group(1))}
    if _BRIGHTNESS_UP_RE.match(text):
        return {"action": "brightness_up"}
    if _BRIGHTNESS_DOWN_RE.match(text):
        return {"action": "brightness_down"}

    match = _TYPE_RE.match(text)
    if match:
        return {"action": "type_text", "text": match.group(1).strip()}

    match = _PRESS_RE.match(text)
    if match:
        return {"action": "press_keys", "sequence": match.group(1).strip()}

    match = _ALARM_RE.match(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        multiplier = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}[unit]
        return {"action": "set_alarm", "seconds": amount * multiplier}

    if _SYSINFO_RE.match(text):
        return {"action": "system_info"}

    match = _MACRO_RE.match(text)
    if match:
        return {"action": "run_macro", "name": f"{match.group(1).lower()} mode"}

    logger.debug("intent_parser: no pattern matched for %r", text)
    return None
