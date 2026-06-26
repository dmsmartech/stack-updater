"""
IT: Handler per i flussi di gestione container Docker. Sequenza completa:
    CONTAINERS_LIST → CONTAINER_DETAIL → CONTAINER_CONFIRM →
    CONTAINER_RUNNING. Gestisce sia le azioni su singolo container
    (start/restart/stop/down/update) sia l'aggiornamento di tutti i
    container in un colpo solo.
EN: Handlers for the Docker-container management flows. Full sequence:
    CONTAINERS_LIST → CONTAINER_DETAIL → CONTAINER_CONFIRM →
    CONTAINER_RUNNING. Supports both per-container actions
    (start/restart/stop/down/update) and bulk updates of every container.
"""
import logging

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT
from lang import t
from helpers.docker import (
    container_status_label, get_container_inspect, get_containers, is_container_running
)
from operations.docker_ops import _run_container_action, _run_containers_all
from states import (
    ALL_RUNNING, CONTAINER_CONFIRM, CONTAINER_DETAIL,
    CONTAINER_RUNNING, CONTAINERS_LIST, MAIN_MENU, UPDATES_MENU
)
from handlers.shared import _show_containers_list, _show_updates_menu
from ui import send_main_menu
from utils import edit, kb, only_me

log = logging.getLogger(__name__)

# =============================================================================
# CONTAINER DETAIL (internal helper)
# =============================================================================

async def _show_container_detail(update: Update, ctx: ContextTypes.DEFAULT_TYPE, cname: str):
    """
    IT: Renderizza la schermata di dettaglio di un singolo container:
        nome, immagine/tag, stato, uptime e porte da `docker inspect`,
        più una tastiera diversa a seconda che il container sia in
        esecuzione (restart/stop/down/update) o fermo (start/update).
    EN: Render the detail screen for a single container: name, image/tag,
        status, uptime and ports from `docker inspect`, plus a keyboard
        that differs based on whether the container is running
        (restart/stop/down/update) or stopped (start/update only).

    Args:
        cname: nome del servizio compose / compose service name.
    """
    containers = ctx.user_data.get("containers", [])
    ct = next((c for c in containers if c["service"] == cname), None)
    if not ct:
        await _show_containers_list(update, ctx, False)
        return
    status_label = container_status_label(ct["status"])

    inspect = await get_container_inspect(ct["name"])
    extra_parts = []
    if inspect.get("uptime"):
        extra_parts.append(t("container_uptime", uptime=inspect["uptime"]))
    if inspect.get("ports"):
        extra_parts.append(t("container_ports", ports=", ".join(inspect["ports"])))
    extra = "".join(extra_parts)

    text = t("container_detail_title",
             name=ct["name"], image=ct["image"], tag=ct["tag"],
             status=status_label, extra=extra)

    if is_container_running(ct["status"]):
        await edit(update, text, kb(
            InlineKeyboardButton(t("btn_restart_container"), callback_data="ct:confirm:restart"),
            InlineKeyboardButton(t("btn_stop_container"),    callback_data="ct:confirm:stop"),
            InlineKeyboardButton(t("btn_down_container"),    callback_data="ct:confirm:down"),
            InlineKeyboardButton(t("btn_update_container"),  callback_data="ct:confirm:update"),
            InlineKeyboardButton(t("btn_back_updates"),      callback_data="ct:back_list"),
        ))
    else:
        await edit(update, text, kb(
            InlineKeyboardButton(t("btn_start_container"),  callback_data="ct:confirm:start"),
            InlineKeyboardButton(t("btn_update_container"), callback_data="ct:confirm:update"),
            InlineKeyboardButton(t("btn_back_updates"),     callback_data="ct:back_list"),
        ))

# =============================================================================
# CONTAINERS LIST → DETAIL → CONFIRM → RUNNING
# =============================================================================

@only_me
async def containers_list_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato CONTAINERS_LIST: scelta di un container (apre il dettaglio),
        "Aggiorna tutti" (conferma globale), back al menu updates.
    EN: CONTAINERS_LIST state: picking a container (opens detail),
        "Update all" (global confirm), back to updates menu.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "nav:updates_menu":
        await _show_updates_menu(update)
        return UPDATES_MENU

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


@only_me
async def container_detail_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato CONTAINER_DETAIL: gestisce il bottone "back to list" e la
        scelta di un'azione (start/restart/stop/down/update) che porta a
        CONTAINER_CONFIRM.
    EN: CONTAINER_DETAIL state: handles the "back to list" button and the
        choice of an action (start/restart/stop/down/update) that leads
        to CONTAINER_CONFIRM.
    """
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
    """
    IT: Stato CONTAINER_CONFIRM: conferma dell'azione (esegue l'operazione
        vera e propria) o annullamento (back al dettaglio / lista). Gestisce
        anche il caso "aggiorna tutti i container" arrivato dalla lista.
    EN: CONTAINER_CONFIRM state: action confirmation (runs the actual
        operation) or cancellation (back to detail / list). Also handles
        the "update all containers" path coming from the list.
    """
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
    """
    IT: Stato CONTAINER_RUNNING: bottoni del messaggio live post-azione —
        Riprova (rilancia stessa azione), back al dettaglio (ricarica
        stato con `get_containers`), nuova lista (manda un nuovo messaggio
        perché quello live è "consumato"), menu principale.
    EN: CONTAINER_RUNNING state: post-action live-message buttons — Retry
        (re-runs the same action), back to detail (refreshes status via
        `get_containers`), new list (sends a fresh message since the
        live one is "consumed"), main menu.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    cname = ctx.user_data.get("selected_container", "")
    action = ctx.user_data.get("ct_action", "")

    if data == "ct:retry_action":
        await _run_container_action(update, ctx, cname, action)
        return CONTAINER_RUNNING

    if data.startswith("ct:back_detail:"):
        # Ricarica i container prima di mostrare il dettaglio così uptime
        # e stato sono freschi dopo l'azione appena eseguita.
        containers = await get_containers()
        ctx.user_data["containers"] = containers
        await _show_container_detail(update, ctx, cname)
        return CONTAINER_DETAIL

    if data == "ct:back_list":
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data == "ct:new_list":          # compat: messaggi precedenti all'aggiornamento
        await _show_containers_list(update, ctx, False)
        return CONTAINERS_LIST

    if data == "nav:new_main":
        await send_main_menu(update.get_bot(), AUTHORIZED_CHAT)
        return MAIN_MENU

    return CONTAINER_RUNNING
