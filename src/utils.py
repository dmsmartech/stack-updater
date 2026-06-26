"""
IT: Funzioni di utilità trasversali: decoratore di autorizzazione, esecuzione
    di comandi shell async, costruzione di tastiere inline, editing e
    aggiornamento dei "messaggi live" del bot. Non dipende da altri layer
    funzionali — solo da `config` per il chat id autorizzato.
EN: Cross-cutting utility functions: authorization decorator, async shell
    command runner, inline-keyboard builders, message-editing and live
    "streaming" message helpers. Independent of any functional layer — only
    depends on `config` for the authorized chat id.
"""
import asyncio
import logging
import os

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.error import BadRequest
from telegram.ext import ConversationHandler, ContextTypes

from config import AUTHORIZED_CHAT

log = logging.getLogger(__name__)

# =============================================================================
# HELPERS
# =============================================================================

PERSISTENT_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("📋 Menu")]],
    resize_keyboard=True,
)

def only_me(func):
    """
    IT: Decoratore per gli handler: blocca qualsiasi messaggio o callback che
        non provenga dal `chat_id` autorizzato salvato in configurazione,
        terminando la conversazione corrente. È la prima linea di difesa del
        bot — anche se Telegram filtra a livello di chat, la verifica server
        side qui evita usi impropri se l'id venisse cambiato a mano.
    EN: Handler decorator: drops any message or callback coming from a user
        id different from the configured `chat_id`, ending the current
        conversation. Acts as the bot's first defense — even though Telegram
        filters at the chat level, the server-side check here prevents
        misuse if the id were manually altered.

    Args:
        func: handler async da proteggere / async handler to wrap.
    Returns:
        wrapper async equivalente / equivalent async wrapper.
    """
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id if update.effective_user else None
        if uid != AUTHORIZED_CHAT:
            return ConversationHandler.END
        return await func(update, ctx)
    return wrapper

APT_ENV = os.environ | {"DEBIAN_FRONTEND": "noninteractive"}

async def run_cmd(cmd: list, cwd: str = None, env: dict = None) -> tuple:
    """
    IT: Esegue un comando come subprocess asincrono, catturando stdout e
        stderr unificati. Ritorna `(returncode, output)` con l'output
        decodificato in stringa (replace per byte non validi).
    EN: Run a command as an async subprocess, capturing stdout and stderr
        merged. Returns `(returncode, output)` with the output decoded to a
        string (errors='replace' for invalid bytes).

    Args:
        cmd: lista argv del comando / argv list of the command.
        cwd: working directory opzionale / optional working directory.
        env: dict di variabili d'ambiente opzionale / optional env dict.
    Returns:
        tuple(int, str) — return code e output combinato /
        tuple(int, str) — return code and combined output.
    """
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )
    out, _ = await proc.communicate()
    return proc.returncode, out.decode(errors="replace").strip()

def truncate(text: str, limit: int = 600) -> str:
    """
    IT: Tronca una stringa lasciando la coda (utile per gli output di apt e
        docker dove gli errori reali stanno in fondo). Aggiunge un prefisso
        "…\\n" per indicare il troncamento.
    EN: Truncate a string keeping the tail (useful for apt/docker output
        where the real errors are at the end). Adds an "…\\n" prefix to
        signal truncation.
    """
    return ("…\n" + text[-limit:]) if len(text) > limit else text

def kb(*rows) -> InlineKeyboardMarkup:
    """
    IT: Costruisce una InlineKeyboardMarkup con ogni bottone su una riga
        separata. Pensata per il layout verticale dominante nel bot.
    EN: Build an InlineKeyboardMarkup with one button per row. Optimized for
        the vertical layout used throughout the bot.
    """
    return InlineKeyboardMarkup([[btn] for btn in rows])

def kb_rows(*rows) -> InlineKeyboardMarkup:
    """
    IT: Costruisce una InlineKeyboardMarkup da righe già formate (liste di
        bottoni), per i casi rari in cui servono più bottoni sulla stessa
        riga.
    EN: Build an InlineKeyboardMarkup from pre-formed rows (button lists),
        for the rare cases where multiple buttons share a row.
    """
    return InlineKeyboardMarkup(list(rows))

async def edit(update: Update, text: str, keyboard: InlineKeyboardMarkup = None):
    """
    IT: Modifica il messaggio collegato al callback_query corrente con nuovo
        testo (HTML) e tastiera opzionale. Ignora silenziosamente l'errore
        "message is not modified" perché si verifica spesso quando la
        schermata target è identica.
    EN: Edit the message tied to the current callback_query, setting new
        text (HTML) and an optional keyboard. Silently swallows the
        "message is not modified" error which happens often when the target
        screen matches the current one.

    Args:
        update:   Update Telegram con un callback_query / Telegram update.
        text:     nuovo testo HTML / new HTML text.
        keyboard: tastiera inline opzionale / optional inline keyboard.
    """
    query = update.callback_query
    try:
        await query.edit_message_text(
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("edit error: %s", e)

async def create_live(bot, chat_id: int, text: str) -> int:
    """
    IT: Invia un nuovo messaggio "live" (che verrà successivamente editato
        con `update_live` per mostrare l'avanzamento di un'operazione) e
        ritorna il suo message_id.
    EN: Send a new "live" message (later edited in place by `update_live` to
        stream operation progress) and return its message_id.
    """
    msg = await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
    return msg.message_id

async def update_live(bot, chat_id: int, msg_id: int,
                      lines: list, keyboard: InlineKeyboardMarkup = None):
    """
    IT: Aggiorna il contenuto di un messaggio live concatenando le `lines`.
        Se il testo supera 4000 caratteri (limite Telegram = 4096) mantiene
        l'header e taglia la prima metà, evitando l'errore "Message too
        long". Errori "not modified" sono ignorati.
    EN: Update a live message's content by joining `lines`. When the text
        exceeds 4000 chars (Telegram's limit is 4096) it keeps the header
        and drops the first half to avoid a "Message too long" error.
        "Not modified" errors are silently ignored.

    Args:
        bot:      istanza del bot / bot instance.
        chat_id:  chat di destinazione / target chat.
        msg_id:   id del messaggio da editare / message id to edit.
        lines:    righe del messaggio / message lines.
        keyboard: tastiera inline opzionale / optional inline keyboard.
    """
    text = "\n".join(lines)
    if len(text) > 4000:
        text = lines[0] + "\n…\n" + "\n".join(lines[-(len(lines)//2):])
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=text, parse_mode="HTML",
            reply_markup=keyboard,
        )
    except BadRequest as e:
        if "not modified" not in str(e).lower():
            log.warning("update_live error: %s", e)
