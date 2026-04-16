"""
Telegram bot for the local assistant.
"""

import logging
import time
from typing import Any

from telegram import Update  # type: ignore
from telegram.error import InvalidToken  # type: ignore
from telegram.ext import (  # type: ignore
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from actions import ACTION_REGISTRY, ActionResult, get_supported_actions, get_supported_examples  # type: ignore
from config import ALLOWED_TELEGRAM_USER_ID, TELEGRAM_TOKEN  # type: ignore
from router import get_intent  # type: ignore
from validator import ActionGuard, ActionLogger, InputValidator  # type: ignore

logger = logging.getLogger(__name__)

pending_choices: dict[int, dict[str, Any]] = {}
pending_confirmations: dict[int, dict[str, Any]] = {}
_SELECTION_TTL = 30  # seconds
_CONFIRMATION_TTL = 45  # seconds


class ConfigurationError(RuntimeError):
    """Raised when required bot configuration is missing or invalid."""


def _validate_token() -> None:
    if not TELEGRAM_TOKEN:
        raise ConfigurationError(
            "Missing Telegram bot token. Set TELEGRAM_TOKEN before starting the app."
        )
    if ":" not in TELEGRAM_TOKEN:
        raise ConfigurationError(
            "Telegram bot token format looks invalid. It should look like "
            "'123456789:ABCDEF...'."
        )


def _is_authorized(update: Update) -> bool:
    user = update.effective_user
    if user is None:
        return False
    if ALLOWED_TELEGRAM_USER_ID is None:
        return True
    return user.id == ALLOWED_TELEGRAM_USER_ID


def _clear_pending(chat_id: int) -> None:
    pending_choices.pop(chat_id, None)

    from actions import _pending_fuzzy  # type: ignore

    _pending_fuzzy.pop(chat_id, None)


def _sync_pending_open_app(chat_id: int) -> None:
    from actions import _pending_fuzzy  # type: ignore

    if chat_id in _pending_fuzzy:
        pending_choices[chat_id] = {
            "action": "open_app",
            "options": list(_pending_fuzzy[chat_id]),
            "timestamp": time.time(),
        }
    else:
        pending_choices.pop(chat_id, None)


def _clear_confirmation(chat_id: int) -> None:
    pending_confirmations.pop(chat_id, None)


def _store_confirmation(chat_id: int, action_id: str, params: dict[str, Any]) -> None:
    pending_confirmations[chat_id] = {
        "action": action_id,
        "params": dict(params),
        "timestamp": time.time(),
    }


async def _reply_with_result(update: Update, result: str | ActionResult) -> None:
    message = update.effective_message
    if message is None:
        return

    if isinstance(result, ActionResult):
        if result.photo_path:
            with open(result.photo_path, "rb") as file_handle:
                await message.reply_photo(photo=file_handle, caption=result.message)
            return
        await message.reply_text(result.message)
        return

    await message.reply_text(result)


def _result_message(result: str | ActionResult) -> str:
    return result.message if isinstance(result, ActionResult) else result


def _requires_confirmation(action_id: str) -> bool:
    action = ACTION_REGISTRY.get(action_id)
    return bool(action and action.requires_confirmation)


def _is_confirmation_reply(user_text: str) -> bool:
    return user_text.lower() in {"yes", "y", "confirm"}


def _is_cancel_reply(user_text: str) -> bool:
    return user_text.lower() in {"no", "n", "cancel"}


def _execute_action(action_id: str, params: dict[str, Any], chat_id: int) -> str | ActionResult:
    params_to_run = dict(params)
    params_to_run["_chat_id"] = chat_id
    return ACTION_REGISTRY[action_id].handler(params_to_run)


async def _reject_unauthorized(update: Update) -> None:
    user = update.effective_user
    user_label = "unknown"
    if user is not None:
        user_label = str(user.username or user.id)
    logger.warning("Rejected unauthorized Telegram user: %s", user_label)

    message = update.effective_message
    if message is not None:
        await message.reply_text("Access denied for this Telegram account.")


async def resolve_selection(
    chat_id: int,
    index: int,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
) -> None:
    """Execute the stored action for the option at *index* (1-based)."""
    state = pending_choices.get(chat_id)
    if state is None:
        if update.message is not None:
            await update.message.reply_text("No pending selection.")
        return

    if time.time() - state["timestamp"] > _SELECTION_TTL:
        _clear_pending(chat_id)
        if update.message is not None:
            await update.message.reply_text("Selection expired. Ask to open the app again.")
        return

    options: list[dict[str, Any]] = state["options"]
    count = len(options)
    if index < 1 or index > count:
        if update.message is not None:
            await update.message.reply_text(f"Invalid selection. Pick 1-{count}.")
        return

    chosen = options[index - 1]
    _clear_pending(chat_id)

    action = state["action"]
    if action == "open_app":
        from actions import _launch  # type: ignore

        result = _launch(str(chosen["name"]), str(chosen["path"]))
    else:
        result = f"OK: Selected {chosen.get('name', chosen)}."

    user_id = update.effective_user.id if update.effective_user else 0
    ActionLogger.log_action(
        user_id,
        {
            "action": action,
            "selection": index,
            "app": chosen.get("name", ""),
        },
        result,
    )

    await _reply_with_result(update, result)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message listing all available actions."""
    del context

    if not _is_authorized(update):
        await _reject_unauthorized(update)
        return

    lines = ["Telegram Local Assistant", "", "Available commands:"]

    for action in get_supported_actions():
        lines.append(f"- `{action.id}`: {action.description}")

    lines += ["", "Examples:"]
    for example in get_supported_examples():
        lines.append(f"- {example}")

    if update.message is not None:
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route an incoming text message through sanitize, intent, guard, execute, and log."""
    try:
        if not _is_authorized(update):
            await _reject_unauthorized(update)
            return

        if update.message is None:
            return

        user_id = update.effective_user.id if update.effective_user else 0
        chat_id = update.message.chat_id

        raw_text: str = update.message.text or ""
        user_text = InputValidator.sanitize(raw_text)

        if user_text.isdigit():
            await resolve_selection(chat_id, int(user_text), update, context)
            return

        if _is_confirmation_reply(user_text):
            state = pending_confirmations.get(chat_id)
            if state is None:
                await update.message.reply_text("No pending confirmation.")
                return
            if time.time() - state["timestamp"] > _CONFIRMATION_TTL:
                _clear_confirmation(chat_id)
                await update.message.reply_text("Confirmation expired. Send the command again.")
                return

            action_id = state["action"]
            params = dict(state["params"])
            _clear_confirmation(chat_id)
            result = _execute_action(action_id, params, chat_id)
            ActionLogger.log_action(user_id, {"action": action_id, **params}, _result_message(result))

            if action_id == "open_app":
                _sync_pending_open_app(chat_id)

            await _reply_with_result(update, result)
            return

        if _is_cancel_reply(user_text):
            if chat_id in pending_confirmations:
                _clear_confirmation(chat_id)
                await update.message.reply_text("Cancelled.")
            else:
                await update.message.reply_text("No pending confirmation.")
            return

        _clear_pending(chat_id)

        intent = get_intent(user_text)
        action_id: str = intent["action"]
        params: dict[str, Any] = intent["params"]

        logger.info(
            "User '%s' -> intent='%s' params=%s",
            update.effective_user.username or update.effective_user.id,
            action_id,
            params,
        )

        guard_dict = {"action": action_id, **params}
        allowed, reason = ActionGuard.check(guard_dict)
        if not allowed:
            ActionLogger.log_action(user_id, guard_dict, f"BLOCKED: {reason}")
            await update.message.reply_text(f"Blocked: {reason}")
            return

        if _requires_confirmation(action_id):
            _store_confirmation(chat_id, action_id, params)
            await update.message.reply_text(
                f"Confirm `{action_id}`? Reply `yes` to continue or `cancel` to stop."
            )
            return

        result = _execute_action(action_id, params, chat_id)
        ActionLogger.log_action(user_id, guard_dict, _result_message(result))

        if action_id == "open_app":
            _sync_pending_open_app(chat_id)

        await _reply_with_result(update, result)

    except Exception as exc:
        logger.error("handle_message error: %s", exc, exc_info=True)
        if update.effective_message is not None:
            await update.effective_message.reply_text("Something went wrong.")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log all Telegram API or polling errors."""
    del update
    logger.error("Telegram error: %s", context.error, exc_info=True)


def run() -> None:
    """Build the Application, register handlers, and start polling."""
    _validate_token()

    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
    except InvalidToken as exc:
        raise ConfigurationError(
            "Invalid Telegram bot token. Create a bot with BotFather and set "
            "TELEGRAM_TOKEN to the token it gives you."
        ) from exc

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    logger.info("Bot is polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
