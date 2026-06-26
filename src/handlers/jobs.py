"""
IT: Job schedulati gestiti da `Application.job_queue`. Al momento solo il
    promemoria mensile, che invia un messaggio Telegram all'utente con il
    menu principale per invitarlo ad aggiornare il sistema.
EN: Scheduled jobs managed by `Application.job_queue`. Currently only the
    monthly reminder, which sends the user a Telegram message with the
    main menu inviting them to update the system.
"""
import logging

from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT, cfg_name, cfg_reminder
from lang import t
from ui import _main_menu_kb

log = logging.getLogger(__name__)

# =============================================================================
# PROMEMORIA MENSILE
# =============================================================================

async def monthly_reminder_job(ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Callback eseguita ogni mese al giorno/ora configurati in
        `stack_updater_config.json`. Invia un messaggio HTML con il
        nickname utente interpolato e il menu principale per facilitare
        l'avvio degli aggiornamenti.
    EN: Callback fired every month on the day/time configured in
        `stack_updater_config.json`. Sends an HTML message with the
        user's nickname interpolated, attaching the main menu so the
        user can start an update with one tap.
    """
    day, hour, minute = cfg_reminder()
    name = cfg_name()
    await ctx.bot.send_message(
        chat_id=AUTHORIZED_CHAT,
        text=t("monthly_reminder", name=name),
        parse_mode="HTML",
        reply_markup=_main_menu_kb(),
    )
