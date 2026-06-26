"""
IT: Handler della sezione Impostazioni. Gestisce sia il menu (stato
    SETTINGS_MENU con i bottoni delle varie opzioni) sia gli input testuali
    (stato SETTINGS_INPUT) per modificare directory docker-compose, giorno
    e ora del promemoria, nickname utente e lingua. Include anche
    "Verifica aggiornamenti" che bypassa la cache 24h e, se trovato un
    update, permette di lanciarlo direttamente. Il cambio del promemoria
    riprogramma il `JobQueue` in-place.
EN: Settings section handlers. Manages both the menu (SETTINGS_MENU state
    with the option buttons) and the textual input (SETTINGS_INPUT state)
    to edit the docker-compose directory, reminder day/time, username and
    language. Also includes "Check for updates" which bypasses the 24 h
    cache and, when an update is found, lets the user launch it
    immediately. Changing the reminder reschedules the `JobQueue` in
    place.
"""
import logging
import re
from datetime import datetime, time as dtime
from pathlib import Path

from telegram import InlineKeyboardButton, Update
from telegram.ext import ContextTypes

from config import cfg_lang, cfg_name, cfg_reminder, load_config, save_config
from lang import L, load_lang, switch_lang, t
from operations.app_update import _run_app_update
from states import MAIN_MENU, SETTINGS_INPUT, SETTINGS_MENU
from ui import _main_menu_kb
from utils import edit, kb, only_me
from version import VERSION, check_remote_version, parse_version

log = logging.getLogger(__name__)

# =============================================================================
# SETTINGS
# =============================================================================

def _settings_kb():
    """
    IT: Costruisce la tastiera inline del menu Impostazioni (directory,
        giorno, ora, username, lingua, verifica updates, back).
    EN: Build the inline keyboard for the Settings menu (directory, day,
        time, username, language, check updates, back).
    """
    return kb(
        InlineKeyboardButton(t("btn_settings_dir"),      callback_data="set:ask:dir"),
        InlineKeyboardButton(t("btn_settings_day"),      callback_data="set:ask:day"),
        InlineKeyboardButton(t("btn_settings_time"),     callback_data="set:ask:time"),
        InlineKeyboardButton(t("btn_settings_username"), callback_data="set:ask:username"),
        InlineKeyboardButton(t("btn_settings_lang"),     callback_data="set:ask:lang"),
        InlineKeyboardButton(t("btn_settings_updates"),  callback_data="set:check:updates"),
        InlineKeyboardButton(t("btn_back_main"),         callback_data="nav:main_from_settings"),
    )

async def _show_settings(update: Update):
    """
    IT: Mostra la schermata principale delle Impostazioni editando il
        messaggio corrente.
    EN: Render the Settings home screen by editing the current message.
    """
    await edit(update, t("settings_menu"), _settings_kb())

