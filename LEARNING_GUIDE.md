# Local Assistant Project Learning Guide

## 1. Project Overview

### What the project does
This project is a Windows-only Telegram bot that lets you control a laptop from your phone. You send text commands in Telegram, the bot parses them into actions, validates them, and then uses Windows automation libraries to perform the action on the laptop.

### Key features
- Open, switch to, and close desktop apps.
- Search for files in the user home directory.
- Control brightness and, when available, volume.
- Type text and press key sequences such as `enter`, `ctrl+c`, and `alt+tab`.
- Send WhatsApp messages or open a WhatsApp chat from Telegram.
- Show system status such as battery, Wi-Fi, IP address, CPU, RAM, and disk usage.
- Open URLs, search Google, search YouTube, and run app-specific shortcuts.
- Create folders, move files, copy/paste clipboard contents, and run macros.
- Take screenshots and send them back through Telegram.

### Real-world use case
The main use case is remote desktop control from a phone. If your laptop is across the room, in another room, or attached to a TV, you can still launch apps, send a message, get system status, or capture a screenshot without touching the keyboard and mouse.

## 2. Architecture Breakdown

### High-level system design
The system is a pipeline:
1. Telegram receives a user message.
2. The bot sanitizes the text.
3. A rule-based parser converts the text into a structured intent.
4. A validator checks whether the action is safe and valid.
5. The action registry executes the matching handler.
6. The result is logged and sent back to Telegram.

The project is intentionally not AI-model-driven at runtime. It is rule-based and deterministic, which makes behavior easier to debug and safer for laptop control.

### Data flow
1. The user sends a command such as `open chrome` or `message Alex hi on whatsapp`.
2. `bot.py` receives the update from Telegram.
3. `InputValidator.sanitize()` normalizes the text.
4. `router.py` calls `intent_parser.parse()` and converts parser output into the action schema used by the bot.
5. `validator.py` runs `ActionGuard.check()` to verify parameters and policy rules.
6. `actions.py` looks up the handler in `ACTION_REGISTRY` and executes it.
7. The handler may launch an app, press keys, move files, or talk to WhatsApp.
8. `ActionLogger` writes the result to a local runtime log file.
9. The bot replies to Telegram, including a screenshot image if the action produced one.

### Components and responsibilities
- `main.py`: bootstrap and dependency installer.
- `bot.py`: Telegram application, command routing, confirmation flow, and response sending.
- `router.py`: adapter from raw parser output to the internal action format.
- `intent_parser.py`: rule-based natural language parsing.
- `validator.py`: security and parameter validation.
- `actions.py`: Windows automation logic and the action registry.
- `whatsapp_handler.py`: WhatsApp launching and message automation.
- `app_discovery.py`: scans the machine for installed apps and caches the results.
- `fuzzy_match.py`: finds close matches when the app name is slightly wrong.
- `key_sequence.py`: parses ordered keyboard instructions like `ctrl+c, enter`.
- `config.py`: environment settings, defaults, app allowlist, and feature flags.

### Tech stack used and why
- Python 3.14: modern language features and broad library support.
- `python-telegram-bot`: Telegram bot framework with async handlers and polling.
- `psutil`: system and process inspection.
- `pyautogui`: keyboard automation and some screenshot behavior.
- `pywinauto`: Windows UI focus and WhatsApp window automation.
- `pygetwindow`: window detection and basic window operations.
- `screen_brightness_control`: brightness management.
- `rapidfuzz`: fuzzy matching for app names.
- Windows shell and PowerShell: launching apps, clipboard operations, screenshot capture, and system commands.

## 3. File-by-File Explanation

### `main.py`
Purpose:
- Starts the application.
- Auto-installs required packages before importing the rest of the bot.
- Configures logging and handles top-level startup errors.

Key logic:
- `ensure_dependencies()` checks whether each required package exists and installs or upgrades it if needed.
- The logging setup writes to both the console and a local runtime log file.
- `ConfigurationError` is caught separately so missing setup is reported as a friendly message instead of a crash.

How it connects:
- This is the entry point.
- It imports `bot.run()` only after dependencies are in place.

### `bot.py`
Purpose:
- Handles Telegram polling and incoming messages.
- Routes user messages through validation, parsing, execution, and logging.

Key logic:
- `_validate_token()` ensures the Telegram token exists and looks valid.
- `start_command()` builds a help message using the actions that are actually available on the current machine.
- `handle_message()` is the main workflow:
  - sanitize input
  - resolve pending app selections
  - confirm dangerous commands
  - parse intent
  - validate intent
  - execute action
  - log result
- `_reply_with_result()` can send either text or a screenshot photo.

How it connects:
- `bot.py` is the orchestration layer between Telegram and the action engine.
- It depends on `router.py`, `validator.py`, and `actions.py`.

