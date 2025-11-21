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
BASE_PATH = "/opt/aq-boss-linux/binaries"
DEFAULT_VERSION = "default"
DEFAULT_DIR = os.path.join(BASE_PATH, DEFAULT_VERSION)
DEFAULT_BIN = os.path.join(DEFAULT_DIR, "azq_boss_pc")
DEFAULT_CONF = os.path.join(DEFAULT_DIR, "default.conf")
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


def wait_for_internet(max_wait=60, interval=10):
    """Wait until we can reach the internet, but cap total wait."""
    print("Checking internet connectivity...")
    waited = 0
    while waited < max_wait:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", PING_TARGET],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                print("Internet is available.")
                return True
        except Exception:
            pass
        waited += interval
        print(
            f"No internet yet. Retrying in {interval} seconds... (waited {waited}/{max_wait}s)"
        )
        time.sleep(interval)
    print("No internet after waiting.")
    return False


def cleanup_old_versions():
    try:
        versions = sorted(os.listdir(BASE_PATH))
        versions = [v for v in versions if v != DEFAULT_VERSION]
        if len(versions) > 2:
            old = versions[:-2]
            for v in old:
                full_path = os.path.join(BASE_PATH, v)
                if os.path.isdir(full_path):
                    print(f"Removing old version: {v}")
                    rmtree(full_path, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Cleanup failed — {e}")


def parse_conf(text):
    conf_vars = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            conf_vars[key.strip()] = value.strip()
    return conf_vars


def run_binary(bin_path, conf_vars, source_label):
    bridge_mode = conf_vars.get("BRIDGE_MODE", "n").lower()
    dest_ip = conf_vars.get("DEST_IP", "")

    cmd = [bin_path]
    if bridge_mode == "y":
        if dest_ip:
            cmd.extend(["--bridge", dest_ip])
        else:
            print(
                f"Warning: BRIDGE_MODE is enabled but DEST_IP missing in {source_label} config — running without bridge."
            )

    os.chmod(bin_path, 0o755)
    print(f"Running {source_label} binary: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=os.path.dirname(bin_path))
        if result.returncode != 0:
            print(f"Warning: {source_label} binary exited with {result.returncode}")
            return False
        return True
    except Exception as e:
        print(f"Warning: Error running {source_label} binary — {e}")
        return False


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
        return False

    conf_vars = parse_conf(r.text)

    aq_boss_ver = conf_vars.get("AQ_BOSS_VER")
    arch = conf_vars.get("ARCH")
    bridge_mode = conf_vars.get("BRIDGE_MODE", "n").lower()
    dest_ip = conf_vars.get("DEST_IP", "")

    if not aq_boss_ver:
        print("Error: AQ_BOSS_VER missing in config")
        return False
    if not arch:
        print("Error: ARCH missing in config")
        return False

    version_dir = os.path.join(BASE_PATH, aq_boss_ver)
    os.makedirs(version_dir, exist_ok=True)

    conf_path = os.path.join(version_dir, conf_filename)
    with open(conf_path, "w") as f:
        f.write(r.text)

    fw_url = f"{FW_BASE_URL}/azq_boss_pc_linux_{arch}-{aq_boss_ver}"
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
        return False

    return run_binary(bin_path, conf_vars, source_label=f"remote:{aq_boss_ver}")


def run_local_version():
    hostname = socket.gethostname()
    conf_filename = f"{hostname}.conf"
    try:
        versions = sorted(
            [
                v
                for v in os.listdir(BASE_PATH)
                if v != DEFAULT_VERSION and os.path.isdir(os.path.join(BASE_PATH, v))
            ]
        )
    except Exception as e:
        print(f"Warning: Failed to list local versions — {e}")
        return False

    for ver in reversed(versions):
        version_dir = os.path.join(BASE_PATH, ver)
        conf_path = os.path.join(version_dir, conf_filename)
        if not os.path.isfile(conf_path):
            continue

        bin_path = os.path.join(version_dir, "azq_boss_pc")
        if not os.path.isfile(bin_path):
            print(
                f"Error: Conf found for {ver} at {conf_path} but binary missing at {bin_path}. Not running default — fix this."
            )
            return "missing_binary"

        try:
            with open(conf_path) as f:
                conf_vars = parse_conf(f.read())
        except Exception as e:
            print(f"Warning: Failed to read local config {conf_path} — {e}")
            continue

        print(f"Using previously downloaded version: {ver}")
        return run_binary(bin_path, conf_vars, source_label=f"local:{ver}")

    return False


def run_default_binary():
    conf_vars = {"BRIDGE_MODE": "n"}
    if os.path.isfile(DEFAULT_CONF):
        try:
            with open(DEFAULT_CONF) as f:
                conf_vars.update(parse_conf(f.read()))
        except Exception as e:
            print(f"Warning: Failed to read default config {DEFAULT_CONF} — {e}")

    if not os.path.isfile(DEFAULT_BIN):
        print(f"Error: Default binary missing at {DEFAULT_BIN}")
        return False

    print("Using bundled default binary (offline fallback).")
    return run_binary(DEFAULT_BIN, conf_vars, source_label="default")


def main():
    if os.geteuid() != 0:
        print("Please run as root (required for /opt access and installs)")
        sys.exit(1)

    ensure_dependencies()
    os.makedirs(BASE_PATH, exist_ok=True)
    os.makedirs(DEFAULT_DIR, exist_ok=True)

    internet_available = wait_for_internet(max_wait=60, interval=10)

    ran = False
    if internet_available:
        ran = fetch_and_run()
        if not ran:
            print("Warning: Online fetch failed, trying previously downloaded version.")
            ran = run_local_version()
            if ran == "missing_binary":
                return
    else:
        ran = run_local_version()
        if ran == "missing_binary":
            # Bug condition: Conf present without its binary; abort.
            return
        if not ran:
            ran = run_default_binary()

    if not ran:
        print("Error: Could not run AQ Boss binary (remote, local, or default).")

    cleanup_old_versions()


if __name__ == "__main__":
    main()
