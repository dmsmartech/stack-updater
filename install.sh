#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
#  Stack Updater — installer
#  https://github.com/dmsmartech/stack-updater
# =============================================================================

REPO="https://raw.githubusercontent.com/dmsmartech/stack-updater/main"
INSTALL_DIR="/usr/local/bin"
SERVICE_DIR="/etc/systemd/system"
BOT_FILE="$INSTALL_DIR/stack_updater.py"
LANG_FILE="$INSTALL_DIR/stack_updater_lang.json"
SERVICE_FILE="$SERVICE_DIR/stack_updater.service"
LOG_FILE="/var/log/stack_updater.log"

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
# Le chiavi _it e _en vengono selezionate dopo la scelta della lingua.
# ---------------------------------------------------------------------------

ui() {
    # ui "chiave" → stampa la stringa nella lingua scelta
    local key="$1"
    local varname="UI_${LANG_CODE^^}_${key}"
    # fallback a EN se la chiave non esiste nella lingua scelta
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
UI_IT_greeting="Stack Updater"
UI_IT_install_complete="🎉 Installazione completata! Sono ora al tuo servizio. Scrivi /start per iniziare. Ti ricordo che ogni mese il giorno {day} alle ore {hour}:00 ti avviserò per un nuovo aggiornamento."
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
UI_IT_chatid_hint2="  Manda un messaggio al tuo bot"
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
UI_IT_docker_dir_label="③ Directory del tuo docker-compose"
UI_IT_docker_dir_hint="La cartella che contiene il file docker-compose.yml"
UI_IT_docker_dir_prompt="Percorso"
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
UI_IT_uninstall_ask="Vuoi disinstallarlo?"
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
UI_EN_greeting="Stack Updater"
UI_EN_install_complete="🎉 Installation complete! I am now at your service. Type /start to begin. Reminder: every month on day {day} at {hour}:00 I will remind you about updates."
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
UI_EN_chatid_hint2="  Send a message to your bot"
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
UI_EN_docker_dir_label="③ Your docker-compose directory"
UI_EN_docker_dir_hint="The folder containing your docker-compose.yml file"
UI_EN_docker_dir_prompt="Path"
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
UI_EN_uninstall_ask="Do you want to uninstall it?"
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
    echo -e "  ${BOLD}Stack Updater v.1.0${RESET}  ${DIM}— created by dm.smartech — Dario Montalbano${RESET}"
    echo ""
    echo -e "${DIM}  ─────────────────────────────────────────${RESET}"
    echo ""
}

step()     { echo -e "\n${BCYAN}▸${RESET} ${BOLD}$1${RESET}"; }
ok()       { echo -e "  ${BGREEN}✓${RESET} $1"; }
warn()     { echo -e "  ${BYELLOW}⚠${RESET}  $1"; }
err()      { echo -e "  ${BRED}✗${RESET} $1"; }
info()     { echo -e "  ${DIM}$1${RESET}"; }
divider()  { echo -e "\n  ${DIM}─────────────────────────────────────────${RESET}\n"; }

# ---------------------------------------------------------------------------
# Sidebar verticale — si stampa una volta per ogni sezione
# Uso: section_header NUMERO_CORRENTE
# Le sezioni sono: 1=Token 2=ChatID 3=Directory 4=Promemoria
# ---------------------------------------------------------------------------

SIDEBAR_IT=("① Token del Telegram Bot" "② Chat ID Telegram" "③ Directory docker-compose" "④ Username" "⑤ Promemoria mensile")
SIDEBAR_EN=("① Telegram Bot Token" "② Telegram Chat ID" "③ docker-compose directory" "④ Username" "⑤ Monthly reminder")

section_header() {
    local current=$1
    local total=4
    echo ""
    for ((i=1; i<=total; i++)); do
        # Scegli array lingua
        if [[ "$LANG_CODE" == "it" ]]; then
            label="${SIDEBAR_IT[$((i-1))]}"
        else
            label="${SIDEBAR_EN[$((i-1))]}"
        fi

        if [[ $i -lt $total ]]; then
            connector="├"
            vline="│"
        else
            connector="└"
            vline=" "
        fi

        if [[ $i -eq $current ]]; then
            # Passo corrente: freccia azzurra, testo bold bianco
            echo -e "  ${BGREEN}${connector}──▶${RESET} ${BOLD}${label}${RESET}"
        else
            # Altri passi: linea verde dim, testo dim
            echo -e "  ${BGREEN}${connector}───${RESET} ${DIM}${label}${RESET}"
        fi

        # Linea verticale tra i passi (non dopo l'ultimo)
        if [[ $i -lt $total ]]; then
            echo -e "  ${BGREEN}${vline}${RESET}"
        fi
    done
    echo ""
}

