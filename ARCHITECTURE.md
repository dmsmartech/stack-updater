# StackUpdater — Architecture & Developer Guide

## Overview

**StackUpdater** is a Telegram bot that automates two recurring sysadmin
chores on a single Debian/Ubuntu host:

- Keeping the operating system up to date (`apt-get update`,
  `apt-get upgrade`, `apt-get full-upgrade`, `apt-get autoremove`).
- Managing the lifecycle of Docker containers defined in a single
  `docker-compose.yml` file (`pull`, `up`, `down`, `restart`, `stop`,
  `start`, per-container or in bulk).

It also exposes a system reboot button, a monthly reminder, a self-update
flow (downloads a newer version of itself from GitHub and restarts via
systemd), and a settings section that lets the user change the
docker-compose directory, reminder schedule, language (IT / EN) and
nickname without touching files on the host.

Only one Telegram user — whose chat id is stored at install time — can
interact with the bot. Every operation runs as the system user that owns
the systemd unit (typically `root`).

## Project Structure

```
stack-updater/                     # repository root
├── install.sh                     # interactive installer / updater / uninstaller
├── VERSION                        # current release version (root, not in src/)
├── ARCHITECTURE.md
├── README.md
├── LICENSE
└── src/                           # all bot source — installed flat into INSTALL_DIR
    ├── stack_updater.py           # entry point: logging, ConversationHandler, polling
    ├── states.py                  # integer constants for the conversation states
    ├── config.py                  # paths + JSON config load/save + cfg_* accessors
    ├── utils.py                   # only_me, run_cmd, kb, edit, update_live, ...
    ├── lang.py                    # t(), switch_lang(), in-memory translations dict
    ├── version.py                 # VERSION, REPO_BASE, check_remote_version()
    ├── ui.py                      # send_main_menu, _main_menu_kb (cross-layer UI)
    ├── languages/
    │   ├── it.json                # Italian strings
    │   └── en.json                # English strings
    ├── handlers/                  # Telegram callback / message handlers
    │   ├── shared.py              # screens reused by multiple handlers
    │   ├── start.py               # /start + persistent "Menu" reply key
    │   ├── menu.py                # main menu, updates menu, update-available screen
    │   ├── system.py              # all system handlers: submenu, update, resources, reboot
    │   ├── docker.py              # Docker handlers: container list/detail/action/update
    │   ├── all_updates.py         # "Update All" flow handlers
    │   ├── settings.py            # settings menu + input handler + reminder reschedule
    │   └── jobs.py                # scheduled job callbacks (monthly reminder)
    ├── helpers/                   # low-level wrappers around system commands
    │   ├── system.py              # apt parsers + CPU / RAM / disk resource readers
    │   └── docker.py              # docker compose discovery + inspect + parsers
    └── operations/                # long-running async operations with live UI
        ├── core.py                # _core_system / _core_containers / ... primitives
        ├── system_ops.py          # standalone wrappers: _run_system, _run_autoremove, ...
        ├── docker_ops.py          # per-container actions + "update all containers"
        ├── all_ops.py             # "Update All" phases (system + containers)
        └── app_update.py          # self-update routine (download + restart)
```

> `install.sh` copies everything from `src/` flat into `INSTALL_DIR` (e.g. `/opt/StackUpdater/`),
> stripping the `src/` prefix. `VERSION` is fetched from the repo root, not from `src/`.

## Architecture Layers

The codebase is split into clear layers with a strict, non-cyclic
dependency direction:

```
config.py        → (no project deps)
utils.py         → config
version.py       → config, utils
lang.py          → config, utils, version
ui.py            → config, lang, utils
helpers/         → config, lang, utils
operations/      → config, lang, utils, helpers, ui
handlers/shared  → config, lang, utils, helpers.docker, ui
handlers/*       → operations, helpers, ui, handlers.shared, ...
stack_updater.py → everything
```

### Handlers (`handlers/`)

A handler is a Python coroutine wired to a state of the
`ConversationHandler`. Each handler:

1. Acknowledges the callback (`query.answer()`).
2. Dispatches on `query.data` (the callback id).
3. Either edits the current message with the next screen (UI transition)
   or delegates to an `operations.*` function for long-running work.
