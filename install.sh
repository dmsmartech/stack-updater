#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
#  Stack Updater — installer
#  https://github.com/dmsmartech/stack-updater
# =============================================================================

REPO="https://raw.githubusercontent.com/dmsmartech/stack-updater/dev"
SERVICE_DIR="/etc/systemd/system"
SERVICE_FILE="$SERVICE_DIR/stack_updater.service"
LOG_FILE="/var/log/stack_updater.log"

# Directory di installazione (default, può essere sovrascritto dall'utente)
INSTALL_DIR="/opt/StackUpdater"

# Lingua selezionata dall'utente (default: en)
LANG_CODE="en"

# ---------------------------------------------------------------------------
# Colori e stili
# ---------------------------------------------------------------------------
RESET="\033[0m"
BOLD="\033[1m"
DIM="\033[2m"
BGREEN="\033[1;32m"
BRED="\033[1;31m"
BYELLOW="\033[1;33m"
BCYAN="\033[1;36m"

# ---------------------------------------------------------------------------
# Stringhe UI bilingui per il wizard stesso
# ---------------------------------------------------------------------------

ui() {
    local key="$1"
    local varname="UI_${LANG_CODE^^}_${key}"
    local fallback="UI_EN_${key}"
    echo -e "${!varname:-${!fallback:-$key}}"
}

# Italiano
UI_IT_prerequisites="Controllo prerequisiti"
UI_IT_configuration="Configurazione"
UI_IT_answer_hint="I valori tra [parentesi] sono i default — premi Invio per accettarli."
UI_IT_python_deps="Installazione dipendenze Python"
UI_IT_writing_bot="Scrittura file bot"
UI_IT_systemd_setup="Configurazione servizio systemd"
UI_IT_install_done="Installazione completata!"
UI_IT_bot_active="Il bot è attivo e in ascolto su Telegram."
UI_IT_write_start="Scrivi"
UI_IT_to_begin="al tuo bot per cominciare."
UI_IT_useful_cmds="Comandi utili:"
UI_IT_status_label="Stato:"
UI_IT_log_label="Log live:"
UI_IT_restart_label="Riavvio:"
UI_IT_disable_label="Disabilita:"
UI_IT_installed_files="File installati:"
UI_IT_confirm_install="Tutto corretto? Procedo con l'installazione"
UI_IT_cancelled="Installazione annullata. Rilancia lo script per ricominciare."
UI_IT_confirm_telegram="Ti ho mandato un messaggio di conferma su Telegram."
UI_IT_root_error="Questo installer richiede i privilegi di root."
UI_IT_root_hint="Rilancialo con:"
UI_IT_py_not_found="Python 3 non trovato. Installa python3 e riprova."
UI_IT_py_version_error="trovato, richiesto 3.9+."
UI_IT_pip_not_found="pip3 non trovato, provo a installarlo..."
UI_IT_docker_not_found="Docker non trovato. Installalo prima di continuare."
UI_IT_compose_not_found="docker compose (plugin v2) non trovato."
UI_IT_compose_hint="Installa il plugin: apt-get install docker-compose-plugin"
UI_IT_systemd_not_found="systemd non trovato. Questo installer richiede systemd."
UI_IT_token_label="① Token del Telegram Bot"
UI_IT_token_hint1="Crealo con @BotFather su Telegram → /newbot"
UI_IT_token_hint2="Formato: 123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ"
UI_IT_token_prompt="Token"
UI_IT_token_empty="Il token non può essere vuoto."
UI_IT_token_checking="Verifico il token..."
UI_IT_token_invalid="Token non valido. Controlla e riprova."
UI_IT_chatid_label="② Chat ID Telegram"
UI_IT_chatid_hint2="Manda un messaggio al tuo bot"
UI_IT_chatid_hint_send="Assicurati di aver mandato almeno un messaggio al bot, poi premi Invio."
UI_IT_chatid_confirm_prompt="Premi Invio quando hai mandato il messaggio al bot..."
UI_IT_chatid_checking="Rilevo il tuo Chat ID automaticamente..."
UI_IT_chatid_not_found="Nessun messaggio trovato. Manda un messaggio al bot e premi Invio."
UI_IT_chatid_attempt_hint="Riprovo il rilevamento automatico"
UI_IT_chatid_max_attempts="Dopo 20 tentativi non ho trovato il tuo Chat ID automaticamente."
UI_IT_chatid_manual_prompt="Inserisci il Chat ID manualmente (es. 127131379)"
UI_IT_chatid_invalid="Chat ID non valido. Deve essere un numero (es. 127131379)."
UI_IT_chatid_manual_invalid="Non riesco a inviare messaggi a quel Chat ID. Controlla e riprova."
UI_IT_test_msg="Stack Updater"
UI_IT_test_sent="Chat ID rilevato e messaggio di conferma inviato!"
UI_IT_install_dir_label="⓪ Directory di installazione"
UI_IT_install_dir_hint="Dove installare Stack Updater (default consigliato: /opt/StackUpdater)"
UI_IT_install_dir_prompt="Directory"
UI_IT_install_dir_created="Directory creata:"
UI_IT_docker_dir_label="③ Directory del tuo docker-compose"
UI_IT_docker_dir_hint="La cartella che contiene il file docker-compose.yml"
UI_IT_docker_dir_found="Trovati file docker-compose in"
UI_IT_docker_dir_manual="Inserisci manualmente"
UI_IT_docker_dir_choice="Seleziona il numero (o 0 per inserire manualmente)"
UI_IT_docker_dir_prompt="Percorso"
UI_IT_docker_dir_required="Il percorso non può essere vuoto."
UI_IT_docker_dir_notfound="La directory non esiste."
UI_IT_docker_dir_create="Vuoi crearla adesso?"
UI_IT_docker_dir_created="Directory creata:"
UI_IT_docker_dir_noyml="Nessun file docker-compose.yml trovato in quella directory."
UI_IT_docker_dir_continue="Continuare lo stesso?"
UI_IT_username_label="④ Il tuo nome"
UI_IT_username_hint="Verrà usato nei messaggi del bot"
UI_IT_username_prompt="Nome"
UI_IT_username_ok="Nome impostato:"
UI_IT_summary_username="Nome:"
UI_IT_reminder_label="⑤ Promemoria mensile"
UI_IT_reminder_hint="Il bot ti manderà un messaggio su Telegram chiedendoti se aggiornare."
UI_IT_reminder_day="Giorno del mese per il promemoria"
UI_IT_reminder_day_invalid="Giorno non valido, uso il 10."
UI_IT_reminder_hour="Ora del promemoria (formato 24h, es. 09)"
UI_IT_reminder_hour_invalid="Ora non valida, uso le 09:00."
UI_IT_reminder_ok="Promemoria: ogni mese il giorno"
UI_IT_reminder_at="alle"
UI_IT_summary_title="Riepilogo configurazione:"
UI_IT_summary_bot="Bot Telegram:"
UI_IT_summary_chatid="Chat ID:"
UI_IT_summary_install_dir="Install dir:"
UI_IT_summary_dir="Docker dir:"
UI_IT_summary_reminder="Promemoria:"
UI_IT_summary_day="giorno"
UI_IT_summary_at="alle"
UI_IT_service_active="Servizio avviato e attivo"
UI_IT_service_error="Il servizio non si è avviato correttamente."
UI_IT_service_log="Log di avvio:"
UI_IT_service_hint1="Controlla il log sopra per capire il problema."
UI_IT_service_hint2="Puoi riavviare con:"
UI_IT_service_hint3="Log in tempo reale:"
UI_IT_err_during="Errore durante:"
UI_IT_already_installed="Stack Updater è già installato su questo sistema."
UI_IT_already_installed_version="Versione installata:"
UI_IT_option_update="Aggiorna"
UI_IT_option_uninstall="Disinstalla"
UI_IT_option_cancel="Annulla"
UI_IT_update_check="Verifica aggiornamenti in corso..."
UI_IT_update_available="È disponibile una nuova versione:"
UI_IT_update_confirm="Vuoi aggiornare?"
UI_IT_updating="Aggiornamento in corso..."
UI_IT_update_done="Aggiornamento completato! Versione:"
UI_IT_update_no_updates="Sei già aggiornato! Versione:"
UI_IT_update_repo_error="Impossibile contattare il repository. Riprova più tardi."
UI_IT_uninstall_yes="Disinstallazione in corso..."
UI_IT_uninstall_done="Disinstallazione completata. Puoi reinstallare rilasciando di nuovo il comando wget."
UI_IT_uninstall_no="Operazione annullata."

