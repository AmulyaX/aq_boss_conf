#!/bin/bash
set -e

PKG_NAME="aq-boss-linux"
PKG_DIR="$(pwd)"
INSTALL_AFTER_BUILD=false

while getopts ":ih" opt; do
  case "$opt" in
    i) INSTALL_AFTER_BUILD=true ;;
    h)
      echo "Usage: $0 [-i]"
      echo "  -i   Install the built package after building"
      exit 0
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
  esac
done

# Extract version from DEBIAN/control
PKG_VERSION=$(grep -m1 '^Version:' "${PKG_DIR}/DEBIAN/control" | awk '{print $2}')
if [ -z "$PKG_VERSION" ]; then
  echo "Error: Could not read Version from DEBIAN/control"
  exit 1
fi

DEB_FILE="${PKG_DIR}/${PKG_NAME}_${PKG_VERSION}_all.deb"

echo "=== Building ${PKG_NAME} ${PKG_VERSION} ==="
REQUIRED_FILES=(
  "DEBIAN/control"
  "DEBIAN/preinst"
  "DEBIAN/postinst"
  "DEBIAN/postrm"
  "etc/systemd/system/aq-boss-linux.service"
  "opt/aq-boss-linux/updater/aq-boss-linux.py"
  "opt/aq-boss-linux/updater/automount.sh"
  "opt/aq-boss-linux/binaries/default/azq_boss_pc"
  "opt/aq-boss-linux/binaries/default/default.conf"
)
for f in "${REQUIRED_FILES[@]}"; do
  [ -f "$f" ] || { echo "Missing $f"; exit 1; }
done

# Ensure default binary exists and is non-empty
DEFAULT_BIN="opt/aq-boss-linux/binaries/default/azq_boss_pc"
if [ ! -s "$DEFAULT_BIN" ]; then
  echo "Default binary missing or empty at $DEFAULT_BIN"
  exit 1
fi

rm -f "${PKG_DIR}"/*.deb || true
chmod 755 DEBIAN/preinst DEBIAN/postinst DEBIAN/postrm opt/aq-boss-linux/updater/aq-boss-linux.py opt/aq-boss-linux/updater/automount.sh opt/aq-boss-linux/binaries/default/azq_boss_pc
chmod 644 etc/systemd/system/aq-boss-linux.service DEBIAN/control opt/aq-boss-linux/binaries/default/default.conf
chmod 644 etc/systemd/system/aq-boss-linux.service DEBIAN/control


dpkg-deb --build "${PKG_DIR}" "${DEB_FILE}"

echo "✅ Built package: ${DEB_FILE}"

if $INSTALL_AFTER_BUILD; then
  echo "Installing ${DEB_FILE}..."
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    SUDO="sudo"
  else
    SUDO=""
  fi
  $SUDO dpkg -i "${DEB_FILE}"
fi
