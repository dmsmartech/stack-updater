# Stack Updater

Automatic update of Debian and Docker containers, controlled via **Telegram Bot** with interactive confirmation, step-by-step notifications and error handling.

## How it works

On the 10th of every month (configurable) you receive a Telegram message with the buttons **Yes, update** / **No, I'll do it later**. If you confirm, the bot executes the three steps one at a time, notifying you in real time. If an error occurs, it shows you what went wrong and asks how to proceed.

```
📅 Monthly reminder — raspberrypi

It's time to update the system!
Do you want to proceed now?

[ ✅ Yes, update now ]  [ ❌ No, I'll do it later ]
```

You can also trigger it at any time by sending `/update` to the bot.

## Installation

```bash
wget -O install.sh https://raw.githubusercontent.com/dmsmartech/stack-updater/main/install.sh
sudo bash install.sh
```

The installer guides you step by step and requires no manual file editing.

**What the installer does:**
- Asks you to choose the language (English / Italiano)
- Checks prerequisites (Python 3.9+, Docker, docker compose v2, systemd)
- Asks for the Telegram bot token and verifies it immediately
- Asks for your Chat ID and sends a test message to confirm it
- Asks for your `docker-compose.yml` directory
- Asks for the day and time of the monthly reminder
- Installs the Python dependency, writes the files and starts the systemd service
- Sends a final confirmation message on Telegram

## Prerequisites

- Debian / Raspberry Pi OS (or derivatives)
- Python 3.9+
- Docker with the `docker compose` v2 plugin
- systemd
- A Telegram bot (created with [@BotFather](https://t.me/BotFather))

## Update flow

```
Step 1 — apt-get update + upgrade
  ↓ OK    → "Debian updated. Moving on to containers."
  ↓ Error → shows problems → [ 🔁 Retry | ▶️ Continue | 🛑 Abort ]

Step 2 — docker compose pull
  ↓ OK    → "Pull completed. Starting containers."
  ↓ Error → lists containers with problems → [ 🔁 Retry | ▶️ Continue | 🛑 Abort ]

Step 3 — docker compose up -d
  ↓ OK    → "Containers started. Cleaning up."
  ↓ Error → lists containers that failed to start → [ 🔁 Retry | ▶️ Continue | 🛑 Abort ]

Cleanup — docker image prune -f

Final summary:
  ✅ "Update completed successfully!" (if everything went fine)
  ⚠️  "Update completed with ignored errors." + problem list (if you continued despite errors)
```

## Languages

The installer lets you choose the language at startup. The selected language is used both for the installation wizard and for all Telegram bot messages.

**Supported languages:**

| Code | Language |
|------|----------|
| `en` | English  |
| `it` | Italiano |

Language files are located in the `languages/` folder. Each file is a simple JSON with all the strings used by the bot.

**Adding a new language** is straightforward: copy `languages/en.json`, rename it to your language code (e.g. `languages/de.json`), translate the values, and open a pull request. The keys must stay exactly the same — only the values change.

```json
{
  "_language": "Deutsch",
  "_code": "de",
  "_author": "your name",

  "btn_update_now": "🔄 Jetzt aktualisieren",
  "monthly_reminder": "📅 <b>Monatliche Erinnerung — {hostname}</b>\n\nEs ist Zeit, das System zu aktualisieren!\nMöchten Sie jetzt fortfahren?",
  ...
}
```

## Useful commands after installation

```bash
# Service status
sudo systemctl status stack_updater

# Live log
sudo journalctl -u stack_updater -f

# Restart
sudo systemctl restart stack_updater

# Uninstall
sudo systemctl disable --now stack_updater
sudo rm /usr/local/bin/stack_updater.py /usr/local/bin/stack_updater_lang.json /etc/systemd/system/stack_updater.service
```

## Installed files

| File | Path |
|------|------|
| Python bot | `/usr/local/bin/stack_updater.py` |
| Language file | `/usr/local/bin/stack_updater_lang.json` |
| systemd service | `/etc/systemd/system/stack_updater.service` |
| Log | `/var/log/stack_updater.log` |

## Repository structure

```
stack-updater/
├── install.sh            ← download and run this
├── stack_updater.py      ← the bot (do not edit manually)
├── README.md
└── languages/
    ├── en.json           ← English
    └── it.json           ← Italiano
```

## License

MIT
