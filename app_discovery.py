"""
Scan common Windows application locations and cache the results.
"""

import json
import logging
import os
import time
from pathlib import Path

from config import APPS_CACHE_FILE  # type: ignore

logger = logging.getLogger(__name__)

_CACHE_FILE = APPS_CACHE_FILE
_CACHE_TTL_SECONDS = 86400
_CACHE_VERSION = 2

_SCAN_DIRS: list[Path] = [
    Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ.get("PROGRAMDATA", "C:/ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path.home() / "Desktop",
    Path(os.environ.get("PUBLIC", "C:/Users/Public")) / "Desktop",
    Path(os.environ.get("PROGRAMFILES", "C:/Program Files")),
    Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps",
]

_SKIP_DIR_NAMES = {
    "recent",
    "temp",
    "cache",
    "packages",
    "application data",
}


def _load_cache() -> dict[str, str] | None:
    if not _CACHE_FILE.exists():
        return None

    try:
        age = time.time() - _CACHE_FILE.stat().st_mtime
        if age > _CACHE_TTL_SECONDS:
            return None

        with _CACHE_FILE.open(encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict) and "apps" in data and "meta" in data:
            meta = data.get("meta", {})
            if meta.get("version") != _CACHE_VERSION:
                return None
            apps = data.get("apps")
            if isinstance(apps, dict):
                return apps

        return None
    except Exception as exc:
        logger.warning("app_discovery: cache read failed: %s", exc)
        return None


def _save_cache(apps: dict[str, str]) -> None:
    payload = {
        "meta": {
            "version": _CACHE_VERSION,
            "generated_at": int(time.time()),
        },
        "apps": apps,
    }

    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _CACHE_FILE.open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
    except Exception as exc:
        logger.warning("app_discovery: cache write failed: %s", exc)


def _should_skip(entry: Path) -> bool:
    return entry.is_dir() and entry.name.lower() in _SKIP_DIR_NAMES


def _scan_dir(directory: Path, apps: dict[str, str], max_depth: int = 3, depth: int = 0) -> None:
    if depth > max_depth:
        return

    try:
        for entry in directory.iterdir():
            try:
                if _should_skip(entry):
                    continue
                if entry.is_dir():
                    _scan_dir(entry, apps, max_depth, depth + 1)
                elif entry.suffix.lower() in {".exe", ".lnk"}:
                    lowered_path = str(entry).lower()
                    if "\\recent\\" in lowered_path:
                        continue
                    name = entry.stem.lower().replace("_", " ").replace("-", " ")
                    apps.setdefault(name, str(entry))
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        return


def discover_apps(force_refresh: bool = False) -> dict[str, str]:
    """Return a mapping of display_name -> exe or shortcut path."""
    if not force_refresh:
        cached = _load_cache()
        if cached is not None:
            return cached

    apps: dict[str, str] = {}
    for scan_dir in _SCAN_DIRS:
        if scan_dir.exists():
            _scan_dir(scan_dir, apps)

    logger.info("app_discovery: found %d apps after scan", len(apps))
    _save_cache(apps)
    return apps
