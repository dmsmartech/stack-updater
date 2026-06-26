"""
IT: Handler del flusso "Aggiorna Tutto" (sistema + container). Sequenza:
    ALL_CONFIRM → ALL_RUNNING. Lo stato ALL_RUNNING gestisce tutti i
    bottoni di follow-up del messaggio live (retry sistema, do_full_upgrade,
    do_autoremove, continue_containers, menu principale) — ogni opzione
    delega a una fase di `operations.all_ops`.
EN: Handlers for the "Update All" flow (system + containers). Sequence:
    ALL_CONFIRM → ALL_RUNNING. The ALL_RUNNING state dispatches every
    follow-up button of the live message (system retry, do_full_upgrade,
    do_autoremove, continue_containers, main menu) — each delegating to a
    phase function in `operations.all_ops`.
"""
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT
from lang import t
from operations.all_ops import (
    _all_autoremove_phase, _all_containers_phase, _all_full_upgrade_phase,
    _all_system_phase, _run_all
)
from operations.docker_ops import _run_containers_all
from states import ALL_CONFIRM, ALL_RUNNING, MAIN_MENU, UPDATES_MENU
from handlers.shared import _show_updates_menu
from ui import send_main_menu
from utils import edit, kb, only_me, update_live

log = logging.getLogger(__name__)

# =============================================================================
# ALL CONFIRM → RUNNING
# =============================================================================

@only_me
async def all_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato ALL_CONFIRM: "Sì" lancia `_run_all`, "No" torna al menu
        updates.
    EN: ALL_CONFIRM state: "Yes" launches `_run_all`, "No" returns to
        the updates menu.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:all":
        await _run_all(update, ctx)
        return ALL_RUNNING

    if data == "nav:updates_menu":
        await _show_updates_menu(update)
        return UPDATES_MENU

    return ALL_CONFIRM

@only_me
async def all_running_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato ALL_RUNNING: dispatcher dei bottoni del messaggio live. Le
        righe correnti sono lette da `ctx.user_data["live_lines"]` per
        riprendere la cronologia. Il caso `all:retry_system` ricostruisce
        un fresh state (così header e step sono nuovi e l'utente non
        confonde il retry con l'errore precedente).
    EN: ALL_RUNNING state: live-message button dispatcher. Current lines
        come from `ctx.user_data["live_lines"]` to preserve history. The
        `all:retry_system` branch rebuilds a fresh state (so the header
        and step are new and the user doesn't confuse the retry with the
        previous error).
    """
    query = update.callback_query
    await query.answer()
    data  = query.data
    bot   = update.get_bot()
    msg_id = query.message.message_id
    lines  = list(ctx.user_data.get("live_lines", []))

    if data == "run:all":
        await _run_all(update, ctx)
        return ALL_RUNNING

    if data == "run:containers_all":
        await _run_containers_all(update, ctx)
        return ALL_RUNNING

    if data == "all:retry_system":
        fresh = [
            t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
            t("separator"),
            t("step_system_title", n=1),
            t("step_system_running"),
        ]
        ctx.user_data["live_lines"] = fresh
        await update_live(bot, AUTHORIZED_CHAT, msg_id, fresh)
        await _all_system_phase(bot, msg_id, fresh, ctx)
        return ALL_RUNNING

    if data == "all:do_full_upgrade":
        await _all_full_upgrade_phase(bot, msg_id, lines, ctx)
        return ALL_RUNNING

    if data == "all:do_autoremove":
        await _all_autoremove_phase(bot, msg_id, lines, ctx)
        return ALL_RUNNING

    if data == "all:continue_containers":
        await _all_containers_phase(bot, msg_id, lines, ctx)
        return ALL_RUNNING

    if data == "nav:new_main":
        await send_main_menu(bot, AUTHORIZED_CHAT)
        return MAIN_MENU

    return ALL_RUNNING
