"""
IT: Sistema di traduzione del bot. Carica al boot il file JSON della lingua
    attiva (it/en) in un dict in-memory `L`, espone la funzione `t()` per
    interpolare le stringhe (con fallback alla chiave se mancante) e
    `switch_lang()` per cambiare lingua a runtime — scaricando il file dal
    repo se non presente in locale.
EN: Bot translation layer. At boot loads the JSON file for the active
    language (it/en) into an in-memory dict `L`, exposes `t()` to interpolate
    strings (falling back to the key when missing) and `switch_lang()` to
    change language at runtime — downloading the file from the repo when not
    available locally.
"""
import logging

from config import LANG_DIR, load_config, save_config
from utils import run_cmd
from version import REPO_BASE

log = logging.getLogger(__name__)

# =============================================================================
# LINGUA
# =============================================================================

def load_lang() -> dict:
    """
    IT: Legge il file JSON corrispondente alla lingua corrente
        (`languages/<code>.json`) e lo ritorna come dict. In caso di errore
        ritorna dict vuoto e logga un warning — `t()` userà le chiavi come
        fallback.
    EN: Read the JSON file matching the current language
        (`languages/<code>.json`) and return it as a dict. On error returns
        an empty dict and logs a warning — `t()` will fall back to keys.
    """
    lang = load_config().get("lang", "it")
    lang_file = LANG_DIR / f"{lang}.json"
    try:
        import json
        with open(lang_file) as f:
            return json.load(f)
    except Exception as e:
        log.warning("Lingua non caricata (%s): %s", lang_file, e)
        return {}

L = load_lang()

def t(key: str, **kwargs) -> str:
    """
    IT: Traduce una chiave applicando interpolazione `.format(**kwargs)`. Se
        la chiave non esiste in `L`, ritorna la chiave stessa (utile in
        sviluppo per individuare stringhe mancanti). Se l'interpolazione
        fallisce ritorna il template grezzo.
    EN: Translate a key applying `.format(**kwargs)` interpolation. When the
        key is missing from `L`, returns the key itself (handy during
        development to spot missing strings). If interpolation fails the raw
        template is returned.

    Args:
        key:    chiave nel file lingua / lookup key in the language file.
        kwargs: variabili da interpolare nel template / placeholder values.
    Returns:
        stringa tradotta o fallback / translated string or fallback.
    """
    template = L.get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError):
        return template

async def switch_lang(lang_code: str) -> bool:
    """
    IT: Cambia la lingua attiva del bot. Se il file lingua non è presente
        localmente lo scarica dal repo. Aggiorna `stack_updater_config.json`
        e ricarica `L` in-place così tutti i `t()` successivi usano la nuova
        lingua senza riavvio.
    EN: Switch the bot's active language. If the language file is missing
        locally it gets downloaded from the repo. Persists the choice in
        `stack_updater_config.json` and reloads `L` in place so subsequent
        `t()` calls use the new language without a restart.

    Args:
        lang_code: codice lingua ("it", "en", ...) / language code.
    Returns:
        True se cambio riuscito, False se download fallito /
        True on success, False if the download failed.
    """
    lang_file = LANG_DIR / f"{lang_code}.json"
    if not lang_file.exists():
        LANG_DIR.mkdir(parents=True, exist_ok=True)
        code, _ = await run_cmd([
            "curl", "-fsSL", "--max-time", "15",
            f"{REPO_BASE}/src/languages/{lang_code}.json",
            "-o", str(lang_file),
        ])
        if code != 0 or not lang_file.exists():
            return False
    c = load_config()
    c["lang"] = lang_code
    save_config(c)
    L.clear()
    L.update(load_lang())
    return True
