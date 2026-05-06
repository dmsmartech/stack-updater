#!/usr/bin/env python3
"""
stack_updater.py — Telegram Bot for automated Debian + Docker updates
Requires: pip3 install "python-telegram-bot[job-queue]" --break-system-packages
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, time as dtime
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)
from telegram.error import BadRequest

# =============================================================================
# FILE PATHS  (tutto relativo alla cartella del bot — indipendente dall'install dir)
# =============================================================================
INSTALL_DIR = Path(__file__).parent          # es. /opt/StackUpdater
CONFIG_FILE = INSTALL_DIR / "stack_updater_config.json"
LANG_DIR    = INSTALL_DIR / "languages"      # es. /opt/StackUpdater/languages/
LOG_FILE    = "/var/log/stack_updater.log"
REBOOT_FLAG = "/var/lib/stack_updater_rebooted"

# Versione corrente del bot (aggiornata ad ogni release)
VERSION = "1.0.2"

# URL base del repository per download aggiornamenti
REPO_BASE = "https://raw.githubusercontent.com/dmsmartech/stack-updater/dev"

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# =============================================================================
# CONVERSATION STATES
# =============================================================================
(
    MAIN_MENU,
    UPDATES_MENU,
    SYSTEM_INFO,
    SYSTEM_CONFIRM,
    SYSTEM_RUNNING,
    CONTAINERS_LIST,
    CONTAINER_DETAIL,
    CONTAINER_CONFIRM,
    CONTAINER_RUNNING,
    ALL_CONFIRM,
    ALL_RUNNING,
    REBOOT_CONFIRM,
    REBOOT_RUNNING,
    SETTINGS_MENU,
    SETTINGS_INPUT,
    UPDATE_AVAILABLE,
) = range(16)

# =============================================================================
# CONFIG
# =============================================================================

def load_config() -> dict:
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception as e:
        log.error("Impossibile caricare config: %s", e)
        return {}

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log.error("Impossibile salvare config: %s", e)

cfg = load_config()
HOSTNAME        = os.uname().nodename
AUTHORIZED_CHAT = cfg.get("chat_id", 0)

# =============================================================================
# LINGUA
# =============================================================================

def load_lang() -> dict:
    lang = load_config().get("lang", "it")
    lang_file = LANG_DIR / f"{lang}.json"
    try:
        with open(lang_file) as f:
            return json.load(f)
    except Exception as e:
        log.warning("Lingua non caricata (%s): %s", lang_file, e)
        return {}

L = load_lang()

def t(key: str, **kwargs) -> str:
    template = L.get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template

def cfg_name() -> str:
    return load_config().get("user_name", "")

def cfg_docker_dir() -> str:
    return load_config().get("docker_dir", "")

def cfg_reminder() -> tuple:
    c = load_config()
    return c.get("reminder_day", 10), c.get("reminder_hour", 9), c.get("reminder_minute", 0)

def cfg_lang() -> str:
    return load_config().get("lang", "it")

async def switch_lang(lang_code: str) -> bool:
    """Cambia la lingua attiva. Scarica il file se non presente."""
    lang_file = LANG_DIR / f"{lang_code}.json"
    if not lang_file.exists():
        LANG_DIR.mkdir(parents=True, exist_ok=True)
        code, _ = await run_cmd([
            "curl", "-fsSL", "--max-time", "15",
            f"{REPO_BASE}/languages/{lang_code}.json",
            "-o", str(lang_file),
        ])
        if code != 0 or not lang_file.exists():
            return False
    c = load_config()
    c["lang"] = lang_code
    save_config(c)
    L.clear()
    L.update(load_lang())
    return True

# =============================================================================
# VERSION CHECK
# =============================================================================

def parse_version(v: str) -> tuple:
    """Converte una stringa versione in tupla per confronto."""
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)

async def check_remote_version() -> str | None:
    """Controlla la versione remota (cache 24h). Ritorna la versione disponibile o None."""
    c = load_config()
    last_check = c.get("last_version_check", 0)
    now = time.time()

    # Usa cache se il controllo è stato fatto nelle ultime 24 ore
    if now - last_check < 86400:
        cached = c.get("available_version", "")
        if cached and parse_version(cached) > parse_version(VERSION):
            return cached
        return None

    # Scarica il file VERSION dal repo
    code, out = await run_cmd([
        "curl", "-fsSL", "--max-time", "5", f"{REPO_BASE}/VERSION"
    ])
    if code != 0:
        return None

    remote = out.strip()
    c["last_version_check"] = now

    if remote and parse_version(remote) > parse_version(VERSION):
        c["available_version"] = remote
    else:
        c.pop("available_version", None)

    save_config(c)
    return c.get("available_version") or None

# =============================================================================
# HELPERS
# =============================================================================

PERSISTENT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📋 Menu")]],
    resize_keyboard=True,
)

def only_me(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if uid != AUTHORIZED_CHAT:
            return ConversationHandler.END
        return await func(update, ctx)
    return wrapper

async def run_cmd(cmd: list, cwd: str = None) -> tuple:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace").strip()

def truncate(text: str, limit: int = 600) -> str:
    return ("…\n" + text[-limit:]) if len(text) > limit else text

def kb(*rows) -> InlineKeyboardMarkup:
    """Costruisce una InlineKeyboardMarkup con ogni elemento su riga separata."""
    return InlineKeyboardMarkup([[btn] for btn in rows])

def kb_rows(*rows) -> InlineKeyboardMarkup:
    """Costruisce una InlineKeyboardMarkup da righe già formate (liste di bottoni)."""
    return InlineKeyboardMarkup(list(rows))

async def edit(update: Update, text: str, keyboard: InlineKeyboardMarkup = None):
    """Modifica il messaggio corrente — usato per tutte le transizioni di schermata."""
    query = update.callback_query
    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("edit error: %s", e)

async def send_main_menu(bot, chat_id: int):
    """Invia un nuovo messaggio con il menu principale (usato post-operazione)."""
    name = cfg_name()
    await bot.send_message(
        chat_id=chat_id,
        text=t("main_menu", name=name),
        parse_mode="HTML",
        reply_markup=kb(
            InlineKeyboardButton(t("btn_updates"),  callback_data="nav:updates"),
            InlineKeyboardButton(t("btn_settings"), callback_data="nav:settings"),
        ),
    )

def _main_menu_kb() -> InlineKeyboardMarkup:
    return kb(
        InlineKeyboardButton(t("btn_updates"),  callback_data="nav:updates"),
        InlineKeyboardButton(t("btn_settings"), callback_data="nav:settings"),
    )

# =============================================================================
# DOCKER HELPERS
# =============================================================================

async def get_containers() -> list[dict]:
    """Ritorna lista di tutti i container (running e stoppati) con service, name, image, tag, stato."""
    _, out = await run_cmd([
        "docker", "compose", "ps", "-a",
        "--format", "{{.Service}}\t{{.Name}}\t{{.Image}}\t{{.Status}}"
    ], cwd=cfg_docker_dir())
    containers = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            service = parts[0].strip()
            name    = parts[1].strip()
            image   = parts[2].strip()
            status  = parts[3].strip()
            tag     = image.split(":")[-1] if ":" in image else "latest"
            img     = image.split(":")[0] if ":" in image else image
            containers.append({"service": service, "name": name, "image": img, "tag": tag, "status": status})
    return containers

async def get_upgradable_count() -> tuple[int, str]:
    """Ritorna (numero pacchetti aggiornabili, nome distro)."""
    await run_cmd(["apt-get", "update", "-qq"])
    _, out = await run_cmd(["apt", "list", "--upgradable"])
    lines = [l for l in out.splitlines() if "/" in l]
    count = len(lines)
    _, distro_out = await run_cmd(["lsb_release", "-ds"])
    distro = distro_out.strip() or "Linux"
    return count, distro

def is_container_running(status: str) -> bool:
    """Ritorna True se il container è in esecuzione."""
    low = status.lower()
    return "up" in low or "running" in low

def container_status_label(status: str) -> str:
    low = status.lower()
    if "up" in low or "running" in low:
        return t("container_running")
    if "exited" in low:
        return t("container_exited")
    return t("container_stopped")

def parse_apt_problems(output: str) -> list:
    return [l.strip() for l in output.splitlines()
            if any(k in l.lower() for k in ("err:", "e:", "warning:", "failed", "unable to"))]

def parse_docker_problems(output: str) -> list:
    return list(dict.fromkeys(
        "• " + l.strip() for l in output.splitlines()
        if any(k in l.lower() for k in ("error", "failed", "exited"))
    ))

# =============================================================================
# LIVE MESSAGE HELPER (per operazioni lunghe)
# =============================================================================

async def create_live(bot, chat_id: int, text: str) -> int:
    msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    return msg.message_id

async def update_live(bot, chat_id: int, msg_id: int,
                      lines: list, keyboard: InlineKeyboardMarkup = None):
    text = "\n".join(lines)
    if len(text) > 4000:
        text = lines[0] + "\n…\n" + "\n".join(lines[-(len(lines)//2):])
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode="HTML",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("update_live error: %s", e)

# =============================================================================
# ENTRY POINT — /start e tasto Menu
# =============================================================================

@only_me
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = cfg_name()

    # Controlla aggiornamenti disponibili
    available = await check_remote_version()
    c = load_config()
    skipped = c.get("skipped_version", "")

    if available and available != skipped:
        await update.message.reply_html(
            t("update_available", version=available),
            reply_markup=kb(
                InlineKeyboardButton(t("btn_update_app"),  callback_data="app:update"),
                InlineKeyboardButton(t("btn_skip_update"), callback_data="nav:skip_update"),
            ),
        )
        return UPDATE_AVAILABLE

    await update.message.reply_html(
        t("main_menu", name=name),
        reply_markup=_main_menu_kb(),
    )
    return MAIN_MENU

@only_me
async def handle_menu_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = cfg_name()

    # Controlla aggiornamenti disponibili
    available = await check_remote_version()
    c = load_config()
    skipped = c.get("skipped_version", "")

    if available and available != skipped:
        await update.message.reply_html(
            t("update_available", version=available),
            reply_markup=kb(
                InlineKeyboardButton(t("btn_update_app"),  callback_data="app:update"),
                InlineKeyboardButton(t("btn_skip_update"), callback_data="nav:skip_update"),
            ),
        )
        return UPDATE_AVAILABLE

    await update.message.reply_html(
        t("main_menu", name=name),
        reply_markup=_main_menu_kb(),
    )
    return MAIN_MENU

# =============================================================================
# UPDATE AVAILABLE callbacks
# =============================================================================

@only_me
async def update_available_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "app:update":
        await _run_app_update(update, ctx)
        return UPDATE_AVAILABLE

    if data == "nav:skip_update":
        # Salva la versione saltata per non mostrare più la notifica
        c = load_config()
        skipped = c.get("available_version", "")
        if skipped:
            c["skipped_version"] = skipped
            save_config(c)
        # Mostra il menu principale editando il messaggio corrente
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    return UPDATE_AVAILABLE

# =============================================================================
# MAIN MENU callbacks
# =============================================================================

@only_me
async def main_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:updates":
        await edit(update, t("updates_menu"), kb(
            InlineKeyboardButton(t("btn_update_system"),     callback_data="upd:system_info"),
            InlineKeyboardButton(t("btn_update_containers"), callback_data="upd:containers_list"),
            InlineKeyboardButton(t("btn_update_all"),        callback_data="upd:all_confirm"),
            InlineKeyboardButton(t("btn_reboot"),            callback_data="upd:reboot_confirm"),
            InlineKeyboardButton(t("btn_back_main"),         callback_data="nav:main"),
        ))
        return UPDATES_MENU

    if data == "nav:settings":
        await _show_settings(update)
        return SETTINGS_MENU

    return MAIN_MENU

# =============================================================================
# UPDATES MENU callbacks
# =============================================================================

@only_me
async def updates_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:main":
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    if data == "upd:system_info":
        await edit(update, "⏳ Recupero informazioni sistema…")
        count, distro = await get_upgradable_count()
        ctx.user_data["pkg_count"] = count
        if count == 0:
            await edit(update,
                t("system_info_title") + "\n\n" +
                t("system_info_distro", distro=distro) + "\n" +
                t("system_info_uptodate"),
                kb(InlineKeyboardButton(t("btn_back_updates"), callback_data="nav:updates_menu"))
            )
        else:
            await edit(update,
                t("system_info_title") + "\n\n" +
                t("system_info_distro", distro=distro) + "\n" +
                t("system_info_packages", count=count),
                kb(
                    InlineKeyboardButton(t("btn_do_update_system"), callback_data="upd:system_confirm"),
                    InlineKeyboardButton(t("btn_back_updates"),     callback_data="nav:updates_menu"),
                )
            )
        return SYSTEM_INFO

    if data == "upd:containers_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data == "upd:all_confirm":
        await edit(update, t("confirm_update_all"), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:all"),
            InlineKeyboardButton(t("btn_no"),  callback_data="nav:updates_menu"),
        ))
        return ALL_CONFIRM

    if data == "upd:reboot_confirm":
        await edit(update, t("confirm_reboot", hostname=HOSTNAME), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:reboot"),
            InlineKeyboardButton(t("btn_no"),  callback_data="nav:updates_menu"),
        ))
        return REBOOT_CONFIRM

    if data == "nav:updates_menu":
        await edit(update, t("updates_menu"), kb(
            InlineKeyboardButton(t("btn_update_system"),     callback_data="upd:system_info"),
            InlineKeyboardButton(t("btn_update_containers"), callback_data="upd:containers_list"),
            InlineKeyboardButton(t("btn_update_all"),        callback_data="upd:all_confirm"),
            InlineKeyboardButton(t("btn_reboot"),            callback_data="upd:reboot_confirm"),
            InlineKeyboardButton(t("btn_back_main"),         callback_data="nav:main"),
        ))
        return UPDATES_MENU

    return UPDATES_MENU

# =============================================================================
# SYSTEM INFO → CONFIRM → RUNNING
# =============================================================================

@only_me
async def system_info_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "upd:system_confirm":
        count = ctx.user_data.get("pkg_count", 0)
        await edit(update, t("system_confirm", count=count), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:system"),
            InlineKeyboardButton(t("btn_no"),  callback_data="upd:system_info"),
        ))
        return SYSTEM_CONFIRM

    if data in ("upd:system_info", "nav:updates_menu"):
        return await updates_menu_cb(update, ctx)

    return SYSTEM_INFO

@only_me
async def system_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:system":
        await _run_system(update, ctx)
        return SYSTEM_RUNNING

    if data == "upd:system_info":
        return await updates_menu_cb(update, ctx)

    return SYSTEM_CONFIRM

@only_me
async def system_running_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:system":
        await _run_system(update, ctx)
        return SYSTEM_RUNNING

    if data == "nav:new_main":
        await send_main_menu(update.get_bot(), AUTHORIZED_CHAT)
        return MAIN_MENU

    return SYSTEM_RUNNING

# =============================================================================
# CONTAINERS LIST → DETAIL → CONFIRM → RUNNING
# =============================================================================

async def _show_containers_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE, send_new: bool = False):
    containers = await get_containers()
    ctx.user_data["containers"] = containers
    if not containers:
        text = t("containers_list_title") + "\n\n" + t("no_containers")
        keyboard = kb(InlineKeyboardButton(t("btn_back_updates"), callback_data="nav:updates_menu"))

        if send_new:
            await update.get_bot().send_message(
                chat_id=AUTHORIZED_CHAT,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await edit(update, text, keyboard)
        return
    def _ct_label(c: dict) -> str:
        icon = "🟢" if is_container_running(c["status"]) else "🟠"
        return f"{icon} {c['name']}"

    btns = [InlineKeyboardButton(_ct_label(c), callback_data=f"ct:detail:{c['service']}")
            for c in containers]
    btns.append(InlineKeyboardButton(t("btn_update_all_containers"), callback_data="ct:all_confirm"))
    btns.append(InlineKeyboardButton(t("btn_back_updates"), callback_data="nav:updates_menu"))

    keyboard = InlineKeyboardMarkup([[b] for b in btns])
    text = t("containers_list_title")

    if send_new:
        await update.get_bot().send_message(
            chat_id=AUTHORIZED_CHAT,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await edit(update, text, keyboard)

@only_me
async def containers_list_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:updates_menu":
        return await updates_menu_cb(update, ctx)

    if data == "ct:all_confirm":
        await edit(update, t("confirm_update_all_containers"), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:containers_all"),
            InlineKeyboardButton(t("btn_no"),  callback_data="ct:back_list"),
        ))
        return CONTAINER_CONFIRM

    if data.startswith("ct:detail:"):
        cname = data.split(":", 2)[2]
        ctx.user_data["selected_container"] = cname
        await _show_container_detail(update, ctx, cname)
        return CONTAINER_DETAIL

    if data == "ct:back_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    return CONTAINERS_LIST

async def _show_container_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE, cname: str):
    containers = ctx.user_data.get("containers", [])
    ct = next((c for c in containers if c["service"] == cname), None)
    if not ct:
        await _show_containers_list(update, ctx, False)
        return
    status_label = container_status_label(ct["status"])
    text = t("container_detail_title",
             name=ct["name"], image=ct["image"], tag=ct["tag"], status=status_label)

    if is_container_running(ct["status"]):
        # Container avviato: mostra tutti i controlli
        await edit(update, text, kb(
            InlineKeyboardButton(t("btn_restart_container"), callback_data="ct:confirm:restart"),
            InlineKeyboardButton(t("btn_stop_container"),    callback_data="ct:confirm:stop"),
            InlineKeyboardButton(t("btn_down_container"),    callback_data="ct:confirm:down"),
            InlineKeyboardButton(t("btn_update_container"),  callback_data="ct:confirm:update"),
            InlineKeyboardButton(t("btn_back_updates"),      callback_data="ct:back_list"),
        ))
    else:
        # Container fermo o rimosso: mostra solo Avvia e Aggiorna
        await edit(update, text, kb(
            InlineKeyboardButton(t("btn_start_container"),  callback_data="ct:confirm:start"),
            InlineKeyboardButton(t("btn_update_container"), callback_data="ct:confirm:update"),
            InlineKeyboardButton(t("btn_back_updates"),     callback_data="ct:back_list"),
        ))

@only_me
async def container_detail_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cname = ctx.user_data.get("selected_container", "")

    if data == "ct:back_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data.startswith("ct:confirm:"):
        action = data.split(":")[2]
        ctx.user_data["ct_action"] = action
        confirm_key = {
            "start":   "confirm_start_container",
            "restart": "confirm_restart_container",
            "stop":    "confirm_stop_container",
            "down":    "confirm_down_container",
            "update":  "confirm_update_container",
        }.get(action, "confirm_update_container")
        await edit(update, t(confirm_key, name=cname), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="ct:do_action"),
            InlineKeyboardButton(t("btn_no"),  callback_data=f"ct:back_detail:{cname}"),
        ))
        return CONTAINER_CONFIRM

    return CONTAINER_DETAIL

@only_me
async def container_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cname = ctx.user_data.get("selected_container", "")

    if data == "ct:do_action":
        action = ctx.user_data.get("ct_action", "")
        await _run_container_action(update, ctx, cname, action)
        return CONTAINER_RUNNING

    if data.startswith("ct:back_detail:"):
        await _show_container_detail(update, ctx, cname)
        return CONTAINER_DETAIL

    if data == "ct:back_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data == "run:containers_all":
        await _run_containers_all(update, ctx)
        return ALL_RUNNING

    return CONTAINER_CONFIRM

@only_me
async def container_running_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    cname = ctx.user_data.get("selected_container", "")
    action = ctx.user_data.get("ct_action", "")

    if data == "ct:retry_action":
        await _run_container_action(update, ctx, cname, action)
        return CONTAINER_RUNNING

    if data.startswith("ct:back_detail:"):
        # Ricarica i container prima di mostrare il dettaglio
        containers = await get_containers()
        ctx.user_data["containers"] = containers
        await _show_container_detail(update, ctx, cname)
        return CONTAINER_DETAIL

    if data == "ct:new_list":
        await _show_containers_list(update, ctx, True)
        return CONTAINERS_LIST

    if data == "nav:new_main":
        await send_main_menu(update.get_bot(), AUTHORIZED_CHAT)
        return MAIN_MENU

    return CONTAINER_RUNNING

# =============================================================================
# ALL CONFIRM → RUNNING
# =============================================================================

@only_me
async def all_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:all":
        await _run_all(update, ctx)
        return ALL_RUNNING

    if data == "nav:updates_menu":
        return await updates_menu_cb(update, ctx)

    return ALL_CONFIRM

@only_me
async def all_running_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ("run:all", "run:containers_all"):
        if data == "run:all":
            await _run_all(update, ctx)
        else:
            await _run_containers_all(update, ctx)
        return ALL_RUNNING

    if data == "nav:new_main":
        await send_main_menu(update.get_bot(), AUTHORIZED_CHAT)
        return MAIN_MENU

    return ALL_RUNNING

# =============================================================================
# REBOOT CONFIRM → RUNNING
# =============================================================================

@only_me
async def reboot_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:reboot":
        await edit(update, t("reboot_bye", hostname=HOSTNAME))
        Path(REBOOT_FLAG).write_text(str(AUTHORIZED_CHAT))
        await asyncio.sleep(2)
        try:
            subprocess.Popen(["/bin/systemctl", "reboot"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.Popen(["/sbin/reboot"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return REBOOT_RUNNING

    if data == "nav:updates_menu":
        return await updates_menu_cb(update, ctx)

    return REBOOT_CONFIRM

# =============================================================================
# SETTINGS
# =============================================================================

def _settings_kb() -> InlineKeyboardMarkup:
    return kb(
        InlineKeyboardButton(t("btn_settings_dir"),      callback_data="set:ask:dir"),
        InlineKeyboardButton(t("btn_settings_day"),      callback_data="set:ask:day"),
        InlineKeyboardButton(t("btn_settings_time"),     callback_data="set:ask:time"),
        InlineKeyboardButton(t("btn_settings_username"), callback_data="set:ask:username"),
        InlineKeyboardButton(t("btn_settings_lang"),     callback_data="set:ask:lang"),
        InlineKeyboardButton(t("btn_settings_updates"),  callback_data="set:check:updates"),
        InlineKeyboardButton(t("btn_back_main"),         callback_data="nav:main_from_settings"),
    )

async def _show_settings(update: Update):
    await edit(update, t("settings_menu"), _settings_kb())

@only_me
async def settings_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    c = load_config()
    day, hour, minute = cfg_reminder()

    if data == "nav:main_from_settings":
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    back_kb = kb(InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"))

    if data == "set:ask:dir":
        ctx.user_data["setting_key"] = "dir"
        await edit(update, t("settings_ask_dir", current=c.get("docker_dir", "")), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:day":
        ctx.user_data["setting_key"] = "day"
        await edit(update, t("settings_ask_day", current=str(day)), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:time":
        now = datetime.now().astimezone()
        system_time = now.strftime("%H:%M")
        timezone = now.tzinfo
        ctx.user_data["setting_key"] = "time"
        current_time = f"{hour:02d}:{minute:02d}"
        await edit(update, t("settings_ask_time", current=current_time, system_time=system_time, timezone=timezone), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:username":
        ctx.user_data["setting_key"] = "username"
        await edit(update, t("settings_ask_username", current=c.get("user_name", "")), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:lang":
        ctx.user_data["setting_key"] = "lang"
        lang_names = {"it": "Italiano", "en": "English"}
        current_label = lang_names.get(cfg_lang(), cfg_lang())
        await edit(update, t("settings_ask_lang", current=current_label), back_kb)
        return SETTINGS_INPUT

    if data == "set:check:updates":
        # Controlla aggiornamenti e mostra risultato
        await edit(update, t("settings_checking_updates"))
        # Forza un controllo fresco resettando il timestamp
        cfg_tmp = load_config()
        cfg_tmp.pop("last_version_check", None)
        save_config(cfg_tmp)
        available = await check_remote_version()
        if available and parse_version(available) > parse_version(VERSION):
            await edit(update,
                t("settings_update_found", current=VERSION, latest=available),
                kb(
                    InlineKeyboardButton(t("btn_update_app"),  callback_data="set:do:update"),
                    InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"),
                )
            )
        else:
            await edit(update, t("settings_no_updates", version=VERSION), back_kb)
        return SETTINGS_MENU

    if data == "set:do:update":
        await _run_app_update(update, ctx)
        return SETTINGS_MENU

    if data == "set:back":
        await _show_settings(update)
        return SETTINGS_MENU

    return SETTINGS_MENU

@only_me
async def settings_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Riceve il testo inserito dall'utente per le impostazioni."""
    text = update.message.text.strip()
    key  = ctx.user_data.get("setting_key", "")
    c    = load_config()

    if key == "dir":
        if not Path(text).is_dir():
            await update.message.reply_html(t("settings_invalid_dir"))
            return SETTINGS_INPUT
        c["docker_dir"] = text
        save_config(c)
        await update.message.reply_html(t("settings_saved_dir", value=text), reply_markup=_settings_kb())

    elif key == "day":
        if not text.isdigit() or not (1 <= int(text) <= 28):
            await update.message.reply_html(t("settings_invalid_day"))
            return SETTINGS_INPUT
        c["reminder_day"] = int(text)
        save_config(c)
        _reschedule_reminder(ctx)
        await update.message.reply_html(t("settings_saved_day", value=text), reply_markup=_settings_kb())

    elif key == "time":
        if not re.match(r"^\d{2}:\d{2}$", text):
            await update.message.reply_html(t("settings_invalid_time"))
            return SETTINGS_INPUT
        hh, mm = int(text[:2]), int(text[3:])
        if hh > 23 or mm > 59:
            await update.message.reply_html(t("settings_invalid_time"))
            return SETTINGS_INPUT
        c["reminder_hour"]   = hh
        c["reminder_minute"] = mm
        save_config(c)
        _reschedule_reminder(ctx)
        await update.message.reply_html(t("settings_saved_time", value=text), reply_markup=_settings_kb())

    elif key == "username":
        if not text:
            return SETTINGS_INPUT
        c["user_name"] = text
        save_config(c)
        await update.message.reply_html(t("settings_saved_username", value=text), reply_markup=_settings_kb())

    elif key == "lang":
        lang_map = {
            "it": "it", "italiano": "it", "italian": "it",
            "en": "en", "english": "en", "inglese": "en",
        }
        lang_code = lang_map.get(text.lower())
        if not lang_code:
            await update.message.reply_html(t("settings_invalid_lang"))
            return SETTINGS_INPUT
        if not await switch_lang(lang_code):
            await update.message.reply_html(t("settings_invalid_lang"))
            return SETTINGS_INPUT
        lang_label = "Italiano" if lang_code == "it" else "English"
        # settings_kb deve essere ricostruita dopo il cambio lingua (L è già aggiornato)
        await update.message.reply_html(
            t("settings_saved_lang", value=lang_label),
            reply_markup=_settings_kb()
        )

    return SETTINGS_MENU

