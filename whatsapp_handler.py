"""
WhatsApp Desktop launch and message automation helpers.
"""

import logging
import os
import subprocess
import time
import webbrowser
from pathlib import Path

import psutil  # type: ignore

from app_discovery import discover_apps  # type: ignore
from config import WHATSAPP_PATH  # type: ignore

logger = logging.getLogger(__name__)

TIMEOUT = 15
_WEB_URL = "https://web.whatsapp.com/"


def _is_whatsapp_running() -> bool:
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"]
            if name and "whatsapp" in name.lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def _launch_target(target: str) -> bool:
    try:
        os.startfile(target)  # type: ignore[attr-defined]
        return True
    except AttributeError:
        pass
    except OSError:
        pass

    try:
        subprocess.Popen([target], shell=False)
        return True
    except Exception:
        try:
            subprocess.Popen(target, shell=True)
            return True
        except Exception as exc:
            logger.debug("whatsapp_handler: launch failed for %s: %s", target, exc)
            return False


def _wait_for_startup(seconds: float = 4.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _is_whatsapp_running():
            return True
        time.sleep(0.5)
    return False


def _focus_whatsapp_window() -> bool:
    try:
        from pywinauto import Application, findwindows  # type: ignore
    except ImportError:
        return False

    try:
        handles = findwindows.find_windows(title_re=".*WhatsApp.*")
        if not handles:
            return False
        app = Application(backend="uia").connect(handle=handles[0])
        dlg = app.top_window()
        try:
            dlg.restore()
        except Exception:
            pass
        dlg.set_focus()
        return True
    except Exception as exc:
        logger.debug("whatsapp_handler: could not focus WhatsApp window: %s", exc)
        return False


def _wait_for_focus(seconds: float = 5.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if _focus_whatsapp_window():
            return True
        time.sleep(0.5)
    return False


def _candidate_paths() -> list[str]:
    candidates: list[str] = []

    def add(path: str) -> None:
        if not path:
            return
        normalized = str(path).strip()
        if not normalized or normalized in candidates:
            return
        path_obj = Path(normalized)
        if path_obj.exists():
            candidates.append(normalized)

    if WHATSAPP_PATH:
        add(WHATSAPP_PATH)

    local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
    app_data = Path(os.environ.get("APPDATA", ""))
    program_data = Path(os.environ.get("PROGRAMDATA", "C:/ProgramData"))
    desktop = Path.home() / "Desktop"
    onedrive_desktop = Path.home() / "OneDrive" / "Desktop"

    for path in [
        local_app_data / "WhatsApp" / "WhatsApp.exe",
        local_app_data / "Programs" / "WhatsApp" / "WhatsApp.exe",
        local_app_data / "Microsoft" / "WindowsApps" / "WhatsApp.exe",
        desktop / "WhatsApp.lnk",
        onedrive_desktop / "WhatsApp.lnk",
        program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "WhatsApp.lnk",
        app_data / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "WhatsApp.lnk",
    ]:
        add(str(path))

    discovered = discover_apps()
    preferred_names = [
        "whatsapp",
        "whatsapp desktop",
        "whatsapp beta",
    ]

    for name in preferred_names:
        if name in discovered:
            add(discovered[name])

    for name, path in discovered.items():
        lowered_name = name.lower()
        lowered_path = path.lower()
        if "whatsapp" not in lowered_name:
            continue
        if "\\recent\\" in lowered_path:
            continue
        add(path)

    return candidates


def has_whatsapp_support() -> bool:
    """Return True when WhatsApp Desktop appears launchable on this machine."""
    if _is_whatsapp_running():
        return True
    return bool(_candidate_paths())


def open_whatsapp_app(prefer_web_fallback: bool = True) -> str:
    """Open WhatsApp Desktop if possible, else optionally fall back to web."""
    if _is_whatsapp_running():
        if _launch_target("whatsapp:"):
            time.sleep(1.0)
            if _wait_for_focus():
                return "OK: Opened WhatsApp."
        if _wait_for_focus():
            return "OK: Focused WhatsApp."
        return "OK: WhatsApp is already running."

    for target in ["whatsapp:"]:
        if _launch_target(target) and _wait_for_startup():
            _wait_for_focus()
            return "OK: Opened WhatsApp."

    for target in _candidate_paths():
        logger.info("whatsapp_handler: trying launch target %s", target)
        if _launch_target(target) and _wait_for_startup():
            _wait_for_focus()
            return "OK: Opened WhatsApp."

    if prefer_web_fallback:
        webbrowser.open(_WEB_URL)
        return "Warning: WhatsApp Desktop was not found. Opened WhatsApp Web instead."

    return (
        "Error: Could not find WhatsApp Desktop. Install it or set WHATSAPP_PATH "
        "to the WhatsApp executable or shortcut."
    )


def open_whatsapp_chat(contact: str) -> str:
    """Launch WhatsApp, search *contact*, and open the first matching chat."""
    contact = contact.strip()
    if not contact:
        return "Error: No contact specified."

    try:
        from pywinauto.keyboard import send_keys  # type: ignore
        import pyautogui  # type: ignore
    except ImportError:
        return "Error: WhatsApp automation dependencies are not installed."

    launch_result = open_whatsapp_app(prefer_web_fallback=False)
    if launch_result.startswith("Error:"):
        return launch_result

    try:
        if not _wait_for_focus():
            return "Error: WhatsApp opened, but its window could not be focused."

        time.sleep(0.8)
        send_keys("^f")
        time.sleep(0.5)
        send_keys("^a{BACKSPACE}")
        time.sleep(0.2)
        pyautogui.write(contact, interval=0.03)
        time.sleep(1.2)

        # Move from the search field into the first result before opening it.
        send_keys("{DOWN}")
        time.sleep(0.2)
        send_keys("{ENTER}")
        time.sleep(0.8)

        logger.info("whatsapp_handler: opened chat for %s", contact)
        return f"OK: Opened WhatsApp chat for {contact}."

    except Exception as exc:
        logger.error("whatsapp_handler: open chat error: %s", exc, exc_info=True)
        return f"Error: Could not open WhatsApp chat for {contact}: {exc}"


def send_whatsapp_message(contact: str, message: str) -> str:
    """Launch WhatsApp, search *contact*, and send *message*."""
    try:
        from pywinauto.keyboard import send_keys  # type: ignore
        import pyautogui  # type: ignore
    except ImportError:
        return "Error: WhatsApp automation dependencies are not installed."

    chat_result = open_whatsapp_chat(contact)
    if chat_result.startswith("Error:"):
        return chat_result

    try:
        time.sleep(0.6)
        pyautogui.write(message, interval=0.03)
        time.sleep(0.2)
        send_keys("{ENTER}")
        logger.info("whatsapp_handler: sent message to %s", contact)
        return f"OK: Message sent to {contact} on WhatsApp."

    except Exception as exc:
        logger.error("whatsapp_handler: unexpected error: %s", exc, exc_info=True)
        return f"Error: WhatsApp automation failed: {exc}"
