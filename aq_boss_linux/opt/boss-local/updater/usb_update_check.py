#!/usr/bin/env python3
import os
import subprocess
import re
import time

PKG_NAME = "aq-boss-linux"
UPDATE_DIR_NAME = "aq_boss_update"


def get_current_version():
    try:
        output = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", PKG_NAME]
        )
        return output.decode().strip()
    except subprocess.CalledProcessError:
        return "0.0.0"


def find_usb_updates():
    for mount_base in ["/media", "/mnt"]:
        for root, dirs, files in os.walk(mount_base):
            if UPDATE_DIR_NAME in dirs:
                path = os.path.join(root, UPDATE_DIR_NAME)
                for f in os.listdir(path):
                    if f.endswith(".deb"):
                        return os.path.join(path, f)
    return None


def extract_version_from_deb(deb_path):
    try:
        output = subprocess.check_output(["dpkg-deb", "-f", deb_path, "Version"])
        return output.decode().strip()
    except:
        return None


def main():
    time.sleep(2)  # wait for mount
    deb_path = find_usb_updates()
    if not deb_path:
        print("No USB update package found.")
        return

    new_ver = extract_version_from_deb(deb_path)
    current_ver = get_current_version()
    print(f"Current version: {current_ver}, Found: {new_ver}")

    def ver_tuple(v):
        return tuple(map(int, re.findall(r"\d+", v)))

    if new_ver and ver_tuple(new_ver) > ver_tuple(current_ver):
        print(f"Updating to version {new_ver}...")
        subprocess.run(["dpkg", "-i", deb_path], check=False)
    else:
        print("No update required.")


if __name__ == "__main__":
    main()
