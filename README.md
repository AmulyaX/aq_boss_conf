# AQ Boss Linux Package

Systemd-driven installer and updater for AQ Boss devices on Linux. Ships with a bundled default binary so devices can boot and run even without internet the first time.

## What’s included
- `aq-boss-linux.service`: main updater runner (late-boot).
- `aq-boss-usb-update@.service`: udev-triggered USB updater.
- `/opt/aq-boss-linux/updater/aq-boss-linux.py`: fetch/run logic with offline fallback.
- `/opt/aq-boss-linux/binaries/default/`: always-present default binary and `default.conf`.
- Helper scripts: `build_deb.sh`, `uninstall.sh`, `show_logs.sh`, and `automount.sh`.

## Installation
1) Build the `.deb` (samples bundled):
```bash
cd aq-boss-linux
./build_deb.sh
# or build and install immediately (requires sudo if not root):
./build_deb.sh -i
```
> The build fails if `opt/aq-boss-linux/binaries/default/azq_boss_pc` is missing or empty.

2) Install the package:
```bash
sudo dpkg -i aq-boss-linux_*.deb
```
3) Services are enabled automatically. If you edited unit files, reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart aq-boss-linux.service
```

## Service behavior (boot)
1) Waits up to 60s for internet:
   - If online: downloads host-specific `*.conf` and matching binary, then runs it.
   - If online fetch fails: falls back to the latest previously downloaded version.
2) If no internet:
   - Uses the latest previously downloaded `conf`+binary if both exist.
   - If a `conf` exists but its binary is missing: logs an error and stops (no default).
   - If no `conf` exists: runs the bundled default binary with `BRIDGE_MODE=n`.
3) Keeps the `default` folder forever; old downloaded versions are cleaned, leaving the newest two.

## USB update flow
- `80-aq-boss-usb.rules` triggers `aq-boss-usb-update@.service` when a USB is inserted.
- The service scans for `aq_boss_update` on mounted media and installs a newer `aq-boss-linux_*.deb` if found.

## Logs
- Main service journal: `sudo ./aq-boss-linux/show_logs.sh --exec`
- USB updater log: `/var/log/aq_boss_usb_update.log`

## Helper scripts
- `build_deb.sh`: builds the Debian package; `-i` installs it after building.
- `uninstall.sh`: stops services, removes units/udev rules, and deletes `/opt/aq-boss-linux`.
- `show_logs.sh`: follows systemd journal for the main service.
- `automount.sh`: enables/checks desktop automount so USB updates work reliably.

## Uninstall
```bash
cd aq-boss-linux
sudo ./uninstall.sh
```

## Repo layouts for configs
`conf/*.conf` files are fetched per-hostname (e.g., `hostname.conf`) from the public repo when online.
