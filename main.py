"""
Entry point for the local assistant.

Ensures dependencies are installed before importing the app, configures
logging, and then delegates to bot.run().
"""

REQUIRED_PACKAGES = [
    "python-telegram-bot==22.6",
    "psutil==5.9.8",
    "pyautogui==0.9.54",
    "screen-brightness-control==0.23.0",
    "requests==2.31.0",
    "rapidfuzz",
    "pywinauto",
    "pygetwindow",
]


def ensure_dependencies() -> None:
    """Auto-install any missing packages before the rest of the app loads."""
    import importlib
    import importlib.metadata
    import subprocess
    import sys

    package_specs = {
        "python-telegram-bot": {
            "version": "22.6",
            "module": "telegram",
        },
        "psutil": {
            "version": "5.9.8",
            "module": "psutil",
        },
        "pyautogui": {
            "version": "0.9.54",
            "module": "pyautogui",
        },
        "screen-brightness-control": {
            "version": "0.23.0",
            "module": "screen_brightness_control",
        },
        "requests": {
            "version": "2.31.0",
            "module": "requests",
        },
        "rapidfuzz": {
            "version": None,
            "module": "rapidfuzz",
        },
        "pywinauto": {
            "version": None,
            "module": "pywinauto",
        },
        "pygetwindow": {
            "version": None,
            "module": "pygetwindow",
        },
    }

    for package_name, spec in package_specs.items():
        expected_version = spec["version"]
        module_name = spec["module"]
        install_target = (
            f"{package_name}=={expected_version}"
            if expected_version is not None
            else package_name
        )

        try:
            importlib.import_module(module_name)
            if expected_version is None:
                continue
            installed_version = importlib.metadata.version(package_name)
            if installed_version == expected_version:
                continue
            print(
                f"Upgrading {package_name} from {installed_version} "
                f"to {expected_version}..."
            )
        except (ImportError, importlib.metadata.PackageNotFoundError):
            print(f"Installing {install_target}...")

        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", install_target],
            check=True,
        )


ensure_dependencies()

import logging
import sys
from pathlib import Path

from bot import ConfigurationError, run  # type: ignore
from config import LOG_FILE  # type: ignore

Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    try:
        logger.info("Starting local AI assistant...")
        run()
    except KeyboardInterrupt:
        logger.info("Stopped by user (KeyboardInterrupt).")
        sys.exit(0)
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        print()
        print("Setup required before the bot can start:")
        print("1. Create a Telegram bot using BotFather.")
        print("2. Set TELEGRAM_TOKEN in your environment.")
        print("3. Optional: set ALLOWED_TELEGRAM_USER_ID to your Telegram numeric user id.")
        print()
        print(f"Details: {exc}")
        sys.exit(1)
    except Exception:
        logging.critical("Fatal error during runtime.", exc_info=True)
        raise
