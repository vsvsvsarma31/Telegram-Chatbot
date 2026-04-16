import ctypes
import logging
import os
import pathlib
import shutil
import socket
import subprocess
import threading
import time
import urllib.parse
import webbrowser
import winsound
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Callable

import psutil  # type: ignore
import pyautogui  # type: ignore
import screen_brightness_control as sbc  # type: ignore

from app_discovery import discover_apps  # type: ignore
from config import ALARM_SOUND, ALLOWED_APPS, DEFAULT_BROWSER, HOME_DIR, NIRCMD_PATH  # type: ignore
from fuzzy_match import fuzzy_find  # type: ignore
from key_sequence import parse_key_sequence  # type: ignore
from whatsapp_handler import (  # type: ignore
    has_whatsapp_support,
    open_whatsapp_app,
    open_whatsapp_chat,
    send_whatsapp_message,
)

_pending_fuzzy: dict[int, list[dict[str, object]]] = {}

logger = logging.getLogger(__name__)

_KEYEVENTF_KEYUP = 0x0002
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT_TRACK = 0xB0
_VK_MEDIA_PREV_TRACK = 0xB1

_SPECIAL_FOLDERS = {
    "desktop": Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "downloads": Path.home() / "Downloads",
    "music": Path.home() / "Music",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "home": HOME_DIR,
}

_WINDOW_APP_ALIASES = {
    "chrome": ["chrome"],
    "spotify": ["spotify"],
    "whatsapp": ["whatsapp"],
    "vscode": ["visual studio code", "vscode", "code"],
    "code": ["visual studio code", "vscode", "code"],
    "discord": ["discord"],
    "notepad": ["notepad"],
    "explorer": ["file explorer", "explorer"],
}

_APP_SHORTCUTS: dict[str, dict[str, tuple[str, ...] | str]] = {
    "chrome": {
        "new tab": ("ctrl", "t"),
        "close tab": ("ctrl", "w"),
        "reopen tab": ("ctrl", "shift", "t"),
        "next tab": ("ctrl", "tab"),
        "previous tab": ("ctrl", "shift", "tab"),
        "reload": ("ctrl", "r"),
        "focus address": ("ctrl", "l"),
    },
    "vscode": {
        "command palette": ("ctrl", "shift", "p"),
        "terminal": ("ctrl", "`"),
        "format": ("shift", "alt", "f"),
        "format document": ("shift", "alt", "f"),
    },
    "spotify": {
        "play": "media_play_pause",
        "pause": "media_play_pause",
        "next": "media_next",
        "previous": "media_previous",
    },
    "whatsapp": {
        "search": ("ctrl", "f"),
    },
}

_ACTION_EXAMPLES: dict[str, list[str]] = {
    "open_app": ["open chrome", "open whatsapp"],
    "open_chat": ["open Alex chat"],
    "switch_app": ["switch to vscode"],
    "close_app": ["close spotify"],
    "find_file": ["find resume"],
    "set_volume": ["set volume to 50", "volume up / volume down / mute"],
    "set_brightness": ["set brightness to 70", "brightness up / brightness down"],
    "type_text": ["type hello world"],
    "press_keys": ["press enter", "press ctrl+c, alt+tab, enter"],
    "media_play_pause": ["play pause", "next track / previous track"],
    "set_alarm": ["alarm in 5 minutes"],
    "system_info": ["system info"],
    "screenshot": ["screenshot"],
    "message": ["message John Hey! on whatsapp"],
    "copy_selected_text": ["copy selected text", "paste clipboard", "set clipboard to hello"],
    "open_url": ["open url https://example.com"],
    "search_google": ["search google python telegram bot"],
    "search_youtube": ["search youtube lofi music"],
    "lock_system": ["lock system", "sleep system"],
    "shutdown_system": ["shutdown system", "restart system", "sign out"],
    "battery_status": ["battery status", "wifi status", "ip address"],
    "open_downloads": ["open downloads"],
    "create_folder": ["create folder notes", "move file report.pdf to downloads"],
    "app_shortcut": ["chrome new tab", "vscode command palette", "spotify next"],
    "run_macro": ["work mode", "study mode", "meeting mode"],
}


@dataclass
class ActionResult:
    message: str
    photo_path: str | None = None


@dataclass
class Action:
    id: str
    description: str
    requires_confirmation: bool
    handler: Callable[[dict], str | ActionResult]


@lru_cache(maxsize=1)
def _nircmd_available() -> bool:
    if os.path.isabs(NIRCMD_PATH) or os.path.sep in NIRCMD_PATH:
        return Path(NIRCMD_PATH).exists()
    return shutil.which(NIRCMD_PATH) is not None


@lru_cache(maxsize=1)
def _brightness_available() -> bool:
    try:
        levels = sbc.get_brightness()
        return bool(levels)
    except Exception:
        return False


def is_action_available(action_id: str) -> bool:
    """Return True if the action is usable on this machine."""
    if action_id in {"set_volume", "volume_up", "volume_down", "mute"}:
        return _nircmd_available()
    if action_id in {"set_brightness", "brightness_up", "brightness_down"}:
        return _brightness_available()
    if action_id in {"message", "open_chat"}:
        return has_whatsapp_support()
    return True


def get_supported_actions() -> list[Action]:
    """Return actions that are both registered and available here."""
    return [
        action
        for action in ACTION_REGISTRY.values()
        if action.id != "unknown" and is_action_available(action.id)
    ]


