"""
Adapter from the rule-based parser to the bot's action/params format.
"""

from typing import Any

from intent_parser import parse  # type: ignore

UNKNOWN = {"action": "unknown", "params": {}}

_ACTION_MAP = {
    "open": "open_app",
    "close": "close_app",
    "find": "find_file",
}


def get_intent(user_text: str) -> dict[str, Any]:
    """Return a normalized intent payload for the bot/action pipeline."""
    parsed = parse(user_text)
    if not parsed:
        return UNKNOWN

    source_action = str(parsed.get("action", "")).strip()
    if not source_action:
        return UNKNOWN

    action_id = _ACTION_MAP.get(source_action, source_action)

    params = {key: value for key, value in parsed.items() if key != "action"}

    if action_id in ("open_app", "close_app"):
        app_name = str(params.pop("target", params.pop("app", ""))).strip()
        if not app_name:
            return UNKNOWN
        params = {"app": app_name}
    elif action_id == "find_file":
        name = str(params.get("name", "")).strip()
        if not name:
            return UNKNOWN
        params = {"name": name}
    elif action_id == "press_keys":
        sequence = str(params.get("sequence", "")).strip()
        if not sequence:
            return UNKNOWN
        params = {"sequence": sequence}

    return {"action": action_id, "params": params}
