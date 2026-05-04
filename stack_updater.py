#!/usr/bin/env python3
"""
stack_updater.py — Telegram Bot for automated Debian + Docker updates
Requires: pip3 install "python-telegram-bot[job-queue]" --break-system-packages
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, time as dtime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

# =============================================================================
# CONFIGURATION — do not edit manually, managed by install.sh
# =============================================================================
TELEGRAM_TOKEN  = "IL_TUO_TOKEN_QUI"
AUTHORIZED_CHAT = 123456789
DOCKER_DIR      = "/home/pi/homeassistant_hub/docker-config"
LOG_FILE        = "/var/log/stack_updater.log"
LANG_FILE       = "/usr/local/bin/stack_updater_lang.json"
# =============================================================================

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)
log = logging.getLogger(__name__)
HOSTNAME = os.uname().nodename


# ---------------------------------------------------------------------------
# Internazionalizzazione — carica il file lingua scelto durante l'installazione
# ---------------------------------------------------------------------------

def load_lang() -> dict:
    """
    Carica il file lingua da LANG_FILE.
    Se non esiste o è corrotto, usa l'inglese come fallback hardcoded minimale.
    """
    try:
        with open(LANG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            log.info("Lingua caricata: %s", data.get("_language", "unknown"))
            return data
    except Exception as e:
        log.warning("Impossibile caricare il file lingua '%s': %s — uso fallback EN", LANG_FILE, e)
        return _fallback_en()


def _fallback_en() -> dict:
    """Stringhe inglesi minimali usate solo se il file lingua manca."""
    return {
        "btn_update_now": "🔄 Update now", "btn_status": "📋 Container status",
        "btn_yes_update": "✅ Yes, update", "btn_no_cancel": "❌ No, cancel",
        "btn_yes_update_now": "✅ Yes, update now", "btn_no_later": "❌ No, I'll do it later",
        "btn_retry": "🔁 Retry", "btn_continue": "▶️ Continue anyway", "btn_abort": "🛑 Abort",
        "start_welcome": "👋 Update bot for <b>{hostname}</b>\n\nWhat would you like to do?",
        "update_confirm": "🖥️ <b>{hostname}</b>\n\nRun full update?\n• Step 1: apt-get update + upgrade\n• Step 2: docker compose pull\n• Step 3: docker compose up -d\n• Cleanup: docker image prune",
        "update_started": "🚀 <b>{hostname}</b> — Update started\n{datetime}",
        "step1_start": "⏳ <b>Step 1/3 — Debian system update</b>\napt-get update + upgrade in progress…",
        "step1_update_failed": "❌ <b>Step 1 — apt-get update failed</b>\n\n<pre>{output}</pre>\n\nWhat would you like to do?",
        "step1_problems": "⚠️ <b>Step 1 — Debian update completed with issues</b>\n\nProblems detected:\n<pre>{problems}</pre>\n\nWhat would you like to do?",
        "step1_upgrade_failed": "❌ <b>Step 1 — apt-get upgrade failed (exit {code})</b>\n\n<pre>{output}</pre>\n\nWhat would you like to do?",
        "step1_ok": "✅ <b>Step 1 completed</b> — Debian updated successfully.\nMoving on to container updates.",
        "step2_start": "⏳ <b>Step 2/3 — Docker image pull</b>\ndocker compose pull in progress…",
        "step2_problems": "⚠️ <b>Step 2 — Pull completed with issues</b>\n\nThese containers had problems:\n<pre>{problems}</pre>\n\nWhat would you like to do?",
        "step2_failed": "❌ <b>Step 2 — docker compose pull failed (exit {code})</b>\n\n<pre>{output}</pre>\n\nWhat would you like to do?",
        "step2_ok": "✅ <b>Step 2 completed</b> — Images updated successfully.\nMoving on to starting containers.",
        "step3_start": "⏳ <b>Step 3/3 — Starting containers</b>\ndocker compose up -d in progress…",
        "step3_problems": "⚠️ <b>Step 3 — Startup completed with issues</b>\n\nThese containers had problems:\n<pre>{problems}</pre>\n\nWhat would you like to do?",
        "step3_failed": "❌ <b>Step 3 — docker compose up failed (exit {code})</b>\n\n<pre>{output}</pre>\n\nWhat would you like to do?",
        "step3_ok": "✅ <b>Step 3 completed</b> — Containers started successfully.\nRunning cleanup…",
        "space_freed": " (space freed: {space})",
        "final_ok": "🎉 <b>Update completed successfully!</b>\nDate: {datetime}{space_freed}\n\nActive containers:\n<pre>{containers}</pre>",
        "final_with_errors": "✅ <b>Update completed with ignored errors.</b>\nDate: {datetime}{space_freed}\n\n<b>Problems encountered:</b>\n{summary}\n\nActive containers:\n<pre>{containers}</pre>",
        "retrying_step": "🔁 Retrying step {step}…",
        "continuing_step": "▶️ Continuing from step {step}…",
        "aborted": "🛑 Update aborted. Please intervene manually if needed.",
        "error_ignored": "(error ignored by user — see previous messages)",
        "status_header": "📋 <b>Active containers on {hostname}:</b>\n<pre>{containers}</pre>",
        "no_containers": "(no containers found)",
        "monthly_reminder": "📅 <b>Monthly reminder — {hostname}</b>\n\nIt's time to update the system!\nDo you want to proceed now?",
        "install_complete": "🎉 <b>Installation complete!</b>\n\nThe bot is running on <b>{hostname}</b>.\n\nSend /start to see the menu, or /update to update now.",
    }


# Carica la lingua all'avvio
L = load_lang()


def t(key: str, **kwargs) -> str:
    """
    Restituisce la stringa tradotta per la chiave data,
    sostituendo i placeholder {nome} con i valori in kwargs.
    Se la chiave non esiste, restituisce la chiave stessa come fallback.
    """
    template = L.get(key, key)
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


# ---------------------------------------------------------------------------
# Helpers base
# ---------------------------------------------------------------------------

def only_me(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        chat_id = (
            update.effective_chat.id if update.effective_chat
            else update.callback_query.message.chat_id
        )
        if chat_id != AUTHORIZED_CHAT:
            return
        return await func(update, ctx)
    return wrapper


async def send(ctx, text: str, keyboard=None):
    kwargs = dict(chat_id=AUTHORIZED_CHAT, text=text, parse_mode="HTML")
    if keyboard:
        kwargs["reply_markup"] = InlineKeyboardMarkup(keyboard)
    return await ctx.bot.send_message(**kwargs)


async def run_cmd(cmd: list, cwd: str = None) -> tuple:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode, stdout.decode(errors="replace").strip()


def truncate(text: str, limit: int = 1200) -> str:
    if len(text) > limit:
        return "…\n" + text[-limit:]
    return text


# ---------------------------------------------------------------------------
# Stato della sessione
# ---------------------------------------------------------------------------

def new_session():
    return {
        "skipped_errors": [],
        "current_step": 0,
    }


def session(ctx) -> dict:
    if "session" not in ctx.application.bot_data:
        ctx.application.bot_data["session"] = new_session()
    return ctx.application.bot_data["session"]


def record_skipped_error(ctx, step_id: str, description: str, problems: list):
    session(ctx)["skipped_errors"].append({
        "step": step_id,
        "description": description,
        "problems": problems,
    })


# ---------------------------------------------------------------------------
# Parsing output per passo
# ---------------------------------------------------------------------------

def parse_apt_problems(output: str) -> list:
    problems = []
    for line in output.splitlines():
        low = line.lower()
        if any(kw in low for kw in ("err:", "e:", "w:", "warning:", "failed", "unable to")):
            problems.append(line.strip())
    return problems


def parse_docker_pull_problems(output: str) -> list:
    problems = []
    current_service = None
    for line in output.splitlines():
        service_match = re.match(r"^\s*(\w[\w_-]*)\s+Pulling\b", line)
        if service_match:
            current_service = service_match.group(1)
        error_match = re.match(r"^\s*(\w[\w_-]*)\s+Error\b", line, re.IGNORECASE)
        if error_match:
            problems.append(f"• {error_match.group(1)}: pull error")
            current_service = None
            continue
        if "error" in line.lower() or "failed" in line.lower():
            label = f"• {current_service}: " if current_service else "• "
            problems.append(label + line.strip())
    return list(dict.fromkeys(problems))


def parse_docker_up_problems(output: str) -> list:
    problems = []
    for line in output.splitlines():
        low = line.lower()
        if "error" in low or "failed" in low or "exited" in low:
            problems.append("• " + line.strip())
    return list(dict.fromkeys(problems))


# ---------------------------------------------------------------------------
# Bottoni di scelta dopo un problema
# ---------------------------------------------------------------------------

def problem_keyboard(step_index: int) -> list:
    return [[
        InlineKeyboardButton(t("btn_retry"),    callback_data=f"retry:{step_index}"),
        InlineKeyboardButton(t("btn_continue"), callback_data=f"continue:{step_index}"),
        InlineKeyboardButton(t("btn_abort"),    callback_data="abort"),
    ]]


# ---------------------------------------------------------------------------
# I tre passi principali
# ---------------------------------------------------------------------------

async def step_apt(ctx) -> bool | None:
    await send(ctx, t("step1_start"))

    code, output = await run_cmd(["apt-get", "update", "-q"])
    log.info("apt-get update: exit=%d", code)

    if code != 0:
        await send(ctx, t("step1_update_failed", output=truncate(output)),
                   keyboard=problem_keyboard(0))
        session(ctx)["current_step"] = 0
        return None

    code, output = await run_cmd(["apt-get", "upgrade", "-y", "-q"])
    log.info("apt-get upgrade: exit=%d", code)

    problems = parse_apt_problems(output)

    if code != 0 or problems:
        if problems:
            msg = t("step1_problems", problems="\n".join(problems[:20]))
        else:
            msg = t("step1_upgrade_failed", code=code, output=truncate(output))
        await send(ctx, msg, keyboard=problem_keyboard(0))
        session(ctx)["current_step"] = 0
        return None

    await send(ctx, t("step1_ok"))
    return True


async def step_docker_pull(ctx) -> bool | None:
    await send(ctx, t("step2_start"))

    code, output = await run_cmd(["docker", "compose", "pull"], cwd=DOCKER_DIR)
    log.info("docker compose pull: exit=%d", code)

    problems = parse_docker_pull_problems(output)

    if code != 0 or problems:
        if problems:
            msg = t("step2_problems", problems="\n".join(problems[:20]))
        else:
            msg = t("step2_failed", code=code, output=truncate(output))
        await send(ctx, msg, keyboard=problem_keyboard(1))
        session(ctx)["current_step"] = 1
        return None

    await send(ctx, t("step2_ok"))
    return True


async def step_docker_up(ctx) -> bool | None:
    await send(ctx, t("step3_start"))

    code, output = await run_cmd(["docker", "compose", "up", "-d"], cwd=DOCKER_DIR)
    log.info("docker compose up -d: exit=%d", code)

    problems = parse_docker_up_problems(output)

    if code != 0 or problems:
        if problems:
            msg = t("step3_problems", problems="\n".join(problems[:20]))
        else:
            msg = t("step3_failed", code=code, output=truncate(output))
        await send(ctx, msg, keyboard=problem_keyboard(2))
        session(ctx)["current_step"] = 2
        return None

    await send(ctx, t("step3_ok"))
    return True


async def step_prune(ctx) -> str:
    code, output = await run_cmd(["docker", "image", "prune", "-f"])
    log.info("docker image prune: exit=%d", code)
    match = re.search(r"Total reclaimed space: (.+)", output)
    if match:
        return t("space_freed", space=match.group(1))
    return ""


# ---------------------------------------------------------------------------
# Orchestratore principale
# ---------------------------------------------------------------------------

STEP_FUNCTIONS = [step_apt, step_docker_pull, step_docker_up]
STEP_NAMES     = ["apt update+upgrade", "docker compose pull", "docker compose up -d"]


async def run_update(ctx, start_from: int = 0):
    if start_from == 0:
        ctx.application.bot_data["session"] = new_session()
        await send(ctx, t("update_started",
                          hostname=HOSTNAME,
                          datetime=datetime.now().strftime("%d/%m/%Y %H:%M")))

    for i in range(start_from, len(STEP_FUNCTIONS)):
        result = await STEP_FUNCTIONS[i](ctx)
        if result is None:
            return

    space_freed = await step_prune(ctx)
    await send_final_report(ctx, space_freed)


async def send_final_report(ctx, space_freed: str = ""):
    sess = session(ctx)
    skipped = sess.get("skipped_errors", [])
    containers = await _container_status()
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not skipped:
        await send(ctx, t("final_ok",
                          datetime=now,
                          space_freed=space_freed,
                          containers=containers))
    else:
        summary_lines = []
        for e in skipped:
            summary_lines.append(f"⚠️ <b>{e['description']}</b>")
            for p in e["problems"]:
                summary_lines.append(f"   {p}")
        await send(ctx, t("final_with_errors",
                          datetime=now,
                          space_freed=space_freed,
                          summary="\n".join(summary_lines),
                          containers=containers))

    ctx.application.bot_data["session"] = new_session()


async def _container_status() -> str:
    _, out = await run_cmd(
        ["docker", "compose", "ps", "--format", "table {{.Name}}\t{{.Status}}"],
        cwd=DOCKER_DIR,
    )
    return out or t("no_containers")


# ---------------------------------------------------------------------------
# Handlers Telegram
# ---------------------------------------------------------------------------

@only_me
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton(t("btn_update_now"), callback_data="update:0"),
        InlineKeyboardButton(t("btn_status"),     callback_data="status"),
    ]]
    await update.message.reply_html(
        t("start_welcome", hostname=HOSTNAME),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


@only_me
async def cmd_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton(t("btn_yes_update"), callback_data="update:0"),
        InlineKeyboardButton(t("btn_no_cancel"),  callback_data="abort"),
    ]]
    await update.message.reply_html(
        t("update_confirm", hostname=HOSTNAME),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


@only_me
async def on_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)
    data = query.data

    if data.startswith("update:"):
        step = int(data.split(":")[1])
        await run_update(ctx, start_from=step)

    elif data.startswith("retry:"):
        step = int(data.split(":")[1])
        await send(ctx, t("retrying_step", step=step + 1))
        await run_update(ctx, start_from=step)

    elif data.startswith("continue:"):
        step = int(data.split(":")[1])
        record_skipped_error(
            ctx,
            step_id=f"step_{step}",
            description=STEP_NAMES[step],
            problems=[t("error_ignored")]
        )
        next_step = step + 1
        if next_step < len(STEP_FUNCTIONS):
            await send(ctx, t("continuing_step", step=next_step + 1))
            await run_update(ctx, start_from=next_step)
        else:
            space_freed = await step_prune(ctx)
            await send_final_report(ctx, space_freed)

    elif data == "abort":
        await send(ctx, t("aborted"))
        ctx.application.bot_data["session"] = new_session()

    elif data == "status":
        containers = await _container_status()
        await send(ctx, t("status_header", hostname=HOSTNAME, containers=containers))


# ---------------------------------------------------------------------------
# Promemoria mensile
# ---------------------------------------------------------------------------

async def monthly_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton(t("btn_yes_update_now"), callback_data="update:0"),
        InlineKeyboardButton(t("btn_no_later"),       callback_data="abort"),
    ]]
    await ctx.bot.send_message(
        chat_id=AUTHORIZED_CHAT,
        text=t("monthly_reminder", hostname=HOSTNAME),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("update", cmd_update))
    app.add_handler(CallbackQueryHandler(on_callback))

    app.job_queue.run_monthly(
        monthly_reminder,
        when=dtime(9, 0),
        day=10,
        name="monthly_reminder",
    )

    log.info("Bot started — polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