def get_supported_examples() -> list[str]:
    """Return example commands filtered by available features."""
    examples: list[str] = []
    for action_id, lines in _ACTION_EXAMPLES.items():
        if not is_action_available(action_id):
            continue
        examples.extend(lines)
    if has_whatsapp_support() and "open whatsapp" not in examples:
        examples.insert(1, "open whatsapp")
    return examples


def _success(message: str, photo_path: str | None = None) -> ActionResult:
    return ActionResult(message=message, photo_path=photo_path)


def _normalize_app_name(value: str) -> str:
    lowered = " ".join(value.strip().lower().split())
    if lowered in {"code", "vs code"}:
        return "vscode"
    if lowered in {"wa", "whatsapp desktop"}:
        return "whatsapp"
    return lowered


def _tap_virtual_key(vk_code: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(vk_code, 0, _KEYEVENTF_KEYUP, 0)


def _run_powershell(script: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )


def _get_clipboard_text() -> str:
    result = _run_powershell("Get-Clipboard -Raw")
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _set_clipboard_text(text: str) -> bool:
    result = _run_powershell("Set-Clipboard -Value ([Console]::In.ReadToEnd())", input_text=text)
    return result.returncode == 0


def _powershell_quote(text: str) -> str:
    return text.replace("'", "''")


def _resolve_special_folder(label: str) -> Path | None:
    normalized = " ".join(label.strip().lower().split())
    alias_map = {
        "download": "downloads",
        "downloads": "downloads",
        "desktop": "desktop",
        "document": "documents",
        "documents": "documents",
        "picture": "pictures",
        "pictures": "pictures",
        "music": "music",
        "video": "videos",
        "videos": "videos",
        "home": "home",
    }
    key = alias_map.get(normalized)
    if key is None:
        return None
    return _SPECIAL_FOLDERS[key]


def _path_within_home(path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(HOME_DIR.resolve())
    except Exception:
        return False


def _resolve_source_file(source: str) -> Path | None:
    raw = source.strip()
    direct = Path(raw).expanduser()
    if direct.exists() and direct.is_file() and _path_within_home(direct):
        return direct

    candidate = (HOME_DIR / raw).expanduser()
    if candidate.exists() and candidate.is_file():
        return candidate

    for path in HOME_DIR.rglob("*"):
        try:
            if path.is_file() and path.name.lower() == raw.lower():
                return path
        except (PermissionError, OSError):
            continue

    for path in HOME_DIR.rglob(f"*{raw}*"):
        try:
            if path.is_file():
                return path
        except (PermissionError, OSError):
            continue
    return None


def _resolve_destination_folder(destination: str) -> Path | None:
    special = _resolve_special_folder(destination)
    if special is not None:
        return special

    candidate = Path(destination).expanduser()
    if not candidate.is_absolute():
        candidate = HOME_DIR / candidate
    try:
        candidate = candidate.resolve()
    except Exception:
        return None
    if not _path_within_home(candidate):
        return None
    return candidate


def _import_window_module():
    try:
        import pygetwindow as gw  # type: ignore

        return gw
    except Exception:
        return None


def _activate_window(window) -> bool:
    try:
        if getattr(window, "isMinimized", False):
            window.restore()
            time.sleep(0.2)
        window.activate()
        return True
    except Exception:
        try:
            window.minimize()
            window.restore()
            window.activate()
            return True
        except Exception:
            return False


def _find_windows(query: str) -> list:
    gw = _import_window_module()
    if gw is None:
        return []

    aliases = _WINDOW_APP_ALIASES.get(query, [query])
    windows = []
    for window in gw.getAllWindows():
        title = getattr(window, "title", "") or ""
        lowered = title.lower()
        if not lowered.strip():
            continue
        if any(alias in lowered for alias in aliases):
            windows.append(window)
    return windows


def _focus_app_window(query: str, launch_if_missing: bool = False) -> bool:
    normalized = _normalize_app_name(query)
    windows = _find_windows(normalized)
    if windows:
        return _activate_window(windows[0])

    if launch_if_missing:
        handle_open_app({"app": normalized})
        time.sleep(1.5)
        windows = _find_windows(normalized)
        if windows:
            return _activate_window(windows[0])
    return False


def _close_windows(query: str) -> bool:
    closed = False
    for window in _find_windows(query):
        try:
            window.close()
            closed = True
        except Exception:
            continue
    return closed


def _process_matches_app(proc: psutil.Process, app: str) -> bool:
    normalized = _normalize_app_name(app)
    aliases = {normalized}

    target = ALLOWED_APPS.get(normalized, "")
    if target:
        target_name = Path(target).name.lower()
        target_stem = Path(target).stem.lower()
        aliases.update({target_name, target_stem})

    aliases.update(_WINDOW_APP_ALIASES.get(normalized, []))

    try:
        name = (proc.info.get("name") or "").lower()
        exe_path = (proc.info.get("exe") or "").lower()
    except Exception:
        return False

    if normalized == "whatsapp":
        return "whatsapp" in name or "whatsapp" in exe_path

    for alias in aliases:
        if not alias:
            continue
        if name == alias or name == f"{alias}.exe":
            return True
        if exe_path.endswith(f"\\{alias}") or exe_path.endswith(f"\\{alias}.exe"):
            return True
    return False


def _capture_screenshot(save_path: Path) -> tuple[bool, str]:
    script = f"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
$width = [int]$bounds.Width
$height = [int]$bounds.Height
if ($width -le 0 -or $height -le 0) {{
    throw 'Screen bounds are not available.'
}}
$bitmap = New-Object System.Drawing.Bitmap $width, $height
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Left, $bounds.Top, 0, 0, $bitmap.Size)
$bitmap.Save('{_powershell_quote(str(save_path))}', [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bitmap.Dispose()
"""
    result = _run_powershell(script)
    if result.returncode == 0 and save_path.exists() and save_path.stat().st_size > 0:
        return True, ""

    fallback_error = (result.stderr or result.stdout).strip()
    try:
        if save_path.exists():
            save_path.unlink()
    except OSError:
        pass

    try:
        image = pyautogui.screenshot()
        image.save(str(save_path))
        if save_path.exists() and save_path.stat().st_size > 0:
            return True, ""
    except Exception as exc:
        fallback_error = f"{fallback_error} | {exc}".strip(" |")

    return False, fallback_error or "unknown screenshot failure"


def _normalize_url(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith(("http://", "https://")):
        return stripped
    if stripped.startswith("www."):
        return f"https://{stripped}"
    return f"https://{stripped}"


def _browser_open(url: str) -> str:
    try:
        webbrowser.open(url)
        return f"OK: Opened {url}"
    except Exception as exc:
        logger.error("browser open error: %s", exc)
        return f"Error: Could not open {url}."


def _media_action(name: str) -> str:
    try:
        if name == "media_play_pause":
            _tap_virtual_key(_VK_MEDIA_PLAY_PAUSE)
            return "OK: Toggled media play and pause."
        if name == "media_next":
            _tap_virtual_key(_VK_MEDIA_NEXT_TRACK)
            return "OK: Skipped to the next track."
        if name == "media_previous":
            _tap_virtual_key(_VK_MEDIA_PREV_TRACK)
            return "OK: Moved to the previous track."
    except Exception as exc:
        logger.error("media action error: %s", exc)
    return "Error: Could not control media playback."


def _open_path(path: str) -> str:
    try:
        os.startfile(path)  # type: ignore[attr-defined]
        return f"OK: Opened {path}."
    except AttributeError:
        pass
    except FileNotFoundError:
        return f"Error: {path} was not found."
    except OSError:
        pass

    try:
        subprocess.Popen([path], shell=False)
        return f"OK: Opened {path}."
    except FileNotFoundError:
        return f"Error: {path} was not found."
    except Exception:
        try:
            subprocess.Popen(path, shell=True)
            return f"OK: Opened {path}."
        except FileNotFoundError:
            return f"Error: {path} was not found."
        except Exception as exc:
            logger.error("open_app error: %s", exc)
            return f"Error: Could not open {path}."


def _launch(name: str, path: str) -> str:
    """Try to start *path* and return a result string."""
    result = _open_path(path)
    if result.startswith("OK: Opened"):
        return f"OK: Opened {name}."
    return result.replace(path, name)


def handle_open_app(params: dict) -> str:
    app = _normalize_app_name(str(params.get("app", "")))
    chat_id = params.get("_chat_id")
    chat_id = chat_id if isinstance(chat_id, int) else None

    if app in {"whatsapp", "whatsapp desktop", "wa"}:
        return open_whatsapp_app(prefer_web_fallback=True)

    if chat_id is not None and chat_id in _pending_fuzzy:
        if app.isdigit():
            choice = int(app) - 1
            options = _pending_fuzzy.pop(chat_id)
            if 0 <= choice < len(options):
                match = options[choice]
                return _launch(str(match["name"]), str(match["path"]))
            _pending_fuzzy[chat_id] = options
            return "Error: Invalid choice. Reply with one of the listed numbers."
        _pending_fuzzy.pop(chat_id, None)

    if app in ALLOWED_APPS:
        return _launch(app, ALLOWED_APPS[app])

    all_apps = {**discover_apps(), **ALLOWED_APPS}
    matches = fuzzy_find(app, all_apps)

    if not matches:
        allowed = ", ".join(sorted(ALLOWED_APPS))
        return f"Error: No app matching '{app}' was found. Try one of: {allowed}"
    if len(matches) == 1:
        match = matches[0]
        return _launch(str(match["name"]), str(match["path"]))

    if chat_id is not None:
        _pending_fuzzy[chat_id] = matches

    lines = [f"Found {len(matches)} matches for '{app}'. Reply with a number:"]
    for index, match in enumerate(matches, 1):
        lines.append(f"{index}. {match['name']} ({match['score']}%)")
    return "\n".join(lines)


def handle_close_app(params: dict) -> str:
    app = _normalize_app_name(str(params.get("app", "")))
    if app not in ALLOWED_APPS:
        return f"Error: '{app}' is not in the allowed app list."

    try:
        found = _close_windows(app)
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if _process_matches_app(proc, app):
                    proc.terminate()
                    found = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if found:
            return f"OK: Closed {app}."
        return f"Warning: {app} does not appear to be running."
    except Exception as exc:
        logger.error("close_app error: %s", exc)
        return f"Error: Could not close {app}."


def handle_find_file(params: dict) -> str:
    name = str(params.get("name", "")).strip()
    if len(name) < 2:
        return "Error: Please provide at least 2 characters."

    results: list[str] = []
    try:
        for path in HOME_DIR.rglob(f"*{name}*"):
            try:
                if path.is_relative_to(HOME_DIR):
                    results.append(str(path))
                    if len(results) >= 5:
                        break
            except PermissionError:
                continue
    except Exception as exc:
        logger.error("find_file error: %s", exc)

    if results:
        return f"Found {len(results)} file(s):\n" + "\n".join(results)
    return f"No files found matching '{name}'."


def handle_system_info(params: dict) -> str:
    del params
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("C:\\")
        return (
            "System Info:\n"
            f"CPU:  {cpu}%\n"
            f"RAM:  {mem.used / 1e9:.1f}GB / {mem.total / 1e9:.1f}GB ({mem.percent}%)\n"
            f"Disk: {disk.used / 1e9:.1f}GB / {disk.total / 1e9:.1f}GB ({disk.percent}%)"
        )
    except Exception as exc:
        logger.error("system_info error: %s", exc)
        return "Error: Could not retrieve system information."


def handle_set_volume(params: dict) -> str:
    level = params.get("level", 50)
    try:
        level = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        return "Error: Invalid volume level."

    try:
        scaled = int(level * 655.35)
        subprocess.run(
            [NIRCMD_PATH, "setsysvolume", str(scaled)],
            shell=False,
            timeout=5,
            check=False,
        )
        return f"OK: Volume set to {level}%."
    except Exception as exc:
        logger.error("set_volume error: %s", exc)
        return "Error: Could not set volume. Is nircmd installed?"


def handle_volume_up(params: dict) -> str:
    del params
    try:
        subprocess.run(
            [NIRCMD_PATH, "changesysvolume", "6553"],
            shell=False,
            timeout=5,
            check=False,
        )
        return "OK: Volume increased."
    except Exception as exc:
        logger.error("volume_up error: %s", exc)
        return "Error: Could not change volume."


def handle_volume_down(params: dict) -> str:
    del params
    try:
        subprocess.run(
            [NIRCMD_PATH, "changesysvolume", "-6553"],
            shell=False,
            timeout=5,
            check=False,
        )
        return "OK: Volume decreased."
    except Exception as exc:
        logger.error("volume_down error: %s", exc)
        return "Error: Could not change volume."


def handle_mute(params: dict) -> str:
    del params
    try:
        subprocess.run(
            [NIRCMD_PATH, "mutesysvolume", "2"],
            shell=False,
            timeout=5,
            check=False,
        )
        return "OK: Toggled mute."
    except Exception as exc:
        logger.error("mute error: %s", exc)
        return "Error: Could not toggle mute."


def handle_set_brightness(params: dict) -> str:
    level = params.get("level", 50)
    try:
        level = max(0, min(100, int(level)))
    except (ValueError, TypeError):
        return "Error: Invalid brightness level."

    try:
        sbc.set_brightness(level)
        return f"OK: Brightness set to {level}%."
    except Exception as exc:
        logger.error("set_brightness error: %s", exc)
        return "Error: Could not set brightness."


def handle_brightness_up(params: dict) -> str:
    del params
    try:
        current = sbc.get_brightness()[0]
        new_value = min(100, current + 10)
        sbc.set_brightness(new_value)
        return f"OK: Brightness set to {new_value}%."
    except Exception as exc:
        logger.error("brightness_up error: %s", exc)
        return "Error: Could not increase brightness."


def handle_brightness_down(params: dict) -> str:
    del params
    try:
        current = sbc.get_brightness()[0]
        new_value = max(0, current - 10)
        sbc.set_brightness(new_value)
        return f"OK: Brightness set to {new_value}%."
    except Exception as exc:
        logger.error("brightness_down error: %s", exc)
        return "Error: Could not decrease brightness."


def handle_type_text(params: dict) -> str:
    text = str(params.get("text", "")).strip()
    if not text:
        return "Error: No text to type."
    if len(text) > 500:
        return "Error: Text is too long."

    try:
        time.sleep(1.5)
        pyautogui.typewrite(text, interval=0.05)
        suffix = "..." if len(text) > 50 else ""
        return f"OK: Typed '{text[:50]}{suffix}'"
    except Exception as exc:
        logger.error("type_text error: %s", exc)
        return "Error: Could not type text."


def handle_press_keys(params: dict) -> str:
    sequence = str(params.get("sequence", "")).strip()
    steps, error = parse_key_sequence(sequence)
    if error:
        return f"Error: {error}"
    if not steps:
        return "Error: No key steps were parsed."

    try:
        time.sleep(1.0)
        labels: list[str] = []
        for step in steps:
            if step["kind"] == "write":
                text = str(step["text"])
                pyautogui.write(text, interval=0.03)
                labels.append(str(step["label"]))
                continue

            keys = [str(key) for key in step["keys"]]
            count = int(step["count"])
            for _ in range(count):
                if len(keys) == 1:
                    pyautogui.press(keys[0])
                else:
                    pyautogui.hotkey(*keys)
            if count > 1:
                labels.append(f"{step['label']} x{count}")
            else:
                labels.append(str(step["label"]))

        return "OK: Pressed " + ", ".join(labels) + "."
    except Exception as exc:
        logger.error("press_keys error: %s", exc)
        return "Error: Could not press the requested keys."


def handle_set_alarm(params: dict) -> str:
    seconds = params.get("seconds", 60)
    try:
        seconds = max(1, min(86400, int(seconds)))
    except (ValueError, TypeError):
        return "Error: Invalid alarm time."

    def alarm_thread() -> None:
        time.sleep(seconds)
        winsound.PlaySound(
            ALARM_SOUND if pathlib.Path(ALARM_SOUND).exists() else "SystemExclamation",
            winsound.SND_FILENAME
            if pathlib.Path(ALARM_SOUND).exists()
            else winsound.SND_ALIAS,
        )

    threading.Thread(target=alarm_thread, daemon=True).start()

    minutes = seconds // 60
    remaining_seconds = seconds % 60
    time_string = f"{minutes}m {remaining_seconds}s" if minutes else f"{remaining_seconds}s"
    return f"OK: Alarm set for {time_string}."


def handle_screenshot(params: dict) -> ActionResult:
    del params
    try:
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        save_path = Path.home() / "Pictures" / filename
        save_path.parent.mkdir(parents=True, exist_ok=True)
        ok, error = _capture_screenshot(save_path)
        if not ok:
            logger.error("screenshot error: %s", error)
            return _success("Error: Could not take a screenshot.")
        return _success(
            f"OK: Screenshot saved to {save_path}",
            photo_path=str(save_path),
        )
    except Exception as exc:
        logger.error("screenshot error: %s", exc)
        return _success("Error: Could not take a screenshot.")


def handle_message(params: dict) -> str:
    contact = str(params.get("contact", "")).strip()
    text = str(params.get("text", "")).strip()
    platform = str(params.get("platform", "whatsapp")).strip().lower()

    if not contact:
        return "Error: No contact specified."
    if not text:
        return "Error: No message text specified."
    if platform in ("whatsapp", "wa"):
        return send_whatsapp_message(contact, text)
    return f"Error: Platform '{platform}' is not supported yet."


def handle_open_chat(params: dict) -> str:
    contact = str(params.get("contact", "")).strip()
    platform = str(params.get("platform", "whatsapp")).strip().lower()

    if not contact:
        return "Error: No contact specified."
    if platform in ("whatsapp", "wa"):
        return open_whatsapp_chat(contact)
    return f"Error: Platform '{platform}' is not supported yet."


def handle_switch_app(params: dict) -> str:
    app = _normalize_app_name(str(params.get("app", "")))
    if _focus_app_window(app, launch_if_missing=True):
        return f"OK: Switched to {app}."
    return f"Error: Could not switch to {app}."


def handle_media_play_pause(params: dict) -> str:
    del params
    return _media_action("media_play_pause")


def handle_media_next(params: dict) -> str:
    del params
    return _media_action("media_next")


def handle_media_previous(params: dict) -> str:
    del params
    return _media_action("media_previous")


def handle_lock_system(params: dict) -> str:
    del params
    try:
        ctypes.windll.user32.LockWorkStation()
        return "OK: Locked the system."
    except Exception as exc:
        logger.error("lock_system error: %s", exc)
        return "Error: Could not lock the system."


def handle_sleep_system(params: dict) -> str:
    del params
    try:
        subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
        return "OK: Putting the system to sleep."
    except Exception as exc:
        logger.error("sleep_system error: %s", exc)
        return "Error: Could not put the system to sleep."


def handle_shutdown_system(params: dict) -> str:
    del params
    try:
        subprocess.Popen(["shutdown", "/s", "/t", "0"], shell=False)
        return "OK: Shutting down the system."
    except Exception as exc:
        logger.error("shutdown_system error: %s", exc)
        return "Error: Could not shut down the system."


def handle_restart_system(params: dict) -> str:
    del params
    try:
        subprocess.Popen(["shutdown", "/r", "/t", "0"], shell=False)
        return "OK: Restarting the system."
    except Exception as exc:
        logger.error("restart_system error: %s", exc)
        return "Error: Could not restart the system."


def handle_signout_system(params: dict) -> str:
    del params
    try:
        subprocess.Popen(["shutdown", "/l"], shell=False)
        return "OK: Signing out."
    except Exception as exc:
        logger.error("signout_system error: %s", exc)
        return "Error: Could not sign out."


def handle_copy_selected_text(params: dict) -> str:
    del params
    try:
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.4)
        text = _get_clipboard_text()
        if not text:
            return "Warning: Copied selection, but the clipboard is empty."
        preview = text[:200] + ("..." if len(text) > 200 else "")
        return f"OK: Copied text:\n{preview}"
    except Exception as exc:
        logger.error("copy_selected_text error: %s", exc)
        return "Error: Could not copy selected text."


def handle_paste_clipboard(params: dict) -> str:
    del params
    try:
        pyautogui.hotkey("ctrl", "v")
        return "OK: Pasted clipboard contents."
    except Exception as exc:
        logger.error("paste_clipboard error: %s", exc)
        return "Error: Could not paste clipboard contents."


def handle_set_clipboard(params: dict) -> str:
    text = str(params.get("text", "")).strip()
    if not text:
        return "Error: Clipboard text is empty."
    if _set_clipboard_text(text):
        return "OK: Clipboard text updated."
    return "Error: Could not update the clipboard."


def handle_show_clipboard(params: dict) -> str:
    del params
    text = _get_clipboard_text()
    if not text:
        return "Warning: Clipboard is empty."
    preview = text[:500] + ("..." if len(text) > 500 else "")
    return f"Clipboard:\n{preview}"


def handle_open_url(params: dict) -> str:
    url = _normalize_url(str(params.get("url", "")))
    return _browser_open(url)


def handle_open_site(params: dict) -> str:
    site = _normalize_url(str(params.get("site", "")))
    return _browser_open(site)


def handle_search_google(params: dict) -> str:
    query = urllib.parse.quote_plus(str(params.get("query", "")).strip())
    return _browser_open(f"https://www.google.com/search?q={query}")


def handle_search_youtube(params: dict) -> str:
    query = urllib.parse.quote_plus(str(params.get("query", "")).strip())
    return _browser_open(f"https://www.youtube.com/results?search_query={query}")


def handle_window_minimize(params: dict) -> str:
    del params
    gw = _import_window_module()
    if gw is None:
        return "Error: Window control is not available."
    try:
        window = gw.getActiveWindow()
        if window is None:
            return "Error: No active window was found."
        window.minimize()
        return "OK: Minimized the active window."
    except Exception as exc:
        logger.error("window_minimize error: %s", exc)
        return "Error: Could not minimize the active window."


def handle_window_maximize(params: dict) -> str:
    del params
    gw = _import_window_module()
    if gw is None:
        return "Error: Window control is not available."
    try:
        window = gw.getActiveWindow()
        if window is None:
            return "Error: No active window was found."
        window.maximize()
        return "OK: Maximized the active window."
    except Exception as exc:
        logger.error("window_maximize error: %s", exc)
        return "Error: Could not maximize the active window."


def handle_window_alt_tab(params: dict) -> str:
    del params
    try:
        pyautogui.hotkey("alt", "tab")
        return "OK: Switched to the next window."
    except Exception as exc:
        logger.error("window_alt_tab error: %s", exc)
        return "Error: Could not switch windows."


def handle_battery_status(params: dict) -> str:
    del params
    battery = psutil.sensors_battery()
    if battery is None:
        return "Warning: Battery information is not available on this device."
    charging = "charging" if battery.power_plugged else "not charging"
    return f"Battery: {battery.percent:.0f}% and {charging}."


def handle_network_status(params: dict) -> str:
    del params
    try:
        wifi_result = _run_powershell("(netsh wlan show interfaces) -join \"`n\"")
        wifi_name = "Not connected"
        if wifi_result.returncode == 0:
            for line in wifi_result.stdout.splitlines():
                stripped = line.strip()
                if stripped.lower().startswith("ssid") and "bssid" not in stripped.lower():
                    parts = stripped.split(":", 1)
                    if len(parts) == 2 and parts[1].strip():
                        wifi_name = parts[1].strip()
                        break

        ip_address = "Unavailable"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
            sock.close()
        except Exception:
            pass

        return f"Wi-Fi: {wifi_name}\nIP Address: {ip_address}"
    except Exception as exc:
        logger.error("network_status error: %s", exc)
        return "Error: Could not retrieve network status."


def handle_ip_address(params: dict) -> str:
    del params
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip_address = sock.getsockname()[0]
        sock.close()
        return f"IP Address: {ip_address}"
    except Exception as exc:
        logger.error("ip_address error: %s", exc)
        return "Error: Could not retrieve the IP address."


def handle_device_status(params: dict) -> str:
    del params
    return handle_battery_status({}) + "\n" + handle_network_status({})


def handle_open_downloads(params: dict) -> str:
    del params
    downloads = _SPECIAL_FOLDERS["downloads"]
    downloads.mkdir(parents=True, exist_ok=True)
    return _open_path(str(downloads)).replace(str(downloads), "Downloads")


def handle_create_folder(params: dict) -> str:
    name = str(params.get("name", "")).strip()
    location = str(params.get("location", "")).strip()
    base = _resolve_special_folder(location) if location else HOME_DIR
    if base is None:
        return f"Error: Unknown folder location '{location}'."
    target = base / name
    try:
        target = target.resolve()
    except Exception:
        return "Error: Folder path is invalid."
    if not _path_within_home(target):
        return "Error: Folder must stay inside your home directory."
    try:
        target.mkdir(parents=True, exist_ok=True)
        return f"OK: Folder ready at {target}"
    except Exception as exc:
        logger.error("create_folder error: %s", exc)
        return "Error: Could not create the folder."


def handle_move_file(params: dict) -> str:
    source = str(params.get("source", "")).strip()
    destination = str(params.get("destination", "")).strip()
    source_path = _resolve_source_file(source)
    if source_path is None:
        return f"Error: Could not find file '{source}'."

    destination_folder = _resolve_destination_folder(destination)
    if destination_folder is None:
        return f"Error: Could not resolve destination '{destination}'."

    try:
        destination_folder.mkdir(parents=True, exist_ok=True)
        target = destination_folder / source_path.name
        shutil.move(str(source_path), str(target))
        return f"OK: Moved {source_path.name} to {target}"
    except Exception as exc:
        logger.error("move_file error: %s", exc)
        return "Error: Could not move the file."


def handle_app_shortcut(params: dict) -> str:
    app = _normalize_app_name(str(params.get("app", "")))
    command = " ".join(str(params.get("command", "")).strip().lower().split())
    if not command:
        return "Error: No shortcut command was provided."

    if app == DEFAULT_BROWSER and (command.startswith("go to ") or command.startswith("open ")):
        url_text = command[6:].strip() if command.startswith("go to ") else command[5:].strip()
        url = _normalize_url(url_text)
        if _focus_app_window(app, launch_if_missing=True):
            time.sleep(0.4)
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.1)
            pyautogui.write(url, interval=0.02)
            pyautogui.press("enter")
            return f"OK: Opened {url} in {app}."

    if app == DEFAULT_BROWSER and command.startswith("search "):
        query = command[7:].strip()
        if _focus_app_window(app, launch_if_missing=True):
            time.sleep(0.4)
            pyautogui.hotkey("ctrl", "l")
            time.sleep(0.1)
            pyautogui.write(f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}", interval=0.02)
            pyautogui.press("enter")
            return f"OK: Searched Google for '{query}' in {app}."

    if app not in _APP_SHORTCUTS:
        return f"Error: No shortcuts are configured for {app}."

    shortcut = _APP_SHORTCUTS[app].get(command)
    if shortcut is None:
        allowed = ", ".join(sorted(_APP_SHORTCUTS[app]))
        return f"Error: Unknown shortcut for {app}. Try: {allowed}"

    if not _focus_app_window(app, launch_if_missing=True):
        return f"Error: Could not focus {app}."

    try:
        time.sleep(0.4)
        if isinstance(shortcut, str):
            if shortcut == "media_play_pause":
                return handle_media_play_pause({})
            if shortcut == "media_next":
                return handle_media_next({})
            if shortcut == "media_previous":
                return handle_media_previous({})
            return "Error: Unsupported shortcut."
        pyautogui.hotkey(*shortcut)
        return f"OK: Ran {app} shortcut '{command}'."
    except Exception as exc:
        logger.error("app_shortcut error: %s", exc)
        return f"Error: Could not run shortcut '{command}' for {app}."


def handle_run_macro(params: dict) -> str:
    name = " ".join(str(params.get("name", "")).strip().lower().split())
    results: list[str] = []

    if name == "work mode":
        results.append(handle_open_app({"app": "chrome"}))
        results.append(handle_open_app({"app": "vscode"}))
        if _brightness_available():
            results.append(handle_set_brightness({"level": 70}))
    elif name == "study mode":
        results.append(handle_open_app({"app": "chrome"}))
        if _brightness_available():
            results.append(handle_set_brightness({"level": 60}))
        if _nircmd_available():
            results.append(handle_mute({}))
    elif name == "meeting mode":
        results.append(handle_open_app({"app": "whatsapp"}))
        results.append(handle_open_app({"app": "chrome"}))
        if _brightness_available():
            results.append(handle_set_brightness({"level": 65}))
        if _nircmd_available():
            results.append(handle_set_volume({"level": 40}))
    else:
        return f"Error: Unknown macro '{name}'."

    return "Macro complete:\n" + "\n".join(f"- {line}" for line in results if line)


def handle_unknown(params: dict) -> str:
    del params
    lines = ["I did not understand that.", "", "Try:"]
    for example in get_supported_examples():
        lines.append(f"- {example}")
    return "\n".join(lines)


ACTION_REGISTRY: dict[str, Action] = {
    "open_app": Action(
        id="open_app",
        description="Open an installed application",
        requires_confirmation=False,
        handler=handle_open_app,
    ),
    "open_chat": Action(
        id="open_chat",
        description="Open a WhatsApp chat without sending a message",
        requires_confirmation=False,
        handler=handle_open_chat,
    ),
    "switch_app": Action(
        id="switch_app",
        description="Focus or open an application window",
        requires_confirmation=False,
        handler=handle_switch_app,
    ),
    "close_app": Action(
        id="close_app",
        description="Close a configured application",
        requires_confirmation=False,
        handler=handle_close_app,
    ),
    "find_file": Action(
        id="find_file",
        description="Search for files in the home directory",
        requires_confirmation=False,
        handler=handle_find_file,
    ),
    "system_info": Action(
        id="system_info",
        description="Show CPU, RAM, and disk usage",
        requires_confirmation=False,
        handler=handle_system_info,
    ),
    "set_volume": Action(
        id="set_volume",
        description="Set system volume to a specific level",
        requires_confirmation=False,
        handler=handle_set_volume,
    ),
    "volume_up": Action(
        id="volume_up",
        description="Increase system volume",
        requires_confirmation=False,
        handler=handle_volume_up,
    ),
    "volume_down": Action(
        id="volume_down",
        description="Decrease system volume",
        requires_confirmation=False,
        handler=handle_volume_down,
    ),
    "mute": Action(
        id="mute",
        description="Toggle system mute",
        requires_confirmation=False,
        handler=handle_mute,
    ),
    "set_brightness": Action(
        id="set_brightness",
        description="Set screen brightness to a specific level",
        requires_confirmation=False,
        handler=handle_set_brightness,
    ),
    "brightness_up": Action(
        id="brightness_up",
        description="Increase screen brightness",
        requires_confirmation=False,
        handler=handle_brightness_up,
    ),
    "brightness_down": Action(
        id="brightness_down",
        description="Decrease screen brightness",
        requires_confirmation=False,
        handler=handle_brightness_down,
    ),
    "type_text": Action(
        id="type_text",
        description="Type plain text",
        requires_confirmation=False,
        handler=handle_type_text,
    ),
    "press_keys": Action(
        id="press_keys",
        description="Press keys or shortcuts in order",
        requires_confirmation=False,
        handler=handle_press_keys,
    ),
    "media_play_pause": Action(
        id="media_play_pause",
        description="Toggle media play and pause",
        requires_confirmation=False,
        handler=handle_media_play_pause,
    ),
    "media_next": Action(
        id="media_next",
        description="Go to the next track",
        requires_confirmation=False,
        handler=handle_media_next,
    ),
    "media_previous": Action(
        id="media_previous",
        description="Go to the previous track",
        requires_confirmation=False,
        handler=handle_media_previous,
    ),
    "set_alarm": Action(
        id="set_alarm",
        description="Set a countdown alarm",
        requires_confirmation=False,
        handler=handle_set_alarm,
    ),
    "screenshot": Action(
        id="screenshot",
        description="Take a screenshot and send it back",
        requires_confirmation=False,
        handler=handle_screenshot,
    ),
    "message": Action(
        id="message",
        description="Send a message via WhatsApp Desktop",
        requires_confirmation=False,
        handler=handle_message,
    ),
    "lock_system": Action(
        id="lock_system",
        description="Lock the laptop",
        requires_confirmation=False,
        handler=handle_lock_system,
    ),
    "sleep_system": Action(
        id="sleep_system",
        description="Put the laptop to sleep",
        requires_confirmation=True,
        handler=handle_sleep_system,
    ),
    "shutdown_system": Action(
        id="shutdown_system",
        description="Shut down the laptop",
        requires_confirmation=True,
        handler=handle_shutdown_system,
    ),
    "restart_system": Action(
        id="restart_system",
        description="Restart the laptop",
        requires_confirmation=True,
        handler=handle_restart_system,
    ),
    "signout_system": Action(
        id="signout_system",
        description="Sign out of Windows",
        requires_confirmation=True,
        handler=handle_signout_system,
    ),
    "copy_selected_text": Action(
        id="copy_selected_text",
        description="Copy selected text and reply with it",
        requires_confirmation=False,
        handler=handle_copy_selected_text,
    ),
    "paste_clipboard": Action(
        id="paste_clipboard",
        description="Paste clipboard contents",
        requires_confirmation=False,
        handler=handle_paste_clipboard,
    ),
    "set_clipboard": Action(
        id="set_clipboard",
        description="Set clipboard text",
        requires_confirmation=False,
        handler=handle_set_clipboard,
    ),
    "show_clipboard": Action(
        id="show_clipboard",
        description="Show clipboard contents",
        requires_confirmation=False,
        handler=handle_show_clipboard,
    ),
    "open_url": Action(
        id="open_url",
        description="Open a full URL in the browser",
        requires_confirmation=False,
        handler=handle_open_url,
    ),
    "open_site": Action(
        id="open_site",
        description="Open a website in the browser",
        requires_confirmation=False,
        handler=handle_open_site,
    ),
    "search_google": Action(
        id="search_google",
        description="Search Google",
        requires_confirmation=False,
        handler=handle_search_google,
    ),
    "search_youtube": Action(
        id="search_youtube",
        description="Search YouTube",
        requires_confirmation=False,
        handler=handle_search_youtube,
    ),
    "window_minimize": Action(
        id="window_minimize",
        description="Minimize the active window",
        requires_confirmation=False,
        handler=handle_window_minimize,
    ),
    "window_maximize": Action(
        id="window_maximize",
        description="Maximize the active window",
        requires_confirmation=False,
        handler=handle_window_maximize,
    ),
    "window_alt_tab": Action(
        id="window_alt_tab",
        description="Switch to the next window",
        requires_confirmation=False,
        handler=handle_window_alt_tab,
    ),
    "battery_status": Action(
        id="battery_status",
        description="Show battery status",
        requires_confirmation=False,
        handler=handle_battery_status,
    ),
    "network_status": Action(
        id="network_status",
        description="Show Wi-Fi and IP status",
        requires_confirmation=False,
        handler=handle_network_status,
    ),
    "ip_address": Action(
        id="ip_address",
        description="Show the local IP address",
        requires_confirmation=False,
        handler=handle_ip_address,
    ),
    "device_status": Action(
        id="device_status",
        description="Show battery and network status",
        requires_confirmation=False,
        handler=handle_device_status,
    ),
    "open_downloads": Action(
        id="open_downloads",
        description="Open the Downloads folder",
        requires_confirmation=False,
        handler=handle_open_downloads,
    ),
    "create_folder": Action(
        id="create_folder",
        description="Create a folder",
        requires_confirmation=False,
        handler=handle_create_folder,
    ),
    "move_file": Action(
        id="move_file",
        description="Move a file inside the home directory",
        requires_confirmation=True,
        handler=handle_move_file,
    ),
    "app_shortcut": Action(
        id="app_shortcut",
        description="Run an app-specific shortcut",
        requires_confirmation=False,
        handler=handle_app_shortcut,
    ),
    "run_macro": Action(
        id="run_macro",
        description="Run a custom macro mode",
        requires_confirmation=False,
        handler=handle_run_macro,
    ),
    "unknown": Action(
        id="unknown",
        description="Show help for unrecognized commands",
        requires_confirmation=False,
        handler=handle_unknown,
    ),
}
