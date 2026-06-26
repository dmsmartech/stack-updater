"""
IT: Gestione della versione del bot e controllo aggiornamenti remoti. Espone
    la costante `VERSION` (versione installata) e `REPO_BASE` (URL raw del
    branch). Il controllo aggiornamenti remoti (`check_remote_version`) è
    cacheato per 24 ore per evitare chiamate ad ogni `/start`.
EN: Bot versioning and remote update check. Exposes the `VERSION` constant
    (installed version) and `REPO_BASE` (raw URL of the branch). The remote
    version check (`check_remote_version`) is cached for 24 h to avoid
    hitting GitHub on every `/start`.
"""
import logging
import time

from config import load_config, save_config
from utils import run_cmd

log = logging.getLogger(__name__)

# =============================================================================
# VERSION
# =============================================================================

VERSION   = "1.0.2"
REPO_BASE = "https://raw.githubusercontent.com/dmsmartech/stack-updater/dev"

def parse_version(v: str) -> tuple:
    """
    IT: Converte una stringa versione (es. "1.2.3") in una tupla di interi
        confrontabile lessicograficamente. In caso di parsing fallito
        ritorna `(0,)` così la versione viene considerata "vecchia".
    EN: Convert a version string (e.g. "1.2.3") to a tuple of integers,
        comparable lexicographically. On parse failure returns `(0,)` so the
        version is treated as "old".
    """
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0,)

async def check_remote_version() -> str | None:
    """
    IT: Controlla se sul repo è disponibile una versione più recente di
        quella installata. Usa una cache di 24 ore salvata nel config
        (`last_version_check` + `available_version`) per evitare chiamate
        ripetute. Ritorna la stringa della versione disponibile o None se
        siamo già aggiornati / il controllo fallisce.
    EN: Check whether the repo exposes a newer version than the installed
        one. Uses a 24 h cache in the config (`last_version_check` +
        `available_version`) to avoid repeated requests. Returns the
        available version string, or None if already up to date or the
        check failed.

    Returns:
        str con la nuova versione o None / new version string or None.
    """
    c = load_config()
    last_check = c.get("last_version_check", 0)
    now = time.time()

    if now - last_check < 86400:
        cached = c.get("available_version", "")
        if cached and parse_version(cached) > parse_version(VERSION):
            return cached
        return None

    code, out = await run_cmd([
        "curl", "-fsSL", "--max-time", "5", f"{REPO_BASE}/VERSION"
    ])
    if code != 0:
        return None

    remote = out.strip()
    c["last_version_check"] = now

    if remote and parse_version(remote) > parse_version(VERSION):
        c["available_version"] = remote
    else:
        c.pop("available_version", None)

    save_config(c)
    return c.get("available_version") or None