### `router.py`
Purpose:
- Converts parser output into the action schema expected by the bot.

Key logic:
- Maps simple parser actions like `open`, `close`, and `find` to internal IDs such as `open_app`, `close_app`, and `find_file`.
- Normalizes `target` into `app` for app commands.
- Ensures key-sequence commands preserve their `sequence` field.

How it connects:
- It is the bridge between the text parser and the action system.

### `intent_parser.py`
Purpose:
- Turns free-form text into a structured intent dictionary.

Key logic:
- Uses many regular expressions to detect command families such as:
  - app control
  - WhatsApp message and chat commands
  - screenshots
  - key sequences
  - browser commands
  - power commands
  - system status
  - filesystem actions
  - macros
- This parser is ordered carefully, because the first matching pattern wins.

How it connects:
- It is the “language understanding” layer, but deterministic.
- It must stay aligned with `validator.py` and `actions.py`.

### `validator.py`
Purpose:
- Prevents invalid or dangerous actions from executing.

Key logic:
- `InputValidator` cleans text and validates app names, contacts, message text, folder names, and simple strings.
- `ActionGuard.check()` enforces:
  - known action IDs
  - allowed action categories
  - parameter formats
  - command-specific constraints
- `ActionLogger` writes an audit trail to disk with rotation.

How it connects:
- It is the policy gate before execution.
- If the parser can produce an action but the guard rejects it, the bot reports a blocked command.

### `actions.py`
Purpose:
- Contains the real operational logic for every command.

Key logic:
- `Action` and `ActionResult` define the execution model.
- `ACTION_REGISTRY` is the central map from action ID to handler.
- `handle_open_app()` opens apps directly or by fuzzy match.
- `handle_close_app()` terminates matching processes or closes windows.
- `handle_screenshot()` captures the screen and returns a photo path for Telegram.
- `handle_press_keys()` runs ordered keyboard steps.
- `handle_message()` and `handle_open_chat()` drive WhatsApp automation.
- Other handlers cover clipboard, browser, window, file, battery, network, and macro actions.

How it connects:
- This is the execution engine.
- Everything the user can do is ultimately implemented here or delegated from here.

### `whatsapp_handler.py`
Purpose:
- Encapsulates WhatsApp-specific launching and messaging logic.

Key logic:
- Detects whether WhatsApp is already running.
- Searches common install locations and shortcuts.
- Opens WhatsApp Desktop or falls back to WhatsApp Web if allowed.
- Opens a chat by focusing the app, searching for a contact, and opening the result.
- Sends a message by typing after the chat is open.

How it connects:
- `actions.py` calls this module for all WhatsApp-related commands.

### `app_discovery.py`
Purpose:
- Scans common Windows locations for installed applications and caches the results.

Key logic:
- Walks through Start Menu, Desktop, Program Files, Windows Apps, and related folders.
- Skips noisy directories such as Recent, Temp, and Cache.
- Caches results in a local runtime app-cache file for faster startup.

How it connects:
- Used by app opening, fuzzy matching, and WhatsApp detection.

### `fuzzy_match.py`
Purpose:
- Handles approximate matching for app names.

Key logic:
- Uses `rapidfuzz.process.extract()` with `WRatio` to find near matches.
- Returns ranked results with scores.

How it connects:
- Used when the user says `open chrom` instead of `open chrome`.

### `key_sequence.py`
Purpose:
- Parses ordered keyboard instructions.

Key logic:
- Splits input on commas or the word `then`.
- Supports repeated keys with syntax like `enter x3`.
- Supports text steps such as `text:hello`.
- Normalizes aliases such as `control` to `ctrl`.

How it connects:
- Used by the `press_keys` action and validated by `validator.py`.

### `config.py`
Purpose:
- Stores environment-based configuration and defaults.

Key logic:
- Reads Telegram token, allowed Telegram user ID, WhatsApp path, and optional Nircmd path from environment variables.
- Defines the app allowlist.
- Defines supported action categories.
- Stores fuzzy matching thresholds and alarm sound path.

How it connects:
- Every other module reads settings from here.

### `startup.bat`
Purpose:
- Convenience launcher for Windows startup.

Key logic:
- Runs `python main.py`.
- Includes comments for adding it to the Windows Startup folder.

How it connects:
- This is the easiest way to auto-start the assistant on login.

## 4. Core Concepts Required

### Programming concepts
- Variables, functions, conditionals, loops, dictionaries, lists, and classes.
- Regular expressions for command parsing.
- Exception handling for safe automation.
- Type hints and dataclasses.
- Async programming in Telegram handlers.
- Process management and subprocess execution.
- File system operations and path handling.