ask() {
    local prompt="$1"
    local default="${2:-}"
    if [[ -n "$default" ]]; then
        echo -ne "\n  ${BOLD}$prompt${RESET} ${DIM}[$default]${RESET}: "
    else
        echo -ne "\n  ${BOLD}$prompt${RESET}: "
    fi
    read -r REPLY
    if [[ -z "$REPLY" && -n "$default" ]]; then
        REPLY="$default"
    fi
}

ask_secret() {
    echo -ne "\n  ${BOLD}$1${RESET}: "
    read -rs REPLY
    echo ""
}

progress() {
    local msg="$1"; shift
    echo -ne "  ${DIM}${msg}...${RESET} "
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
# Selezione lingua — PRIMO STEP, prima di tutto il resto
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
# Controlla se già installato
# ---------------------------------------------------------------------------

check_existing_install() {
    if systemctl list-unit-files stack_updater.service &>/dev/null        && systemctl list-unit-files stack_updater.service | grep -q "stack_updater"; then

        divider
        warn "$(ui already_installed)"
        echo ""
        ask "$(ui uninstall_ask)" "n"

        if [[ "${REPLY,,}" =~ ^(y|yes|s|si)$ ]]; then
            echo ""
            step "$(ui uninstall_yes)"
            systemctl disable --now stack_updater 2>/dev/null || true
            rm -f /usr/local/bin/stack_updater.py
            rm -f /usr/local/bin/stack_updater_lang.json
            rm -f /etc/systemd/system/stack_updater.service
            rm -f /var/log/stack_updater.log
            systemctl daemon-reload
            echo ""
            ok "$(ui uninstall_done)"
            echo ""
            exit 0
        else
            echo ""
            warn "$(ui uninstall_no)"
            echo ""
            exit 0
        fi
    fi
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
        progress "pip3" apt-get install -y python3-pip
    fi
    ok "pip3"

    if ! command -v docker &>/dev/null; then
        err "$(ui docker_not_found)"
        info "https://docs.docker.com/engine/install/"
        exit 1
    fi
    ok "Docker $(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1)"

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
# Costruisce i messaggi con newline reali per Telegram
# ---------------------------------------------------------------------------

# Invia un messaggio Telegram con newline reali usando JSON
tg_send() {
    local chat_id="$1"
    local text="$2"
    local return_output="${3:-false}"   # se "true" ritorna l output, altrimenti silenzia
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
        printf "Ciao %s, sono Stack Updater! 👋\nIl tuo bot è pronto.\n\nDammi un momento per completare la configurazione..." "$name"
    else
        printf "Hi %s, I am Stack Updater! 👋\nYour bot is ready.\n\nGive me a moment to finish the configuration..." "$name"
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
    if [[ "$LANG_CODE" == "it" ]]; then
        printf "Installazione completata 🎉\n\nCiao %s, eccoci! Sono ora al tuo servizio. Insieme possiamo:\n\n- Aggiornare il tuo sistema Linux\n- Aggiornare i container Docker, insieme o singolarmente\n- Riavviare il sistema\n- Modificare la pianificazione del promemoria mensile\n\nScrivi /start per iniziare.\n\n📅 Il promemoria è impostato per il giorno %s di ogni mese alle ore %s:%s." "$USER_NAME" "$REMINDER_DAY" "$(printf '%02d' $REMINDER_HOUR)" "$(printf '%02d' $REMINDER_MINUTE)"
    else
        printf "Installation complete 🎉\n\nHi %s, here we are! I am now at your service. Together we can:\n\n- Update your Linux system\n- Update Docker containers, together or individually\n- Restart the system\n- Modify the monthly reminder schedule\n\nType /start to begin.\n\n📅 The reminder is set for day %s of every month at %s:%s." "$USER_NAME" "$REMINDER_DAY" "$(printf '%02d' $REMINDER_HOUR)" "$(printf '%02d' $REMINDER_MINUTE)"
    fi
}

# ---------------------------------------------------------------------------
# Configurazione interattiva
# ---------------------------------------------------------------------------

configure() {
    divider
    step "$(ui configuration)"
    echo ""
    info "$(ui answer_hint)"

    # ── Token ───────────────────────────────────────────────────────────────
    section_header 1
    info "$(ui token_hint1)"
    info "$(ui token_hint2)"

    local token_ok=false
    while [[ "$token_ok" == false ]]; do
        ask "$(ui token_prompt)"
        TG_TOKEN="$REPLY"
        if [[ -z "$TG_TOKEN" ]]; then
            err "$(ui token_empty)"; continue
        fi
        echo -ne "  ${DIM}$(ui token_checking)${RESET} "
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
    section_header 2
    info "$(ui chatid_hint2) @${BOT_NAME}"
    info "$(ui chatid_hint_send)"
    echo ""

    local chatid_ok=false
    local chatid_attempts=0
    local chatid_max=20

    while [[ "$chatid_ok" == false ]]; do
        chatid_attempts=$((chatid_attempts + 1))

        if [[ $chatid_attempts -le $chatid_max ]]; then
            # Tentativo automatico via getUpdates
            if [[ $chatid_attempts -gt 1 ]]; then
                info "$(ui chatid_attempt_hint) ($chatid_attempts/$chatid_max)"
            fi
            echo -ne "  ${BOLD}$(ui chatid_confirm_prompt)${RESET} "
            read -r _confirm || true

            echo -ne "  ${DIM}$(ui chatid_checking)${RESET} "

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
                echo ""
            fi

        else
            # Dopo 20 tentativi falliti: inserimento manuale
            echo ""
            warn "$(ui chatid_max_attempts)"
            echo ""
            local manual_ok=false
            while [[ "$manual_ok" == false ]]; do
                echo -ne "  ${BOLD}$(ui chatid_manual_prompt)${RESET}: "
                read -r manual_id || true
                if [[ "$manual_id" =~ ^-?[0-9]+$ ]]; then
                    TG_CHAT_ID="$manual_id"
                    echo -ne "  ${DIM}$(ui chatid_checking)${RESET} "
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
    section_header 3
    info "$(ui docker_dir_hint)"

    local dir_ok=false
    while [[ "$dir_ok" == false ]]; do
        ask "$(ui docker_dir_prompt)" "/home/pi/homeassistant_hub/docker-config"
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

    # ── Username ────────────────────────────────────────────────────────────
    section_header 4
    echo ""
    echo -e "  ${BOLD}$(ui username_label)${RESET}"
    info "$(ui username_hint)"

    ask "$(ui username_prompt)" "Admin"
    USER_NAME="$REPLY"
    ok "$(ui username_ok) $USER_NAME"
    tg_send "$TG_CHAT_ID" "$(build_greeting_msg "$USER_NAME")"

    # ── Promemoria ──────────────────────────────────────────────────────────
    section_header 5
    info "$(ui reminder_hint)"

    ask "$(ui reminder_day)" "10"
    REMINDER_DAY="$REPLY"
    if [[ ! "$REMINDER_DAY" =~ ^[0-9]+$ ]] || [[ "$REMINDER_DAY" -lt 1 ]] || [[ "$REMINDER_DAY" -gt 28 ]]; then
        warn "$(ui reminder_day_invalid)"; REMINDER_DAY="10"
    fi

    # Accetta sia HH che HH:MM
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

    # Rimuove zero iniziale per Python
    REMINDER_HOUR=$(echo "$REMINDER_HOUR" | sed 's/^0*//')
    REMINDER_HOUR="${REMINDER_HOUR:-0}"
    REMINDER_MINUTE=$(echo "$REMINDER_MINUTE" | sed 's/^0*//')
    REMINDER_MINUTE="${REMINDER_MINUTE:-0}"

    if [[ "$REMINDER_HOUR" -gt 23 ]] || [[ "$REMINDER_MINUTE" -gt 59 ]]; then
        warn "$(ui reminder_hour_invalid)"; REMINDER_HOUR="9"; REMINDER_MINUTE="0"
    fi

    ok "$(ui reminder_ok) $REMINDER_DAY $(ui reminder_at) $(printf '%02d:%02d' $REMINDER_HOUR $REMINDER_MINUTE)"

    # ── Riepilogo ───────────────────────────────────────────────────────────
    divider
    echo -e "  ${BOLD}$(ui summary_title)${RESET}"
    echo ""
    echo -e "  ${DIM}$(ui summary_bot)${RESET}      @${BOT_NAME}"
    echo -e "  ${DIM}$(ui summary_chatid)${RESET}     $TG_CHAT_ID"
    echo -e "  ${DIM}$(ui summary_dir)${RESET}   $DOCKER_DIR"
    echo -e "  ${DIM}$(ui summary_username)${RESET}   $USER_NAME"
    echo -e "  ${DIM}$(ui summary_reminder)${RESET}  $(ui summary_day) $REMINDER_DAY $(ui summary_at) ${REMINDER_HOUR}:${REMINDER_MINUTE}:00"
    echo ""
    ask "$(ui confirm_install)" "y"
    if [[ ! "${REPLY,,}" =~ ^(y|yes|s|si)$ && -n "$REPLY" ]]; then
        echo ""
        warn "$(ui cancelled)"
        exit 0
    fi
}

# ---------------------------------------------------------------------------
# Installazione dipendenze Python
# ---------------------------------------------------------------------------

install_dependencies() {
    divider
    step "$(ui python_deps)"
    progress "python-telegram-bot[job-queue]" \
        pip3 install "python-telegram-bot[job-queue]" --break-system-packages --quiet --prefix=/usr/local
}

# ---------------------------------------------------------------------------
# Scrittura del bot e del file lingua
# ---------------------------------------------------------------------------

write_bot() {
    divider
    step "$(ui writing_bot)"

    # Scarica o usa il file locale
    if [[ -f "./stack_updater.py" ]]; then
        cp "./stack_updater.py" "$BOT_FILE"
    else
        echo -ne "  ${DIM}Download stack_updater.py...${RESET} "
        curl -fsSL "$REPO/stack_updater.py" -o "$BOT_FILE"
        echo -e "${BGREEN}✓${RESET}"
    fi
    chmod +x "$BOT_FILE"
    ok "$BOT_FILE"

    # Scrive il file di configurazione JSON
    local REMINDER_MINUTE_VAL="${REMINDER_MINUTE:-0}"
    python3 -c "
import json
config = {
    'token':           '${TG_TOKEN}',
    'chat_id':         ${TG_CHAT_ID},
    'docker_dir':      '${DOCKER_DIR}',
    'reminder_day':    ${REMINDER_DAY},
    'reminder_hour':   ${REMINDER_HOUR},
    'reminder_minute': ${REMINDER_MINUTE_VAL},
    'user_name':       '${USER_NAME}',
}
with open('/usr/local/bin/stack_updater_config.json', 'w') as f:
    json.dump(config, f, indent=2)
"
    ok "/usr/local/bin/stack_updater_config.json"

    # Scarica e installa il file lingua scelto
    if [[ -f "./languages/${LANG_CODE}.json" ]]; then
        cp "./languages/${LANG_CODE}.json" "$LANG_FILE"
    else
        echo -ne "  ${DIM}Download languages/${LANG_CODE}.json...${RESET} "
        curl -fsSL "$REPO/languages/${LANG_CODE}.json" -o "$LANG_FILE"
        echo -e "${BGREEN}✓${RESET}"
    fi
    ok "$LANG_FILE"

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

    # Trova il python3 e il path dove è installato telegram
    PYTHON_BIN=$(python3 -c "import sys; print(sys.executable)")
    TELEGRAM_PATH=$(python3 -c "import telegram; import os; print(os.path.dirname(os.path.dirname(telegram.__file__)))" 2>/dev/null || echo "")

    cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=Stack Updater — Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
Environment="PYTHONPATH=${TELEGRAM_PATH}"
ExecStart=${PYTHON_BIN} $BOT_FILE
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
    echo -e "  ${DIM}  $BOT_FILE${RESET}"
    echo -e "  ${DIM}  $LANG_FILE${RESET}"
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
