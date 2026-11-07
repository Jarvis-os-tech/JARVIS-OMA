import sys
import shutil
import subprocess

def uninstall_package(package_name: str) -> str:
    """Uninstall a package using the system's available package manager."""

    # pacman
    if shutil.which("pacman"):
        cmd = ["sudo", "pacman", "-Rns", "--noconfirm", package_name]
    # yay
    elif shutil.which("yay"):
        cmd = ["yay", "-Rns", "--noconfirm", package_name]
    # flatpak
    elif shutil.which("flatpak"):
        cmd = ["flatpak", "uninstall", "-y", package_name]
    else:
        return "ERROR: No supported package manager found."

    try:
        # Run command and capture output
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR: {e.stderr.strip()}"
