#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"

mode="${1:-setup}"
case "$mode" in
    setup|python|cron) ;;
    *) echo "Usage: $0 [setup|python|cron]" >&2; exit 2 ;;
esac

if [ "$(id -u)" -eq 0 ]; then
    echo "Run setup as your logged-in desktop user, without sudo. Setup uses sudo only for system packages/services." >&2
    exit 1
fi

install_packages() {
    if ! command -v apt-get >/dev/null; then
        echo "Automatic package setup requires Debian/Ubuntu. Install these packages manually: $*" >&2
        exit 1
    fi
    sudo apt-get update
    sudo apt-get install -y "$@"
}

check_python() {
    /usr/bin/python3 -c 'import gi; gi.require_version("Gio", "2.0"); from gi.repository import Gio, GLib'
}

if ! check_python >/dev/null 2>&1; then
    install_packages python3 python3-gi gir1.2-glib-2.0
fi
check_python
echo "Python ready: /usr/bin/python3 with GNOME PyGObject."
if [ "$mode" = python ]; then exit 0; fi

if ! command -v crontab >/dev/null || [ ! -x /usr/bin/flock ] || [ ! -x /usr/bin/logger ]; then
    install_packages cron util-linux
fi
if command -v systemctl >/dev/null && [ -d /run/systemd/system ]; then
    if ! systemctl is-active --quiet cron.service || ! systemctl is-enabled --quiet cron.service; then
        sudo systemctl enable --now cron.service
    fi
else
    echo "Ensure the system cron daemon is running; no systemd service was detected."
fi
/usr/bin/python3 manage_cron.py install
