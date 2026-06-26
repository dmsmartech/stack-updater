"""
IT: Helper di basso livello per il sistema: interazione con apt/dpkg e
    lettura delle risorse hardware (CPU, RAM, disco). Contiene i parser
    che analizzano l'output testuale di `apt-get`, la funzione di scoperta
    dei pacchetti aggiornabili e le routine async per leggere carico CPU,
    uso RAM e spazio disco.
EN: Low-level system helpers: apt/dpkg interaction and hardware resource
    reading (CPU, RAM, disk). Provides the parsers that turn `apt-get`
    textual output into structured data, the upgradable-package discovery
    routine and async routines for CPU load, RAM usage and disk space.
"""
import asyncio
import logging
import os
import re

from utils import run_cmd

log = logging.getLogger(__name__)

# =============================================================================
# APT / DPKG HELPERS
# =============================================================================

async def get_upgradable_count() -> tuple[int, str]:
    """
    IT: Esegue `apt-get update` silente, poi conta i pacchetti elencati come
        aggiornabili da `apt list --upgradable` e rileva il nome della
        distribuzione tramite `lsb_release`.
    EN: Run a silent `apt-get update`, count the upgradable packages listed
        by `apt list --upgradable` and detect the distro name via
        `lsb_release`.

    Returns:
        tuple(int, str) — (numero pacchetti, nome distro) /
        tuple(int, str) — (package count, distro name).
    """
    await run_cmd(["apt-get", "update", "-qq"])
    _, out = await run_cmd(["apt", "list", "--upgradable"])
    lines = [l for l in out.splitlines() if "/" in l]
    count = len(lines)
    _, distro_out = await run_cmd(["lsb_release", "-ds"])
    distro = distro_out.strip() or "Linux"
    return count, distro


def parse_apt_problems(output: str) -> list:
    """
    IT: Estrae le righe di errore reale dall'output di apt usando pattern
        ancorati all'inizio riga (e:, err:, error:) oppure keyword note
        come "failed", "unable to fetch/lock". Necessario perché grep
        semplice su "e:" matchava parole italiane come "attuale:".
    EN: Pull real error lines out of apt's output using line-anchored
        patterns (e:, err:, error:) or known keywords like "failed",
        "unable to fetch/lock". Needed because a naive "e:" grep would
        match Italian words such as "attuale:".

    Args:
        output: testo grezzo restituito da apt / raw apt output.
    Returns:
        lista di righe di errore individuate / list of detected error lines.
    """
    result = []
    for l in output.splitlines():
        s = l.strip()
        low = s.lower()
        if (low.startswith(("e: ", "err:", "error:"))
                or any(k in low for k in ("failed", "unable to fetch", "unable to lock"))):
            result.append(s)
    return result


def parse_autoremove_packages(output: str) -> list:
    """
    IT: Identifica i nomi dei pacchetti "non più richiesti" annunciati da
        `apt-get upgrade`, parsando il blocco che segue la riga "non sono
        più richiesti" (IT) o "no longer required/needed" (EN) fino al
        prossimo blocco riconoscibile.
    EN: Pull the names of "no longer required" packages announced by
        `apt-get upgrade`, by parsing the block following the
        "no longer required/needed" (EN) or "non sono più richiesti" (IT)
        header up to the next recognized block.

    Args:
        output: output di `apt-get upgrade` / `apt-get upgrade` output.
    Returns:
        lista di nomi pacchetto / list of package names.
    """
    packages = []
    in_block = False
    for line in output.splitlines():
        lower = line.lower()
        if ("non sono più richiesti" in lower or "no longer required" in lower
                or "no longer needed" in lower):
            in_block = True
            continue
        if in_block:
            stripped = line.strip()
            slow = stripped.lower()
            if (not stripped or slow.startswith("usare ") or slow.startswith("use ")
                    or slow.startswith("sudo") or slow.startswith("run ")
                    or slow.startswith("i seguenti") or slow.startswith("the following")):
                in_block = False
                continue
            packages.extend(stripped.split())
    return packages


