#!/usr/bin/env bash
set -euo pipefail

SERVICE="udisks2.service"
UPDATER_LOG_LABEL="[Automount]"

log() {
    echo "$UPDATER_LOG_LABEL $*"
}

usage() {
    cat <<'USAGE'
Usage: automount.sh --enable | --check
  --enable   Best-effort enable USB automount for active desktop user
  --check    Check whether automount is enabled for the active desktop user

Notes:
- Requires a running user session; runs under the active graphical user if found.
- Supports GNOME (Ubuntu), Cinnamon (Linux Mint), and LXQt (Lubuntu).
USAGE
}

ensure_udisks() {
    if systemctl list-unit-files "$SERVICE" >/dev/null 2>&1; then
        systemctl enable --now "$SERVICE" >/dev/null 2>&1 || true
    fi
}

active_user() {
    # Pick the first graphical session user if present
    local user
    user=$(loginctl list-sessions --no-legend 2>/dev/null | awk 'NR==1{print $3}')
    if [ -z "$user" ]; then
        user=$(who | awk 'NR==1{print $1}')
    fi
    echo "$user"
}

desktop_for_user() {
    local user="$1"
    local procs
    procs=$(ps -u "$user" -o comm= 2>/dev/null || true)
    if echo "$procs" | grep -qi "cinnamon"; then
        echo "cinnamon"
    elif echo "$procs" | grep -qi "lxqt"; then
        echo "lxqt"
    elif echo "$procs" | grep -qi "gnome-shell"; then
        echo "gnome"
    else
        echo "unknown"
    fi
}

run_gsettings() {
    local user="$1" schema="$2" key="$3" value="$4"
    local uid
    uid=$(id -u "$user")
    sudo -u "$user" env \
        XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        gsettings set "$schema" "$key" "$value" >/dev/null 2>&1 || true
}

read_gsettings() {
    local user="$1" schema="$2" key="$3"
    local uid
    uid=$(id -u "$user")
    sudo -u "$user" env \
        XDG_RUNTIME_DIR="/run/user/$uid" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" \
        gsettings get "$schema" "$key" 2>/dev/null || true
}

enable_gnome() {
    local user="$1"
    run_gsettings "$user" "org.gnome.desktop.media-handling" "automount" "true"
    run_gsettings "$user" "org.gnome.desktop.media-handling" "automount-open" "true"
}

check_gnome() {
    local user="$1"
    local a o
    a=$(read_gsettings "$user" "org.gnome.desktop.media-handling" "automount")
    o=$(read_gsettings "$user" "org.gnome.desktop.media-handling" "automount-open")
    [ "$a" = "true" ] && [ "$o" = "true" ]
}

enable_cinnamon() {
    local user="$1"
    run_gsettings "$user" "org.cinnamon.desktop.media-handling" "automount" "true"
    run_gsettings "$user" "org.cinnamon.desktop.media-handling" "automount-open" "true"
}

check_cinnamon() {
    local user="$1"
    local a o
    a=$(read_gsettings "$user" "org.cinnamon.desktop.media-handling" "automount")
    o=$(read_gsettings "$user" "org.cinnamon.desktop.media-handling" "automount-open")
    [ "$a" = "true" ] && [ "$o" = "true" ]
}

lxqt_config_path() {
    local user="$1"
    local home
    home=$(getent passwd "$user" | cut -d: -f6)
    echo "$home/.config/pcmanfm-qt/lxqt/settings.conf"
}

enable_lxqt() {
    local user="$1"
    local path
    path=$(lxqt_config_path "$user")
    local dir
    dir=$(dirname "$path")
    sudo -u "$user" mkdir -p "$dir"
    cat <<'EOF' | sudo -u "$user" tee "$path" >/dev/null
[Volume]
mount_on_startup=true
mount_removable=true
mount_removable_ntfs=true
autorun=true
EOF
}

check_lxqt() {
    local user="$1"
    local path
    path=$(lxqt_config_path "$user")
    [ -f "$path" ] && grep -q "mount_removable=true" "$path"
}

enable_for_desktop() {
    local user="$1" desktop="$2"
    case "$desktop" in
        gnome) enable_gnome "$user" ;;
        cinnamon) enable_cinnamon "$user" ;;
        lxqt) enable_lxqt "$user" ;;
        *) return 1 ;;
    esac
}

check_for_desktop() {
    local user="$1" desktop="$2"
    case "$desktop" in
        gnome) check_gnome "$user" ;;
        cinnamon) check_cinnamon "$user" ;;
        lxqt) check_lxqt "$user" ;;
        *) return 1 ;;
    esac
}

ACTION=""
while [ $# -gt 0 ]; do
    case "$1" in
        --enable) ACTION="enable"; shift ;;
        --check) ACTION="check"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

if [ -z "$ACTION" ]; then
    usage
    exit 1
fi

ensure_udisks

USER_NAME=$(active_user)
if [ -z "$USER_NAME" ]; then
    log "No active user session detected; cannot configure automount."
    exit 1
fi

DESKTOP=$(desktop_for_user "$USER_NAME")
if [ "$DESKTOP" = "unknown" ]; then
    log "Could not detect desktop environment for user $USER_NAME."
    exit 1
fi

if [ "$ACTION" = "enable" ]; then
    if enable_for_desktop "$USER_NAME" "$DESKTOP"; then
        if check_for_desktop "$USER_NAME" "$DESKTOP"; then
            log "Automount enabled for $DESKTOP user $USER_NAME."
            exit 0
        else
            log "Attempted to enable automount for $DESKTOP but verification failed."
            exit 1
        fi
    else
        log "Automount enable not supported for desktop '$DESKTOP'."
        exit 1
    fi
fi

if [ "$ACTION" = "check" ]; then
    if check_for_desktop "$USER_NAME" "$DESKTOP"; then
        log "Automount is enabled for $DESKTOP user $USER_NAME."
        exit 0
    else
        log "Automount is NOT enabled for $DESKTOP user $USER_NAME."
        exit 1
    fi
fi
