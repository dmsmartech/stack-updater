"""
IT: Funzioni condivise tra i diversi handler della conversazione. Contiene le
    schermate riusate da più handler (menu aggiornamenti, lista container) che
    altrimenti sarebbero duplicate o creerebbero dipendenze incrociate fra
    moduli dello stesso layer.
EN: Shared helpers used by multiple handlers of the Telegram conversation.
    Houses the screens reused across handlers (updates menu, containers list)
    so they don't get duplicated or create cross-imports between sibling
    handler modules.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT
from lang import t
from utils import edit, kb

log = logging.getLogger(__name__)


# =============================================================================
# UPDATES MENU
# =============================================================================

async def _show_updates_menu(update: Update):
    """
    IT: Mostra il menu degli aggiornamenti (sistema, container, tutto, riavvio)
        editando il messaggio corrente. Usata come schermata "home" della
        sezione aggiornamenti, sia in entrata dal menu principale sia come
        ritorno dalle sotto-sezioni.
    EN: Render the updates menu (system, containers, all, reboot) by editing
        the current message. Acts as the "home" screen of the updates section,
        used both on entry from the main menu and as a back target from
        sub-sections.

    Args:
        update: oggetto Update con il callback_query da cui editare il messaggio /
                Update object whose callback_query message is edited in place.
    """
    await edit(update, t("updates_menu"), kb(
        InlineKeyboardButton(t("btn_system_menu"),       callback_data="nav:system_menu"),
        InlineKeyboardButton(t("btn_update_containers"), callback_data="upd:containers_list"),
        InlineKeyboardButton(t("btn_update_all"),        callback_data="upd:all_confirm"),
        InlineKeyboardButton(t("btn_back_main"),         callback_data="nav:main"),
    ))


# =============================================================================
# SYSTEM MENU
# =============================================================================

async def _show_system_menu(update: Update):
    """
    IT: Mostra il sottomenu Sistema (aggiorna sistema, stato risorse,
        torna indietro) editando il messaggio corrente. Usata sia
        dall'entrata dal menu aggiornamenti sia come destinazione "back"
        dalla schermata di dettaglio sistema e dalla schermata risorse.
    EN: Render the System sub-menu (update system, resource status, back)
        by editing the current message. Used both on entry from the
        updates menu and as the "back" target from the system detail and
        resource status screens.

    Args:
        update: oggetto Update con il callback_query da cui editare il
                messaggio / Update object whose callback_query message
                is edited in place.
    """
    await edit(update, t("system_menu_title"), kb(
        InlineKeyboardButton(t("btn_system_update"),  callback_data="sys:update"),
        InlineKeyboardButton(t("btn_system_status"),  callback_data="sys:resources"),
        InlineKeyboardButton(t("btn_reboot"),         callback_data="sys:reboot"),
        InlineKeyboardButton(t("btn_back_updates"),   callback_data="nav:updates_menu"),
    ))


# =============================================================================
# CONTAINERS LIST
# =============================================================================

async def _show_containers_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                                send_new: bool = False):
    """
    IT: Recupera la lista dei container Docker tramite `docker compose ps` e
        la mostra come tastiera inline: ogni container è un bottone, più due
        azioni globali (aggiorna tutti, torna indietro). Memorizza la lista
        in `ctx.user_data["containers"]` per il dettaglio successivo. Se
        `send_new` è True invia un nuovo messaggio (usato dopo un'operazione
        che ha già "consumato" il messaggio live), altrimenti edita quello
        corrente.
    EN: Fetch the Docker container list via `docker compose ps` and render it
        as an inline keyboard: one button per container plus two global
        actions (update all, back). Stores the list under
        `ctx.user_data["containers"]` for the subsequent detail view. When
        `send_new` is True a brand-new message is sent (used after an
        operation that already consumed the live message); otherwise the
        current message is edited in place.

    Args:
        update:   Telegram Update / Telegram Update.
        ctx:      contesto del bot per il caching della lista / bot context
                  used to cache the container list.
        send_new: se True invia un nuovo messaggio invece di editare /
                  if True send a new message instead of editing the current one.
    """
    from helpers.docker import get_containers, is_container_running

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
        """
        IT: Costruisce l'etichetta del bottone con icona di stato + nome.
        EN: Build the button label with a status icon and the container name.
        """
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
