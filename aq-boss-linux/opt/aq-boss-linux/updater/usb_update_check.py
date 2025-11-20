#!/usr/bin/env python3
import os
import subprocess
import re
import time
import fcntl

PKG_NAME = "aq-boss-linux"
SERVICE_NAME = "aq-boss-linux.service"
LOG_FILE = "/var/log/aq_boss_usb_update.log"
UPDATE_FOLDER = "aq_boss_update"
LOCK_FILE = "/tmp/aq_boss_update.lock"
AUTOMOUNT_HELPER = "/opt/aq-boss-linux/updater/automount.sh"


def log(msg):
    """Write message to console and log file with timestamp."""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def acquire_lock():
    """Prevent multiple concurrent update runs."""
    try:
        fd = open(LOCK_FILE, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        log("Checkpoint 1: Lock acquired, starting update process.")
        return fd
    except OSError:
        log("Another update process is already running, exiting.")
        exit(0)


def release_lock(fd):
    try:
        log("Checkpoint 9: Releasing lock and exiting.")
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        os.remove(LOCK_FILE)
    except Exception:
        pass


def check_automount():
    """Run helper to verify automount; log warnings if disabled."""
    if not os.path.isfile(AUTOMOUNT_HELPER):
        log("Automount helper not found; skipping automount check.")
        return
    try:
        result = subprocess.run(
            [AUTOMOUNT_HELPER, "--check"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        stdout = (result.stdout or "").strip()
        if stdout:
            for line in stdout.splitlines():
                log(line)
        if result.returncode != 0:
            log("Automount appears disabled. Enable USB automount in your desktop settings so USB updates work.")
    except Exception as exc:
        log(f"Automount check failed: {exc}")


def find_update_folder(timeout=60, interval=5):
    """Search inside /media, /mnt, and /run/media (max depth 3) every 5s for up to 60s for aq_boss_update."""
    log(
        f"Checkpoint 2: Scanning for '{UPDATE_FOLDER}' folder (up to {timeout}s, max depth 3)..."
    )
    elapsed = 0
    while elapsed < timeout:
        found = []
        for base in ["/media", "/mnt", "/run/media"]:
            if not os.path.isdir(base):
                continue
            log(f"Scanning under {base}...")
            for root, dirs, _ in os.walk(base, topdown=True):
                # calculate depth relative to base
                depth = root[len(base) :].count(os.sep)
                if depth >= 3:
                    dirs[:] = []  # stop descending further
                    continue
                try:
                    if UPDATE_FOLDER in dirs:
                        path = os.path.join(root, UPDATE_FOLDER)
                        found.append(path)
                except PermissionError:
                    log(f"Permission denied scanning {root}, skipping.")
                    continue
                except Exception as e:
                    log(f"Error scanning {root}: {e}")
                    continue
        if found:
            log(f"Found update folder(s): {found}")
            return found[0]
        elapsed += interval
        log(
            f"Waiting... ({elapsed}/{timeout}s) — still looking for '{UPDATE_FOLDER}' inside /media or /mnt."
        )
        time.sleep(interval)
    log(f"Timeout reached ({timeout}s) — no '{UPDATE_FOLDER}' folder found.")
    return None


def get_current_version():
    try:
        output = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", PKG_NAME],
            stderr=subprocess.DEVNULL,
        )
        version = output.decode().strip()
        log(f"Checkpoint 3: Detected currently installed version {version}")
        return version
    except subprocess.CalledProcessError:
        log("Checkpoint 3: Package not installed, assuming version 0.0.0")
        return "0.0.0"


def find_update_deb(update_dir):
    """Look only inside the detected aq_boss_update folder for .deb matching PKG_NAME."""
    log(f"Checkpoint 4: Searching for .deb inside {update_dir}...")
    for root, _, files in os.walk(update_dir):
        for f in files:
            if f.endswith(".deb") and PKG_NAME in f:
                full_path = os.path.join(root, f)
                log(f"Found update candidate: {full_path}")
                return full_path
    log("No matching .deb file found inside update folder.")
    return None


def get_pkg_name_from_deb(deb_path):
    try:
        output = subprocess.check_output(["dpkg-deb", "-f", deb_path, "Package"])
        pkg_name = output.decode().strip()
        log(f"Checkpoint 5: Package name inside .deb: {pkg_name}")
        return pkg_name
    except subprocess.CalledProcessError:
        log("Could not read Package field from .deb.")
        return None


def extract_version_from_deb(deb_path):
    try:
        output = subprocess.check_output(["dpkg-deb", "-f", deb_path, "Version"])
        version = output.decode().strip()
        log(f"Checkpoint 6: Version inside .deb: {version}")
        return version
    except subprocess.CalledProcessError:
        log("Could not read Version field from .deb.")
        return None


def compare_versions(v1, v2):
    def vt(v):
        return tuple(map(int, re.findall(r"\d+", v))) if v else (0,)

    return vt(v1) > vt(v2)


def stop_service():
    log(f"Checkpoint 7: Stopping {SERVICE_NAME}...")
    subprocess.run(["systemctl", "stop", SERVICE_NAME], check=False)
    time.sleep(1)


def restart_service():
    log(f"Checkpoint 8: Restarting {SERVICE_NAME}...")
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "start", SERVICE_NAME], check=False)


def main():
    lock_fd = acquire_lock()

    check_automount()

    update_dir = find_update_folder(timeout=60, interval=5)
    if not update_dir:
        release_lock(lock_fd)
        return

    deb_path = find_update_deb(update_dir)
    if not deb_path:
        release_lock(lock_fd)
        return

    pkg_name = get_pkg_name_from_deb(deb_path)
    if pkg_name != PKG_NAME:
        log(f"Skipping {deb_path}: package name mismatch ({pkg_name}).")
        release_lock(lock_fd)
        return

    new_ver = extract_version_from_deb(deb_path)
    current_ver = get_current_version()

    log(f"Checkpoint 7: Current version: {current_ver}, USB version: {new_ver}")

    if new_ver and compare_versions(new_ver, current_ver):
        log(f"Found newer {PKG_NAME} version {new_ver}, proceeding with update.")
        stop_service()
        log(f"Installing {new_ver} from {deb_path}...")
        subprocess.run(["dpkg", "-i", deb_path], check=False)
        restart_service()
        log(f"Update complete: now running {new_ver}")
    else:
        log("No newer package found or version mismatch.")

    release_lock(lock_fd)


if __name__ == "__main__":
    main()
