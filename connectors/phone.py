"""Phone connector bridging PipeWire Telephony (HFP) and OMyPhone synced contacts.

Enables JARVIS to:
- Make outgoing phone calls by contact name or direct phone number
- Answer incoming phone calls
- Hang up / decline calls
- Mute/unmute microphone during calls
- Send DTMF keypad tones
- Search contacts synced from mobile device (OMyPhone contacts.json)
- Query call history and missed calls (OMyPhone history.json)
- Monitor real-time incoming call events via D-Bus session bus
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import unicodedata
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)

SERVICE = "org.pipewire.Telephony"
MANAGER_PATH = "/org/pipewire/Telephony"
MANAGER_IFACE = "org.ofono.Manager"
VOICE_CALL_MANAGER_IFACE = "org.ofono.VoiceCallManager"
VOICE_CALL_IFACE = "org.ofono.VoiceCall"
GATEWAY_IFACE = "org.pipewire.Telephony.AudioGateway1"
CALL_IFACE = "org.pipewire.Telephony.Call1"

NUMBER_RE = re.compile(r"\+?[0-9*#]{1,32}")
TONES_RE = re.compile(r"[0-9*#ABCD]{1,32}")
CALL_PATH_RE = re.compile(r"/org/pipewire/Telephony/ag[0-9]+/call[0-9]+")
_PAUSE_OR_EXTENSION = re.compile(r"[,;pPwWxX]")
_FORMATTING_CHARS = " \xa0-()."


def clean_phone_number(raw: str) -> str:
    """Normalize phone number removing formatting spaces, dashes, parens."""
    if not isinstance(raw, str):
        return ""
    before_pause = _PAUSE_OR_EXTENSION.split(raw.strip(), maxsplit=1)[0]
    kept: list[str] = []
    for char in before_pause:
        if char in _FORMATTING_CHARS or unicodedata.category(char) == "Cf":
            continue
        if char == "+":
            if not kept:
                kept.append(char)
            continue
        if char.isdigit() or char in "*#":
            kept.append(char)
    return "".join(kept)


class PhoneError(ValueError):
    """User-presentable phone or telephony error."""


class PhoneConnector:
    """Interface to PipeWire Telephony over D-Bus and OMyPhone contacts."""

    CONTACTS_PATH = Path.home() / ".local" / "state" / "omyphone" / "contacts.json"
    HISTORY_PATH = Path.home() / ".local" / "state" / "omyphone" / "history.json"
    RECENTS_PATH = Path.home() / ".local" / "state" / "omyphone" / "recents.json"

    def __init__(
        self,
        contacts_path: Path | None = None,
        history_path: Path | None = None,
    ) -> None:
        self.contacts_path = Path(contacts_path) if contacts_path else self.CONTACTS_PATH
        self.history_path = Path(history_path) if history_path else self.HISTORY_PATH
        self._busctl = shutil.which("busctl")
        self._wpctl = shutil.which("wpctl")

    # ── D-Bus Execution Helper ──────────────────────────────────────────

    async def _run_busctl(self, args: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
        """Execute a busctl user command asynchronously."""
        cmd = ["busctl", "--user", *args]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return proc.returncode or 0, stdout.decode().strip(), stderr.decode().strip()
        except asyncio.TimeoutError:
            proc.kill()
            return -1, "", "D-Bus operation timed out"
        except Exception as e:
            return -1, "", str(e)

    # ── Gateway and Call Discovery ──────────────────────────────────────

    async def _get_objects(self, path: str, interface: str, method: str) -> dict:
        # PipeWire's dynamic objects are returned by GetModems/GetCalls but
        # are not necessarily listed by D-Bus introspection (busctl tree).
        code, out, err = await self._run_busctl([
            "--json=short", "call", SERVICE, path, interface, method,
        ])
        if code != 0:
            raise PhoneError(f"Phone discovery failed ({method}): {err or out}")
        try:
            payload = json.loads(out)
            data = payload["data"]
            if not isinstance(data, list) or len(data) != 1:
                raise ValueError("expected one result")
            objects = data[0]
            if isinstance(objects, list):
                objects = dict(objects)  # oFono's array-of-structs representation
            if not isinstance(objects, dict):
                raise ValueError("expected object map")
            return objects
        except (ValueError, KeyError, TypeError) as error:
            raise PhoneError(f"Invalid phone discovery response ({method})") from error

    async def get_gateways(self) -> list[str]:
        """Return list of available AudioGateway paths (e.g. /org/pipewire/Telephony/ag0)."""
        objects = await self._get_objects(MANAGER_PATH, MANAGER_IFACE, "GetModems")
        return sorted(path for path in objects
                      if re.fullmatch(r"/org/pipewire/Telephony/ag[0-9]+", path))

    async def get_calls(self) -> list[dict[str, Any]]:
        """Return list of active call objects with their path, number, state."""
        calls: list[dict[str, Any]] = []
        for gateway in await self.get_gateways():
            objects = await self._get_objects(gateway, VOICE_CALL_MANAGER_IFACE, "GetCalls")
            for path, properties in objects.items():
                if not CALL_PATH_RE.fullmatch(path) or not path.startswith(gateway + "/"):
                    continue
                if not isinstance(properties, dict):
                    raise PhoneError("Invalid phone call properties")

                def string_property(name, default=""):
                    value = properties.get(name, default)
                    if isinstance(value, dict):
                        value = value.get("data", default)
                    return value if isinstance(value, str) else default

                number = string_property("LineIdentification")
                calls.append({
                    "path": path,
                    "number": number,
                    "name": self.resolve_number_to_name(number) if number else "",
                    "state": string_property("State", "unknown"),
                })
        return calls

    # ── Telephony Actions ───────────────────────────────────────────────

    async def dial(self, recipient: str) -> dict[str, Any]:
        """Dial a phone number or contact name."""
        if not recipient or not recipient.strip():
            raise PhoneError("Please specify a contact name or phone number to call.")

        raw_query = recipient.strip()
        matched_name, phone_number = self.resolve_contact(raw_query)

        cleaned = clean_phone_number(phone_number)
        if not cleaned or not NUMBER_RE.fullmatch(cleaned):
            raise PhoneError(f"Invalid phone number '{phone_number}' for recipient '{recipient}'.")

        gateways = await self.get_gateways()
        if not gateways:
            raise PhoneError("No phone is currently connected to PipeWire Telephony via Bluetooth.")

        gateway = gateways[0]
        code, out, err = await self._run_busctl([
            "call", SERVICE, gateway, GATEWAY_IFACE, "Dial", "s", cleaned
        ])
        if code != 0:
            raise PhoneError(f"Dial failed: {err or out or 'Unknown D-Bus error'}")

        display_name = matched_name if matched_name else cleaned
        return {
            "status": "dialing",
            "number": cleaned,
            "name": display_name,
            "gateway": gateway,
            "message": f"Calling {display_name} ({cleaned})...",
        }

    async def answer(self, call_path: str | None = None) -> dict[str, Any]:
        """Answer an incoming phone call."""
        target_path = call_path
        if not target_path:
            calls = await self.get_calls()
            incoming = [c for c in calls if c.get("state") in ("incoming", "waiting")]
            target_call = incoming[0] if incoming else (calls[0] if calls else None)
            if not target_call:
                raise PhoneError("No active or incoming phone calls found to answer.")
            target_path = target_call["path"]

        code, out, err = await self._run_busctl([
            "call", SERVICE, target_path, CALL_IFACE, "Answer"
        ])
        if code != 0:
            raise PhoneError(f"Failed to answer call: {err or out or 'Call may have ended'}")

        return {
            "status": "answered",
            "call_path": target_path,
            "message": "Call answered.",
        }

    async def hangup(self, call_path: str | None = None) -> dict[str, Any]:
        """Hang up or end an active phone call."""
        target_path = call_path
        if not target_path:
            calls = await self.get_calls()
            if not calls:
                raise PhoneError("No active phone calls found to hang up.")
            target_path = calls[0]["path"]

        code, out, err = await self._run_busctl([
            "call", SERVICE, target_path, CALL_IFACE, "Hangup"
        ])
        if code != 0:
            raise PhoneError(f"Failed to hang up call: {err or out or 'Call already ended'}")

        return {
            "status": "hung_up",
            "call_path": target_path,
            "message": "Call ended.",
        }

    async def decline(self, call_path: str | None = None) -> dict[str, Any]:
        """Decline or reject an incoming phone call."""
        # In PipeWire Telephony, declining an incoming call uses Hangup on that call object
        target_path = call_path
        if not target_path:
            calls = await self.get_calls()
            incoming = [c for c in calls if c.get("state") in ("incoming", "waiting")]
            target_call = incoming[0] if incoming else (calls[0] if calls else None)
            if not target_call:
                raise PhoneError("No incoming phone calls found to decline.")
            target_path = target_call["path"]

        code, out, err = await self._run_busctl([
            "call", SERVICE, target_path, CALL_IFACE, "Hangup"
        ])
        if code != 0:
            raise PhoneError(f"Failed to decline call: {err or out or 'Call already ended'}")

        return {
            "status": "declined",
            "call_path": target_path,
            "message": "Call declined.",
        }

    async def send_tones(self, digits: str) -> dict[str, Any]:
        """Send DTMF keypad tones during a call."""
        clean_digits = "".join(c for c in digits.upper() if c in "0123456789*#ABCD")
        if not clean_digits or not TONES_RE.fullmatch(clean_digits):
            raise PhoneError(f"Invalid DTMF tones '{digits}'. Must be digits 0-9, *, #, or A-D.")

        gateways = await self.get_gateways()
        if not gateways:
            raise PhoneError("No phone gateway connected.")

        gateway = gateways[0]
        code, out, err = await self._run_busctl([
            "call", SERVICE, gateway, GATEWAY_IFACE, "SendTones", "s", clean_digits
        ])
        if code != 0:
            raise PhoneError(f"Failed to send tones: {err or out or 'Unknown error'}")

        return {
            "status": "sent",
            "digits": clean_digits,
            "message": f"Sent DTMF tone(s): {clean_digits}",
        }

    async def set_mute(self, action: str) -> dict[str, Any]:
        """Mute or unmute call microphone via wpctl."""
        act = (action or "toggle").lower().strip()
        source = "@DEFAULT_AUDIO_SOURCE@"

        if act == "status":
            proc = await asyncio.create_subprocess_exec(
                "wpctl", "get-volume", source,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, _ = await proc.communicate()
            is_muted = "[MUTED]" in out.decode()
            return {"status": "muted" if is_muted else "unmuted", "muted": is_muted}

        mute_arg = "toggle"
        if act in ("mute", "on", "true", "1"):
            mute_arg = "1"
        elif act in ("unmute", "off", "false", "0"):
            mute_arg = "0"

        proc = await asyncio.create_subprocess_exec(
            "wpctl", "set-mute", source, mute_arg,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        # Check final status
        check_proc = await asyncio.create_subprocess_exec(
            "wpctl", "get-volume", source,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        check_out, _ = await check_proc.communicate()
        is_muted = "[MUTED]" in check_out.decode()
        return {
            "status": "muted" if is_muted else "unmuted",
            "muted": is_muted,
            "message": f"Microphone {'muted' if is_muted else 'unmuted'}.",
        }

    # ── Contacts & History (OMyPhone Data) ──────────────────────────────

    def load_contacts(self) -> list[dict[str, Any]]:
        """Load contacts from ~/.local/state/omyphone/contacts.json."""
        if not self.contacts_path.exists():
            return []
        try:
            data = json.loads(self.contacts_path.read_text(encoding="utf-8"))
            return data.get("contacts", []) if isinstance(data, dict) else []
        except Exception as e:
            log.warning("Could not read contacts from %s: %s", self.contacts_path, e)
            return []

    def resolve_contact(self, query: str) -> tuple[str, str]:
        """Resolve a query string to (matched_name, phone_number)."""
        clean_q = query.strip()
        # If query is already a phone number, return it directly
        cleaned_num = clean_phone_number(clean_q)
        if len(cleaned_num) >= 3 and cleaned_num.replace("+", "").isdigit() and not any(c.isalpha() for c in clean_q):
            name = self.resolve_number_to_name(cleaned_num)
            return name, cleaned_num

        contacts = self.load_contacts()
        q_norm = clean_q.casefold()

        # 1. Exact match on contact name
        for c in contacts:
            c_name = c.get("name", "").strip()
            if c_name.casefold() == q_norm:
                numbers = c.get("numbers", [])
                if numbers:
                    return c_name, numbers[0].get("number", "")

        # 2. Word boundary / startswith match
        for c in contacts:
            c_name = c.get("name", "").strip()
            c_norm = c_name.casefold()
            if c_norm.startswith(q_norm) or f" {q_norm}" in f" {c_norm}":
                numbers = c.get("numbers", [])
                if numbers:
                    return c_name, numbers[0].get("number", "")

        # 3. Substring match
        for c in contacts:
            c_name = c.get("name", "").strip()
            if q_norm in c_name.casefold():
                numbers = c.get("numbers", [])
                if numbers:
                    return c_name, numbers[0].get("number", "")

        # Fallback: Treat query as a phone number
        return "", clean_q

    def resolve_number_to_name(self, number: str) -> str:
        """Find contact name by matching normalized phone number."""
        if not number:
            return ""
        clean_target = clean_phone_number(number)
        if not clean_target:
            return ""

        contacts = self.load_contacts()
        for c in contacts:
            for num_entry in c.get("numbers", []):
                cand = clean_phone_number(num_entry.get("number", ""))
                if cand and (cand == clean_target or cand.endswith(clean_target) or clean_target.endswith(cand)):
                    name = c.get("name", "").strip()
                    if name:
                        return name
        return ""

    def list_contacts(self, query: str = "", limit: int = 10) -> list[dict[str, Any]]:
        """Search contacts by query string."""
        contacts = self.load_contacts()
        if not query or not query.strip():
            return contacts[:limit]

        q = query.casefold().strip()
        matched = []
        for c in contacts:
            name = c.get("name", "")
            numbers = [n.get("number", "") for n in c.get("numbers", [])]
            if q in name.casefold() or any(q in num for num in numbers):
                matched.append(c)
                if len(matched) >= limit:
                    break
        return matched

    def get_recent_calls(self, filter_type: str = "all", limit: int = 10) -> list[dict[str, Any]]:
        """Get call history from ~/.local/state/omyphone/history.json."""
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
            calls = data.get("calls", []) if isinstance(data, dict) else []
            f = filter_type.lower().strip()
            if f in ("missed", "incoming", "outgoing"):
                calls = [c for c in calls if c.get("direction") == f]
            return calls[:limit]
        except Exception as e:
            log.warning("Could not read call history from %s: %s", self.history_path, e)
            return []

    async def get_status(self) -> dict[str, Any]:
        """Return connected gateways, active calls, and contacts availability."""
        gateways = await self.get_gateways()
        calls = await self.get_calls()
        contacts_count = len(self.load_contacts())
        return {
            "connected": len(gateways) > 0,
            "gateways": gateways,
            "active_calls": calls,
            "contacts_count": contacts_count,
            "has_calls": len(calls) > 0,
        }

    # ── Real-time Incoming Call Signal Listener ─────────────────────────

    async def listen_for_calls(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        stop_event: asyncio.Event,
    ) -> None:
        """Monitor D-Bus signals for incoming calls and invoke callback."""
        proc = await asyncio.create_subprocess_exec(
            "busctl", "--user", "monitor", SERVICE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        log.info("Started real-time D-Bus phone call listener")
        try:
            while not stop_event.is_set():
                if proc.stdout is None:
                    break
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace")
                # Look for CallAdded or PropertyChanged signals
                if "CallAdded" in line or "org.ofono.VoiceCallManager" in line:
                    await asyncio.sleep(0.3)  # brief settle to read call properties
                    calls = await self.get_calls()
                    incoming = [c for c in calls if c.get("state") in ("incoming", "waiting")]
                    for inc in incoming:
                        try:
                            await callback({
                                "event": "incoming_call",
                                "call_path": inc["path"],
                                "number": inc["number"],
                                "name": inc["name"] or inc["number"],
                            })
                        except Exception as cb_err:
                            log.error("Error in phone call listener callback: %s", cb_err)
        except asyncio.CancelledError:
            raise
        finally:
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.wait()
            log.info("Stopped phone call listener")
