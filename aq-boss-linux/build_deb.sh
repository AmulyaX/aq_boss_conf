#!/bin/bash
set -e

PKG_NAME="aq-boss-linux"
PKG_DIR="$(pwd)"

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
)
for f in "${REQUIRED_FILES[@]}"; do
  [ -f "$f" ] || { echo "Missing $f"; exit 1; }
done

rm -f "${PKG_DIR}"/*.deb || true
chmod 755 DEBIAN/preinst DEBIAN/postinst DEBIAN/postrm opt/aq-boss-linux/updater/aq-boss-linux.py
chmod 644 etc/systemd/system/aq-boss-linux.service DEBIAN/control
sudo chown -R root:root . || true

dpkg-deb --build "${PKG_DIR}" "${DEB_FILE}"

echo "✅ Built package: ${DEB_FILE}"
