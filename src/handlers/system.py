"""
IT: Handler per il sottomenu Sistema e per tutti i flussi legati al
    sistema: aggiornamento (SYSTEM_MENU → SYSTEM_INFO → SYSTEM_CONFIRM →
    SYSTEM_RUNNING), risorse hardware (SYSTEM_STATUS) e riavvio macchina
    (REBOOT_CONFIRM → REBOOT_RUNNING). Ogni handler risponde a una
    manciata di callback ID e delega l'esecuzione vera e propria al layer
    operations (`_run_system`, `_run_autoremove`, `_run_full_upgrade`) e
    agli helper di sistema (`helpers.system`).
EN: Handlers for the System sub-menu and all system-related flows:
    update (SYSTEM_MENU → SYSTEM_INFO → SYSTEM_CONFIRM → SYSTEM_RUNNING),
    hardware resources (SYSTEM_STATUS) and machine reboot
    (REBOOT_CONFIRM → REBOOT_RUNNING). Each handler responds to a small
    set of callback ids and delegates the actual work to the operations
    layer (`_run_system`, `_run_autoremove`, `_run_full_upgrade`) and the
    system helpers (`helpers.system`).
"""
import asyncio
import logging
import subprocess
from pathlib import Path

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT, REBOOT_FLAG
from lang import t
from operations.system_ops import _run_autoremove, _run_full_upgrade, _run_system
from states import (
    MAIN_MENU, REBOOT_CONFIRM, REBOOT_RUNNING,
    SYSTEM_CONFIRM, SYSTEM_INFO, SYSTEM_MENU,
    SYSTEM_RUNNING, SYSTEM_STATUS, UPDATES_MENU,
)
from handlers.shared import _show_system_menu, _show_updates_menu
from ui import send_main_menu
from utils import edit, kb, only_me

log = logging.getLogger(__name__)

# =============================================================================
# SYSTEM STATUS — helper condiviso tra sys:resources e il pulsante Aggiorna
# =============================================================================

async def _show_system_status(update: Update) -> None:
    """
    IT: Raccoglie uptime, CPU, RAM, swap e dischi, compone il messaggio di
        stato sistema e lo mostra editando il messaggio corrente. Usata sia
        dalla prima apertura (SYSTEM_MENU → sys:resources) sia dal pulsante
        "Aggiorna" nello stato SYSTEM_STATUS.
    EN: Gather uptime, CPU, RAM, swap and disk data, compose the system
        status message and display it by editing the current message. Used
        both on first open (SYSTEM_MENU → sys:resources) and when the user
        presses the "Refresh" button in SYSTEM_STATUS state.
    """
    from helpers.system import (
        _bar, get_cpu_percent, get_disk_info,
        get_ram_info, get_swap_info, get_uptime,
    )

    uptime_str             = await get_uptime()
    cpu_pct                = await get_cpu_percent()
    ram_pct, ram_used, ram_tot = await get_ram_info()
    swap                   = await get_swap_info()
    disks                  = await get_disk_info()

    # Dischi con riga vuota tra uno e l'altro
    disk_items = [
        t("system_status_disk",
          bar=_bar(pct), pct=f"{pct:.0f}",
          used=used, total=total, mount=mount)
        for pct, used, total, mount in disks
    ]
    disk_lines: list[str] = []
    for i, item in enumerate(disk_items):
        disk_lines.append(item)
        if i < len(disk_items) - 1:
            disk_lines.append("")
    disk_lines = disk_lines or [t("system_status_no_disk")]

    # Swap (omesso se non configurato)
    swap_lines: list[str] = []
    if swap:
        swap_pct, swap_used, swap_tot = swap
        swap_lines = [
            "",
            t("system_status_swap",
              bar=_bar(swap_pct), pct=f"{swap_pct:.0f}",
              used=swap_used, total=swap_tot),
        ]

    text = "\n".join([
        t("system_status_title"),
        "",
        t("system_status_uptime", uptime=uptime_str),
        "<code>──────────────────────</code>",
        "",
        t("system_status_cpu", bar=_bar(cpu_pct), pct=f"{cpu_pct:.0f}"),
        "",
        t("system_status_ram", bar=_bar(ram_pct), pct=f"{ram_pct:.0f}",
          used=ram_used, total=ram_tot),
        *swap_lines,
        "",
        *disk_lines,
    ])

    await edit(update, text, kb(
        InlineKeyboardButton(t("btn_refresh"),     callback_data="sys:resources"),
        InlineKeyboardButton(t("btn_back_updates"), callback_data="nav:system_menu"),
    ))


# =============================================================================
# SYSTEM MENU
# =============================================================================