# English
UI_EN_prerequisites="Checking prerequisites"
UI_EN_configuration="Configuration"
UI_EN_answer_hint="Values in [brackets] are defaults — press Enter to accept."
UI_EN_python_deps="Installing Python dependencies"
UI_EN_writing_bot="Writing bot file"
UI_EN_systemd_setup="Setting up systemd service"
UI_EN_install_done="Installation complete!"
UI_EN_bot_active="The bot is active and listening on Telegram."
UI_EN_write_start="Send"
UI_EN_to_begin="to your bot to get started."
UI_EN_useful_cmds="Useful commands:"
UI_EN_status_label="Status:"
UI_EN_log_label="Live log:"
UI_EN_restart_label="Restart:"
UI_EN_disable_label="Disable:"
UI_EN_installed_files="Installed files:"
UI_EN_confirm_install="Everything correct? Proceed with installation"
UI_EN_cancelled="Installation cancelled. Re-run the script to start over."
UI_EN_confirm_telegram="A confirmation message has been sent to your Telegram."
UI_EN_root_error="This installer requires root privileges."
UI_EN_root_hint="Re-run with:"
UI_EN_py_not_found="Python 3 not found. Please install python3 and try again."
UI_EN_py_version_error="found, requires 3.9+."
UI_EN_pip_not_found="pip3 not found, trying to install it..."
UI_EN_docker_not_found="Docker not found. Please install it before continuing."
UI_EN_compose_not_found="docker compose (v2 plugin) not found."
UI_EN_compose_hint="Install the plugin: apt-get install docker-compose-plugin"
UI_EN_systemd_not_found="systemd not found. This installer requires systemd."
UI_EN_token_label="① Telegram Bot Token"
UI_EN_token_hint1="Create one with @BotFather on Telegram → /newbot"
UI_EN_token_hint2="Format: 123456789:ABCDefGhIJKlmNoPQRsTUVwxyZ"
UI_EN_token_prompt="Token"
UI_EN_token_empty="Token cannot be empty."
UI_EN_token_checking="Verifying token..."
UI_EN_token_invalid="Invalid token. Please check and try again."
UI_EN_chatid_label="② Telegram Chat ID"
UI_EN_chatid_hint2="Send a message to your bot"
UI_EN_chatid_hint_send="Make sure you have sent at least one message to the bot, then press Enter."
UI_EN_chatid_confirm_prompt="Press Enter once you have sent a message to the bot..."
UI_EN_chatid_checking="Auto-detecting your Chat ID..."
UI_EN_chatid_not_found="No messages found. Send a message to the bot and press Enter."
UI_EN_chatid_attempt_hint="Retrying automatic detection"
UI_EN_chatid_max_attempts="After 20 attempts I could not detect your Chat ID automatically."
UI_EN_chatid_manual_prompt="Enter your Chat ID manually (e.g. 123456789)"
UI_EN_chatid_invalid="Invalid Chat ID. Must be a number (e.g. 123456789)."
UI_EN_chatid_manual_invalid="Cannot send messages to that Chat ID. Please check and try again."
UI_EN_test_msg="Stack Updater"
UI_EN_test_sent="Chat ID detected and confirmation message sent!"
UI_EN_install_dir_label="⓪ Installation directory"
UI_EN_install_dir_hint="Where to install Stack Updater (recommended default: /opt/StackUpdater)"
UI_EN_install_dir_prompt="Directory"
UI_EN_install_dir_created="Directory created:"
UI_EN_docker_dir_label="③ Your docker-compose directory"
UI_EN_docker_dir_hint="The folder containing your docker-compose.yml file"
UI_EN_docker_dir_found="Found docker-compose files in"
UI_EN_docker_dir_manual="Enter manually"
UI_EN_docker_dir_choice="Select the number (or 0 to enter manually)"
UI_EN_docker_dir_prompt="Path"
UI_EN_docker_dir_required="Path cannot be empty."
UI_EN_docker_dir_notfound="Directory does not exist."
UI_EN_docker_dir_create="Do you want to create it now?"
UI_EN_docker_dir_created="Directory created:"
UI_EN_docker_dir_noyml="No docker-compose.yml file found in that directory."
UI_EN_docker_dir_continue="Continue anyway?"
UI_EN_username_label="④ Your name"
UI_EN_username_hint="Will be used in bot messages"
UI_EN_username_prompt="Name"
UI_EN_username_ok="Name set:"
UI_EN_summary_username="Name:"
UI_EN_reminder_label="⑤ Monthly reminder"
UI_EN_reminder_hint="The bot will send you a Telegram message asking if you want to update."
UI_EN_reminder_day="Day of the month for the reminder"
UI_EN_reminder_day_invalid="Invalid day, using 10."
UI_EN_reminder_hour="Reminder time (24h format, e.g. 09)"
UI_EN_reminder_hour_invalid="Invalid hour, using 09:00."
UI_EN_reminder_ok="Reminder: every month on day"
UI_EN_reminder_at="at"
UI_EN_summary_title="Configuration summary:"
UI_EN_summary_bot="Telegram bot:"
UI_EN_summary_chatid="Chat ID:"
UI_EN_summary_install_dir="Install dir:"
UI_EN_summary_dir="Docker dir:"
UI_EN_summary_reminder="Reminder:"
UI_EN_summary_day="day"
UI_EN_summary_at="at"
UI_EN_service_active="Service started and active"
UI_EN_service_error="The service did not start correctly."
UI_EN_service_log="Startup log:"
UI_EN_service_hint1="Check the log above to understand the problem."
UI_EN_service_hint2="You can restart with:"
UI_EN_service_hint3="Live log:"
UI_EN_err_during="Error during:"
UI_EN_already_installed="Stack Updater is already installed on this system."
UI_EN_already_installed_version="Installed version:"
UI_EN_option_update="Update"
UI_EN_option_uninstall="Uninstall"
UI_EN_option_cancel="Cancel"
UI_EN_update_check="Checking for updates..."
UI_EN_update_available="A new version is available:"
UI_EN_update_confirm="Do you want to update?"
UI_EN_updating="Updating..."
UI_EN_update_done="Update complete! Version:"
UI_EN_update_no_updates="You're already up to date! Version:"
UI_EN_update_repo_error="Cannot reach the repository. Please try again later."
UI_EN_uninstall_yes="Uninstalling..."
UI_EN_uninstall_done="Uninstallation complete. You can reinstall by running the wget command again."
UI_EN_uninstall_no="Operation cancelled."

