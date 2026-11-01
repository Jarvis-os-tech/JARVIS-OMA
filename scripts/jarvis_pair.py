#!/usr/bin/env python3
"""
scripts/jarvis_pair.py — Desktop QR code pairing utility for JARVIS Mobile companion.

Generates a secure QR code in the terminal containing device credentials,
Google Cloud mailbox endpoints (jarvis-os-508612), and encrypted sync keys.
"""

import json
import os
import secrets
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import qrcode
except ImportError:
    qrcode = None


CONFIG_DIR = Path.home() / ".config" / "jarvis"
PAIRING_FILE = CONFIG_DIR / "pairing_credentials.json"
PROJECT_ID = "jarvis-os-508612"
GCS_BUCKET = "jarvis-os-508612-memory-sync"


def get_or_create_credentials() -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if PAIRING_FILE.exists():
        try:
            with open(PAIRING_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "auth_token" in data and "device_id" in data:
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

    return creds


def get_gemini_api_key() -> str:
    # 1. Environment variable
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]

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


def main():
    creds = get_or_create_credentials()
    api_key = get_gemini_api_key()

    payload = {
        "v": creds["version"],
        "pid": creds["project_id"],
        "dev": creds["device_id"],
        "tok": creds["auth_token"],
        "bkt": creds["gcs_bucket"],
        "ep": creds["endpoint"],
    }
    if api_key:
        payload["key"] = api_key

    payload_json = json.dumps(payload, separators=(",", ":"))

    print("\n" + "=" * 60)
    print("   JARVIS OS — MOBILE COMPANION PAIRING")
    print("=" * 60)
    print(f"Device ID:     {creds['device_id']}")
    print(f"Cloud Project: {creds['project_id']}")
    print(f"Sync Bucket:   {creds['gcs_bucket']}")
    print("-" * 60)
    print("Scan this QR code from the JARVIS Mobile companion app:")
    print("-" * 60 + "\n")

    if qrcode is not None:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(payload_json)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    else:
        print("[WARNING] qrcode python package not installed.")
        print("Raw pairing payload:")
        print(payload_json)

    print("\n" + "-" * 60)
    print("Pairing payload checksum / token: " + creds["auth_token"][:12] + "...")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