def parse_held_packages(output: str) -> int:
    """
    IT: Ritorna il numero di pacchetti trattenuti riportato in coda
        all'output di `apt-get upgrade` (es. "4 non aggiornati" / "4 not
        upgraded"). Ritorna 0 se non c'è nessun trattenuto.
    EN: Return the number of held-back packages reported at the tail of
        `apt-get upgrade` output (e.g. "4 not upgraded" / "4 non
        aggiornati"). Returns 0 when none are held.
    """
    for line in output.splitlines():
        low = line.lower()
        m = re.search(r'(\d+) non aggiornati?', low)
        if not m:
            m = re.search(r'(\d+) not upgraded', low)
        if m:
            count = int(m.group(1))
            if count > 0:
                return count
    return 0


# =============================================================================
# SYSTEM RESOURCES (CPU, RAM, disco / disk)
# =============================================================================

def _bar(percent: float, width: int = 20) -> str:
    """
    IT: Genera una barra di avanzamento Unicode con caratteri `█` (pieno)
        e `░` (vuoto), da usare dentro un tag <code> di Telegram per
        larghezza fissa. Il valore viene forzato nell'intervallo [0, 100].
    EN: Build a Unicode progress bar using `█` (filled) and `░` (empty)
        block characters, intended to be wrapped in a Telegram <code> tag
        for monospaced alignment. The value is clamped to [0, 100].

    Args:
        percent: valore percentuale (0–100) / percentage value (0–100).
        width:   numero totale di caratteri della barra / total bar chars.
    Returns:
        str — barra Unicode / Unicode bar string.
    """
    filled = round(max(0.0, min(100.0, percent)) / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _human(n_bytes: int) -> str:
    """
    IT: Converte un numero di byte in stringa leggibile (B, KB, MB, GB,
        TB). Usato per formattare RAM e disco.
    EN: Convert a byte count to a human-readable string (B, KB, MB, GB,
        TB). Used to format RAM and disk figures.

    Args:
        n_bytes: dimensione in byte / size in bytes.
    Returns:
        str — stringa formattata / formatted string.
    """
    n: float = n_bytes
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


async def get_uptime() -> str:
    """
    IT: Legge il tempo di attività del sistema da `/proc/uptime` e lo
        restituisce come stringa compatta (es. "3d 5h 12min").
        Le unità con valore zero all'inizio vengono omesse (es. "45min"
        se il sistema è su da meno di un'ora).
    EN: Read system uptime from `/proc/uptime` and return it as a compact
        string (e.g. "3d 5h 12min"). Leading zero-value units are omitted
        (e.g. "45min" when uptime is under one hour).

    Returns:
        str — stringa uptime formattata / formatted uptime string.
    """
    try:
        with open("/proc/uptime") as f:
            seconds = float(f.read().split()[0])
        days    = int(seconds // 86400)
        hours   = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        parts: list[str] = []
        if days:
            parts.append(f"{days}d")
        if hours or days:
            parts.append(f"{hours}h")
        parts.append(f"{minutes}min")
        return " ".join(parts)
    except Exception:
        return "N/A"


async def get_swap_info() -> tuple[float, str, str] | None:
    """
    IT: Legge l'utilizzo dello swap dalla riga "Swap:" di `free -b`.
        Ritorna None se lo swap non è configurato (totale = 0).
    EN: Read swap usage from the "Swap:" line of `free -b`.
        Returns None when swap is not configured (total = 0).

    Returns:
        tuple(float, str, str) — (percent, used_human, total_human)
        oppure None se swap assente / or None if no swap.
    """
    _, out = await run_cmd(["free", "-b"])
    for line in out.splitlines():
        if line.startswith("Swap:"):
            parts = line.split()
            total = int(parts[1])
            if total == 0:
                return None
            used = int(parts[2])
            pct  = used / total * 100 if total else 0.0
            return round(pct, 1), _human(used), _human(total)
    return None


async def get_cpu_percent(interval: float = 0.5) -> float:
    """
    IT: Calcola la percentuale di utilizzo CPU leggendo `/proc/stat` due
        volte a distanza di `interval` secondi e confrontando i delta di
        tempo idle e totale. Usa `asyncio.sleep` per non bloccare
        l'event loop durante l'attesa.
    EN: Calculate CPU usage percentage by reading `/proc/stat` twice
        `interval` seconds apart and comparing the idle/total time deltas.
        Uses `asyncio.sleep` so the event loop is not blocked while
        waiting.

    Args:
        interval: secondi tra le due letture / seconds between reads.
    Returns:
        float — percentuale CPU (0.0–100.0) / CPU percentage (0.0–100.0).
    """
    def _stat() -> tuple[int, int]:
        with open("/proc/stat") as f:
            fields = [int(x) for x in f.readline().split()[1:]]
        idle  = fields[3] + (fields[4] if len(fields) > 4 else 0)  # idle + iowait
        return idle, sum(fields)

    idle1, total1 = _stat()
    await asyncio.sleep(interval)
    idle2, total2 = _stat()

    diff_total = total2 - total1
    if diff_total == 0:
        return 0.0
    return round((1 - (idle2 - idle1) / diff_total) * 100, 1)


async def get_ram_info() -> tuple[float, str, str]:
    """
    IT: Legge l'utilizzo RAM da `free -b` (byte per massima precisione).
        La RAM "usata" è calcolata come `totale − disponibile`, che
        esclude cache e buffer e rispecchia l'uso reale delle applicazioni.
    EN: Read RAM usage from `free -b` (bytes for maximum precision).
        "Used" RAM is computed as `total − available`, which excludes
        cache and buffers and reflects real application memory usage.

    Returns:
        tuple(float, str, str) — (percent, used_human, total_human).
    """
    _, out = await run_cmd(["free", "-b"])
    for line in out.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            total = int(parts[1])
            avail = int(parts[6]) if len(parts) > 6 else int(parts[3])
            used  = total - avail
            pct   = used / total * 100 if total else 0.0
            return round(pct, 1), _human(used), _human(total)
    return 0.0, "?", "?"


async def get_disk_info() -> list[tuple[float, str, str, str]]:
    """
    IT: Legge l'utilizzo di tutti i filesystem reali da `df -h`, filtrando
        solo le righe il cui device inizia con `/dev/` (esclude tmpfs,
        devtmpfs, overlay, squashfs e altri filesystem virtuali).
        Gestisce anche il caso in cui il path del device vada a capo
        (riga lunga spezzata da df).
    EN: Read usage for every real filesystem from `df -h`, keeping only
        rows whose device starts with `/dev/` (excludes tmpfs, devtmpfs,
        overlay, squashfs and other virtual filesystems). Handles the
        edge case where df wraps long device paths onto the next line.

    Returns:
        list of tuple(float, str, str, str) —
        [(percent, used_human, total_human, mountpoint), …]
        sorted by mountpoint.
    """
    _, out = await run_cmd(["df", "-h"])
    results: list[tuple[float, str, str, str]] = []
    lines = out.splitlines()
    i = 1  # skip header
    while i < len(lines):
        parts = lines[i].split()
        # df wraps the device name on a separate line when it is very long
        if len(parts) == 1 and i + 1 < len(lines):
            parts = parts + lines[i + 1].split()
            i += 1
        i += 1
        if len(parts) < 6:
            continue
        source = parts[0]
        if not source.startswith("/dev/"):
            continue
        # df -h columns: Filesystem  Size  Used  Avail  Use%  Mounted on
        size  = parts[1]
        used  = parts[2]
        mount = parts[5]
        try:
            pct = float(parts[4].rstrip("%"))
        except (IndexError, ValueError):
            pct = 0.0
        results.append((pct, used, size, mount))
    results.sort(key=lambda x: x[3])   # ordina per mountpoint / sort by mountpoint
    return results