# ---------------------------------------------------------------------------
# Helpers UI
# ---------------------------------------------------------------------------

print_banner() {
    clear
    echo -e "${BCYAN}"
    echo "  ███████╗████████╗ █████╗  ██████╗██╗  ██╗"
    echo "  ██╔════╝╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝"
    echo "  ███████╗   ██║   ███████║██║     █████╔╝ "
    echo "  ╚════██║   ██║   ██╔══██║██║     ██╔═██╗ "
    echo "  ███████║   ██║   ██║  ██║╚██████╗██║  ██╗"
    echo "  ╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝"
    echo ""
    echo "  ██╗   ██╗██████╗ ██████╗  █████╗ ████████╗███████╗██████╗ "
    echo "  ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚══██╔══╝██╔════╝██╔══██╗"
    echo "  ██║   ██║██████╔╝██║  ██║███████║   ██║   █████╗  ██████╔╝"
    echo "  ██║   ██║██╔═══╝ ██║  ██║██╔══██║   ██║   ██╔══╝  ██╔══██╗"
    echo "  ╚██████╔╝██║     ██████╔╝██║  ██║   ██║   ███████╗██║  ██║"
    echo "   ╚═════╝ ╚═╝     ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝"
    echo -e "${RESET}"
    echo -e "  ${BOLD}Stack Updater v.1.0.2${RESET}  ${DIM}— created by dm.smartech — Dario Montalbano${RESET}"
    echo ""
    echo -e "${DIM}  ─────────────────────────────────────────${RESET}"
    echo ""
}

UI_CONFIG_MODE=false
UI_CONFIG_LINE="${BGREEN}┃${RESET}"

ui_indent() {
    if [[ "$UI_CONFIG_MODE" == true ]]; then
        echo -ne "  ${UI_CONFIG_LINE}\t"
    else
        echo -ne "  "
    fi
}

ui_blank() {
    if [[ "$UI_CONFIG_MODE" == true ]]; then
        echo -e "  ${UI_CONFIG_LINE}"
    else
        echo ""
    fi
}

step()     { echo -e "\n${BCYAN}▸${RESET} ${BOLD}$1${RESET}"; }
ok()       { ui_indent; echo -e "${BGREEN}✓${RESET} $1"; }
warn()     { ui_indent; echo -e "${BYELLOW}⚠${RESET}  $1"; }
err()      { ui_indent; echo -e "${BRED}✗${RESET} $1"; }
info()     { ui_indent; echo -e "${DIM}$1${RESET}"; }
divider() {
    if [[ "$UI_CONFIG_MODE" == true ]]; then
        echo -e "  ${UI_CONFIG_LINE}${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
        echo -e "  ${UI_CONFIG_LINE}"
    else
        echo -e "\n  ${DIM}─────────────────────────────────────────${RESET}\n"
    fi
}

# ---------------------------------------------------------------------------
# Sidebar verticale
# ---------------------------------------------------------------------------

SIDEBAR_IT=("① Directory di installazione" "② Token del Telegram Bot" "③ Chat ID Telegram" "④ Directory docker-compose" "⑤ Inserisci un nickname" "⑥ Promemoria mensile" "⑦ Riepilogo configurazione")
SIDEBAR_EN=("① Installation directory" "② Telegram Bot Token" "③ Telegram Chat ID" "④ docker-compose directory" "⑤ Enter a nickname" "⑥ Monthly reminder" "⑦ Configuration summary")

section_header() {
    local current=$1
    local label
    if [[ "$LANG_CODE" == "it" ]]; then
        label="${SIDEBAR_IT[$((current-1))]}"
    else
        label="${SIDEBAR_EN[$((current-1))]}"
    fi

    divider
    echo -e "  ${BGREEN}┣━━▶${RESET} ${BOLD}${label}${RESET}"
    echo -e "  ${UI_CONFIG_LINE}"
}

ask() {
    local prompt="$1"
    local default="${2:-}"
    if [[ -n "$default" ]]; then
        ui_blank
        ui_indent
        echo -ne "${BOLD}$prompt${RESET} ${DIM}[$default]${RESET}: "
    else
        ui_blank
        ui_indent
        echo -ne "${BOLD}$prompt${RESET}: "
    fi
    read -r REPLY
    if [[ -z "$REPLY" && -n "$default" ]]; then
        REPLY="$default"
    fi
}

ask_secret() {
    ui_blank
    ui_indent
    echo -ne "${BOLD}$1${RESET}: "
    read -rs REPLY
    echo ""
}

progress() {
    local msg="$1"; shift
    ui_indent
    echo -ne "${DIM}${msg}...${RESET} "
    if "$@" > /tmp/su_progress.log 2>&1; then
        echo -e "${BGREEN}✓${RESET}"
    else
        echo -e "${BRED}✗${RESET}"
        err "$(ui err_during) $msg"
        tail -5 /tmp/su_progress.log | sed 's/^/    /'
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Selezione lingua
# ---------------------------------------------------------------------------

select_language() {
    print_banner
    echo -e "  ${BOLD}Please select your language / Seleziona la lingua:${RESET}"
    echo ""
    echo -e "  ${BCYAN}1)${RESET} English"
    echo -e "  ${BCYAN}2)${RESET} Italiano"
    echo ""
    echo -ne "  ${BOLD}Choice / Scelta${RESET} ${DIM}[1]${RESET}: "
    read -r lang_choice

    case "${lang_choice:-1}" in
        2|it|IT|italiano|Italiano)
            LANG_CODE="it"
            ok "Lingua selezionata: Italiano"
            ;;
        *)
            LANG_CODE="en"
            ok "Language selected: English"
            ;;
    esac
    echo ""
}

# ---------------------------------------------------------------------------
# Auto-detection directory docker-compose
# ---------------------------------------------------------------------------

detect_docker_compose_dirs() {
    local -a found=()
    local -a search_roots=("/home" "/opt" "/srv" "/root" "/var/lib" "/docker" "/containers" "/data" "/mnt")
    local f d
    # Ricerca nei path più comuni, massimo 5 livelli di profondità
    while IFS= read -r f; do
        d="$(dirname "$f")"
        # Deduplica
        local already=false
        for existing in "${found[@]+"${found[@]}"}"; do
            [[ "$existing" == "$d" ]] && already=true && break
        done
        [[ "$already" == "false" ]] && found+=("$d")
    done < <(find "${search_roots[@]}" -maxdepth 5 \
        \( -name "docker-compose.yml" -o -name "docker-compose.yaml" \) 2>/dev/null | sort)
    printf '%s\n' "${found[@]+"${found[@]}"}"
}