4. Returns the next conversation state (an integer from `states.py`) — or
   the same state to stay where it is.

Handlers never talk to `apt` / `docker` directly: they call `operations/`
or `helpers/`.

`handlers/shared.py` collects screens reused by more than one handler
(`_show_updates_menu`, `_show_system_menu`, `_show_containers_list`) so
sibling modules don't import each other.

Each handler file groups all flows that belong to the same domain:

- `handlers/system.py` — everything system-related: the System submenu
  (`system_menu_cb`), resource status (`system_status_cb`), the update
  flow (`system_info_cb`, `system_confirm_cb`, `system_running_cb`) and
  the reboot confirmation (`reboot_confirm_cb`).
- `handlers/docker.py` — everything Docker-related: container list, detail
  screen, per-container action confirm, and post-action state.

### Operations (`operations/`)

Operations encapsulate long-running async sequences (typically multiple
shell calls + live message updates). They:

- Render progress through `utils.update_live()` on a "live" Telegram
  message id captured at the start of the flow.
- Stash intermediate state into `ctx.user_data` (live message id,
  current lines, selected container, etc.) so a follow-up button can
  resume from where the previous step left off.
- Surface interactive buttons (Retry / Continue / Full upgrade / ...)
  whose callback ids are routed back into the handler that owns the
  state.

`operations/core.py` contains the heart of the apt and docker pipelines
as **parametric primitives**: the same `_core_system` is reused for the
standalone system flow and for the "Update All" pipeline by varying the
callback ids and the optional `on_success` continuation. This avoids
duplicating the apt error-handling / held-package / autoremove logic.

### Helpers (`helpers/`)

Stateless, side-effect-light wrappers around the system commands the bot
relies on:

- `helpers/system.py` — two sections in one file:
  - **apt/dpkg**: `get_upgradable_count()`, `parse_apt_problems()`,
    `parse_autoremove_packages()`, `parse_held_packages()`. Parsers are
    bilingual because apt follows the system locale.
  - **Resources**: `get_cpu_percent()` (reads `/proc/stat` twice 0.5 s
    apart), `get_ram_info()` (parses `free -b`), `get_disk_info()`
    (parses `df -h` for every `/dev/*` filesystem). Also provides
    `_bar(percent)` to build Unicode progress bars (`█░`) and
    `_human(bytes)` for human-readable sizes.
- `helpers/docker.py` — `docker compose ps`, `docker inspect`,
  image-id maps to detect real updates after `pull`, status formatters.

Helpers never touch the Telegram API and don't import handlers / operations.

### Shared Utilities

- `config.py` — file paths, JSON config load/save, `cfg_*` accessors
  that re-read the file each time (so changes from the Settings section
  apply without a restart).
- `utils.py` — `only_me` decorator (authorization), `run_cmd` (async
  subprocess), inline keyboard builders, `edit` (in-place message
  edit), `update_live` (length-aware live-message update).
- `lang.py` — `t(key, **kwargs)` returns the translated and interpolated
  string. The `L` dict is loaded at boot and replaced in place by
  `switch_lang()` so existing `t()` calls pick up the new language.
- `ui.py` — only the **truly cross-cutting** UI primitives
  (`_main_menu_kb`, `send_main_menu`) used by handlers, operations and
  scheduled jobs alike.
- `version.py` — `VERSION` constant, `REPO_BASE` raw URL, and
  `check_remote_version()` with a 24h cache.

## Data Flow

A complete request, taking "Update System" as an example:

