"""
IT: Entry point della conversazione Telegram: `/start` e tasto persistente
    "📋 Menu". Entrambi controllano se è disponibile una nuova versione del
    bot (con cache 24h) e — se sì e non è stata già "skippata" — mostrano
    prima la schermata di update. Altrimenti vanno direttamente al menu
    principale.
EN: Entry points of the Telegram conversation: `/start` command and the
    persistent "📋 Menu" reply-keyboard button. Both check for a new bot
    version (24 h cache) and — if one is available and not previously
    skipped — surface the update screen first. Otherwise they jump straight
    to the main menu.
"""
import html
import logging

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import cfg_name, load_config
from lang import t
from states import MAIN_MENU, UPDATE_AVAILABLE
from ui import _main_menu_kb
from utils import kb, only_me
from version import VERSION, check_remote_version

# =============================================================================
# ASCII LOGO — mostrato su /start come intestazione del menu principale
# ASCII LOGO — shown on /start as main-menu header
# =============================================================================

_ASCII_ART = (
    " ____  _____  _    ____ _  __\n"
    "/ ___|_   _|/ \\  / ___|| |/ /\n"
    "\\___ \\ | | / _ \\| |    | ' /\n"
    " ___) || |/ ___ \\ |___ | . \\\n"
    "|____/ |_/_/   \\_\\____||_|\\_\\\n"
    "\n"
    " _   _ ____  ____    _  _____ _____ ____\n"
    "| | | |  _ \\|  _ \\  / \\|_   _| ____|  _ \\\n"
    "| | | | |_) | | | |/ _ \\ | | |  _| | |_) |\n"
    "| |_| |  __/| |_| / ___ \\| | | |___|  _ <\n"
    " \\___/|_|   |____/_/   \\_\\_| |_____|_| \\_\\"
)

def _logo_header() -> str:
    """
    IT: Restituisce l'header ASCII art + versione pronto per reply_html.
    EN: Returns the ASCII art header + version ready for reply_html.
    """
    return f"<pre>{html.escape(_ASCII_ART)}\n\nv {VERSION}</pre>"

log = logging.getLogger(__name__)

# =============================================================================
# ENTRY POINT — /start e tasto Menu
# =============================================================================

@only_me
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Handler del comando `/start`. Controlla aggiornamenti disponibili —
        se ce ne sono e non sono stati saltati dall'utente, mostra la
        schermata UPDATE_AVAILABLE. Altrimenti mostra il menu principale.
    EN: `/start` command handler. Checks for available updates — if any
        and not previously skipped by the user, shows the UPDATE_AVAILABLE
        screen. Otherwise jumps straight to the main menu.

    Returns:
        Il prossimo stato della conversazione / next conversation state.
    """
    name = cfg_name()

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

    await update.message.reply_text("😊")
    await update.message.reply_html(
        t("main_menu", name=name),
        reply_markup=_main_menu_kb(),
    )
    return MAIN_MENU

@only_me
async def handle_menu_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Handler per il tasto "📋 Menu" della reply keyboard persistente.
        Logica identica a `cmd_start`: serve a riportare l'utente al menu
        principale da qualsiasi punto della chat.
    EN: Handler for the "📋 Menu" persistent reply-keyboard button. Same
        logic as `cmd_start`: lets the user jump back to the main menu
        from anywhere in the chat history.
    """
    name = cfg_name()

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