# ---------------------------------------------------------------------------
# Invia messaggio Telegram
# ---------------------------------------------------------------------------

tg_send() {
    local chat_id="$1"
    local text="$2"
    local return_output="${3:-false}"
    local json
    json=$(python3 -c "
import json, sys
text = sys.argv[1]
print(json.dumps({'chat_id': int(sys.argv[2]), 'text': text, 'parse_mode': 'HTML'}))
" "$text" "$chat_id" 2>/dev/null) || true
    if [[ "$return_output" == "true" ]]; then
        curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "$json" 2>/dev/null || true
    else
        curl -s -X POST "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
            -H "Content-Type: application/json" \
            -d "$json" > /dev/null 2>&1 || true
    fi
}

build_greeting_msg() {
    local name="$1"
    if [[ "$LANG_CODE" == "it" ]]; then
        printf "Ciao %s, sono Stack Updater! 👋\nIl tuo bot è quasi pronto...\n\nDammi un momento per completare la configurazione..." "$name"
    else
        printf "Hi %s, I'm Stack Updater! 👋\nYour bot is almost ready...\n\nGive me a moment to complete the configuration..." "$name"
    fi
}

build_chatid_test_msg() {
    if [[ "$LANG_CODE" == "it" ]]; then
        printf "Stack Updater — verifica Chat ID ✓"
    else
        printf "Stack Updater — Chat ID verified ✓"
    fi
}

build_install_complete_msg() {
    local _version
    _version=$(cat "$INSTALL_DIR/VERSION" 2>/dev/null | tr -d '[:space:]') || true
    [[ -z "$_version" ]] && _version="?"

    local _art
    _art=$(cat <<'ART'
 ____  _____  _    ____ _  __
/ ___|_   _|/ \  / ___|| |/ /
\___ \ | | / _ \| |    | ' /
 ___) || |/ ___ \ |___ | . \
|____/ |_/_/   \_\____||_|\_\

 _   _ ____  ____    _  _____ _____ ____
| | | |  _ \|  _ \  / \|_   _| ____|  _ \
| | | | |_) | | | |/ _ \ | | |  _| | |_) |
| |_| |  __/| |_| / ___ \| | | |___|  _ &lt;
 \___/|_|   |____/_/   \_\_| |_____|_| \_\
ART
)

    local _header
    _header=$(printf '<pre>%s\n\nv %s</pre>' "$_art" "$_version")

    if [[ "$LANG_CODE" == "it" ]]; then
        printf '%s\n\nInstallazione completata 🎉\n\n<b>%s, sono ora al tuo servizio.</b>\nInsieme possiamo:\n\n• Aggiornare il tuo sistema Linux\n• Aggiornare i container Docker, insieme o singolarmente\n• Riavviare il sistema\n• Modificare la pianificazione del promemoria mensile\n\nScrivi /start per iniziare.\n\n📅 <i>Il promemoria è impostato per il giorno %s di ogni mese alle ore %02d:%02d.</i>' \
            "$_header" "$USER_NAME" "$REMINDER_DAY" "$REMINDER_HOUR" "$REMINDER_MINUTE"
    else
        printf '%s\n\nInstallation complete 🎉\n\n<b>%s, I'"'"'m now at your service.</b>\nTogether we can:\n\n• Update your Linux system\n• Update Docker containers, together or individually\n• Reboot the system\n• Change the monthly reminder schedule\n\nType /start to begin.\n\n📅 <i>The reminder is set for day %s of every month at %02d:%02d.</i>' \
            "$_header" "$USER_NAME" "$REMINDER_DAY" "$REMINDER_HOUR" "$REMINDER_MINUTE"
    fi
}

# ---------------------------------------------------------------------------
# Funzione di disinstallazione
# ---------------------------------------------------------------------------

do_uninstall() {
    local _install_dir="${1:-}"

    step "$(ui uninstall_yes)"
    systemctl disable --now stack_updater 2>/dev/null || true

    # Rimuovi file specifici (sicuro anche in dir di sistema)
    if [[ -n "$_install_dir" ]]; then
        rm -f  "$_install_dir/stack_updater.py"
        rm -f  "$_install_dir/stack_updater_config.json"
        rm -f  "$_install_dir/VERSION"
        rm -f  "$_install_dir/states.py"
        rm -f  "$_install_dir/config.py"
        rm -f  "$_install_dir/utils.py"
        rm -f  "$_install_dir/lang.py"
        rm -f  "$_install_dir/version.py"
        rm -f  "$_install_dir/ui.py"
        rm -rf "$_install_dir/handlers"
        rm -rf "$_install_dir/helpers"
        rm -rf "$_install_dir/operations"
        rm -rf "$_install_dir/__pycache__"
        rm -rf "$_install_dir/languages"
        # Compatibilità con installazioni precedenti (file piatti)
        rm -f  "$_install_dir/stack_updater_lang.json"
        rm -f  "$_install_dir/stack_updater_lang_it.json"
        rm -f  "$_install_dir/stack_updater_lang_en.json"
        # Se la dir è denominata "StackUpdater" ed è vuota, rimuovila
        if [[ "$(basename "$_install_dir")" == "StackUpdater" ]] \
           && [[ -z "$(ls -A "$_install_dir" 2>/dev/null)" ]]; then
            rmdir "$_install_dir" 2>/dev/null || true
        fi
    fi

    rm -f "$SERVICE_FILE"
    rm -f "$LOG_FILE"
    rm -f "/var/lib/stack_updater_rebooted"
    systemctl daemon-reload

    echo ""
    ok "$(ui uninstall_done)"
    echo ""
}

# ---------------------------------------------------------------------------
# Funzione di aggiornamento
# ---------------------------------------------------------------------------