def _reschedule_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    """Rimuove e ricrea il job del promemoria con i nuovi valori."""
    jq = ctx.application.job_queue
    for job in jq.get_jobs_by_name("monthly_reminder"):
        job.schedule_removal()
    day, hour, minute = cfg_reminder()
    tz = datetime.now().astimezone().tzinfo
    jq.run_monthly(
        monthly_reminder_job,
        when=dtime(hour, minute, tzinfo=tz),
        day=day,
        name="monthly_reminder",
    )
    log.info("Promemoria ripianificato: giorno %d alle %02d:%02d", day, hour, minute)

# =============================================================================
# OPERAZIONI — AGGIORNAMENTO BOT
# =============================================================================

async def _run_app_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Scarica la nuova versione del bot e si riavvia via systemd."""
    query    = update.callback_query
    bot      = update.get_bot()
    msg_id   = query.message.message_id
    c        = load_config()
    new_version = c.get("available_version", "?")
    start_dt    = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = [
        t("live_header", datetime=start_dt),
        t("separator"),
        t("step_update_title"),
        t("step_update_download"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # Download nuovo bot
    tmp_bot = INSTALL_DIR / "stack_updater.py.new"
    code, out = await run_cmd([
        "curl", "-fsSL", "--max-time", "30",
        f"{REPO_BASE}/stack_updater.py", "-o", str(tmp_bot),
    ])
    if code != 0 or not tmp_bot.exists():
        lines.append(t("step_update_error") + t("error_detail", detail=truncate(out)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"),
        ))
        return

    # Download nuovi file lingua
    LANG_DIR.mkdir(parents=True, exist_ok=True)
    for lang_code in ["it", "en"]:
        await run_cmd([
            "curl", "-fsSL", "--max-time", "10",
            f"{REPO_BASE}/languages/{lang_code}.json",
            "-o", str(LANG_DIR / f"{lang_code}.json"),
        ])

    # Download nuovo VERSION
    await run_cmd([
        "curl", "-fsSL", "--max-time", "10",
        f"{REPO_BASE}/VERSION", "-o", str(INSTALL_DIR / "VERSION"),
    ])

    # Aggiorna config: rimuovi tracking aggiornamenti, salva stato per il post-restart
    c.pop("available_version", None)
    c.pop("skipped_version", None)
    c.pop("last_version_check", None)
    c["update_restart_msg_id"]   = msg_id
    c["update_restart_version"]  = new_version
    c["update_restart_datetime"] = start_dt
    save_config(c)

    # Sostituisce atomicamente il bot file
    shutil.move(str(tmp_bot), str(INSTALL_DIR / "stack_updater.py"))

    lines.append(t("step_update_ok", version=new_version))
    lines.append("")
    lines.append(t("step_update_restarting"))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # Riavvia il servizio dopo 3 secondi (il bot ha tempo di inviare il messaggio)
    await asyncio.sleep(1)
    subprocess.Popen(
        ["bash", "-c", "sleep 3 && systemctl restart stack_updater"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

# =============================================================================
# OPERAZIONI — SISTEMA
# =============================================================================

async def _run_system(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id
    ctx.user_data["live_msg_id"] = msg_id

    lines = [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
        t("step_system_title", n=1),
        t("step_system_running"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # apt update
    code, out = await run_cmd(["apt-get", "update", "-q"])
    if code != 0:
        lines.append(t("step_system_error") + t("error_detail", detail=truncate(out)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:system"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    # apt upgrade
    code, out = await run_cmd(["apt-get", "upgrade", "-y", "-q"])
    problems = parse_apt_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_system_warning") if problems else t("step_system_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:system"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_system_ok"))
    lines.append(t("separator"))
    lines.append("🎉 <b>Aggiornamento sistema completato!</b>")
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
        InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
    ))

# =============================================================================
# OPERAZIONI — SINGOLO CONTAINER
# =============================================================================

async def _run_container_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                                 cname: str, action: str):
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id
    ctx.user_data["live_msg_id"] = msg_id

    title_key = {
        "start":   "step_single_start",
        "restart": "step_single_restart",
        "stop":    "step_single_stop",
        "down":    "step_single_down",
        "update":  "step_single_update",
    }.get(action, "step_single_update")

    lines = [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
        t(title_key, name=cname),
        t("step_single_running"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    docker_dir = cfg_docker_dir()
    code = 0

    if action == "start":
        code, out = await run_cmd(["docker", "compose", "up", "-d", cname], cwd=docker_dir)
    elif action == "restart":
        code, out = await run_cmd(["docker", "compose", "restart", cname], cwd=docker_dir)
    elif action == "stop":
        code, out = await run_cmd(["docker", "compose", "stop", cname], cwd=docker_dir)
    elif action == "down":
        code, out = await run_cmd(["docker", "compose", "rm", "-sf", cname], cwd=docker_dir)
    elif action == "update":
        code, out = await run_cmd(["docker", "compose", "pull", cname], cwd=docker_dir)
        if code == 0:
            code, out = await run_cmd(["docker", "compose", "up", "-d", cname], cwd=docker_dir)

    if code != 0:
        lines.append(t("step_single_error") + t("error_detail", detail=truncate(out)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),        callback_data="ct:retry_action"),
            InlineKeyboardButton(t("btn_back_updates"), callback_data=f"ct:back_detail:{cname}"),
        ))
        return

    lines.append(t("step_single_ok"))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
        InlineKeyboardButton(t("btn_back_updates"), callback_data="ct:new_list"),
    ))

# =============================================================================
# OPERAZIONI — TUTTI I CONTAINER
# =============================================================================

async def _run_containers_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id
    ctx.user_data["live_msg_id"] = msg_id
    docker_dir = cfg_docker_dir()

    lines = [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
        t("step_pull_title", n=1),
        t("step_pull_running"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    code, out = await run_cmd(["docker", "compose", "pull"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_pull_warning") if problems else t("step_pull_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:containers_all"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_pull_ok"))
    lines.append(t("separator"))
    lines.append(t("step_up_title", n=2))
    lines.append(t("step_up_running"))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    code, out = await run_cmd(["docker", "compose", "up", "-d"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_up_warning") if problems else t("step_up_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:containers_all"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_up_ok"))
    lines.append(t("separator"))
    lines.append(t("step_cleanup_running"))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    _, prune_out = await run_cmd(["docker", "image", "prune", "-f"])
    match = re.search(r"Total reclaimed space: (.+)", prune_out)
    space = t("space_freed", space=match.group(1)) if match else ""
    lines.append(t("step_cleanup_ok", space=space))

    containers = await get_containers()
    ct_status = "\n".join(f"{c['name']}: {c['status']}" for c in containers) or t("no_containers")
    lines.append(t("final_ok", containers=ct_status))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
        InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
    ))

# =============================================================================
# OPERAZIONI — TUTTO (sistema + container)
# =============================================================================

async def _run_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id
    ctx.user_data["live_msg_id"] = msg_id
    docker_dir = cfg_docker_dir()

    lines = [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
        t("step_system_title", n=1),
        t("step_system_running"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # Step 1 — sistema
    code, out = await run_cmd(["apt-get", "update", "-q"])
    if code == 0:
        code, out = await run_cmd(["apt-get", "upgrade", "-y", "-q"])
    problems = parse_apt_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_system_warning") if problems else t("step_system_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:all"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return
    lines.append(t("step_system_ok"))

    # Step 2 — docker pull
    lines += [t("separator"), t("step_pull_title", n=2), t("step_pull_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    code, out = await run_cmd(["docker", "compose", "pull"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_pull_warning") if problems else t("step_pull_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:all"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return
    lines.append(t("step_pull_ok"))

    # Step 3 — docker up
    lines += [t("separator"), t("step_up_title", n=3), t("step_up_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    code, out = await run_cmd(["docker", "compose", "up", "-d"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_up_warning") if problems else t("step_up_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data="run:all"),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return
    lines.append(t("step_up_ok"))

    # Pulizia
    lines += [t("separator"), t("step_cleanup_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    _, prune_out = await run_cmd(["docker", "image", "prune", "-f"])
    match = re.search(r"Total reclaimed space: (.+)", prune_out)
    space = t("space_freed", space=match.group(1)) if match else ""
    lines.append(t("step_cleanup_ok", space=space))

    containers = await get_containers()
    ct_status = "\n".join(f"{c['name']}: {c['status']}" for c in containers) or t("no_containers")
    lines.append(t("final_ok", containers=ct_status))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
        InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
    ))

# =============================================================================
# PROMEMORIA MENSILE
# =============================================================================

async def monthly_reminder_job(ctx: ContextTypes.DEFAULT_TYPE):
    day, hour, minute = cfg_reminder()
    name = cfg_name()
    await ctx.bot.send_message(
        chat_id=AUTHORIZED_CHAT,
        text=t("monthly_reminder", name=name),
        parse_mode="HTML",
        reply_markup=_main_menu_kb(),
    )

# =============================================================================
# MAIN
# =============================================================================

def main():

    async def post_init(application):
        # Controlla flag di riavvio sistema
        flag = Path(REBOOT_FLAG)
        if flag.exists():
            try:
                flag.unlink()
            except Exception:
                pass
            await application.bot.send_message(
                chat_id=AUTHORIZED_CHAT,
                text=t("reboot_done"),
                parse_mode="HTML",
                reply_markup=_main_menu_kb(),
            )

        # Controlla se il bot si è riavviato dopo un aggiornamento self-update
        c = load_config()
        restart_msg_id  = c.pop("update_restart_msg_id", None)
        restart_version = c.pop("update_restart_version", None)
        restart_dt      = c.pop("update_restart_datetime", "")
        if restart_msg_id:
            save_config(c)
            lines = [
                t("live_header", datetime=restart_dt),
                t("separator"),
                t("step_update_title"),
                t("step_update_download"),
                t("step_update_ok", version=restart_version or "?"),
                "",
                t("step_update_restarted"),
            ]
            try:
                await application.bot.edit_message_text(
                    chat_id=AUTHORIZED_CHAT,
                    message_id=restart_msg_id,
                    text="\n".join(lines),
                    parse_mode="HTML",
                    reply_markup=kb(
                        InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
                    ),
                )
            except Exception as e:
                log.warning("Impossibile editare messaggio post-aggiornamento: %s", e)

    app = Application.builder().token(cfg.get("token", "")).post_init(post_init).build()

    # Pattern per i callback di ogni stato
    MAIN_CB       = r"^nav:(updates|settings)$"
    UPDATES_CB    = r"^(upd:|nav:(main|updates_menu)|run:(reboot|all)|ct:)"
    SYS_INFO_CB   = r"^(upd:system_confirm|nav:updates_menu|upd:system_info)$"
    SYS_CONF_CB   = r"^(run:system|upd:system_info)$"
    SYS_RUN_CB    = r"^(run:system|nav:new_main)$"
    CT_LIST_CB    = r"^(ct:|nav:updates_menu)"
    CT_DETAIL_CB  = r"^(ct:confirm:|ct:back_list)"
    CT_CONF_CB    = r"^(ct:do_action|ct:back_detail:|ct:back_list|run:containers_all)"
    CT_RUN_CB     = r"^(ct:retry_action|ct:back_detail:|ct:new_list|nav:new_main)"
    ALL_CONF_CB   = r"^(run:all|nav:updates_menu)$"
    ALL_RUN_CB    = r"^(run:all|run:containers_all|nav:new_main)$"
    REBOOT_CB     = r"^(run:reboot|nav:updates_menu)$"
    SETTINGS_CB   = r"^(set:|nav:(main_from_settings|back))"
    UPD_AVAIL_CB  = r"^(app:update|nav:skip_update)$"

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT & filters.Regex("^📋 Menu$"), handle_menu_key),
        ],
        states={
            MAIN_MENU:        [CallbackQueryHandler(main_menu_cb,         pattern=MAIN_CB)],
            UPDATES_MENU:     [CallbackQueryHandler(updates_menu_cb,      pattern=UPDATES_CB)],
            SYSTEM_INFO:      [CallbackQueryHandler(system_info_cb,       pattern=SYS_INFO_CB)],
            SYSTEM_CONFIRM:   [CallbackQueryHandler(system_confirm_cb,    pattern=SYS_CONF_CB)],
            SYSTEM_RUNNING:   [CallbackQueryHandler(system_running_cb,    pattern=SYS_RUN_CB)],
            CONTAINERS_LIST:  [CallbackQueryHandler(containers_list_cb,   pattern=CT_LIST_CB)],
            CONTAINER_DETAIL: [CallbackQueryHandler(container_detail_cb,  pattern=CT_DETAIL_CB)],
            CONTAINER_CONFIRM:[CallbackQueryHandler(container_confirm_cb, pattern=CT_CONF_CB)],
            CONTAINER_RUNNING:[CallbackQueryHandler(container_running_cb, pattern=CT_RUN_CB)],
            ALL_CONFIRM:      [CallbackQueryHandler(all_confirm_cb,       pattern=ALL_CONF_CB)],
            ALL_RUNNING:      [CallbackQueryHandler(all_running_cb,       pattern=ALL_RUN_CB)],
            REBOOT_CONFIRM:   [CallbackQueryHandler(reboot_confirm_cb,    pattern=REBOOT_CB)],
            SETTINGS_MENU:    [CallbackQueryHandler(settings_menu_cb,     pattern=SETTINGS_CB)],
            SETTINGS_INPUT:   [
                CallbackQueryHandler(settings_menu_cb, pattern=r"^set:back$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, settings_input_handler),
            ],
            UPDATE_AVAILABLE: [CallbackQueryHandler(update_available_cb,  pattern=UPD_AVAIL_CB)],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.TEXT & filters.Regex("^📋 Menu$"), handle_menu_key),
        ],
        per_message=False,
        allow_reentry=True,
    )

    app.add_handler(conv)

    # Handler globale per nav:new_main — cattura il click sul pulsante "Menu Principale"
    # del messaggio di aggiornamento dopo il riavvio del bot (nessun stato conversazione attivo)
    async def _global_new_main_cb(upd: Update, _ctx: ContextTypes.DEFAULT_TYPE):
        query = upd.callback_query
        if not query:
            return
        if upd.effective_user and upd.effective_user.id != AUTHORIZED_CHAT:
            return
        await query.answer()
        await send_main_menu(upd.get_bot(), AUTHORIZED_CHAT)

    app.add_handler(CallbackQueryHandler(_global_new_main_cb, pattern="^nav:new_main$"))

    tz = datetime.now().astimezone().tzinfo

    day, hour, minute = cfg_reminder()
    app.job_queue.run_monthly(
        monthly_reminder_job,
        when=dtime(hour, minute, tzinfo=tz),
        day=day,
        name="monthly_reminder",
    )

    log.info("Bot started — polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