```
User taps "Aggiornamenti" in the main menu
└─ ConversationHandler in state MAIN_MENU routes to main_menu_cb
   └─ data == "nav:updates" → handlers.shared._show_updates_menu(update)
      └─ returns state UPDATES_MENU

User taps "🖥️ System"
└─ updates_menu_cb (state UPDATES_MENU)
   └─ data == "nav:system_menu" → handlers.shared._show_system_menu(update)
      └─ returns state SYSTEM_MENU   (submenu with: Update / Resources / Reboot / Back)

User taps "🖥️ Aggiorna Sistema"
└─ system_menu_cb (state SYSTEM_MENU)
   └─ data == "sys:update"
      ├─ helpers.system.get_upgradable_count() → (count, distro)
      └─ if count > 0: edit with package summary + buttons
         returns state SYSTEM_INFO
      └─ if count == 0: calls _run_system directly
         returns state SYSTEM_RUNNING

User taps "📊 Stato Sistema"
└─ system_menu_cb (state SYSTEM_MENU)
   └─ data == "sys:resources"
      ├─ helpers.system.get_cpu_percent()  → 38.0
      ├─ helpers.system.get_ram_info()     → (61.2, "1.8 GB", "2.9 GB")
      ├─ helpers.system.get_disk_info()    → [(40.0, "12G", "32G", "/"), ...]
      └─ edit with Unicode bar display, returns state SYSTEM_STATUS

User taps "Aggiorna ora" (from SYSTEM_INFO)
└─ system_info_cb → "upd:system_confirm"
   └─ edit with Yes/← Sistema, returns SYSTEM_CONFIRM

User taps Yes
└─ system_confirm_cb → "run:system"
   └─ operations.system_ops._run_system(update, ctx)
      ├─ initializes lines, stores live_msg_id in ctx.user_data
      ├─ utils.update_live(...) — paints "Phase 1 running"
      └─ operations.core._core_system(..., retry_cb="run:system", ...)
         ├─ run_cmd(apt-get update)      → updates lines
         ├─ run_cmd(apt-get upgrade -y)  → updates lines
         ├─ if held packages → shows "Full upgrade" button
         ├─ if autoremovable → shows "Autoremove" button
         └─ else → shows "Main menu" button
      returns state SYSTEM_RUNNING

User taps "Autoremove" → system_running_cb routes to "apt:autoremove"
└─ operations.system_ops._run_autoremove(update, ctx)
   └─ operations.core._core_autoremove(...) → updates live message
```

The same shape applies to every flow: handler routes by callback id,
delegates UI transitions to `handlers/shared.py` or `ui.py`, delegates
long-running work to `operations/*`, which in turn invoke `helpers/*` for
the actual system commands.

## Adding a New Feature — Step by Step

Let's add a **"Network Status"** entry to the System submenu that shows
active network interfaces in a Telegram message.

### 1. Pick a state id and a callback prefix

Add a new state to `states.py`:

```python
(
    MAIN_MENU,
    UPDATES_MENU,
    SYSTEM_MENU,
    # ... existing states ...
    UPDATE_AVAILABLE,
    NETWORK_STATUS,      # ← new state
) = range(19)            # bump the range size
```

Pick a callback prefix — let's use `net:` for everything related.

### 2. Add the translation keys

In **both** `src/languages/en.json` and `src/languages/it.json`:

```json
{
  "btn_network_status": "🌐 Network Status",
  "network_status_title": "<b>🌐 Network Status</b>",
  "network_status_iface": "🔹 <b>{iface}</b>  <code>{addr}</code>"
}
```

### 3. Add the helper function

The feature reads network data — that's system information, so it belongs
in the existing `src/helpers/system.py`:

```python
async def get_network_info() -> list[tuple[str, str]]:
    """
    IT: Ritorna la lista di coppie (interfaccia, indirizzo IP) per le
        interfacce attive lette da `ip -brief addr`.
    EN: Return a list of (interface, IP address) pairs for active
        interfaces read from `ip -brief addr`.
    """
    _, out = await run_cmd(["ip", "-brief", "addr"])
    result = []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[1] == "UP":
            result.append((parts[0], parts[2]))
    return result
```

No new file needed — `helpers/system.py` already groups all OS-level
data helpers.

### 4. Add the button to the System submenu

In `src/handlers/shared.py`, `_show_system_menu`:

```python
await edit(update, t("system_menu_title"), kb(
    InlineKeyboardButton(t("btn_system_update"),   callback_data="sys:update"),
    InlineKeyboardButton(t("btn_system_status"),   callback_data="sys:resources"),
    InlineKeyboardButton(t("btn_network_status"),  callback_data="sys:network"),  # ← new
    InlineKeyboardButton(t("btn_back_updates"),    callback_data="nav:updates_menu"),
))
```