do_update() {
    local _install_dir="$1"
    local _current_version="${2:-?}"

    divider
    step "$(ui update_check)"
    echo -ne "  ${DIM}$(ui update_check)${RESET} "

    local _remote_version
    _remote_version=$(curl -fsSL --max-time 10 "$REPO/VERSION" 2>/dev/null | tr -d '[:space:]') || true

    if [[ -z "$_remote_version" ]]; then
        echo -e "${BRED}✗${RESET}"
        err "$(ui update_repo_error)"
        exit 1
    fi
    echo -e "${BGREEN}✓${RESET}"

    if [[ "$_remote_version" == "$_current_version" ]]; then
        ok "$(ui update_no_updates) ${BOLD}$_current_version${RESET}"
        echo ""
        exit 0
    fi

    echo ""
    warn "$(ui update_available) ${BOLD}$_remote_version${RESET}"
    ask "$(ui update_confirm)" "y"
    if [[ ! "${REPLY,,}" =~ ^(y|yes|s|si)$ && -n "$REPLY" ]]; then
        echo ""
        warn "$(ui uninstall_no)"
        exit 0
    fi

    divider
    step "$(ui updating)"

    # Prepara struttura sottocartelle
    mkdir -p "$_install_dir/handlers"
    mkdir -p "$_install_dir/helpers"
    mkdir -p "$_install_dir/operations"
    mkdir -p "$_install_dir/languages"

    # Scarica il nuovo bot (in src/ nel repo, piatto in INSTALL_DIR)
    echo -ne "  ${DIM}Download stack_updater.py...${RESET} "
    curl -fsSL "$REPO/src/stack_updater.py" -o "$_install_dir/stack_updater.py"
    chmod +x "$_install_dir/stack_updater.py"
    echo -e "${BGREEN}✓${RESET}"
    ok "$_install_dir/stack_updater.py"

    # Scarica tutti i moduli Python del bot (da src/ nel repo)
    local _bot_files=(
        "states.py"
        "config.py"
        "utils.py"
        "lang.py"
        "version.py"
        "ui.py"
        "handlers/__init__.py"
        "handlers/shared.py"
        "handlers/start.py"
        "handlers/menu.py"
        "handlers/system.py"
        "handlers/docker.py"
        "handlers/all_updates.py"
        "handlers/settings.py"
        "handlers/jobs.py"
        "helpers/__init__.py"
        "helpers/system.py"
        "helpers/docker.py"
        "operations/__init__.py"
        "operations/core.py"
        "operations/system_ops.py"
        "operations/docker_ops.py"
        "operations/all_ops.py"
        "operations/app_update.py"
    )
    local _f
    for _f in "${_bot_files[@]}"; do
        echo -ne "  ${DIM}Download ${_f}...${RESET} "
        curl -fsSL "$REPO/src/${_f}" -o "$_install_dir/${_f}"
        echo -e "${BGREEN}✓${RESET}"
        ok "$_install_dir/${_f}"
    done

    # Scarica i file lingua (da src/languages/ nel repo)
    for _lang in it en; do
        echo -ne "  ${DIM}Download languages/${_lang}.json...${RESET} "
        curl -fsSL "$REPO/src/languages/$_lang.json" -o "$_install_dir/languages/$_lang.json"
        echo -e "${BGREEN}✓${RESET}"
        ok "$_install_dir/languages/$_lang.json"
    done

    # VERSION rimane alla root del repo
    echo -ne "  ${DIM}Download VERSION...${RESET} "
    curl -fsSL "$REPO/VERSION" -o "$_install_dir/VERSION"
    echo -e "${BGREEN}✓${RESET}"
    ok "$_install_dir/VERSION"

    # Riavvia il servizio
    progress "systemctl restart stack_updater" systemctl restart stack_updater

    echo ""
    ok "$(ui update_done) ${BOLD}$_remote_version${RESET}"
    echo ""
}

# ---------------------------------------------------------------------------
# Controlla se già installato
# ---------------------------------------------------------------------------

check_existing_install() {
    if ! systemctl list-unit-files stack_updater.service &>/dev/null \
       || ! systemctl list-unit-files stack_updater.service | grep -q "stack_updater"; then
        return 0  # non installato, procedi con l'installazione normale
    fi

    divider
    warn "$(ui already_installed)"

    # Recupera la directory di installazione dal service file
    local _bot_path _install_dir _installed_version
    _bot_path=$(grep "ExecStart=" "$SERVICE_FILE" 2>/dev/null | awk '{print $NF}' | head -1) || true
    _install_dir=$(dirname "${_bot_path:-/opt/StackUpdater/stack_updater.py}")
    _installed_version="?"
    [[ -f "$_install_dir/VERSION" ]] && _installed_version=$(cat "$_install_dir/VERSION" | tr -d '[:space:]')
    [[ -n "$_installed_version" && "$_installed_version" != "?" ]] \
        && echo -e "  $(ui already_installed_version) ${BOLD}$_installed_version${RESET}"

    echo ""
    echo -e "  ${BCYAN}1)${RESET} $(ui option_update)"
    echo -e "  ${BCYAN}2)${RESET} $(ui option_uninstall)"
    echo -e "  ${BCYAN}3)${RESET} $(ui option_cancel)"
    echo ""
    ask "Choice" "3"

    case "$REPLY" in
        1)
            do_update "$_install_dir" "$_installed_version"
            exit 0
            ;;
        2)
            do_uninstall "$_install_dir"
            exit 0
            ;;
        *)
            echo ""
            warn "$(ui uninstall_no)"
            echo ""
            exit 0
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Verifica prerequisiti
# ---------------------------------------------------------------------------

check_prerequisites() {
    step "$(ui prerequisites)"

    if [[ $EUID -ne 0 ]]; then
        err "$(ui root_error)"
        echo -e "  $(ui root_hint) ${BOLD}sudo bash install.sh${RESET}"
        exit 1
    fi
    ok "Root"

    if ! command -v python3 &>/dev/null; then
        err "$(ui py_not_found)"; exit 1
    fi
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [[ "$PY_MAJOR" -lt 3 ]] || [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -lt 9 ]]; then
        err "Python $PY_VERSION $(ui py_version_error)"; exit 1
    fi
    ok "Python $PY_VERSION"

    if ! command -v pip3 &>/dev/null; then
        warn "$(ui pip_not_found)"
        ui_indent; echo -ne "${DIM}pip3...${RESET} "

        _pip_ok=false

        if python3 -m pip --version >/dev/null 2>&1; then
            # pip è già installato ma pip3 non è nel PATH (es. Debian con python3-pip
            # installato senza creare il symlink) → crea un wrapper minimale
            printf '#!/bin/sh\nexec python3 -m pip "$@"\n' > /usr/local/bin/pip3
            chmod +x /usr/local/bin/pip3
            _pip_ok=true
        elif apt-get install -y python3-pip >/tmp/su_progress.log 2>&1; then
            # apt-get standard
            _pip_ok=true
        elif apt-get install -y python3-pip --fix-missing >>/tmp/su_progress.log 2>&1; then
            # apt-get con --fix-missing (mirror parzialmente sincronizzato)
            _pip_ok=true
        elif python3 -m ensurepip >/tmp/su_progress.log 2>&1; then
            # ensurepip built-in (senza --upgrade per evitare conflitti con pacchetti Debian)
            _pip_ok=true
        elif curl -fsSL --max-time 30 https://bootstrap.pypa.io/get-pip.py \
                  -o /tmp/get-pip.py >/tmp/su_progress.log 2>&1 \
             && python3 /tmp/get-pip.py --break-system-packages >>/tmp/su_progress.log 2>&1; then
            # get-pip.py da bootstrap.pypa.io
            _pip_ok=true
        fi

        if [[ "$_pip_ok" == false ]]; then
            echo -e "${BRED}✗${RESET}"
            err "$(ui err_during) pip3"
            tail -5 /tmp/su_progress.log | sed 's/^/    /'
            exit 1
        fi
        echo -e "${BGREEN}✓${RESET}"
    fi
    ok "pip3"

    if ! command -v docker &>/dev/null; then
        err "$(ui docker_not_found)"
        info "https://docs.docker.com/engine/install/"
        exit 1
    fi
    # Separato da ok per evitare che grep senza match causi uscita con pipefail
    _docker_ver=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || true)
    ok "Docker ${_docker_ver:-$(docker --version 2>/dev/null)}"

    if ! docker compose version &>/dev/null; then
        err "$(ui compose_not_found)"
        info "$(ui compose_hint)"
        exit 1
    fi
    ok "docker compose $(docker compose version --short 2>/dev/null || echo 'v2')"

    if ! command -v systemctl &>/dev/null; then
        err "$(ui systemd_not_found)"; exit 1
    fi
    ok "systemd"

    if ! command -v curl &>/dev/null; then
        progress "curl" apt-get install -y curl
    fi
    ok "curl"
}

