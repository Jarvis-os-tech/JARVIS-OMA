#!/usr/bin/env python3
"""
scripts/jarvis_pair.py — Desktop QR code pairing utility for JARVIS Mobile companion.

Generates a secure QR code in the terminal containing device credentials,
Google Cloud mailbox endpoints (jarvis-os-508612), and encrypted sync keys.
"""

import argparse
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import qrcode
except ImportError:
    qrcode = None


CONFIG_DIR = Path.home() / ".config" / "jarvis"
PAIRING_FILE = CONFIG_DIR / "pairing_credentials.json"
PROJECT_ID = "jarvis-os-508612"
GCS_BUCKET = "jarvis-os-508612-memory-sync"


def get_or_create_credentials() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    if PAIRING_FILE.exists():
        try:
            with open(PAIRING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "auth_token" in data and "device_id" in data:
                    PAIRING_FILE.chmod(0o600)
                    return data
        except Exception:
            pass

    # Generate new pairing credential
    device_id = f"{socket.gethostname()}-{secrets.token_hex(4)}"
    auth_token = secrets.token_hex(32)
    sync_secret = secrets.token_hex(32)

    creds = {
        "version": 1,
        "project_id": PROJECT_ID,
        "gcs_bucket": GCS_BUCKET,
        "device_id": device_id,
        "auth_token": auth_token,
        "sync_secret": sync_secret,
        "endpoint": f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents/sync_mailboxes/{device_id}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    with open(PAIRING_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)
    PAIRING_FILE.chmod(0o600)

    return creds


def get_gemini_api_key() -> str:
    # Use the same credential loading as the PC voice client.
    from jarvis_voice.config import load_env
    load_env()
    # 1. Environment variable
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if os.environ.get("GOOGLE_API_KEY"):
        return os.environ["GOOGLE_API_KEY"]

    # 2. Config file check
    config_paths = [
        Path.home() / ".config" / "jarvis" / "config.toml",
        Path("config.toml"),
        Path("configs/config.toml"),
    ]
    for cp in config_paths:
        if cp.exists():
            try:
                import tomllib
                with open(cp, "rb") as f:
                    cfg = tomllib.load(f)
                    key = cfg.get("gemini", {}).get("api_key") or cfg.get("api_key")
                    if key:
                        return key
            except Exception:
                pass
    return ""


def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 1))
        return s.getsockname()[0]
    except Exception:
        return '127.0.0.1'
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(description="Generate pairing QR code and payload for JARVIS Mobile companion")
    parser.add_argument("-o", "--output", default="pairing_qr.png", help="Path to save PNG QR code (default: pairing_qr.png)")
    parser.add_argument("--view", action="store_true", help="Open QR code in default image viewer")
    parser.add_argument("--pairing-session", default="", help="Private window confirmation session")
    parser.add_argument("--transient", action="store_true", help="Do not save a second QR image")
    parser.add_argument("--show-payload", action="store_true", help="Explicitly print the secret pairing payload for manual transfer")
    parser.add_argument("--no-ascii", action="store_true", help="Suppress terminal ASCII QR code")
    args = parser.parse_args()

    creds = get_or_create_credentials()
    api_key = get_gemini_api_key()
    if not api_key:
        print("Configure the PC Gemini key before sharing it with your phone.")
        return 1
    local_ip = get_local_ip()
    default_exec = f"http://{local_ip}:8766" if local_ip != "127.0.0.1" else "http://127.0.0.1:8766"

    payload = {
        "v": creds["version"],
        "pid": creds["project_id"],
        "dev": creds["device_id"],
        "tok": creds["auth_token"],
        "bkt": creds["gcs_bucket"],
        "ep": creds["endpoint"],
        "exec": creds.get("execution_endpoint", default_exec),
    }
    if api_key:
        payload["key"] = api_key
    if args.pairing_session:
        from scripts.pairing_window_state import path_for
        path_for(args.pairing_session)
        payload["pair_session"] = args.pairing_session

    payload_json = json.dumps(payload, separators=(",", ":"))

    print("\n" + "=" * 60)
    print("   JARVIS OS — MOBILE COMPANION PAIRING")
    print("=" * 60)
    print(f"Device ID:          {creds['device_id']}")
    print(f"Cloud Project:      {creds['project_id']}")
    print(f"Sync Bucket:        {creds['gcs_bucket']}")
    print(f"Execution Endpoint: {payload['exec']}")
    print("-" * 60)

    png_path = Path(args.output).resolve()
    config_png = CONFIG_DIR / "pairing_qr.png"

    if qrcode is not None:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(payload_json)
        qr.make(fit=True)

        # Generate and save PNG image
        try:
            img = qr.make_image(fill_color="black", back_color="white")
            png_path.parent.mkdir(parents=True, exist_ok=True)
            png_path.touch(mode=0o600, exist_ok=True)
            png_path.chmod(0o600)
            img.save(str(png_path))
            print(f"Saved high-res QR code image to: {png_path}")
            if png_path != config_png and not args.transient:
                try:
                    config_png.touch(mode=0o600, exist_ok=True)
                    config_png.chmod(0o600)
                    img.save(str(config_png))
                except Exception:
                    pass
        except Exception as e:
            print(f"[WARNING] Could not save PNG image: {e}")

        if not args.no_ascii:
            print("-" * 60)
            print("Scan this QR code from the JARVIS Mobile companion app:")
            print("-" * 60 + "\n")
            # For terminal printing, use smaller box size
            term_qr = qrcode.QRCode(
                version=None,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=1,
                border=2,
            )
            term_qr.add_data(payload_json)
            term_qr.make(fit=True)
            term_qr.print_ascii(invert=True)
    else:
        print("[WARNING] qrcode python package not installed.")
        print("Install the qrcode package to generate a private pairing image.")

    if args.show_payload:
        print("Private pairing payload — do not share publicly:")
        print(payload_json)
    print("Scan only with your own phone. This QR grants access to your PC and Gemini account.")

    if args.view and png_path.exists():
        # Try viewers: imv, xdg-open
        for viewer in ["imv", "xdg-open"]:
            try:
                subprocess.Popen([viewer, str(png_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Opened QR code using {viewer}")
                break
            except Exception:
                continue


if __name__ == "__main__":
    sys.exit(main() or 0)