### Library and framework knowledge
- `python-telegram-bot` polling, handlers, updates, and messages.
- `psutil` process and system inspection.
- `pyautogui` for keyboard input.
- `pywinauto` and `pygetwindow` for UI/window automation.
- `screen_brightness_control` for display control.
- `rapidfuzz` for fuzzy string matching.

### System design concepts
- Command pipeline architecture.
- Separation of parsing, validation, and execution.
- Registry pattern for actions.
- Allowlisting and policy gates.
- Optional feature detection based on local machine capabilities.
- Audit logging.

### Tools and environment
- Windows command line and PowerShell.
- Telegram BotFather and bot tokens.
- Git and file inspection.
- Python package management with pip.
- Local environment variables.

## 5. Skill Gap Roadmap

### Beginner

#### Python fundamentals
- Learn: strings, lists, dicts, functions, imports, loops, and exceptions.
- Why needed: every module depends on these basics.
- Practice:
  - Write a function that normalizes text.
  - Parse a simple command string into a dictionary.
  - Catch and report errors cleanly.

#### File and path handling
- Learn: `pathlib`, `os.path`, file existence, directory creation.
- Why needed: app discovery, screenshots, downloads, and file moves all rely on paths.
- Practice:
  - Create a folder if it does not exist.
  - Find a file by name inside a directory tree.

#### Regular expressions
- Learn: anchors, groups, optional sections, and `re.IGNORECASE`.
- Why needed: the command parser is mostly regex-driven.
- Practice:
  - Detect `open chrome`.
  - Detect `message Alex hi on whatsapp`.
  - Detect `press ctrl+c, enter`.

### Intermediate

#### API-based Telegram bots
- Learn: bot tokens, polling, handlers, message replies, and async callbacks.
- Why needed: Telegram is the user interface for the whole project.
- Practice:
  - Reply to `/start`.
  - Echo a received message.
  - Send a photo back to the chat.

#### Windows automation
- Learn: window focus, hotkeys, process termination, launching apps.
- Why needed: this project controls the laptop directly.
- Practice:
  - Open Notepad.
  - Type text.
  - Press `alt+tab`.
  - Close a window.

#### Validation and guardrails
- Learn: input sanitization, allowlists, and parameter checks.
- Why needed: the bot should not blindly run dangerous input.
- Practice:
  - Reject invalid folder names.
  - Reject unsupported platforms.
  - Require confirmation for shutdown.

#### Process and service inspection
- Learn: `psutil`, process names, process termination, and running-state checks.
- Why needed: closing apps and checking availability depend on it.
- Practice:
  - List running processes.
  - Find whether WhatsApp is running.

### Advanced

#### Architecture and maintainability
- Learn: module boundaries, registries, adapters, and separation of concerns.
- Why needed: this project has many actions and needs to stay scalable.
- Practice:
  - Add a new action without changing the parser everywhere.
  - Refactor a handler into a helper module.

#### UI automation reliability
- Learn: focus management, window title matching, timing, and fallback strategies.
- Why needed: WhatsApp and app switching are brittle if timing is not handled carefully.
- Practice:
  - Re-focus an app after it opens.
  - Retry when a window is not yet ready.

#### Security and safety design
- Learn: confirmation flows, local authorization, logging, and least privilege.
- Why needed: the bot can do destructive things like shutdown or file moves.
- Practice:
  - Add confirmations for dangerous actions.
  - Restrict the bot to one Telegram user ID.

#### Windows-specific integration
- Learn: clipboard APIs, screenshot capture, shell commands, special folders, and app shortcuts.
- Why needed: the project is intentionally Windows-oriented.
- Practice:
  - Read and write clipboard contents.
  - Open the Downloads folder.
  - Capture the desktop and send the image.

## 6. Step-by-Step Rebuild Plan

### Milestone 1: Skeleton
- Create a Python project with a `main.py` entry point.
- Add logging.
- Add dependency installation or a `requirements.txt`.
- Confirm the bot can start without crashing.

Common mistakes:
- Starting Telegram before the token is configured.
- Importing optional modules too early.

### Milestone 2: Telegram interface
- Create a bot with BotFather.
- Implement polling and a `/start` command.
- Echo test messages.
- Add authorization by Telegram user ID.

Common mistakes:
- Forgetting to restrict who can control the laptop.
- Treating every Telegram message as trusted input.

### Milestone 3: Parsing layer
- Build a rule-based parser with regex patterns.
- Convert raw text into structured intents.
- Keep parser output stable and simple.

Common mistakes:
- Mixing parsing, validation, and execution in the same function.
- Writing overly broad regexes that misclassify commands.

### Milestone 4: Validation and policy
- Add an action registry.
- Add guard rules for app names, text, contacts, and file paths.
- Require confirmation for dangerous actions.
- Add audit logging.

Common mistakes:
- Allowing arbitrary shell commands.
- Accepting file paths outside the intended scope.

