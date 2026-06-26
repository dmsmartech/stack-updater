"""
IT: Componenti UI condivisi a livello trasversale, usati sia dagli handler che
    dalle operations e dai job schedulati. Contiene solo elementi del menu
    principale, perché ogni altra schermata appartiene esclusivamente al layer
    handlers (vedi `handlers/shared.py`).
EN: Cross-cutting UI components used by handlers, operations and scheduled
    jobs alike. Only the main-menu primitives live here; every other screen
    belongs to the handlers layer (see `handlers/shared.py`).
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import cfg_name
from lang import t
from utils import kb

log = logging.getLogger(__name__)


# =============================================================================
# UI — MAIN MENU
# =============================================================================

def _main_menu_kb() -> InlineKeyboardMarkup:
    """
    IT: Costruisce la tastiera inline del menu principale (Aggiornamenti +
        Impostazioni). Esposta come funzione per essere riusata in ogni punto
        che mostra il menu principale (callback handler, job mensile, schermo
        post-riavvio).
    EN: Build the inline keyboard for the main menu (Updates + Settings).
        Exposed as a function so every place that shows the main menu
        (callback handlers, monthly job, post-reboot screen) can reuse it.

    Returns:
        InlineKeyboardMarkup con i due bottoni del menu principale /
        InlineKeyboardMarkup with the two main menu buttons.
    """
    return kb(
        InlineKeyboardButton(t("btn_updates"),  callback_data="nav:updates"),
        InlineKeyboardButton(t("btn_settings"), callback_data="nav:settings"),
    )


async def send_main_menu(bot, chat_id: int):
    """
    IT: Invia un nuovo messaggio con il menu principale, usato quando non c'è
        un messaggio precedente da editare (es. dopo un'operazione live che
        ha consumato il messaggio, o dopo il riavvio del bot).
    EN: Send a fresh message with the main menu, used when there is no prior
        message to edit (e.g. after a live operation that consumed its
        message, or after the bot restarts).

    Args:
        bot:     istanza del bot Telegram / Telegram bot instance.
        chat_id: id della chat di destinazione / target chat id.
    """
    name = cfg_name()
    await bot.send_message(
        chat_id=chat_id,
        text=t("main_menu", name=name),
        parse_mode="HTML",
        reply_markup=_main_menu_kb(),
    )
