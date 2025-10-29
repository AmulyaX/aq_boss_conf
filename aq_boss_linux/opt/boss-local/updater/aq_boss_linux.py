#!/usr/bin/env python3
import os
import socket
import subprocess
import requests
import sys
import time
from shutil import which, rmtree

CONF_BASE_URL = (
    "https://raw.githubusercontent.com/AmulyaX/aq_boss_conf/refs/heads/main/conf"
)
FW_BASE_URL = "https://fw.azenqos.com/boss-local"
BASE_PATH = "/opt/boss-local/binaries"
REQUIRED_PACKAGES = ["adb", "net-tools"]
PING_TARGET = "8.8.8.8"


def ensure_dependencies():
    missing = [pkg for pkg in REQUIRED_PACKAGES if which(pkg) is None]
    if missing:
        print(f"Installing missing dependencies: {', '.join(missing)}")
        try:
            subprocess.run(
                ["apt-get", "update", "-y"], check=True, stdout=subprocess.DEVNULL
            )
            subprocess.run(["apt-get", "install", "-y"] + missing, check=True)
        except Exception as e:
            print(f"Error installing dependencies: {e}")


def wait_for_internet():
    """Wait until we can reach the internet."""
    print("Checking internet connectivity...")
    while True:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", PING_TARGET],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                print("Internet is available.")
                break
        except Exception:
            pass
        print("No internet yet. Retrying in 10 seconds...")
        time.sleep(10)


def cleanup_old_versions():
    try:
        versions = sorted(os.listdir(BASE_PATH))
        if len(versions) > 2:
            old = versions[:-2]
            for v in old:
                full_path = os.path.join(BASE_PATH, v)
                if os.path.isdir(full_path):
                    print(f"Removing old version: {v}")
                    rmtree(full_path, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Cleanup failed — {e}")


def fetch_and_run():
    hostname = socket.gethostname()
    conf_filename = f"{hostname}.conf"
    conf_url = f"{CONF_BASE_URL}/{conf_filename}"

    print(f"Fetching configuration for {hostname}...")

    try:
        r = requests.get(conf_url, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Warning: Could not fetch configuration — {e}")
        return

    conf_vars = {}
    for line in r.text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            conf_vars[key.strip()] = value.strip()

    aq_boss_ver = conf_vars.get("AQ_BOSS_VER")
    bridge_mode = conf_vars.get("BRIDGE_MODE", "n").lower()
    dest_ip = conf_vars.get("DEST_IP", "")

    if not aq_boss_ver:
        print("Error: AQ_BOSS_VER missing in config")
        return

    version_dir = os.path.join(BASE_PATH, aq_boss_ver)
    os.makedirs(version_dir, exist_ok=True)

    conf_path = os.path.join(version_dir, conf_filename)
    with open(conf_path, "w") as f:
        f.write(r.text)

    fw_url = f"{FW_BASE_URL}/azq_boss_pc-{aq_boss_ver}"
    bin_path = os.path.join(version_dir, "azq_boss_pc")

    print(f"Downloading binary version {aq_boss_ver} from {fw_url}...")
    try:
        r = requests.get(fw_url, timeout=30)
        r.raise_for_status()
        with open(bin_path, "wb") as f:
            f.write(r.content)
        os.chmod(bin_path, 0o755)
    except requests.RequestException as e:
        print(f"Warning: Failed to download binary — {e}")
        return

    cmd = [bin_path]
    if bridge_mode == "y":
        if not dest_ip:
            print("Error: BRIDGE_MODE is enabled but DEST_IP missing")
            return
        cmd.extend(["--bridge", dest_ip])

    print(f"Running: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=version_dir)
    except Exception as e:
        print(f"Warning: Error running binary — {e}")


def main():
    if os.geteuid() != 0:
        print("Please run as root (required for /opt access and installs)")
        sys.exit(1)

    ensure_dependencies()
    wait_for_internet()
    fetch_and_run()
    cleanup_old_versions()


if __name__ == "__main__":
    main()