### Milestone 5: Desktop control
- Implement app launch and close.
- Add window focus and key-sequence support.
- Add clipboard, browser, and system-status actions.

Common mistakes:
- Assuming one executable name will work on every machine.
- Forgetting that GUI automation needs timing delays.

### Milestone 6: WhatsApp integration
- Detect WhatsApp availability.
- Open the app or web fallback.
- Open a chat.
- Send a message.

Common mistakes:
- Hardcoding a single window title or process name.
- Assuming the search box behaves the same across WhatsApp versions.

### Milestone 7: Quality and polish
- Add fuzzy matching for app names.
- Add user-friendly help output.
- Send screenshot photos directly to Telegram.
- Keep runtime feature detection in sync with help text.

Common mistakes:
- Showing commands in help that are unavailable on the current machine.
- Letting runtime behavior drift away from documented examples.

## 7. Deep Explanation of Logic

### Why the project uses a rule-based parser instead of a model
The bot needs to be predictable. If a user types `close whatsapp`, the system should always interpret that the same way. A rule-based parser gives:
- deterministic behavior
- easier debugging
- fewer false positives
- more direct safety control

The tradeoff is that you must manually add patterns for new commands.

### Mental model for the action pipeline
Think of the system as a factory line:
- `intent_parser.py` is the intake scanner.
- `validator.py` is the safety inspector.
- `actions.py` is the machinery.
- `bot.py` is the coordinator that speaks to the customer.

This separation is what makes the codebase understandable. A new command should not force you to rewrite the entire bot.

### Why `ACTION_REGISTRY` matters
The registry is the central catalog of what the bot can do. Instead of hardcoding many `if` or `match` statements, the project maps action IDs to handler functions. This gives:
- a single source of truth
- easier help generation
- easier validation
- easier feature toggles

If you want to add a new command, the ideal flow is:
1. add parser support
2. add validation
3. add handler
4. register the action
5. add a help example

### Why confirmation is used for destructive actions
Actions like shutdown, restart, sign out, sleep, and file move can cause real harm or disruption. The confirmation layer prevents accidental execution from a mistyped message. This is a basic safety design pattern: high-risk actions should require explicit approval.

### Why WhatsApp automation is tricky
WhatsApp Desktop is a GUI app, not a stable API. That means the bot must interact with:
- windows
- focus state
- timing
- keyboard shortcuts
- UI variations between versions

Because of that, the implementation uses fallbacks:
- open the app if it is not running
- bring the window to the foreground
- search for the contact
- open the chat
- type the message

### Why screenshots are sent as `ActionResult`
Screenshots are not just text. The bot needs to return both:
- a user-readable caption
- a file path that can be uploaded to Telegram

That is why `ActionResult` exists. It lets one action return richer output without inventing a separate response system.

## 8. Improvements and Critique

### What is poorly designed or fragile
- `main.py` auto-installs dependencies at runtime. This is convenient, but risky and slow.
- The Telegram token should only come from environment variables. Do not hardcode it in the repo.
- WhatsApp automation depends on UI behavior that may change across versions.
- Screenshot capture relies on Windows desktop APIs and can fail in non-interactive environments.
- `actions.py` is large and is doing too many things at once.

### Better alternatives
- Move dependency installation into a one-time setup script or pinned virtual environment.
- Remove hardcoded secrets and require environment variables.
- Split `actions.py` into smaller modules:
  - `actions_app.py`
  - `actions_system.py`
  - `actions_browser.py`
  - `actions_whatsapp.py`
- Use a more structured UI automation layer for WhatsApp if long-term reliability matters.
- Add tests around parser, validation, and command routing.

### Scalability considerations
- As the command list grows, a single parser file will become harder to maintain.
- The app discovery cache can become stale if installed programs change often.
- More actions will increase the importance of good help generation and feature detection.
- Windows automation is inherently brittle, so retries and explicit error messages matter.

### Suggested refactors for expert-level quality
- Move the command grammar into a declarative table or a small parser framework.
- Make every action handler return a standardized result type.
- Add unit tests for `intent_parser.py`, `validator.py`, and `key_sequence.py`.
- Separate “what the bot understands” from “what the machine can actually do.”
- Replace ad hoc helper functions with small service classes where state is meaningful.

## Rebuild Summary
If you were rebuilding this from scratch, the right order would be:
1. Telegram bot skeleton.
2. Parser and validation.
3. Action registry.
4. App launching and system info.
5. Key sequences and clipboard.
6. Screenshot and Telegram file replies.
7. WhatsApp automation.
8. Fuzzy matching, discovery, and macros.
9. Safety, logging, and polish.

The big lesson is that this is not just “a Telegram bot.” It is a layered Windows automation system with strict input parsing, safety controls, and many machine-specific fallbacks.
