#!/bin/bash
set -e

PKG_NAME="aq-boss-linux"
PKG_VERSION="1.0.0"
PKG_DIR="$(pwd)"
DEB_FILE="${PKG_DIR}/${PKG_NAME}_${PKG_VERSION}_all.deb"

echo "=== Building ${PKG_NAME} ${PKG_VERSION} ==="
REQUIRED_FILES=(
  "DEBIAN/control"
  "DEBIAN/preinst"
  "DEBIAN/postinst"
  "DEBIAN/postrm"
  "etc/systemd/system/aq_boss_linux.service"
  "opt/boss-local/updater/aq_boss_linux.py"
)
for f in "${REQUIRED_FILES[@]}"; do
  [ -f "$f" ] || { echo "Missing $f"; exit 1; }
done

rm -f "${PKG_DIR}"/*.deb || true
chmod 755 DEBIAN/preinst DEBIAN/postinst DEBIAN/postrm opt/boss-local/updater/aq_boss_linux.py
chmod 644 etc/systemd/system/aq_boss_linux.service DEBIAN/control
sudo chown -R root:root . || true

dpkg-deb --build "${PKG_DIR}" "${DEB_FILE}"

echo "✅ Built package: ${DEB_FILE}"
