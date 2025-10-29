#!/usr/bin/env python3
import os
import subprocess
import re
import time

PKG_NAME = "aq-boss-linux"


def get_current_version():
    try:
        output = subprocess.check_output(
            ["dpkg-query", "-W", "-f=${Version}", PKG_NAME]
        )
        return output.decode().strip()
    except subprocess.CalledProcessError:
        return "0.0.0"


def find_usb_updates():
    """Recursively search all mounted USB paths for matching package .deb files."""
    candidates = []
    for mount_base in ["/media", "/mnt"]:
        for root, _, files in os.walk(mount_base):
            for f in files:
                if f.endswith(".deb") and PKG_NAME in f:
                    full_path = os.path.join(root, f)
                    candidates.append(full_path)
    return candidates


def get_pkg_name_from_deb(deb_path):
    """Extract the package name inside the .deb to confirm it's correct."""
    try:
        output = subprocess.check_output(["dpkg-deb", "-f", deb_path, "Package"])
        return output.decode().strip()
    except subprocess.CalledProcessError:
        return None


def extract_version_from_deb(deb_path):
    try:
        output = subprocess.check_output(["dpkg-deb", "-f", deb_path, "Version"])
        return output.decode().strip()
    except subprocess.CalledProcessError:
        return None


def compare_versions(v1, v2):
    """Compare version numbers numerically."""

    def vt(v):
        return tuple(map(int, re.findall(r"\d+", v))) if v else (0,)

    return vt(v1) > vt(v2)


def main():
    time.sleep(2)  # give USB a bit of time to mount
    deb_candidates = find_usb_updates()

    if not deb_candidates:
        print("No matching .deb files found on connected USB drives.")
        return

    current_ver = get_current_version()
    newest_path = None
    newest_ver = current_ver

    for deb_path in deb_candidates:
        pkg_name = get_pkg_name_from_deb(deb_path)
        if pkg_name != PKG_NAME:
            continue  # skip unrelated packages

        new_ver = extract_version_from_deb(deb_path)
        if new_ver and compare_versions(new_ver, newest_ver):
            newest_ver = new_ver
            newest_path = deb_path

    if newest_path and compare_versions(newest_ver, current_ver):
        print(f"Found newer {PKG_NAME} version {newest_ver} at {newest_path}")
        subprocess.run(["dpkg", "-i", newest_path], check=False)
    else:
        print("No newer package found.")


if __name__ == "__main__":
    main()
