"""
IT: Self-update del bot. Scarica dall'URL raw del repo tutti i file Python,
    i file lingua e il file VERSION, li sostituisce in `INSTALL_DIR`, salva
    lo stato di "restart in corso" nel config per riprendere l'UX dopo il
    riavvio, infine lancia in background `systemctl restart stack_updater`.
    Il messaggio live viene completato dopo il riavvio dal blocco
    `post_init` di `stack_updater.py`.
EN: Bot self-update routine. Downloads every Python file, language file and
    the VERSION file from the repo's raw URL, swaps them into `INSTALL_DIR`,
    persists a "restart in progress" marker in the config so the UX can
    resume after the restart, then fires `systemctl restart stack_updater`
    in the background. The live message is completed after the restart by
    the `post_init` hook in `stack_updater.py`.
"""
import asyncio
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import AUTHORIZED_CHAT, INSTALL_DIR, LANG_DIR, load_config, save_config
from lang import t
from utils import kb, run_cmd, truncate, update_live
from version import REPO_BASE

log = logging.getLogger(__name__)

# =============================================================================
# OPERAZIONI — AGGIORNAMENTO BOT
# =============================================================================

# Elenco di tutti i file Python che compongono il bot (oltre a stack_updater.py).
# Ogni voce è (relative_path,) — viene scaricata sotto INSTALL_DIR mantenendo
# la struttura di sottocartelle (handlers/, helpers/, operations/).
_BOT_FILES = [
    "states.py",
    "config.py",
    "utils.py",
    "lang.py",
    "version.py",
    "ui.py",
    "handlers/__init__.py",
    "handlers/shared.py",
    "handlers/start.py",
    "handlers/menu.py",
    "handlers/system.py",
    "handlers/docker.py",
    "handlers/all_updates.py",
    "handlers/settings.py",
    "handlers/jobs.py",
    "helpers/__init__.py",
    "helpers/docker.py",
    "helpers/system.py",
    "operations/__init__.py",
    "operations/core.py",
    "operations/system_ops.py",
    "operations/docker_ops.py",
    "operations/all_ops.py",
    "operations/app_update.py",
]


async def _download_file(rel_path: str) -> tuple[int, str]:
    """
    IT: Scarica un singolo file dal repo (`REPO_BASE/src/<rel_path>`) e lo
        salva in `INSTALL_DIR/<rel_path>`. Il prefisso `src/` è solo nel
        repo (struttura organizzativa); l'installazione è sempre piatta.
        Crea le directory intermedie se non esistono.
        Ritorna `(returncode, output)` di curl.
    EN: Download a single file from the repo (`REPO_BASE/src/<rel_path>`)
        into `INSTALL_DIR/<rel_path>`. The `src/` prefix exists only in
        the repo (organisational structure); the install layout is always
        flat. Creates parent directories on demand.
        Returns curl's `(returncode, output)`.
    """
    dest = INSTALL_DIR / rel_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    return await run_cmd([
        "curl", "-fsSL", "--max-time", "30",
        f"{REPO_BASE}/src/{rel_path}", "-o", str(dest),
    ])


async def _run_app_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Esegue il self-update del bot. Scarica `stack_updater.py` come file
        temporaneo (per non rompere il processo attivo se il download
        fallisce), poi tutti gli altri moduli Python in-place, i file
        lingua e il file VERSION. Su successo persiste in config gli
        identificatori del messaggio live (id, versione, timestamp) per la
        ripresa post-restart, sostituisce atomicamente `stack_updater.py`
        e lancia il riavvio del servizio.
    EN: Run the bot self-update. Downloads `stack_updater.py` to a
        temporary file first (so a download failure does not corrupt the
        running process), then every other Python module in place, the
        language files and the VERSION file. On success persists the
        live-message identifiers (id, version, timestamp) in the config so
        the UI can resume after the restart, atomically swaps
        `stack_updater.py` and triggers the service restart.
    """
    query    = update.callback_query
    bot      = update.get_bot()
    msg_id   = query.message.message_id
    c        = load_config()
    new_version = c.get("available_version", "?")
    start_dt    = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = [
        t("live_header", datetime=start_dt),
        t("separator"),
        t("step_update_title"),
        t("step_update_download"),
    ]
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # stack_updater.py viene scaricato come file temporaneo: lo si sostituisce
    # solo alla fine, dopo che tutti gli altri file sono stati aggiornati.
    tmp_bot = INSTALL_DIR / "stack_updater.py.new"
    code, out = await run_cmd([
        "curl", "-fsSL", "--max-time", "30",
        f"{REPO_BASE}/src/stack_updater.py", "-o", str(tmp_bot),
    ])
    if code != 0 or not tmp_bot.exists():
        lines.append(t("step_update_error") + t("error_detail", detail=truncate(out)))
        await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
            InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"),
        ))
        return

    # Scarica tutti i moduli Python (handlers/, helpers/, operations/, root)
    for rel in _BOT_FILES:
        code, out = await _download_file(rel)
        if code != 0:
            # Se uno fallisce annulla l'update — il bot vecchio continua a
            # funzionare perché stack_updater.py non è ancora stato sostituito.
            tmp_bot.unlink(missing_ok=True)
            lines.append(t("step_update_error") + t("error_detail", detail=truncate(out or rel)))
            await update_live(bot, AUTHORIZED_CHAT, msg_id, lines, kb(
                InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"),
            ))
            return

    LANG_DIR.mkdir(parents=True, exist_ok=True)
    for lang_code in ["it", "en"]:
        await run_cmd([
            "curl", "-fsSL", "--max-time", "10",
            f"{REPO_BASE}/src/languages/{lang_code}.json",
            "-o", str(LANG_DIR / f"{lang_code}.json"),
        ])

    await run_cmd([
        "curl", "-fsSL", "--max-time", "10",
        f"{REPO_BASE}/VERSION", "-o", str(INSTALL_DIR / "VERSION"),
    ])

    c.pop("available_version", None)
    c.pop("skipped_version", None)
    c.pop("last_version_check", None)
    c["update_restart_msg_id"]   = msg_id
    c["update_restart_version"]  = new_version
    c["update_restart_datetime"] = start_dt
    save_config(c)

    # Move atomico: dal punto di vista del filesystem la sostituzione del
    # bot avviene in un singolo syscall, riducendo la finestra di tempo in
    # cui un crash lascerebbe stack_updater.py in stato incoerente.
    shutil.move(str(tmp_bot), str(INSTALL_DIR / "stack_updater.py"))

    lines.append(t("step_update_ok", version=new_version))
    lines.append("")
    lines.append(t("step_update_restarting"))
    await update_live(bot, AUTHORIZED_CHAT, msg_id, lines)

    # Sleep 3s da subshell così il messaggio è già consegnato a Telegram
    # quando systemctl uccide il processo.
    await asyncio.sleep(1)
    subprocess.Popen(
        ["bash", "-c", "sleep 3 && systemctl restart stack_updater"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