@only_me
async def settings_menu_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Dispatcher dei bottoni del menu Impostazioni. Ogni `set:ask:*`
        mostra la schermata di input richiedendo all'utente di scrivere il
        nuovo valore (passando a SETTINGS_INPUT). `set:check:updates`
        forza un controllo aggiornamenti aggirando la cache 24h.
    EN: Settings-menu button dispatcher. Each `set:ask:*` shows the input
        screen prompting the user to type the new value (moving to
        SETTINGS_INPUT). `set:check:updates` forces an update check that
        bypasses the 24 h cache.
    """
    query = update.callback_query
    await query.answer()
    data = query.data
    c = load_config()
    day, hour, minute = cfg_reminder()

    if data == "nav:main_from_settings":
        name = cfg_name()
        await edit(update, t("main_menu", name=name), _main_menu_kb())
        return MAIN_MENU

    back_kb = kb(InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"))

    if data == "set:ask:dir":
        ctx.user_data["setting_key"] = "dir"
        await edit(update, t("settings_ask_dir", current=c.get("docker_dir", "")), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:day":
        ctx.user_data["setting_key"] = "day"
        await edit(update, t("settings_ask_day", current=str(day)), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:time":
        now = datetime.now().astimezone()
        system_time = now.strftime("%H:%M")
        timezone = now.tzinfo
        ctx.user_data["setting_key"] = "time"
        current_time = f"{hour:02d}:{minute:02d}"
        await edit(update, t("settings_ask_time", current=current_time, system_time=system_time, timezone=timezone), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:username":
        ctx.user_data["setting_key"] = "username"
        await edit(update, t("settings_ask_username", current=c.get("user_name", "")), back_kb)
        return SETTINGS_INPUT

    if data == "set:ask:lang":
        ctx.user_data["setting_key"] = "lang"
        lang_names = {"it": "Italiano", "en": "English"}
        current_label = lang_names.get(cfg_lang(), cfg_lang())
        await edit(update, t("settings_ask_lang", current=current_label), back_kb)
        return SETTINGS_INPUT

    if data == "set:check:updates":
        await edit(update, t("settings_checking_updates"))
        # Forza il refresh resettando il timestamp di cache.
        cfg_tmp = load_config()
        cfg_tmp.pop("last_version_check", None)
        save_config(cfg_tmp)
        available = await check_remote_version()
        if available and parse_version(available) > parse_version(VERSION):
            await edit(update,
                t("settings_update_found", current=VERSION, latest=available),
                kb(
                    InlineKeyboardButton(t("btn_update_app"),  callback_data="set:do:update"),
                    InlineKeyboardButton(t("btn_back_updates"), callback_data="set:back"),
                )
            )
        else:
            await edit(update, t("settings_no_updates", version=VERSION), back_kb)
        return SETTINGS_MENU

    if data == "set:do:update":
        await _run_app_update(update, ctx)
        return SETTINGS_MENU

    if data == "set:back":
        await _show_settings(update)
        return SETTINGS_MENU

    return SETTINGS_MENU

@only_me
async def settings_input_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Riceve il testo inserito dall'utente in SETTINGS_INPUT e applica
        l'aggiornamento corrispondente a `ctx.user_data["setting_key"]`
        (dir/day/time/username/lang) con validazione per ogni tipo:
            - dir: deve esistere come directory
            - day: intero 1..28
            - time: formato HH:MM con ranges validi
            - username: non vuoto
            - lang: mappato a 'it' o 'en' (case insensitive)
        Su cambio di giorno/ora ripianifica il job mensile.
    EN: Handle the user-typed text in SETTINGS_INPUT and apply the
        update matching `ctx.user_data["setting_key"]`
        (dir/day/time/username/lang), with per-type validation:
            - dir: must be an existing directory
            - day: integer in 1..28
            - time: HH:MM with valid ranges
            - username: non-empty
            - lang: mapped to 'it' or 'en' (case insensitive)
        Reschedules the monthly job when day/time changes.
    """
    text = update.message.text.strip()
    key  = ctx.user_data.get("setting_key", "")
    c    = load_config()

    if key == "dir":
        if not Path(text).is_dir():
            await update.message.reply_html(t("settings_invalid_dir"))
            return SETTINGS_INPUT
        c["docker_dir"] = text
        save_config(c)
        await update.message.reply_html(t("settings_saved_dir", value=text), reply_markup=_settings_kb())

    elif key == "day":
        if not text.isdigit() or not (1 <= int(text) <= 28):
            await update.message.reply_html(t("settings_invalid_day"))
            return SETTINGS_INPUT
        c["reminder_day"] = int(text)
        save_config(c)
        _reschedule_reminder(ctx)
        await update.message.reply_html(t("settings_saved_day", value=text), reply_markup=_settings_kb())

    elif key == "time":
        if not re.match(r"^\d{2}:\d{2}$", text):
            await update.message.reply_html(t("settings_invalid_time"))
            return SETTINGS_INPUT
        hh, mm = int(text[:2]), int(text[3:])
        if hh > 23 or mm > 59:
            await update.message.reply_html(t("settings_invalid_time"))
            return SETTINGS_INPUT
        c["reminder_hour"]   = hh
        c["reminder_minute"] = mm
        save_config(c)
        _reschedule_reminder(ctx)
        await update.message.reply_html(t("settings_saved_time", value=text), reply_markup=_settings_kb())

    elif key == "username":
        if not text:
            return SETTINGS_INPUT
        c["user_name"] = text
        save_config(c)
        await update.message.reply_html(t("settings_saved_username", value=text), reply_markup=_settings_kb())

    elif key == "lang":
        lang_map = {
            "it": "it", "italiano": "it", "italian": "it",
            "en": "en", "english": "en", "inglese": "en",
        }
        lang_code = lang_map.get(text.lower())
        if not lang_code:
            await update.message.reply_html(t("settings_invalid_lang"))
            return SETTINGS_INPUT
        if not await switch_lang(lang_code):
            await update.message.reply_html(t("settings_invalid_lang"))
            return SETTINGS_INPUT
        lang_label = "Italiano" if lang_code == "it" else "English"
        # _settings_kb() viene ricostruita dopo il cambio lingua perché
        # legge le stringhe da L che è stato appena aggiornato.
        await update.message.reply_html(
            t("settings_saved_lang", value=lang_label),
            reply_markup=_settings_kb()
        )

    return SETTINGS_MENU

def _reschedule_reminder(ctx: ContextTypes.DEFAULT_TYPE):
    """
    IT: Rimuove il job mensile corrente dal `JobQueue` e ne crea uno nuovo
        con i valori aggiornati di giorno/ora/minuto presi dalla config.
        Senza riavvio del bot.
    EN: Remove the current monthly job from the `JobQueue` and create a
        new one with the updated day/hour/minute values from the config.
        No bot restart required.
    """
    from handlers.jobs import monthly_reminder_job
    jq = ctx.application.job_queue
    for job in jq.get_jobs_by_name("monthly_reminder"):
        job.schedule_removal()
    day, hour, minute = cfg_reminder()
    tz = datetime.now().astimezone().tzinfo
    jq.run_monthly(
        monthly_reminder_job,
        when=dtime(hour, minute, tzinfo=tz),
        day=day,
        name="monthly_reminder",
    )
    log.info("Promemoria ripianificato: giorno %d alle %02d:%02d", day, hour, minute)
