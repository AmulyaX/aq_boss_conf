#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="aq-boss-linux.service"
UPDATER_LOG="/var/log/aq_boss_usb_update.log"

usage() {
    cat <<'USAGE'
Usage: show_logs.sh --service|--exec [--lines N]
  --service   Follow USB updater log at /var/log/aq_boss_usb_update.log
  --exec      Follow journal for aq-boss-linux.service (binary run)

Options (common):
  --lines N   Number of lines to show initially (default: 200)
  -h, --help  This help

Logs stream until you press Ctrl+C.
USAGE
}

TARGET=""
LINES=200

while [ $# -gt 0 ]; do
    case "$1" in
        --service) TARGET="service"; shift ;;
        --exec) TARGET="exec"; shift ;;
        --lines) LINES="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *)
            echo "Unknown option: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [ -z "$TARGET" ]; then
    echo "Please specify one of --service or --exec." >&2
    usage
    exit 1
fi

run_journal() {
    journalctl -u "$SERVICE_NAME" -n "$LINES" -f --no-pager
}

run_updater_log() {
    if [ ! -f "$UPDATER_LOG" ]; then
        echo "Updater log not found at $UPDATER_LOG" >&2
        exit 1
    fi
    tail -n "$LINES" -f "$UPDATER_LOG"
}

case "$TARGET" in
    service) # updater log
        run_updater_log
        ;;
    exec) # binary (service) logs
        run_journal
        ;;
    *)
        echo "Unknown target: $TARGET" >&2
        usage
        exit 1
        ;;
esac
