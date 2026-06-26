#!/usr/bin/env python3
"""
IT: Punto di ingresso del bot Stack Updater — un bot Telegram per
    automatizzare aggiornamenti di sistema Debian e container Docker. Il
    file configura il logging, registra tutti gli handler della
    ConversationHandler con i pattern di callback per ogni stato, registra
    il job mensile di promemoria e avvia il polling. La funzione
    `post_init` riprende l'UX dopo un riavvio sistema o un self-update.
    Requisiti: pip3 install "python-telegram-bot[job-queue]"
    --break-system-packages
EN: Entry point of the Stack Updater bot — a Telegram bot that automates
    Debian system updates and Docker container updates. This file sets up
    logging, registers every handler of the ConversationHandler with the
    per-state callback patterns, schedules the monthly reminder job and
    launches the polling loop. The `post_init` function resumes the UX
    after a system reboot or a self-update.
    Requires: pip3 install "python-telegram-bot[job-queue]"
    --break-system-packages
"""

import logging
from datetime import datetime, time as dtime

from telegram import InlineKeyboardButton, Update
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)

# =============================================================================
# LOGGING — must be set up before any module import that uses logging
# =============================================================================
from config import LOG_FILE

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# =============================================================================
# PROJECT MODULES
# =============================================================================
from config import AUTHORIZED_CHAT, REBOOT_FLAG, load_config, save_config
from lang import t
from states import (
    ALL_CONFIRM, ALL_RUNNING, CONTAINER_CONFIRM, CONTAINER_DETAIL,
    CONTAINER_RUNNING, CONTAINERS_LIST, MAIN_MENU, REBOOT_CONFIRM,
    REBOOT_RUNNING, SETTINGS_INPUT, SETTINGS_MENU, SYSTEM_CONFIRM,
    SYSTEM_INFO, SYSTEM_MENU, SYSTEM_RUNNING, SYSTEM_STATUS,
    UPDATE_AVAILABLE, UPDATES_MENU,
)
from ui import _main_menu_kb, send_main_menu
from utils import kb

from handlers.start import cmd_start, handle_menu_key
from handlers.menu import (
    main_menu_cb, updates_menu_cb, update_available_cb, _global_new_main_cb
)
from handlers.system import (
    system_menu_cb, system_info_cb, system_confirm_cb,
    system_running_cb, system_status_cb, reboot_confirm_cb,
)
from handlers.docker import (
    containers_list_cb, container_detail_cb, container_confirm_cb, container_running_cb
)
from handlers.all_updates import all_confirm_cb, all_running_cb
from handlers.settings import settings_menu_cb, settings_input_handler
from handlers.jobs import monthly_reminder_job

# =============================================================================
# POST INIT
# =============================================================================

async def post_init(application):
    """
    IT: Hook eseguito da python-telegram-bot subito dopo l'inizializzazione
        dell'`Application`. Due responsabilità:
        1) se esiste il file `REBOOT_FLAG`, è il segnale che il sistema è
           appena stato riavviato dal bot: lo rimuove e invia un messaggio
           "riavvio completato".
        2) se il config contiene `update_restart_msg_id`, il bot si è
           riavviato a seguito di un self-update: edita il messaggio live
           originale con l'esito finale e il bottone "Menu principale".
    EN: Hook called by python-telegram-bot right after the `Application`
        is built. Two responsibilities:
        1) if `REBOOT_FLAG` exists, the system was just rebooted by the
           bot: remove the flag and send a "reboot done" message.
        2) if the config carries `update_restart_msg_id`, the bot just
           restarted after a self-update: edit the original live message
           with the final outcome plus a "Main menu" button.
    """
    from pathlib import Path

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

# =============================================================================
# MAIN
# =============================================================================

def main():
    """
    IT: Costruisce l'`Application` di python-telegram-bot, registra il
        `ConversationHandler` con i pattern di callback per ogni stato,
        l'handler globale per `nav:new_main`, schedula il job mensile e
        avvia il polling.
    EN: Build the python-telegram-bot `Application`, register the
        `ConversationHandler` with the per-state callback patterns, the
        global `nav:new_main` fallback handler, schedule the monthly job
        and start the polling loop.
    """
    cfg = load_config()
    app = Application.builder().token(cfg.get("token", "")).post_init(post_init).build()

    # Pattern dei callback ammessi in ciascuno stato della conversazione.
    # Tenere allineati con quelli usati dagli handler di ciascun layer.
    MAIN_CB       = r"^nav:(updates|settings)$"
    UPDATES_CB    = r"^(upd:|nav:(main|updates_menu|system_menu)|run:all|ct:)"
    SYS_MENU_CB   = r"^(sys:(update|resources|reboot)|nav:updates_menu)$"
    SYS_INFO_CB   = r"^(upd:system_confirm|nav:system_menu)$"
    SYS_CONF_CB   = r"^(run:system|nav:system_menu)$"
    SYS_RUN_CB    = r"^(run:system|nav:new_main|apt:autoremove|apt:full_upgrade)$"
    SYS_STAT_CB   = r"^(nav:system_menu|sys:resources)$"
    CT_LIST_CB    = r"^(ct:|nav:updates_menu)"
    CT_DETAIL_CB  = r"^(ct:confirm:|ct:back_list)"
    CT_CONF_CB    = r"^(ct:do_action|ct:back_detail:|ct:back_list|run:containers_all)"
    CT_RUN_CB     = r"^(ct:retry_action|ct:back_detail:|ct:back_list|ct:new_list|nav:new_main)"
    ALL_CONF_CB   = r"^(run:all|nav:updates_menu)$"
    ALL_RUN_CB    = r"^(run:all|run:containers_all|nav:new_main|all:(retry_system|do_full_upgrade|do_autoremove|continue_containers))$"
    REBOOT_CB     = r"^(run:reboot|nav:system_menu)$"
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
            SYSTEM_MENU:      [CallbackQueryHandler(system_menu_cb,       pattern=SYS_MENU_CB)],
            SYSTEM_INFO:      [CallbackQueryHandler(system_info_cb,       pattern=SYS_INFO_CB)],
            SYSTEM_CONFIRM:   [CallbackQueryHandler(system_confirm_cb,    pattern=SYS_CONF_CB)],
            SYSTEM_RUNNING:   [CallbackQueryHandler(system_running_cb,    pattern=SYS_RUN_CB)],
            SYSTEM_STATUS:    [CallbackQueryHandler(system_status_cb,     pattern=SYS_STAT_CB)],
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

    # Handler globale per nav:new_main — cattura il click sul pulsante
    # "Menu Principale" del messaggio di aggiornamento dopo il riavvio del
    # bot, quando non c'è nessuno stato conversazione attivo.
    app.add_handler(CallbackQueryHandler(_global_new_main_cb, pattern="^nav:new_main$"))

    tz = datetime.now().astimezone().tzinfo
    from config import cfg_reminder
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
