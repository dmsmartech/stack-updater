"""
IT: "Cuore" delle operazioni a lungo termine: contiene le primitive
    parametrizzate `_core_system`, `_core_full_upgrade`, `_core_autoremove`
    e `_core_containers` che eseguono passo-passo apt e docker compose,
    aggiornando il messaggio live e mostrando bottoni di interazione
    (Riprova, Continua, Full upgrade, ecc.). Queste primitive sono riusate
    sia dai wrapper standalone (system_ops, docker_ops) sia dalla
    pipeline "Aggiorna Tutto" (all_ops) variando le callback per i bottoni.
EN: "Heart" of the long-running operations: parametric primitives
    (`_core_system`, `_core_full_upgrade`, `_core_autoremove`,
    `_core_containers`) that step through apt and docker compose, updating
    the live message and surfacing interactive buttons (Retry, Continue,
    Full upgrade, ...). These primitives are reused both by the standalone
    wrappers (system_ops, docker_ops) and by the "Update All" pipeline
    (all_ops), differentiated only by callback data.
"""
import logging
import re

from telegram import InlineKeyboardButton

from config import AUTHORIZED_CHAT, cfg_docker_dir
from lang import t
from helpers.system import parse_apt_problems, parse_autoremove_packages, parse_held_packages
from helpers.docker import (
    _compose_service_image_ids, get_containers, parse_docker_problems
)
from utils import APT_ENV, kb, run_cmd, truncate, update_live

log = logging.getLogger(__name__)

# =============================================================================
# CORE HELPERS (condivisi tra flusso standalone e "Aggiorna Tutto")
# =============================================================================

async def _core_system(bot, msg_id: int, lines: list, ctx, *,
                       retry_cb: str, full_upgrade_cb: str, autoremove_cb: str,
                       extra_btns: tuple = (), on_success=None):
    """
    IT: Esegue la fase "sistema": `apt-get update` → `apt-get upgrade -y`,
        rilevando errori, pacchetti trattenuti (suggerendo full-upgrade) e
        pacchetti rimovibili (suggerendo autoremove). Sostituisce i bottoni
        del messaggio live con le azioni opportune. Parametrizzata sui
        callback ID per essere riusabile dal flusso standalone (es.
        `run:system`) e da Aggiorna Tutto (es. `all:retry_system`).
    EN: Run the "system" phase: `apt-get update` → `apt-get upgrade -y`,
        detecting errors, held packages (suggesting full-upgrade) and
        autoremovable packages (suggesting autoremove). Swaps the live
        message's buttons with the appropriate actions. Parametrized over
        callback IDs so it can be reused by the standalone flow (e.g.
        `run:system`) and by the "Update All" pipeline (e.g.
        `all:retry_system`).

    Args:
        bot:             istanza bot / bot instance.
        msg_id:          id messaggio live / live message id.
        lines:           buffer di righe del messaggio / message line buffer.
        ctx:             contesto del bot / bot context.
        retry_cb:        callback per il bottone "Riprova" / Retry button cb.
        full_upgrade_cb: callback per il bottone "Full upgrade" / cb.
        autoremove_cb:   callback per il bottone "Autoremove" / cb.
        extra_btns:      tupla di bottoni aggiuntivi (es. "Continua") /
                         extra buttons tuple (e.g. "Continue").
        on_success:      callback async invocata se tutto è OK /
                         async callback invoked on success.
    """
    lines = list(lines)

    code, out = await run_cmd(["apt-get", "update", "-q"], env=APT_ENV)
    if code != 0:
        lines.append(t("step_system_error") + t("error_detail", detail=truncate(out)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    code, out = await run_cmd(["apt-get", "upgrade", "-y", "-q"], env=APT_ENV)
    problems = parse_apt_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_system_warning") if problems else t("step_system_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_system_ok"))

    held = parse_held_packages(out)
    if held > 0:
        ctx.user_data["live_lines"] = lines[:]
        prompt_lines = lines + [t("separator"), t("full_upgrade_prompt", count=held)]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, prompt_lines, kb(
            InlineKeyboardButton(t("btn_full_upgrade"), callback_data=full_upgrade_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"),    callback_data="nav:new_main"),
        ))
        return

    autoremove_pkgs = parse_autoremove_packages(out)
    if autoremove_pkgs:
        pkg_count = len(autoremove_pkgs)
        pkg_display = ", ".join(autoremove_pkgs[:15])
        if pkg_count > 15:
            pkg_display += f" … (+{pkg_count - 15})"
        ctx.user_data["live_lines"] = lines[:]
        prompt_lines = lines + [t("separator"),
                                t("autoremove_prompt", count=pkg_count, packages=pkg_display)]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, prompt_lines, kb(
            InlineKeyboardButton(t("btn_autoremove"), callback_data=autoremove_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"),  callback_data="nav:new_main"),
        ))
        return

    if on_success:
        await on_success(bot, msg_id, lines, ctx)
    else:
        lines.append(t("separator"))
        lines.append("🎉 <b>Aggiornamento sistema completato!</b>")
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))


async def _core_autoremove(bot, msg_id: int, lines: list, ctx, *,
                           retry_cb: str, extra_btns: tuple = (), on_success=None):
    """
    IT: Esegue `apt-get autoremove -y -q` aggiornando il messaggio live.
        Su errore mostra il bottone Riprova (con `retry_cb`) e gli
        eventuali `extra_btns`. Su successo invoca `on_success` se passata,
        altrimenti chiude con il bottone "Menu principale".
    EN: Run `apt-get autoremove -y -q` while updating the live message. On
        failure shows a Retry button (using `retry_cb`) along with any
        `extra_btns`. On success calls `on_success` if provided, otherwise
        closes with a "Main menu" button.

    Args:
        bot, msg_id, lines, ctx: contesto del messaggio live / live context.
        retry_cb:                callback per il bottone Riprova / Retry cb.
        extra_btns:              bottoni extra opzionali / optional extra btns.
        on_success:              callback async di follow-up / follow-up cb.
    """
    lines = list(lines)

    code, out = await run_cmd(["apt-get", "autoremove", "-y", "-q"], env=APT_ENV)
    if code != 0:
        problems = parse_apt_problems(out)
        detail = "\n".join(problems[:15]) if problems else out
        lines.append(t("step_autoremove_error") + t("error_detail", detail=truncate(detail)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_autoremove_ok"))
    if on_success:
        await on_success(bot, msg_id, lines, ctx)
    else:
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))


