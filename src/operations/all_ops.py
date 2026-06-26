"""
IT: Pipeline "Aggiorna Tutto" — fasi che orchestrano sistema + container
    in un'unica sequenza, con interattività in caso di trattenuti,
    autoremove o errori. Ogni fase è una funzione async invocata sia
    direttamente da `_run_all` sia dai callback handler quando l'utente
    sceglie come proseguire (full-upgrade, autoremove, continua container).
    Tutte usano `extra_btns=(Continua → container,)` per offrire una via di
    uscita verso la fase successiva senza dover risolvere il problema apt.
EN: "Update All" pipeline — phases that orchestrate system + containers in
    a single sequence, prompting the user when held packages, autoremove or
    errors come up. Each phase is an async function called both from
    `_run_all` and from callback handlers when the user picks how to
    proceed (full-upgrade, autoremove, continue to containers). They all
    pass `extra_btns=(Continue → containers,)` to offer a forward escape
    that skips the current apt problem.
"""
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT
from lang import t
from operations.core import _core_system, _core_autoremove, _core_full_upgrade, _core_containers
from utils import update_live

log = logging.getLogger(__name__)

# =============================================================================
# OPERAZIONI — TUTTO (sistema + container) — fasi che usano i core helper
# =============================================================================

async def _run_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Entry point del flusso "Aggiorna Tutto": inizializza il messaggio
        live, salva le righe iniziali in `ctx.user_data["live_lines"]` e
        invoca la prima fase (`_all_system_phase`).
    EN: Entry point for the "Update All" flow: initialize the live message,
        stash the initial lines under `ctx.user_data["live_lines"]` and
        kick off the first phase (`_all_system_phase`).
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
    ctx.user_data["live_lines"] = lines
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    await _all_system_phase(bot, msg_id, lines, ctx)


async def _all_system_phase(bot, msg_id: int, lines: list, ctx):
    """
    IT: Fase 1 — `apt update` + `apt upgrade`. Sul successo continua
        automaticamente alla fase container; in caso di trattenuti /
        rimovibili / errori, mostra anche il bottone "Continua container"
        per saltare avanti senza risolvere il problema apt.
    EN: Phase 1 — `apt update` + `apt upgrade`. On success automatically
        proceeds to the container phase; on held/autoremove/errors also
        exposes a "Continue to containers" button so the user can skip
        forward without fixing the apt issue.
    """
    _cont = (InlineKeyboardButton(t("btn_continue_containers"), callback_data="all:continue_containers"),)
    await _core_system(bot, msg_id, lines, ctx,
                       retry_cb="all:retry_system",
                       full_upgrade_cb="all:do_full_upgrade",
                       autoremove_cb="all:do_autoremove",
                       extra_btns=_cont,
                       on_success=_all_containers_phase)


async def _all_full_upgrade_phase(bot, msg_id: int, lines: list, ctx):
    """
    IT: Esegue un full-upgrade nel contesto di "Aggiorna Tutto", poi
        prosegue alla fase container (o si ferma in attesa di autoremove
        follow-up se serve).
    EN: Run a full-upgrade within the "Update All" flow, then move on to
        the container phase (or pause for a follow-up autoremove
        suggestion if needed).
    """
    lines = list(lines)
    lines += [t("separator"), t("step_full_upgrade_title"), t("step_full_upgrade_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    _cont = (InlineKeyboardButton(t("btn_continue_containers"), callback_data="all:continue_containers"),)
    await _core_full_upgrade(bot, msg_id, lines, ctx,
                             retry_cb="all:do_full_upgrade",
                             autoremove_cb="all:do_autoremove",
                             extra_btns=_cont,
                             on_success=_all_containers_phase)


async def _all_autoremove_phase(bot, msg_id: int, lines: list, ctx):
    """
    IT: Esegue un autoremove nel contesto di "Aggiorna Tutto", poi
        prosegue verso la fase container.
    EN: Run an autoremove within the "Update All" flow, then continue to
        the container phase.
    """
    lines = list(lines)
    lines += [t("separator"), t("step_autoremove_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    _cont = (InlineKeyboardButton(t("btn_continue_containers"), callback_data="all:continue_containers"),)
    await _core_autoremove(bot, msg_id, lines, ctx,
                           retry_cb="all:do_autoremove",
                           extra_btns=_cont,
                           on_success=_all_containers_phase)


async def _all_containers_phase(bot, msg_id: int, lines: list, ctx):
    """
    IT: Fase finale di "Aggiorna Tutto": pull → up → cleanup → summary.
        Usa `_core_containers` con `up_n=3` perché il pull è lo step 2
        (sistema=1, pull=2, up=3) nella numerazione del flusso completo.
    EN: Final phase of "Update All": pull → up → cleanup → summary. Calls
        `_core_containers` with `up_n=3` because pull is step 2 (system=1,
        pull=2, up=3) in the combined numbering.
    """
    lines = list(lines)
    lines += [t("separator"), t("step_pull_title", n=2), t("step_pull_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    await _core_containers(bot, msg_id, lines, ctx, up_n=3, retry_cb="run:all")