# ---------------------------------------------------------------------------
# Configurazione interattiva
# ---------------------------------------------------------------------------

configure() {
    divider
    step "$(ui configuration)"
    echo ""
    info "$(ui answer_hint)"
    UI_CONFIG_MODE=true

    # ── Directory di installazione ──────────────────────────────────────────
    section_header 1
    info "$(ui install_dir_hint)"
    ask "$(ui install_dir_prompt)" "/opt/StackUpdater"
    INSTALL_DIR="$REPLY"
    if [[ ! -d "$INSTALL_DIR" ]]; then
        mkdir -p "$INSTALL_DIR"
        ok "$(ui install_dir_created) $INSTALL_DIR"
    else
        ok "$INSTALL_DIR"
    fi

    # ── Token ───────────────────────────────────────────────────────────────
    section_header 2
    info "$(ui token_hint1)"
    info "$(ui token_hint2)"

    local token_ok=false
    while [[ "$token_ok" == false ]]; do
        ask "$(ui token_prompt)"
        TG_TOKEN="$REPLY"
        if [[ -z "$TG_TOKEN" ]]; then
            err "$(ui token_empty)"; continue
        fi
        ui_indent
        echo -ne "${DIM}$(ui token_checking)${RESET} "
        local response
        response=$(curl -s "https://api.telegram.org/bot${TG_TOKEN}/getMe")
        if echo "$response" | grep -q '"ok":true'; then
            BOT_NAME=$(echo "$response" | grep -oP '"username":"\K[^"]+')
            echo -e "${BGREEN}✓${RESET}"
            ok "@${BOT_NAME}"
            token_ok=true
        else
            echo -e "${BRED}✗${RESET}"
            err "$(ui token_invalid)"
        fi
    done

    # ── Chat ID automatico via getUpdates ───────────────────────────────────
    section_header 3
    info "$(ui chatid_hint2) @${BOT_NAME}"
    info "$(ui chatid_hint_send)"
    ui_blank

    local chatid_ok=false
    local chatid_attempts=0
    local chatid_max=20

    while [[ "$chatid_ok" == false ]]; do
        chatid_attempts=$((chatid_attempts + 1))

        if [[ $chatid_attempts -le $chatid_max ]]; then
            if [[ $chatid_attempts -gt 1 ]]; then
                info "$(ui chatid_attempt_hint) ($chatid_attempts/$chatid_max)"
            fi
            ui_indent
            echo -ne "${BOLD}$(ui chatid_confirm_prompt)${RESET} "
            read -r _confirm || true

            ui_indent
            echo -ne "${DIM}$(ui chatid_checking)${RESET} "

            local updates_response
            updates_response=$(curl -s "https://api.telegram.org/bot${TG_TOKEN}/getUpdates" 2>/dev/null) || true

            local TG_CHAT_ID_RAW
            TG_CHAT_ID_RAW=$(echo "$updates_response" | grep -oP '"chat":\{"id":\K-?[0-9]+' | tail -1) || true
            TG_CHAT_ID="${TG_CHAT_ID_RAW:-}"

            if [[ -n "$TG_CHAT_ID" ]]; then
                echo -e "${BGREEN}✓${RESET}"
                ok "Chat ID: $TG_CHAT_ID"
                ok "$(ui test_sent)"
                chatid_ok=true
            else
                echo -e "${BRED}✗${RESET}"
                warn "$(ui chatid_not_found)"
                info "$(ui chatid_hint_send)"
                ui_blank
            fi

        else
            ui_blank
            warn "$(ui chatid_max_attempts)"
            ui_blank
            local manual_ok=false
            while [[ "$manual_ok" == false ]]; do
                ui_indent
                echo -ne "${BOLD}$(ui chatid_manual_prompt)${RESET}: "
                read -r manual_id || true
                if [[ "$manual_id" =~ ^-?[0-9]+$ ]]; then
                    TG_CHAT_ID="$manual_id"
                    ui_indent
                    echo -ne "${DIM}$(ui chatid_checking)${RESET} "
                    local send_test
                    send_test=$(tg_send "$TG_CHAT_ID" "$(build_chatid_test_msg)" "true")
                    if echo "$send_test" | grep -q '"ok":true'; then
                        echo -e "${BGREEN}✓${RESET}"
                        ok "Chat ID: $TG_CHAT_ID"
                        ok "$(ui test_sent)"
                        chatid_ok=true
                        manual_ok=true
                    else
                        echo -e "${BRED}✗${RESET}"
                        err "$(ui chatid_manual_invalid)"
                    fi
                else
                    err "$(ui chatid_invalid)"
                fi
            done
        fi
    done

    # ── Docker dir ──────────────────────────────────────────────────────────
    section_header 4
    info "$(ui docker_dir_hint)"

    # Auto-rilevamento
    local -a _detected=()
    mapfile -t _detected < <(detect_docker_compose_dirs 2>/dev/null)
    DOCKER_DIR=""

    if [[ ${#_detected[@]} -gt 0 ]]; then
        ui_blank
        info "$(ui docker_dir_found):"
        local i
        for i in "${!_detected[@]}"; do
            ui_indent
            echo -e "${BCYAN}$((i+1)))${RESET} ${_detected[$i]}"
        done
        ui_indent
        echo -e "${BCYAN}0)${RESET} $(ui docker_dir_manual)"
        ui_blank
        ask "$(ui docker_dir_choice)" "1"
        local _choice="$REPLY"
        if [[ "$_choice" =~ ^[1-9][0-9]*$ ]] && (( _choice >= 1 && _choice <= ${#_detected[@]} )); then
            DOCKER_DIR="${_detected[$((_choice-1))]}"
            ok "$DOCKER_DIR"
        fi
    fi

    # Se non scelto o 0: inserimento manuale
    if [[ -z "$DOCKER_DIR" ]]; then
        local dir_ok=false
        while [[ "$dir_ok" == false ]]; do
            ask "$(ui docker_dir_prompt)"
            if [[ -z "$REPLY" ]]; then
                err "$(ui docker_dir_required)"; continue
            fi
            DOCKER_DIR="$REPLY"
            if [[ ! -d "$DOCKER_DIR" ]]; then
                warn "$(ui docker_dir_notfound)"
                ask "$(ui docker_dir_create)" "y"
                if [[ "${REPLY,,}" =~ ^(y|yes|s|si)$ ]]; then
                    mkdir -p "$DOCKER_DIR"
                    ok "$(ui docker_dir_created) $DOCKER_DIR"
                    dir_ok=true
                fi
            elif ! find "$DOCKER_DIR" -maxdepth 1 \( -name '*.yml' -o -name '*.yaml' \) 2>/dev/null | grep -q .; then
                warn "$(ui docker_dir_noyml)"
                ask "$(ui docker_dir_continue)" "y"
                if [[ "${REPLY,,}" =~ ^(y|yes|s|si)$ ]]; then
                    dir_ok=true
                fi
            else
                ok "$DOCKER_DIR"
                dir_ok=true
            fi
        done
    fi

    # ── Username ────────────────────────────────────────────────────────────
    section_header 5
    info "$(ui username_hint)"

    ask "$(ui username_prompt)" "Admin"
    USER_NAME="$REPLY"
    ok "$(ui username_ok) $USER_NAME"
    tg_send "$TG_CHAT_ID" "$(build_greeting_msg "$USER_NAME")"

    # ── Promemoria ──────────────────────────────────────────────────────────
    section_header 6
    info "$(ui reminder_hint)"

    ask "$(ui reminder_day)" "10"
    REMINDER_DAY="$REPLY"
    if [[ ! "$REMINDER_DAY" =~ ^[0-9]+$ ]] || [[ "$REMINDER_DAY" -lt 1 ]] || [[ "$REMINDER_DAY" -gt 28 ]]; then
        warn "$(ui reminder_day_invalid)"; REMINDER_DAY="10"
    fi

    ask "$(ui reminder_hour)" "09:00"
    REMINDER_INPUT="$REPLY"

    if [[ "$REMINDER_INPUT" =~ ^([0-9]{1,2}):([0-9]{2})$ ]]; then
        REMINDER_HOUR="${BASH_REMATCH[1]}"
        REMINDER_MINUTE="${BASH_REMATCH[2]}"
    elif [[ "$REMINDER_INPUT" =~ ^([0-9]{1,2})$ ]]; then
        REMINDER_HOUR="${BASH_REMATCH[1]}"
        REMINDER_MINUTE="0"
    else
        warn "$(ui reminder_hour_invalid)"; REMINDER_HOUR="9"; REMINDER_MINUTE="0"
    fi

    REMINDER_HOUR=$(echo "$REMINDER_HOUR" | sed 's/^0*//')
    REMINDER_HOUR="${REMINDER_HOUR:-0}"
    REMINDER_MINUTE=$(echo "$REMINDER_MINUTE" | sed 's/^0*//')
    REMINDER_MINUTE="${REMINDER_MINUTE:-0}"

    if [[ "$REMINDER_HOUR" -gt 23 ]] || [[ "$REMINDER_MINUTE" -gt 59 ]]; then
        warn "$(ui reminder_hour_invalid)"; REMINDER_HOUR="9"; REMINDER_MINUTE="0"
    fi

    ok "$(ui reminder_ok) $REMINDER_DAY $(ui reminder_at) $(printf '%02d:%02d' $REMINDER_HOUR $REMINDER_MINUTE)"

    # ── Riepilogo ───────────────────────────────────────────────────────────
    section_header 7
    ui_blank
    local _col=16
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_bot)"         "@${BOT_NAME}"
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_chatid)"      "$TG_CHAT_ID"
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_install_dir)" "$INSTALL_DIR"
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_dir)"         "$DOCKER_DIR"
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_username)"    "$USER_NAME"
    ui_indent; printf "${DIM}%-${_col}s${RESET} %s\n" "$(ui summary_reminder)"    "$(ui summary_day) $REMINDER_DAY $(ui summary_at) $(printf '%02d:%02d' $REMINDER_HOUR $REMINDER_MINUTE)"
    ui_blank
    ask "$(ui confirm_install)" "y"
    if [[ ! "${REPLY,,}" =~ ^(y|yes|s|si)$ && -n "$REPLY" ]]; then
        ui_blank
        warn "$(ui cancelled)"
        exit 0
    fi
    UI_CONFIG_MODE=false
}

# ---------------------------------------------------------------------------
# Installazione dipendenze Python
# ---------------------------------------------------------------------------

install_dependencies() {
    divider
    step "$(ui python_deps)"
    # Niente --prefix: lasciamo che pip scelga il path corretto per il sistema.
    # Con --prefix=/usr/local certi pip installano in site-packages/ invece di
    # dist-packages/, che Python non cerca di default su Debian → ModuleNotFoundError.
    progress "python-telegram-bot[job-queue]" \
        pip3 install "python-telegram-bot[job-queue]" --break-system-packages --quiet
}

# ---------------------------------------------------------------------------
# Scrittura del bot e dei file lingua
# ---------------------------------------------------------------------------

write_bot() {
    divider
    step "$(ui writing_bot)"

    # Crea la struttura di cartelle
    mkdir -p "$INSTALL_DIR/languages"
    mkdir -p "$INSTALL_DIR/handlers"
    mkdir -p "$INSTALL_DIR/helpers"
    mkdir -p "$INSTALL_DIR/operations"

    # Scarica o usa il file locale (in src/ nel repo, piatto in INSTALL_DIR)
    if [[ -f "./src/stack_updater.py" ]]; then
        cp "./src/stack_updater.py" "$INSTALL_DIR/stack_updater.py"
    else
        echo -ne "  ${DIM}Download stack_updater.py...${RESET} "
        curl -fsSL "$REPO/src/stack_updater.py" -o "$INSTALL_DIR/stack_updater.py"
        echo -e "${BGREEN}✓${RESET}"
    fi
    chmod +x "$INSTALL_DIR/stack_updater.py"
    ok "$INSTALL_DIR/stack_updater.py"

    # VERSION rimane alla root del repo
    if [[ -f "./VERSION" ]]; then
        cp "./VERSION" "$INSTALL_DIR/VERSION"
    else
        echo -ne "  ${DIM}Download VERSION...${RESET} "
        curl -fsSL "$REPO/VERSION" -o "$INSTALL_DIR/VERSION"
        echo -e "${BGREEN}✓${RESET}"
    fi
    ok "$INSTALL_DIR/VERSION"

    # Scarica (o copia dal repo locale) tutti i moduli Python del bot.
    # Nel repo stanno in src/<percorso>; vengono installati piatti in INSTALL_DIR.
    # Tenere allineato con la lista in src/operations/app_update.py e con
    # do_update() più in basso in questo script.
    local _bot_files=(
        "states.py"
        "config.py"
        "utils.py"
        "lang.py"
        "version.py"
        "ui.py"
        "handlers/__init__.py"
        "handlers/shared.py"
        "handlers/start.py"
        "handlers/menu.py"
        "handlers/system.py"
        "handlers/docker.py"
        "handlers/all_updates.py"
        "handlers/settings.py"
        "handlers/jobs.py"
        "helpers/__init__.py"
        "helpers/system.py"
        "helpers/docker.py"
        "operations/__init__.py"
        "operations/core.py"
        "operations/system_ops.py"
        "operations/docker_ops.py"
        "operations/all_ops.py"
        "operations/app_update.py"
    )
    local _f
    for _f in "${_bot_files[@]}"; do
        if [[ -f "./src/${_f}" ]]; then
            cp "./src/${_f}" "$INSTALL_DIR/${_f}"
        else
            echo -ne "  ${DIM}Download ${_f}...${RESET} "
            curl -fsSL "$REPO/src/${_f}" -o "$INSTALL_DIR/${_f}"
            echo -e "${BGREEN}✓${RESET}"
        fi
        ok "$INSTALL_DIR/${_f}"
    done

    # Scarica tutti i file lingua nella cartella languages/
    for _lang in it en; do
        if [[ -f "./src/languages/${_lang}.json" ]]; then
            cp "./src/languages/${_lang}.json" "$INSTALL_DIR/languages/${_lang}.json"
        else
            echo -ne "  ${DIM}Download languages/${_lang}.json...${RESET} "
            curl -fsSL "$REPO/src/languages/${_lang}.json" -o "$INSTALL_DIR/languages/${_lang}.json"
            echo -e "${BGREEN}✓${RESET}"
        fi
        ok "$INSTALL_DIR/languages/${_lang}.json"
    done

    # Scrive il file di configurazione JSON
    # I valori stringa vengono passati come argomenti sys.argv per evitare
    # che caratteri speciali (apostrofi, virgolette, ecc.) rompano il codice Python inline.
    local REMINDER_MINUTE_VAL="${REMINDER_MINUTE:-0}"
    python3 - "$TG_TOKEN" "$TG_CHAT_ID" "$DOCKER_DIR" \
              "$REMINDER_DAY" "$REMINDER_HOUR" "$REMINDER_MINUTE_VAL" \
              "$USER_NAME" "$LANG_CODE" "$INSTALL_DIR" <<'PYEOF'
import json, sys
token, chat_id, docker_dir, reminder_day, reminder_hour, reminder_minute, \
    user_name, lang, install_dir = sys.argv[1:]
config = {
    'token':           token,
    'chat_id':         int(chat_id),
    'docker_dir':      docker_dir,
    'reminder_day':    int(reminder_day),
    'reminder_hour':   int(reminder_hour),
    'reminder_minute': int(reminder_minute),
    'user_name':       user_name,
    'lang':            lang,
}
with open(f'{install_dir}/stack_updater_config.json', 'w') as f:
    json.dump(config, f, indent=2)
PYEOF
    chmod 600 "$INSTALL_DIR/stack_updater_config.json"
    ok "$INSTALL_DIR/stack_updater_config.json"

    # Log
    touch "$LOG_FILE"
    chmod 644 "$LOG_FILE"
    ok "$LOG_FILE"
}

# ---------------------------------------------------------------------------
# Servizio systemd
# ---------------------------------------------------------------------------

write_service() {
    divider
    step "$(ui systemd_setup)"

    PYTHON_BIN=$(python3 -c "import sys; print(sys.executable)")

    # Rileva il path reale dove pip ha installato python-telegram-bot.
    # Usa "pip show" invece di "import telegram" perché su Debian pip può installare
    # in site-packages/ invece di dist-packages/, che Python non cerca di default.
    # Nota: _pip_show separato da awk per evitare che pipefail causi l'uscita
    # dello script se "pip show" restituisce codice non-zero.
    _pip_show=$(python3 -m pip show python-telegram-bot 2>/dev/null || true)
    TELEGRAM_PATH=$(echo "$_pip_show" | awk '/^Location:/ {print $2}')

    # Fallback 1: se pip show non restituisce nulla, usa tutte le site-packages di sistema
    if [[ -z "$TELEGRAM_PATH" ]]; then
        TELEGRAM_PATH=$(python3 -c \
            "import site; print(':'.join(p for p in site.getsitepackages() if p))" \
            2>/dev/null || echo "")
    fi

    # Fallback 2: verifica che telegram sia davvero importabile con il path rilevato.
    # Se non lo è (es. pip ha usato un layout insolito), cerca la cartella telegram
    # direttamente nel filesystem come ultima risorsa.
    if ! PYTHONPATH="$TELEGRAM_PATH" python3 -c "import telegram" 2>/dev/null; then
        _tg_dir=$(find /usr/local/lib /usr/lib -maxdepth 6 \
            -name "telegram" -type d 2>/dev/null | head -1 || true)
        if [[ -n "$_tg_dir" ]]; then
            TELEGRAM_PATH=$(dirname "$_tg_dir")
        fi
    fi

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Stack Updater — Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Environment="PYTHONPATH=${TELEGRAM_PATH}"
ExecStart=${PYTHON_BIN} ${INSTALL_DIR}/stack_updater.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    ok "$SERVICE_FILE"
    progress "systemctl daemon-reload"          systemctl daemon-reload
    progress "systemctl enable stack_updater"   systemctl enable stack_updater
    progress "systemctl start stack_updater"    systemctl start stack_updater

    sleep 3
    if systemctl is-active --quiet stack_updater; then
        ok "$(ui service_active)"
    else
        err "$(ui service_error)"
        echo ""
        info "$(ui service_log)"
        journalctl -u stack_updater -n 15 --no-pager | sed 's/^/    /'
        echo ""
        warn "$(ui service_hint1)"
        warn "$(ui service_hint2) sudo systemctl restart stack_updater"
        warn "$(ui service_hint3) sudo journalctl -u stack_updater -f"
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Messaggio finale
# ---------------------------------------------------------------------------

print_success() {
    divider
    echo -e "  ${BGREEN}${BOLD}$(ui install_done)${RESET}"
    echo ""
    echo -e "  $(ui bot_active)"
    echo -e "  $(ui write_start) ${BOLD}/start${RESET} $(ui to_begin)"
    echo ""
    echo -e "  ${BOLD}$(ui useful_cmds)${RESET}"
    echo -e "  ${DIM}$(ui status_label)${RESET}    sudo systemctl status stack_updater"
    echo -e "  ${DIM}$(ui log_label)${RESET}   sudo journalctl -u stack_updater -f"
    echo -e "  ${DIM}$(ui restart_label)${RESET}  sudo systemctl restart stack_updater"
    echo -e "  ${DIM}$(ui disable_label)${RESET}  sudo systemctl disable --now stack_updater"
    echo ""
    echo -e "  ${BOLD}$(ui installed_files)${RESET}"
    echo -e "  ${DIM}  $INSTALL_DIR/stack_updater.py${RESET}"
    echo -e "  ${DIM}  $INSTALL_DIR/stack_updater_config.json${RESET}"
    echo -e "  ${DIM}  $INSTALL_DIR/languages/${RESET}"
    echo -e "  ${DIM}  $SERVICE_FILE${RESET}"
    echo -e "  ${DIM}  $LOG_FILE${RESET}"
    divider

    tg_send "$TG_CHAT_ID" "$(build_install_complete_msg)"

    echo -e "  ${DIM}$(ui confirm_telegram)${RESET}"
    echo ""
}

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

main() {
    select_language
    check_existing_install
    check_prerequisites
    configure
    install_dependencies
    write_bot
    write_service
    print_success
}

main "$@"
