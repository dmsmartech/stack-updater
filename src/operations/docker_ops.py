"""
IT: Wrapper standalone delle operazioni sui container Docker.
    `_run_container_action` esegue una singola azione
    (start/restart/stop/down/update) su un container, mostrando l'esito
    nel messaggio live. `_run_containers_all` invoca la pipeline completa
    `_core_containers` (pull+up+cleanup) per tutti i container del
    progetto compose.
EN: Standalone wrappers for Docker container operations.
    `_run_container_action` runs a single action (start/restart/stop/down/
    update) on one container, reporting the outcome on the live message.
    `_run_containers_all` invokes the full `_core_containers` pipeline
    (pull+up+cleanup) for every container in the compose project.
"""
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT, cfg_docker_dir
from lang import t
from operations.core import _core_containers
from utils import kb, run_cmd, truncate, update_live

log = logging.getLogger(__name__)

# =============================================================================
# OPERAZIONI — SINGOLO CONTAINER
# =============================================================================

async def _run_container_action(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                                 cname: str, action: str):
    """
    IT: Esegue un'azione su un singolo container. Mappa l'azione su uno o
        due comandi `docker compose` (per "update" esegue prima `pull` poi
        `up -d`). Sul fallimento mostra "Riprova" e ritorno al dettaglio;
        sul successo mostra il bottone per tornare alla lista.
    EN: Run an action against a single container. Maps the action to one or
        two `docker compose` commands (for "update" it runs `pull` then
        `up -d`). On failure shows a Retry button and a back-to-detail
        button; on success shows the back-to-list button.

    Args:
        update: Update Telegram / Telegram update.
        ctx:    contesto del bot / bot context.
        cname:  nome del servizio compose / compose service name.
        action: "start" | "restart" | "stop" | "down" | "update".
    """
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
        InlineKeyboardButton(t("btn_back_updates"), callback_data="ct:back_list"),
    ))

# =============================================================================
# OPERAZIONI — TUTTI I CONTAINER (wrapper standalone)
# =============================================================================

async def _run_containers_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Avvia l'aggiornamento standalone di tutti i container del progetto
        compose, delegando a `_core_containers` con `up_n=2` (numerazione
        coerente: 1=pull, 2=up nella variante standalone).
    EN: Run the standalone "update all containers" flow for the compose
        project, delegating to `_core_containers` with `up_n=2` (consistent
        numbering: 1=pull, 2=up in the standalone variant).
    """
    query  = update.callback_query
    bot    = update.get_bot()
    msg_id = query.message.message_id
    ctx.user_data["live_msg_id"] = msg_id

    lines = [
        t("live_header", datetime=datetime.now().strftime("%d/%m/%Y %H:%M")),
        t("separator"),
        t("step_pull_title", n=1),
        t("step_pull_running"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    await _core_containers(bot, msg_id, lines, ctx, up_n=2, retry_cb="run:containers_all")
