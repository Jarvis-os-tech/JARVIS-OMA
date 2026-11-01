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
import time
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
        recents_path: Path | None = None,
    ) -> None:
        self.contacts_path = Path(contacts_path) if contacts_path else self.CONTACTS_PATH
        self.history_path = Path(history_path) if history_path else self.HISTORY_PATH
        self.recents_path = Path(recents_path) if recents_path else self.RECENTS_PATH
        self._busctl = shutil.which("busctl")
        self._wpctl = shutil.which("wpctl")
        self._last_dialed: dict[str, Any] = {}
        self._tracked_calls: dict[str, dict[str, Any]] = {}
        self._announced_cache: dict[tuple[str, str], float] = {}
        self._has_gateways: bool | None = None

    def _mark_announced(self, event_type: str, number: str) -> None:
        clean = clean_phone_number(number) if number else "system"
        now = time.time()
        self._announced_cache[(event_type, clean)] = now
        for k, v in list(self._announced_cache.items()):
            if now - v > 60.0:
                self._announced_cache.pop(k, None)

    def _is_announced(self, event_type: str, number: str, window: float = 20.0) -> bool:
        clean = clean_phone_number(number) if number else "system"
        ts = self._announced_cache.get((event_type, clean))
        if ts is not None and (time.time() - ts) < window:
            return True
        return False

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
        self._last_dialed = {
            "number": cleaned,
            "name": display_name,
            "time": time.time(),
        }
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

        if target_path and target_path in self._tracked_calls:
            self._tracked_calls[target_path]["answered"] = True
            self._tracked_calls[target_path]["active_at"] = time.time()
            self._tracked_calls[target_path]["state"] = "active"

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

        if target_path and target_path in self._tracked_calls:
            self._tracked_calls[target_path]["hung_up_by_user"] = True

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

        if target_path and target_path in self._tracked_calls:
            self._tracked_calls[target_path]["declined"] = True

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

    # ── Real-time Call Lifecycle & Recents Listener ─────────────────────

    async def _watch_recents(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        stop_event: asyncio.Event,
    ) -> None:
        """Poll recents.json to guarantee call completion & hang-off announcements."""
        seen_keys: set[tuple[Any, ...]] = set()
        if self.recents_path.exists():
            try:
                data = json.loads(self.recents_path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    for e in data:
                        if isinstance(e, dict):
                            seen_keys.add((e.get("start"), e.get("number"), e.get("direction")))
            except Exception:
                pass

        last_mtime = 0.0
        try:
            if self.recents_path.exists():
                last_mtime = self.recents_path.stat().st_mtime
        except OSError:
            pass

        while not stop_event.is_set():
            try:
                await asyncio.sleep(0.5)
                if not self.recents_path.exists():
                    continue
                try:
                    cur_mtime = self.recents_path.stat().st_mtime
                except OSError:
                    continue

                if cur_mtime <= last_mtime:
                    continue
                last_mtime = cur_mtime

                try:
                    entries = json.loads(self.recents_path.read_text(encoding="utf-8"))
                except Exception:
                    continue

                if not isinstance(entries, list):
                    continue

                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    key = (entry.get("start"), entry.get("number"), entry.get("direction"))
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)

                    number = entry.get("number", "")
                    direction = entry.get("direction", "")
                    duration = int(entry.get("duration", 0))
                    name = self.resolve_number_to_name(number) or number or "Unknown"

                    if direction == "outgoing":
                        if duration == 0:
                            if not self._is_announced("outgoing_disconnected", number):
                                self._mark_announced("outgoing_disconnected", number)
                                await callback({
                                    "event": "outgoing_disconnected",
                                    "number": number,
                                    "name": name,
                                    "duration": 0,
                                    "direction": "outgoing",
                                    "reason": "unanswered_or_rejected",
                                })
                        else:
                            if not self._is_announced("call_ended", number):
                                self._mark_announced("call_ended", number)
                                await callback({
                                    "event": "call_ended",
                                    "number": number,
                                    "name": name,
                                    "duration": duration,
                                    "direction": "outgoing",
                                })
                    elif direction == "missed" or (direction == "incoming" and duration == 0):
                        if not self._is_announced("incoming_missed", number):
                            self._mark_announced("incoming_missed", number)
                            await callback({
                                "event": "incoming_missed",
                                "number": number,
                                "name": name,
                                "duration": 0,
                                "direction": "incoming",
                            })
                    elif direction == "incoming" and duration > 0:
                        if not self._is_announced("call_ended", number):
                            self._mark_announced("call_ended", number)
                            await callback({
                                "event": "call_ended",
                                "number": number,
                                "name": name,
                                "duration": duration,
                                "direction": "incoming",
                            })
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("Recents file monitor error: %s", e)

    async def _handle_call_terminated(
        self,
        info: dict[str, Any],
        path: str,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Process termination for a tracked call."""
        num = info.get("number", "")
        nm = info.get("name", "") or num or "Unknown"
        dur = int(round(time.time() - info["active_at"])) if info.get("answered") and info.get("active_at") else 0

        try:
            if info.get("incoming"):
                if not info.get("answered") and not info.get("declined"):
                    if not self._is_announced("incoming_missed", num):
                        self._mark_announced("incoming_missed", num)
                        await callback({
                            "event": "incoming_missed",
                            "call_path": path,
                            "number": num,
                            "name": nm,
                        })
                elif info.get("declined"):
                    await callback({
                        "event": "call_declined",
                        "call_path": path,
                        "number": num,
                        "name": nm,
                    })
                elif info.get("answered"):
                    if not self._is_announced("call_ended", num):
                        self._mark_announced("call_ended", num)
                        await callback({
                            "event": "call_ended",
                            "call_path": path,
                            "number": num,
                            "name": nm,
                            "duration": dur,
                            "direction": "incoming",
                        })
            else:  # Outgoing call
                if not info.get("answered"):
                    if not self._is_announced("outgoing_disconnected", num):
                        self._mark_announced("outgoing_disconnected", num)
                        await callback({
                            "event": "outgoing_disconnected",
                            "call_path": path,
                            "number": num,
                            "name": nm,
                            "reason": "unanswered_or_rejected",
                            "hung_up_by_user": info.get("hung_up_by_user", False),
                        })
                else:
                    if not self._is_announced("call_ended", num):
                        self._mark_announced("call_ended", num)
                        await callback({
                            "event": "call_ended",
                            "call_path": path,
                            "number": num,
                            "name": nm,
                            "duration": dur,
                            "direction": "outgoing",
                        })
        except Exception as cb_err:
            log.error("Error in call termination callback: %s", cb_err)

    async def listen_for_calls(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        stop_event: asyncio.Event,
    ) -> None:
        """Monitor D-Bus signals and recents for full phone call lifecycle events."""
        proc = await asyncio.create_subprocess_exec(
            "busctl", "--user", "monitor", SERVICE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        recents_task = asyncio.create_task(self._watch_recents(callback, stop_event))
        log.info("Started real-time D-Bus phone call listener and recents monitor")
        try:
            while not stop_event.is_set():
                if proc.stdout is None:
                    break
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode(errors="replace")

                # Handle Modem signals
                if "ModemAdded" in line:
                    self._has_gateways = True
                    if not self._is_announced("phone_connected", "bt"):
                        self._mark_announced("phone_connected", "bt")
                        try:
                            await callback({"event": "phone_connected"})
                        except Exception as err:
                            log.error("Error in phone_connected callback: %s", err)
                    continue
                if "ModemRemoved" in line:
                    self._has_gateways = False
                    if not self._is_announced("phone_disconnected", "bt"):
                        self._mark_announced("phone_disconnected", "bt")
                        try:
                            await callback({"event": "phone_disconnected"})
                        except Exception as err:
                            log.error("Error in phone_disconnected callback: %s", err)
                    continue

                # Handle Call signals
                if any(k in line for k in ("CallAdded", "CallRemoved", "PropertyChanged", "VoiceCallManager")):
                    await asyncio.sleep(0.15)
                    try:
                        active_calls = await self.get_calls()
                    except Exception:
                        active_calls = []

                    active_by_path = {c["path"]: c for c in active_calls}

                    # Check for newly added or updated calls
                    for path, call in active_by_path.items():
                        state = call.get("state", "unknown")
                        number = call.get("number", "")
                        name = call.get("name", "")

                        if path not in self._tracked_calls:
                            is_incoming = state in ("incoming", "waiting")
                            if not is_incoming and not number:
                                if self._last_dialed and (time.time() - self._last_dialed.get("time", 0) < 30):
                                    number = self._last_dialed.get("number", "")
                                    name = self._last_dialed.get("name", "")
                            if not name and number:
                                name = self.resolve_number_to_name(number) or number

                            self._tracked_calls[path] = {
                                "path": path,
                                "number": number,
                                "name": name or number or "Unknown",
                                "incoming": is_incoming,
                                "state": state,
                                "answered": (state == "active"),
                                "declined": False,
                                "hung_up_by_user": False,
                                "start_time": time.time(),
                                "active_at": time.time() if state == "active" else None,
                            }

                            if is_incoming:
                                if not self._is_announced("incoming_call", number):
                                    self._mark_announced("incoming_call", number)
                                    try:
                                        await callback({
                                            "event": "incoming_call",
                                            "call_path": path,
                                            "number": number,
                                            "name": name or number or "Unknown",
                                        })
                                    except Exception as cb_err:
                                        log.error("Error in incoming_call callback: %s", cb_err)
                            else:
                                try:
                                    await callback({
                                        "event": "outgoing_call",
                                        "call_path": path,
                                        "number": number,
                                        "name": name or number or "Unknown",
                                        "state": state,
                                    })
                                except Exception as cb_err:
                                    log.error("Error in outgoing_call callback: %s", cb_err)
                        else:
                            info = self._tracked_calls[path]
                            if number and not info.get("number"):
                                info["number"] = number
                                if not info.get("name") or info["name"] == "Unknown":
                                    info["name"] = self.resolve_number_to_name(number) or number
                            if state == "active" and not info.get("answered"):
                                info["answered"] = True
                                info["active_at"] = time.time()
                                info["state"] = "active"
                                if not self._is_announced("call_connected", info["number"]):
                                    self._mark_announced("call_connected", info["number"])
                                    try:
                                        await callback({
                                            "event": "call_connected",
                                            "call_path": path,
                                            "number": info["number"],
                                            "name": info["name"],
                                        })
                                    except Exception as cb_err:
                                        log.error("Error in call_connected callback: %s", cb_err)
                            elif state == "disconnected":
                                self._tracked_calls.pop(path, None)
                                await self._handle_call_terminated(info, path, callback)
                            else:
                                info["state"] = state

                    # Check for calls that were removed from active list
                    for path in list(self._tracked_calls.keys()):
                        if path not in active_by_path:
                            info = self._tracked_calls.pop(path)
                            await self._handle_call_terminated(info, path, callback)
        except asyncio.CancelledError:
            raise
        finally:
            recents_task.cancel()
            try:
                await recents_task
            except (asyncio.CancelledError, Exception):
                pass
            if proc.returncode is None:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            await proc.wait()
            log.info("Stopped phone call listener")
