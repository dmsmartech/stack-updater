"""
IT: Wrapper standalone delle operazioni sistema. Convertono un Update di
    Telegram in una chiamata al rispettivo core (`_core_system`,
    `_core_autoremove`, `_core_full_upgrade`) inizializzando il messaggio
    live e i callback id specifici del flusso "solo sistema" (separato da
    "Aggiorna Tutto").
EN: Standalone wrappers for the system-update operations. They translate a
    Telegram Update into a call to the matching core primitive
    (`_core_system`, `_core_autoremove`, `_core_full_upgrade`),
    initializing the live message and the callback ids specific to the
    "system only" flow (distinct from "Update All").
"""
import logging
from datetime import datetime

from telegram.ext import ContextTypes
from telegram import Update

from config import AUTHORIZED_CHAT
from lang import t
from operations.core import _core_system, _core_autoremove, _core_full_upgrade
from utils import update_live

log = logging.getLogger(__name__)

# =============================================================================
# OPERAZIONI — SISTEMA (wrapper standalone)
# =============================================================================

async def _run_system(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Avvia l'aggiornamento di sistema standalone: crea il messaggio live
        con header e titolo del passo 1, lo memorizza in `ctx.user_data` e
        invoca `_core_system` con le callback id del flusso standalone.
    EN: Kick off the standalone system update: build the live message with
        header and step-1 title, stash its id in `ctx.user_data`, then call
        `_core_system` with the standalone callback ids.
    """
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
    await _core_system(bot, msg_id, lines, ctx,
                       retry_cb="run:system",
                       full_upgrade_cb="apt:full_upgrade",
                       autoremove_cb="apt:autoremove")


async def _run_autoremove(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Avvia un autoremove standalone (di norma proposto dopo
        l'aggiornamento). Riprende le righe del messaggio live precedente
        se presenti in `ctx.user_data["live_lines"]`, così l'utente vede
        la cronologia completa.
    EN: Run a standalone autoremove (typically offered after an upgrade).
        Reuses the previous live-message lines stored in
        `ctx.user_data["live_lines"]` when present, so the user keeps the
        full history visible.
    """
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id

    lines = list(ctx.user_data.get("live_lines", [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
    ]))
    lines += [t("separator"), t("step_autoremove_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    await _core_autoremove(bot, msg_id, lines, ctx, retry_cb="apt:autoremove")


async def _run_full_upgrade(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Avvia un full-upgrade standalone, proposto quando `apt-get upgrade`
        ha lasciato pacchetti trattenuti. Come `_run_autoremove`, riusa le
        righe del messaggio live precedente.
    EN: Run a standalone full-upgrade, offered when `apt-get upgrade` left
        some packages held back. Like `_run_autoremove`, reuses the
        previous live-message lines.
    """
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id

    lines = list(ctx.user_data.get("live_lines", [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
    ]))
    lines += [t("separator"), t("step_full_upgrade_title"), t("step_full_upgrade_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    await _core_full_upgrade(bot, msg_id, lines, ctx,
                             retry_cb="apt:full_upgrade",
                             autoremove_cb="apt:autoremove")