### 5. Add the handler

The feature is system-related, so it lives in the existing
`src/handlers/system.py`. Add:

- a new branch inside `system_menu_cb` to handle `sys:network`
- a new handler `network_status_cb` for the `NETWORK_STATUS` state

```python
# inside system_menu_cb, after the sys:resources block:
if data == "sys:network":
    from helpers.system import get_network_info
    ifaces = await get_network_info()
    lines = [t("network_status_title"), ""]
    lines += [t("network_status_iface", iface=i, addr=a) for i, a in ifaces]
    await edit(update, "\n".join(lines), kb(
        InlineKeyboardButton(t("btn_back_system"), callback_data="nav:system_menu"),
    ))
    return NETWORK_STATUS

# new handler for the NETWORK_STATUS state:
@only_me
async def network_status_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU
    return NETWORK_STATUS
```

### 6. Wire it into `stack_updater.py`

Import the new handler and state, extend the `SYS_MENU_CB` pattern and
register the new state:

```python
from handlers.system import (..., network_status_cb)
from states import (..., NETWORK_STATUS)

SYS_MENU_CB    = r"^(sys:(update|resources|network)|nav:updates_menu)$"
NET_STAT_CB    = r"^nav:system_menu$"

states = {
    # ... existing states ...
    NETWORK_STATUS: [CallbackQueryHandler(network_status_cb, pattern=NET_STAT_CB)],
}
```

### 7. Keep the file lists in sync

No new files were added (helper function went into `helpers/system.py`,
handler went into `handlers/system.py`), so **no changes** are needed to
`install.sh` or `operations/app_update.py`.

If you ever create a **new file**, add it to:
- `_bot_files` in `install.sh` → both `write_bot()` and `do_update()`
- `_BOT_FILES` in `src/operations/app_update.py`

Without this, the self-update will not deliver the new module.

### 8. Smoke test

```bash
python3 -c "
import ast, pathlib
for f in ['src/handlers/system.py', 'src/helpers/system.py', 'src/states.py', 'src/stack_updater.py']:
    ast.parse(pathlib.Path(f).read_text())
    print('OK', f)
"
sudo systemctl restart stack_updater
journalctl -u stack_updater -f
```

## Conversation States

States are plain integers defined as a `range(N)` tuple in `states.py` so
they auto-renumber when you add new ones. Each state is associated with
one or more `CallbackQueryHandler` (and/or `MessageHandler`) in
`stack_updater.py` under the `states={...}` dict of the
`ConversationHandler`.

For each state you must also define a regex `pattern` that matches the
callback ids the handler accepts. The pattern acts as a guard: a
callback that does not match is ignored and the state is not entered.

To add a new state:

1. Append a name to the tuple in `states.py` and bump `range(N)`.
2. Add a handler coroutine that returns the new state when the user
   moves *into* it and the appropriate next state when they move *out*.
3. Add the entry to the `states={}` dict in `stack_updater.py`, with a
   regex pattern that lists every callback id reachable from that state.

## Language System

`languages/<code>.json` files are flat key→string maps. Strings can
contain `{placeholders}` filled by `str.format` via `t(key, foo=bar)`.

At boot, `lang.py` loads the file matching `config["lang"]` (defaults to
"it") into a module-level dict `L`. `t()` looks up `L[key]`; if missing
it returns the key itself, which makes missing translations obvious in
the UI.

`switch_lang(code)`:

1. If the target file isn't local yet, downloads it from
   `REPO_BASE/src/languages/<code>.json`.
2. Persists `lang` in the config.
3. `L.clear() + L.update(load_lang())` so the in-memory dict reflects
   the new file without restarting the bot.

To add a new string:

1. Add the key/value pair to **both** `languages/it.json` and
   `languages/en.json`.
2. Call it with `t("my_new_key", placeholder=value)` from any module.

## Configuration

Configuration lives in `INSTALL_DIR/stack_updater_config.json` (mode 600).
It's a single flat JSON object that holds both user-controlled settings
(token, chat id, docker dir, reminder schedule, nickname, language) and
bot internal state (cached available version, "skipped" version,
pending-restart markers used by the self-update flow).

