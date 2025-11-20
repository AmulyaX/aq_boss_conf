#!/usr/bin/env bash
set -euo pipefail

PACKAGE="aq-boss-linux"
SERVICE_NAME="aq-boss-linux.service"
USB_RULE="/etc/udev/rules.d/80-aq-boss-usb.rules"
SYSTEMD_UNIT="/etc/systemd/system/aq-boss-usb-update@.service"
INSTALL_DIR="/opt/aq-boss-linux"
LOG_FILE="/var/log/aq_boss_usb_update.log"
LOCK_FILE="/tmp/aq_boss_update.lock"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
    echo "Please run this script with sudo/root privileges." >&2
    exit 1
fi

has_systemd() {
    pidof systemd >/dev/null 2>&1 && command -v systemctl >/dev/null 2>&1
}

is_installed() {
    if dpkg-query -W -f='${Status}' "$PACKAGE" 2>/dev/null | grep -q "install ok installed"; then
        return 0
    fi
    return 1
}

stop_services() {
    if has_systemd; then
        echo "Stopping and disabling $SERVICE_NAME..."
        systemctl stop "$SERVICE_NAME" 2>/dev/null || true
        systemctl disable "$SERVICE_NAME" 2>/dev/null || true

        echo "Stopping AQ Boss USB updater instances..."
        systemctl list-units --all | awk '/aq-boss-usb-update@/ {print $1}' | while read -r svc; do
            [ -n "$svc" ] || continue
            systemctl stop "$svc" 2>/dev/null || true
        done

        systemctl daemon-reload || true
    fi
}

purge_package() {
    if command -v apt-get >/dev/null 2>&1; then
        echo "Purging package $PACKAGE via apt-get..."
        apt-get purge -y "$PACKAGE" || true
    elif command -v dpkg >/dev/null 2>&1; then
        echo "Purging package $PACKAGE via dpkg..."
        dpkg --purge "$PACKAGE" || true
    else
        echo "Neither apt-get nor dpkg is available; skipping package purge." >&2
    fi
}

cleanup_files() {
    echo "Removing residual files..."
    rm -rf "$INSTALL_DIR" 2>/dev/null || true
    rm -f "$USB_RULE" "$SYSTEMD_UNIT" "$LOG_FILE" "$LOCK_FILE" 2>/dev/null || true

    if has_systemd; then
        systemctl daemon-reload || true
    fi
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules || true
    fi
}

main() {
    echo "== AQ Boss Linux uninstall =="

    if is_installed; then
        stop_services
        purge_package
    else
        echo "Package $PACKAGE is not marked as installed; proceeding with cleanup only."
        # Still try to purge in case it's in a half-configured state
        purge_package
    fi

    cleanup_files
    echo "Uninstall complete."
}

main "$@"
