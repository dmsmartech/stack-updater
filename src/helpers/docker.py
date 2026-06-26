"""
IT: Helper di basso livello per Docker / docker compose. Contiene la
    discovery dei container del progetto compose configurato, l'estrazione
    di metadati via `docker inspect` (uptime, porte, reti, restart policy),
    la mappa servizio→image-id per rilevare aggiornamenti reali post-pull e
    funzioni di parsing/formatting per l'output verso l'utente.
EN: Low-level Docker / docker compose helpers. Includes container discovery
    for the configured compose project, metadata extraction via `docker
    inspect` (uptime, ports, networks, restart policy), the service→image-id
    map used to detect actual updates after a pull, plus parsing/formatting
    helpers for user-facing output.
"""
import json
import logging
import re
from datetime import datetime, timezone

from config import cfg_docker_dir
from lang import t
from utils import run_cmd

log = logging.getLogger(__name__)

# =============================================================================
# DOCKER HELPERS
# =============================================================================

async def get_containers() -> list[dict]:
    """
    IT: Ritorna la lista di tutti i container del progetto compose
        (running e stoppati). Ogni elemento è un dict con `service`, `name`,
        `image` (senza tag), `tag`, `status`. Usa `docker compose ps -a`
        nella directory configurata.
    EN: Return all containers of the compose project (both running and
        stopped). Each item is a dict with `service`, `name`, `image`
        (without tag), `tag`, `status`. Runs `docker compose ps -a` in the
        configured directory.
    """
    _, out = await run_cmd([
        "docker", "compose", "ps", "-a",
        "--format", "{{.Service}}\t{{.Name}}\t{{.Image}}\t{{.Status}}"
    ], cwd=cfg_docker_dir())
    containers = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            service = parts[0].strip()
            name    = parts[1].strip()
            image   = parts[2].strip()
            status  = parts[3].strip()
            tag     = image.split(":")[-1] if ":" in image else "latest"
            img     = image.split(":")[0] if ":" in image else image
            containers.append({"service": service, "name": name, "image": img, "tag": tag, "status": status})
    return containers

def format_uptime(delta) -> str:
    """
    IT: Formatta un `timedelta` in una stringa compatta (es. "2d 3h",
        "45m", "< 1m") adatta alla UI Telegram.
    EN: Format a `timedelta` as a compact string (e.g. "2d 3h", "45m",
        "< 1m") suitable for the Telegram UI.
    """
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    if days > 0:
        return f"{days}d {hours}h" if hours else f"{days}d"
    if hours > 0:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m" if minutes else "< 1m"

async def get_container_inspect(container_name: str) -> dict:
    """
    IT: Esegue `docker inspect` su un container e ritorna un dict con i
        campi rilevanti per la UI: `uptime` (se in esecuzione), `ports`
        (mapping host→container), `networks` (lista), `restart_policy`.
        Ritorna dict vuoto in caso di errore.
    EN: Run `docker inspect` against a container and return a dict with the
        UI-relevant fields: `uptime` (when running), `ports` (host→container
        bindings), `networks` (list), `restart_policy`. Returns an empty
        dict on failure.

    Args:
        container_name: nome esatto del container Docker /
                        exact Docker container name.
    """
    code, out = await run_cmd(["docker", "inspect", container_name])
    if code != 0 or not out:
        return {}
    try:
        data = json.loads(out)
        if not data:
            return {}
        c = data[0]
        uptime = ""
        if c.get("State", {}).get("Running", False):
            started_at = c["State"].get("StartedAt", "")
            if started_at:
                dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime = format_uptime(datetime.now(timezone.utc) - dt)
        port_bindings = c.get("HostConfig", {}).get("PortBindings", {}) or {}
        ports = []
        for cp, bindings in port_bindings.items():
            if bindings:
                for b in bindings:
                    hp = b.get("HostPort", "")
                    if hp:
                        ports.append(f"{hp}→{cp}")
        networks = list(c.get("NetworkSettings", {}).get("Networks", {}).keys())
        restart = c.get("HostConfig", {}).get("RestartPolicy", {}).get("Name", "no")
        return {"uptime": uptime, "ports": ports, "networks": networks, "restart_policy": restart}
    except Exception as e:
        log.warning("docker inspect error: %s", e)
        return {}

async def _compose_service_image_ids(docker_dir: str) -> dict:
    """
    IT: Ritorna `{service: image_id}` per tutti i servizi compose esistenti
        nella directory passata. Usato per confrontare prima/dopo
        `docker compose pull`: se l'image id di un servizio cambia, è stato
        effettivamente scaricato un aggiornamento (utile per mostrare la
        lista dei servizi realmente aggiornati).
    EN: Return `{service: image_id}` for every compose service present in
        the given directory. Used to compare before/after `docker compose
        pull`: when a service's image id changes, an update was actually
        downloaded (used to show the list of really-updated services).

    Args:
        docker_dir: directory che contiene il docker-compose.yml /
                    directory containing the docker-compose.yml.
    """
    _, ps_out = await run_cmd(
        ["docker", "compose", "ps", "-a", "--format", "{{.Service}}\t{{.Image}}"],
        cwd=docker_dir
    )
    result = {}
    for line in ps_out.splitlines():
        parts = line.strip().split("\t")
        if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
            service, image = parts[0].strip(), parts[1].strip()
            _, id_out = await run_cmd(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image]
            )
            if id_out.strip():
                result[service] = id_out.strip()
    return result

def is_container_running(status: str) -> bool:
    """
    IT: Ritorna True se la stringa di stato Docker indica un container in
        esecuzione (es. "Up 2 hours", "running").
    EN: Return True when the Docker status string indicates a running
        container (e.g. "Up 2 hours", "running").
    """
    low = status.lower()
    return "up" in low or "running" in low

def container_status_label(status: str) -> str:
    """
    IT: Traduce lo stato grezzo di Docker in un'etichetta UI localizzata
        ("In esecuzione", "Terminato", "Stoppato" — o equivalenti EN).
    EN: Map Docker's raw status to a localized UI label ("Running",
        "Exited", "Stopped" — or IT equivalents).
    """
    low = status.lower()
    if "up" in low or "running" in low:
        return t("container_running")
    if "exited" in low:
        return t("container_exited")
    return t("container_stopped")

def parse_docker_problems(output: str) -> list:
    """
    IT: Estrae le righe d'errore dall'output di docker, prefissandole con
        "• " per la visualizzazione e deduplicandole. Filtra per le keyword
        "error", "failed", "exited".
    EN: Extract error lines from docker output, prefixing them with "• " for
        display and deduplicating. Filters by the keywords "error",
        "failed", "exited".
    """
    return list(dict.fromkeys(
        "• " + l.strip() for l in output.splitlines()
        if any(k in l.lower() for k in ("error", "failed", "exited"))
    ))