async def _core_full_upgrade(bot, msg_id: int, lines: list, ctx, *,
                             retry_cb: str, autoremove_cb: str,
                             extra_btns: tuple = (), on_success=None):
    """
    IT: Esegue `apt-get full-upgrade -y -q`, gestendo anche un'eventuale
        offerta di autoremove a valle (i full-upgrade spesso lasciano
        pacchetti orfani). Stessa logica di parametrizzazione sui callback
        di `_core_system`.
    EN: Run `apt-get full-upgrade -y -q`, also surfacing a follow-up
        autoremove suggestion when applicable (full upgrades often leave
        orphan packages). Same callback parametrization pattern as
        `_core_system`.

    Args:
        retry_cb:      callback per il bottone Riprova / Retry button cb.
        autoremove_cb: callback per autoremove follow-up / autoremove cb.
        extra_btns:    bottoni extra opzionali / optional extra buttons.
        on_success:    callback async di follow-up / follow-up callback.
    """
    lines = list(lines)

    code, out = await run_cmd(["apt-get", "full-upgrade", "-y", "-q"], env=APT_ENV)
    problems = parse_apt_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        lines.append(t("step_full_upgrade_error") + t("error_detail", detail=truncate(detail)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_full_upgrade_ok"))

    autoremove_pkgs = parse_autoremove_packages(out)
    if autoremove_pkgs:
        pkg_count = len(autoremove_pkgs)
        pkg_display = ", ".join(autoremove_pkgs[:15])
        if pkg_count > 15:
            pkg_display += f" … (+{pkg_count - 15})"
        ctx.user_data["live_lines"] = lines[:]
        prompt_lines = lines + [t("separator"),
                                t("autoremove_prompt", count=pkg_count, packages=pkg_display)]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, prompt_lines, kb(
            InlineKeyboardButton(t("btn_autoremove"), callback_data=autoremove_cb),
            *extra_btns,
            InlineKeyboardButton(t("btn_main_menu"),  callback_data="nav:new_main"),
        ))
        return

    if on_success:
        await on_success(bot, msg_id, lines, ctx)
    else:
        lines.append(t("separator"))
        lines.append("🎉 <b>Aggiornamento sistema completato!</b>")
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))


async def _core_containers(bot, msg_id: int, lines: list, ctx, *,
                           up_n: int = 2, retry_cb: str):
    """
    IT: Esegue la pipeline container: `docker compose pull` (con confronto
        image id per individuare i servizi effettivamente aggiornati) →
        `docker compose up -d` → `docker image prune -f` → riepilogo stato
        finale dei container. Le righe ricevute devono già contenere il
        titolo e lo stato del pull. `up_n` è il numero che precede il
        titolo del passo "up" (per la numerazione coerente nel flusso
        standalone vs. "Aggiorna Tutto").
    EN: Run the container pipeline: `docker compose pull` (comparing image
        ids before/after to find services that actually updated) →
        `docker compose up -d` → `docker image prune -f` → final container
        status summary. The incoming `lines` should already contain the
        pull title and "running" status. `up_n` is the step number printed
        before the "up" title (for consistent numbering between standalone
        and "Update All" flows).

    Args:
        up_n:     numero dello step "up" / "up" step number.
        retry_cb: callback per il bottone Riprova / Retry button callback.
    """
    lines = list(lines)
    docker_dir = cfg_docker_dir()

    ids_before = await _compose_service_image_ids(docker_dir)
    code, out = await run_cmd(["docker", "compose", "pull"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_pull_warning") if problems else t("step_pull_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    ids_after = await _compose_service_image_ids(docker_dir)
    pulled = [s for s in ids_before if ids_after.get(s) and ids_after[s] != ids_before[s]]
    lines.append(t("step_pull_updated", list="\n".join(pulled)) if pulled
                 else t("step_pull_no_updates"))

    lines += [t("separator"), t("step_up_title", n=up_n), t("step_up_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    code, out = await run_cmd(["docker", "compose", "up", "-d"], cwd=docker_dir)
    problems = parse_docker_problems(out)
    if code != 0 or problems:
        detail = "\n".join(problems[:15]) if problems else out
        line = t("step_up_warning") if problems else t("step_up_error")
        lines.append(line + t("error_detail", detail=truncate(detail)))
        ctx.user_data["live_lines"] = lines[:]
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_retry"),     callback_data=retry_cb),
            InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
        ))
        return

    lines.append(t("step_up_ok"))

    lines += [t("separator"), t("step_cleanup_running")]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)
    _, prune_out = await run_cmd(["docker", "image", "prune", "-f"])
    match = re.search(r"Total reclaimed space: (.+)", prune_out)
    space = t("space_freed", space=match.group(1)) if match else ""
    lines.append(t("step_cleanup_ok", space=space))

    containers = await get_containers()
    ct_status = "\n".join(f"{c['name']}: {c['status']}" for c in containers) or t("no_containers")
    lines.append(t("final_ok", containers=ct_status))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
        InlineKeyboardButton(t("btn_main_menu"), callback_data="nav:new_main"),
    ))
