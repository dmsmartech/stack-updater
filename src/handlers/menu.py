"""
IT: Handler del menu principale, del menu aggiornamenti e della schermata
    "aggiornamento bot disponibile". Contiene anche il fallback globale
    `_global_new_main_cb` per il bottone "Menu principale" che compare nel
    messaggio post-riavvio quando la conversazione non è più attiva.
EN: Handlers for the main menu, the updates menu and the "bot update
    available" screen. Also includes the global fallback
    `_global_new_main_cb` for the "Main menu" button shown in the post-
    restart message when the conversation is no longer active.
"""
import logging

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT, cfg_name, load_config, save_config
from lang import t
from operations.app_update import _run_app_update
from states import (
    ALL_CONFIRM, CONTAINERS_LIST, MAIN_MENU,
    SETTINGS_MENU, SYSTEM_MENU, UPDATE_AVAILABLE, UPDATES_MENU,
)
from handlers.shared import _show_containers_list, _show_system_menu, _show_updates_menu
from ui import _main_menu_kb, send_main_menu
from utils import edit, kb, only_me

log = logging.getLogger(__name__)

# =============================================================================
# MAIN MENU callbacks
# =============================================================================

@only_me
async def main_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Gestisce i due bottoni del menu principale: "Aggiornamenti"
        (apre il menu updates) e "Impostazioni" (apre il menu settings,
        importato lazy per evitare import circolari).
    EN: Handles the two main-menu buttons: "Updates" (opens the updates
        menu) and "Settings" (opens the settings menu, imported lazily to
        avoid circular imports).
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:updates":
        await _show_updates_menu(update)
        return UPDATES_MENU

    if data == "nav:settings":
        from handlers.settings import _show_settings
        await _show_settings(update)
        return SETTINGS_MENU

    return MAIN_MENU

# =============================================================================
# UPDATES MENU callbacks
# =============================================================================

@only_me
async def updates_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Gestisce tutti i bottoni del menu Aggiornamenti: Sistema (apre il
        sottomenu Sistema), Container, Aggiorna Tutto, Riavvia, Torna al
        menu principale.
    EN: Handles every button of the Updates menu: System (opens the
        System sub-menu), Containers, Update All, Reboot, Back.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:main":
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    if data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU

    if data == "upd:containers_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data == "upd:all_confirm":
        await edit(update, t("confirm_update_all"), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:all"),
            InlineKeyboardButton(t("btn_no"),  callback_data="nav:updates_menu"),
        ))
        return ALL_CONFIRM

    if data == "nav:updates_menu":
        await _show_updates_menu(update)
        return UPDATES_MENU

    return UPDATES_MENU

# =============================================================================
# UPDATE AVAILABLE callbacks
# =============================================================================

@only_me
async def update_available_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Gestisce i bottoni della schermata "aggiornamento bot disponibile":
        "Aggiorna" lancia `_run_app_update`; "Salta" memorizza la versione
        in `skipped_version` per non mostrarla più finché non ne arriva
        un'altra.
    EN: Handles the buttons of the "bot update available" screen: "Update"
        runs `_run_app_update`; "Skip" stores the version in
        `skipped_version` so it won't be shown again until a newer release
        appears.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "app:update":
        await _run_app_update(update, ctx)
        return UPDATE_AVAILABLE

    if data == "nav:skip_update":
        c = load_config()
        skipped = c.get("available_version", "")
        if skipped:
            c["skipped_version"] = skipped
            save_config(c)
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    return UPDATE_AVAILABLE

# =============================================================================
# GLOBAL nav:new_main handler
# =============================================================================

async def _global_new_main_cb(upd: Update, _ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Handler globale (fuori conversazione) per il bottone "Menu
        principale" che compare nel messaggio editato dopo il restart del
        bot. Non c'è alcuno stato conversazione attivo a quel punto, quindi
        serve un handler indipendente che esegua il controllo di
        autorizzazione manualmente.
    EN: Global handler (outside the conversation) for the "Main menu"
        button that appears in the message edited after the bot restart.
        No conversation state is active at that point, so we need a
        standalone handler that performs the authorization check manually.
    """
    query = upd.callback_query
    if not query:
        return
    if upd.effective_user and upd.effective_user.id != AUTHORIZED_CHAT:
        return
    await query.answer()
    await send_main_menu(upd.get_bot(), AUTHORIZED_CHAT)
