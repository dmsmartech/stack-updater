"""
IT: Gestione della configurazione persistente del bot. Espone i path delle
    risorse (config JSON, directory lingue, log, flag di reboot), le funzioni
    `load_config` / `save_config` per leggere e scrivere il file JSON, e una
    serie di accessor `cfg_*` che restituiscono il valore corrente di ciascun
    campo facendo una rilettura del file (per riflettere modifiche fatte a
    runtime tramite la sezione Impostazioni).
EN: Persistent bot configuration. Exposes resource paths (config JSON,
    languages dir, log file, reboot flag), the `load_config` / `save_config`
    helpers to read/write the JSON file, and a set of `cfg_*` accessors that
    re-read the file each time so runtime changes made from the Settings
    section are picked up immediately.
"""
import json
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

# =============================================================================
# FILE PATHS
# =============================================================================
INSTALL_DIR = Path(__file__).parent
CONFIG_FILE = INSTALL_DIR / "stack_updater_config.json"
LANG_DIR    = INSTALL_DIR / "languages"
LOG_FILE    = "/var/log/stack_updater.log"
REBOOT_FLAG = "/var/lib/stack_updater_rebooted"

# =============================================================================
# CONFIG
# =============================================================================

def load_config() -> dict:
    """
    IT: Carica e ritorna il file di configurazione JSON come dict. In caso di
        errore (file mancante, JSON malformato) ritorna un dict vuoto e
        scrive un log d'errore — il bot continua a funzionare con i default.
    EN: Load and return the JSON config file as a dict. On any error (missing
        file, malformed JSON) returns an empty dict and logs an error — the
        bot keeps running with built-in defaults.

    Returns:
        dict con la configurazione (vuoto se non leggibile) /
        dict with the configuration (empty if unreadable).
    """
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except Exception as e:
        log.error("Impossibile caricare config: %s", e)
        return {}

def save_config(cfg: dict):
    """
    IT: Salva il dict passato come configurazione JSON, sovrascrivendo il
        file. Indentazione 2 spazi per renderlo leggibile a mano. Errori
        loggati senza propagare l'eccezione.
    EN: Persist the given dict as the JSON config, overwriting the file. Uses
        2-space indentation so the file stays human-readable. Errors are
        logged without raising.

    Args:
        cfg: dizionario di configurazione da serializzare /
             configuration dictionary to serialize.
    """
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        log.error("Impossibile salvare config: %s", e)

# =============================================================================
# MODULE-LEVEL VARIABLES
# =============================================================================
_cfg = load_config()
AUTHORIZED_CHAT = _cfg.get("chat_id", 0)
HOSTNAME        = os.uname().nodename

# =============================================================================
# CONFIG ACCESSORS
# =============================================================================

def cfg_name() -> str:
    """
    IT: Ritorna il nickname utente salvato in configurazione (usato nei
        messaggi del bot). Stringa vuota se non impostato.
    EN: Return the user nickname stored in config (interpolated into bot
        messages). Empty string when not set.
    """
    return load_config().get("user_name", "")

def cfg_docker_dir() -> str:
    """
    IT: Ritorna il path della directory contenente il file
        `docker-compose.yml` su cui il bot opera.
    EN: Return the path of the directory containing the `docker-compose.yml`
        the bot operates on.
    """
    return load_config().get("docker_dir", "")

def cfg_reminder() -> tuple:
    """
    IT: Ritorna la configurazione del promemoria mensile come tupla
        (giorno, ora, minuto). Default 10 alle 09:00 se non configurato.
    EN: Return the monthly reminder schedule as a (day, hour, minute) tuple.
        Defaults to day 10 at 09:00 when missing.

    Returns:
        tuple(int, int, int) — giorno del mese, ora, minuto /
        tuple(int, int, int) — day of month, hour, minute.
    """
    c = load_config()
    return c.get("reminder_day", 10), c.get("reminder_hour", 9), c.get("reminder_minute", 0)

def cfg_lang() -> str:
    """
    IT: Ritorna il codice lingua attivo ('it' o 'en'). Default 'it'.
    EN: Return the active language code ('it' or 'en'). Defaults to 'it'.
    """
    return load_config().get("lang", "it")