Reading:

- `config.load_config()` returns the parsed dict (empty on error).
- `config.cfg_name()`, `cfg_docker_dir()`, `cfg_reminder()`,
  `cfg_lang()` are convenience accessors that **re-read** the file each
  time, so changes made through the Settings section take effect
  immediately without a restart.
- `config.AUTHORIZED_CHAT` is read once at import time and used by the
  `@only_me` decorator.

Writing:

```python
from config import load_config, save_config
c = load_config()
c["my_new_field"] = "value"
save_config(c)
```

Always do a load → mutate → save cycle to avoid clobbering fields written
by another flow.

## Security Notes

- **Single authorized user.** The `@only_me` decorator in `utils.py`
  blocks any update whose `effective_user.id` differs from the
  configured `chat_id`. It's the first line of defense even though
  Telegram already filters at the chat level.
- **Token storage.** The bot token is stored in
  `stack_updater_config.json` with mode `600` (root-only readable),
  set by `install.sh`. Never log the token or echo it in messages.
- **Shell injection.** All shell calls go through `utils.run_cmd`,
  which uses `asyncio.create_subprocess_exec(*cmd, ...)` — arguments
  are passed as a list (no `shell=True`), so untrusted strings cannot
  be interpolated into a shell command. Be careful when adding new
  helpers: never build commands with f-strings into `shell=True`.
- **systemd reboot path.** `reboot_confirm_cb` invokes
  `/bin/systemctl reboot` with `/sbin/reboot` as fallback — absolute
  paths to avoid PATH-based attacks even though the bot already runs
  as root.
- **Self-update.** `_run_app_update` downloads files via `curl -fsSL`
  from `REPO_BASE` (raw GitHub URL of the project's `dev` branch).
  Anyone with push access to that branch can ship code that runs as
  root on every installation. Treat the upstream branch as part of
  the trust boundary.
- **No external auth.** There is no PAM / OAuth integration; the bot
  inherits the privileges of the systemd unit (typically root, needed
  for `apt-get` and system reboot).

## Running & Testing

### One-shot syntax check

```bash
for f in src/stack_updater.py src/states.py src/config.py src/utils.py \
         src/lang.py src/version.py src/ui.py \
         src/handlers/*.py src/helpers/*.py src/operations/*.py; do
    python3 -c "import ast; ast.parse(open('$f').read())" || echo "FAIL $f"
done
```

### Local development run

The bot needs `stack_updater_config.json` and write access to
`/var/log/stack_updater.log`. For local testing the easiest path is:

```bash
sudo touch /var/log/stack_updater.log
sudo chown $USER /var/log/stack_updater.log

# create a minimal config inside src/ (config.py looks next to stack_updater.py)
cat > src/stack_updater_config.json <<'EOF'
{
  "token": "<your-bot-token>",
  "chat_id": <your-chat-id>,
  "docker_dir": "/path/to/compose",
  "reminder_day": 10,
  "reminder_hour": 9,
  "reminder_minute": 0,
  "user_name": "Dev",
  "lang": "en"
}
EOF

pip3 install "python-telegram-bot[job-queue]"
python3 src/stack_updater.py
```

### Production install

```bash
curl -fsSL https://raw.githubusercontent.com/dmsmartech/stack-updater/dev/install.sh | sudo bash
```

The installer drops a systemd unit at `/etc/systemd/system/stack_updater.service`.
Useful commands:

```bash
sudo systemctl status   stack_updater
sudo systemctl restart  stack_updater
sudo journalctl -u      stack_updater -f
```

### Smoke test after a change

1. Send `/start` to the bot.
2. Open every menu reachable from the change you made.
3. Trigger the long-running operation if applicable and verify that the
   live message updates correctly and that the follow-up buttons (Retry,
   Continue, Main menu) all route back into the conversation.
4. Check `journalctl -u stack_updater -f` for warnings — `edit` and
   `update_live` log to `WARNING` if Telegram rejects an edit for any
   reason other than "not modified".