@only_me
async def system_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato SYSTEM_MENU: gestisce i tre bottoni del sottomenu Sistema.
        "Aggiorna Sistema" esegue `apt update` per il conteggio pacchetti
        e porta a SYSTEM_INFO (o avvia subito `_run_system` se 0
        pacchetti); "Stato Risorse" recupera CPU/RAM/disco e porta a
        SYSTEM_STATUS; "← Torna Indietro" ritorna al menu aggiornamenti.
    EN: SYSTEM_MENU state: handles the three buttons of the System
        sub-menu. "Update System" runs `apt update` for the package
        count and moves to SYSTEM_INFO (or immediately launches
        `_run_system` when 0 packages); "System Status" fetches
        CPU/RAM/disk and moves to SYSTEM_STATUS; "← Go Back" returns
        to the updates menu.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "sys:update":
        await edit(update, t("settings_checking_updates"))
        from helpers.system import get_upgradable_count
        count, distro = await get_upgradable_count()
        ctx.user_data["pkg_count"] = count
        if count == 0:
            await _run_system(update, ctx)
            return SYSTEM_RUNNING
        await edit(update,
            t("system_info_title") + "\n\n" +
            t("system_info_distro", distro=distro) + "\n" +
            t("system_info_packages", count=count),
            kb(
                InlineKeyboardButton(t("btn_do_update_system"), callback_data="upd:system_confirm"),
                InlineKeyboardButton(t("btn_back_updates"),      callback_data="nav:system_menu"),
            )
        )
        return SYSTEM_INFO

    if data == "sys:resources":
        await _show_system_status(update)
        return SYSTEM_STATUS

    if data == "sys:reboot":
        await edit(update, t("confirm_reboot"), kb(
            InlineKeyboardButton(t("btn_yes"), callback_data="run:reboot"),
            InlineKeyboardButton(t("btn_no"),  callback_data="nav:system_menu"),
        ))
        return REBOOT_CONFIRM

    if data == "nav:updates_menu":
        await _show_updates_menu(update)
        return UPDATES_MENU

    return SYSTEM_MENU


# =============================================================================
# SYSTEM STATUS (risorse CPU / RAM / disco)
# =============================================================================

@only_me
async def system_status_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato SYSTEM_STATUS: gestisce il pulsante "🔄 Aggiorna" (ricarica
        le risorse in-place) e "← Torna Indietro" (torna al sottomenu Sistema).
    EN: SYSTEM_STATUS state: handles the "🔄 Refresh" button (reloads
        resource data in-place) and "← Go Back" (returns to System sub-menu).
    """
    query = update.callback_query
    await query.answer()

    if query.data == "sys:resources":
        await _show_system_status(update)
        return SYSTEM_STATUS

    if query.data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU

    return SYSTEM_STATUS


# =============================================================================
# SYSTEM INFO → CONFIRM → RUNNING
# =============================================================================

@only_me
async def system_info_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato SYSTEM_INFO: mostra il riepilogo pacchetti, riceve la
        conferma dell'utente (passa a SYSTEM_CONFIRM) o il "back"
        (torna al sottomenu Sistema).
    EN: SYSTEM_INFO state: shows the package summary, receives the user's
        confirmation (moves to SYSTEM_CONFIRM) or the back action
        (returns to the System sub-menu).
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "upd:system_confirm":
        count = ctx.user_data.get("pkg_count", 0)
        await edit(update, t("system_confirm", count=count), kb(
            InlineKeyboardButton(t("btn_yes"),         callback_data="run:system"),
            InlineKeyboardButton(t("btn_back_updates"), callback_data="nav:system_menu"),
        ))
        return SYSTEM_CONFIRM

    if data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU

    return SYSTEM_INFO


@only_me
async def system_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato SYSTEM_CONFIRM: "Sì" lancia `_run_system`, "← Sistema"
        torna al sottomenu Sistema.
    EN: SYSTEM_CONFIRM state: "Yes" launches `_run_system`, "← System"
        goes back to the System sub-menu.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:system":
        await _run_system(update, ctx)
        return SYSTEM_RUNNING

    if data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU

    return SYSTEM_CONFIRM


@only_me
async def system_running_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato SYSTEM_RUNNING: gestisce i bottoni di follow-up del
        messaggio live (Riprova sistema, Full upgrade, Autoremove, Menu
        principale).
    EN: SYSTEM_RUNNING state: handles the live-message follow-up buttons
        (Retry system, Full upgrade, Autoremove, Main menu).
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:system":
        await _run_system(update, ctx)
        return SYSTEM_RUNNING

    if data == "apt:autoremove":
        await _run_autoremove(update, ctx)
        return SYSTEM_RUNNING

    if data == "apt:full_upgrade":
        await _run_full_upgrade(update, ctx)
        return SYSTEM_RUNNING

    if data == "nav:new_main":
        await send_main_menu(update.get_bot(), AUTHORIZED_CHAT)
        return MAIN_MENU

    return SYSTEM_RUNNING


# =============================================================================
# REBOOT CONFIRM → RUNNING
# =============================================================================

@only_me
async def reboot_confirm_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Stato REBOOT_CONFIRM: "Sì" scrive il flag di reboot, mostra il
        messaggio di addio e lancia `systemctl reboot` (con fallback su
        `/sbin/reboot`). "No" torna al menu aggiornamenti. Al boot
        successivo, `post_init` di `stack_updater.py` rileva il flag, lo
        rimuove e invia un messaggio di conferma "riavvio completato".
    EN: REBOOT_CONFIRM state: "Yes" writes the reboot flag, shows the
        goodbye message and invokes `systemctl reboot` (with a
        `/sbin/reboot` fallback). "No" returns to the updates menu. On
        the next boot, `post_init` in `stack_updater.py` picks up the
        flag, deletes it, and sends a "reboot done" confirmation message.
    """
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "run:reboot":
        await edit(update, t("reboot_bye"))
        Path(REBOOT_FLAG).write_text(str(AUTHORIZED_CHAT))
        # Breve sleep per dare a Telegram il tempo di consegnare l'edit
        # prima che systemd ci tolga la corrente / brief sleep so Telegram
        # delivers the edit before systemd cuts power.
        await asyncio.sleep(2)
        try:
            subprocess.Popen(["/bin/systemctl", "reboot"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.Popen(["/sbin/reboot"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return REBOOT_RUNNING

    if data == "nav:system_menu":
        await _show_system_menu(update)
        return SYSTEM_MENU

    return REBOOT_CONFIRM
