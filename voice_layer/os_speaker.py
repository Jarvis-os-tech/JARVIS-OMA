"""JARVIS OS System Speaker Daemon (jarvis-os-speaker).

Asynchronous collectors for D-Bus notifications, hardware/power events,
systemd service health, and shell command events. Feeds an anti-spam
Humanizer Arbiter and routes speech through the JARVIS Speech Bus.
"""

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
log = logging.getLogger('jarvis.os_speaker')

SPEAK_SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis-voice-speak.sock"
CONTROL_SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")) / "jarvis" / "control.sock"
COOLDOWN_SECONDS = 300.0  # 5 minutes anti-spam cooldown per dedup_key

# Load Groq API Key if available
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    env_file = Path("/home/g0pi/JARVIS OS/.env")
    if env_file.is_file():
        try:
            for line in env_file.read_text().splitlines():
                if line.startswith("GROQ_API_KEY_1="):
                    GROQ_API_KEY = line.split("=", 1)[1].strip().strip('"\'')
                    break
        except Exception:
            pass


class SpeechClient:
    """Delivers speech announcements to JARVIS Voice socket without local fallback TTS."""

    async def speak(self, text: str, priority: str = "normal", source: str = "os", dedup_key: str = "", silent: bool = False) -> bool:
        if not text or not text.strip():
            return False

        payload = json.dumps({
            "command": "speak",
            "text": text.strip(),
            "priority": priority,
            "source": source,
            "dedup_key": dedup_key,
            "silent": silent,
            "speak": not silent
        }) + "\n"

        # Try dedicated speak socket or control socket
        for sock_path in (SPEAK_SOCKET, CONTROL_SOCKET):
            if sock_path.exists():
                try:
                    reader, writer = await asyncio.wait_for(
                        asyncio.open_unix_connection(str(sock_path)), timeout=0.5
                    )
                    writer.write(payload.encode())
                    await writer.drain()
                    resp_line = await asyncio.wait_for(reader.readline(), timeout=0.8)
                    writer.close()
                    await writer.wait_closed()
                    log.info("Dispatched alert via %s (silent=%s, priority=%s): '%s'", sock_path.name, silent, priority, text)
                    return True
                except Exception as err:
                    log.debug("Socket %s communication failed: %s", sock_path, err)

        return False


class EventClassifier:
    """Classifies system events and notifications into must-tell criticals vs silent context."""

    # Trivial / routine noise patterns that must NEVER be spoken aloud
    NOISE_PATTERNS = [
        r'\b(?:screenshot|omasnap|copied to clipboard|saved to)\b',
        r'\b(?:layout set|theme changed|workspace \d|switched to workspace)\b',
        r'\b(?:agent finished|task finished|git repository|build finished successfully)\b',
        r'\b(?:issue resolved|auto-healed|healed|restored|normal)\b',
        r'\b(?:usb device connected|usb device disconnected|power cable connected)\b',
        r'\b(?:volume|brightness|song|track|playback|spotify)\b',
    ]

    # Critical triggers that JARVIS MUST tell the user
    CRITICAL_PATTERNS = [
        # Failures & Crashes
        (r'\b(?:crash(?:ed|es)?|segfault|segmentation fault|core dump(?:ed)?|kernel panic)\b', 'crash'),
        (r'\b(?:failed with result|failed at step|service.*failed|failed to start|emergency|fatal error|unhandled exception)\b', 'failure'),
        (r'\b(?:killed by oom|out of memory|oom-killer)\b', 'oom'),
        # High resource usage
        (r'(?:ram|memory)\s*(?:usage\s*)?(?:is\s*)?(?:at\s*)?(?:9[0-9]|100)(?:\.[0-9]+)?\s*%', 'high_ram'),
        (r'cpu\s*(?:usage\s*)?(?:is\s*)?(?:at\s*)?(?:9[5-9]|100)(?:\.[0-9]+)?\s*%', 'high_cpu'),
        (r'\b(?:disk full|storage full|filesystem is full|no space left on device)\b', 'disk_full'),
        (r'\b(?:thermal throttling|critical temperature|cpu overheating)\b', 'thermal'),
        # Low Battery
        (r'\b(?:critical battery|battery is low|battery.*(?:down to|remaining|at)\s*(?:[1-9]|1[0-9]|20)\s*(?:%|percent)|time to recharge)\b', 'low_battery'),
    ]

    @classmethod
    def should_tell(cls, text: str, source: str = "os", urgency: int = 1) -> tuple[bool, str]:
        lowered = text.casefold()

        # 1. Noise / routine / auto-resolved events are strictly silent
        for pattern in cls.NOISE_PATTERNS:
            if re.search(pattern, lowered):
                return False, "routine_noise"

        # 2. Match against critical patterns (failures, crashes, high usage, low battery)
        for pattern, category in cls.CRITICAL_PATTERNS:
            if re.search(pattern, lowered):
                return True, category

        # 3. Explicit D-Bus critical urgency notifications containing warning or error keywords
        if urgency == 2 and re.search(r'\b(?:error|fail|warning|alert|critical|halt|stopped)\b', lowered):
            return True, "critical_urgency"

        return False, "non_critical"


class SpeechArbiter:
    """Filters, humanizes, deduplicates, and dispatches OS events."""

    def __init__(self, client: SpeechClient):
        self.client = client
        self.cooldowns: dict[str, float] = {}

    def is_rate_limited(self, dedup_key: str) -> bool:
        if not dedup_key:
            return False
        now = time.monotonic()
        last_time = self.cooldowns.get(dedup_key, 0.0)
        if now - last_time < COOLDOWN_SECONDS:
            log.debug("Rate-limited dedup_key: %s (%.1fs remaining)", dedup_key, COOLDOWN_SECONDS - (now - last_time))
            return True
        self.cooldowns[dedup_key] = now
        return False

    async def clean_and_humanize(self, raw_text: str, source: str) -> str:
        text = raw_text.strip()
        # 1. Strip raw paths (/home/..., /usr/..., /var/...)
        text = re.sub(r'/(?:[a-zA-Z0-9_.-]+/)+[a-zA-Z0-9_.-]+', lambda m: Path(m.group(0)).name, text)
        # 2. Strip hex memory addresses (0x7fff...)
        text = re.sub(r'0x[0-9a-fA-F]+', '', text)
        # 3. Strip traceback markers
        text = re.sub(r'Traceback \(most recent call last\):?', '', text, flags=re.IGNORECASE)
        # 4. Collapse spaces
        text = re.sub(r'\s+', ' ', text).strip()

        # If already clean and concise, return
        if len(text.split()) <= 14 and not any(k in text for k in ('Error', 'Exception', 'Failed', 'Traceback')):
            return text

        # Online LLM fast rewrite for complex/technical notifications
        if GROQ_API_KEY and len(text.split()) > 7:
            try:
                import httpx
                headers = {'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'}
                body = {
                    'model': 'qwen/qwen3.8-27b',
                    'messages': [
                        {'role': 'system', 'content': 'You are the JARVIS voice alert engine. Rephrase this into one short, clear spoken English sentence (max 12 words, no code, no paths):'},
                        {'role': 'user', 'content': text}
                    ],
                    'max_tokens': 30,
                    'temperature': 0.2
                }
                async with httpx.AsyncClient(timeout=1.0) as http_client:
                    res = await http_client.post('https://api.groq.com/openai/v1/chat/completions', json=body, headers=headers)
                    if res.status_code == 200:
                        ans = res.json()['choices'][0]['message']['content'].strip()
                        if ans and len(ans) < 160:
                            return ans
            except Exception as err:
                log.debug("Groq humanizer skipped: %s", err)

        # Truncate cleanly if offline
        words = text.split()
        return " ".join(words[:16]) + ("." if not text.endswith(".") else "")

    async def handle_event(self, text: str, priority: str = "normal", source: str = "os", dedup_key: str = "", urgency: int = 1, silent: Optional[bool] = None):
        if self.is_rate_limited(dedup_key):
            return

        should_tell, category = EventClassifier.should_tell(text, source=source, urgency=urgency)
        # If caller explicitly set silent, respect it; otherwise decide via classifier
        if silent is None:
            silent = not should_tell
        elif not silent and not should_tell:
            silent = True

        event_priority = "critical" if should_tell else priority

        human_text = await self.clean_and_humanize(text, source)
        if human_text:
            log.info("Event classified [category=%s, tell=%s, silent=%s]: '%s'", category, should_tell, silent, human_text)
            await self.client.speak(human_text, priority=event_priority, source=source, dedup_key=dedup_key, silent=silent)


# ============================================================================
# WATCHER 1: D-Bus Desktop Notifications (org.freedesktop.Notifications)
# ============================================================================
async def watch_dbus_notifications(arbiter: SpeechArbiter):
    """Monitors session desktop notifications via dbus-monitor."""
    log.info("Starting D-Bus Notifications watcher...")
    IGNORED_APPS = {
        'xfce4-power-manager', 'volume', 'brightness', 'pavucontrol',
        'playerctl', 'spotify', 'cava', 'hyprland'
    }

    while True:
        try:
            cmd = ['dbus-monitor', '--session', "interface='org.freedesktop.Notifications',member='Notify'"]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )

            current_app = ""
            current_summary = ""
            current_body = ""
            current_urgency = 1
            in_notify = False
            line_count = 0

            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode('utf-8', errors='ignore').strip()

                if "member=Notify" in line:
                    in_notify = True
                    line_count = 0
                    current_app = current_summary = current_body = ""
                    current_urgency = 1
                    continue

                if in_notify:
                    line_count += 1
                    if line.startswith('string "'):
                        val = line[8:].rstrip('"')
                        if line_count == 1:
                            current_app = val
                        elif line_count == 4:
                            current_summary = val
                        elif line_count == 5:
                            current_body = val
                    elif 'string "urgency"' in line:
                        # Next lines contain variant byte X
                        continue
                    elif in_notify and 'byte ' in line:
                        try:
                            current_urgency = int(line.split('byte ')[1].strip())
                        except Exception:
                            pass

                    # End of Notify message (method return or new call)
                    if line.startswith('int32 ') or (line_count > 15 and current_summary):
                        in_notify = False
                        app_lower = current_app.lower()
                        if app_lower not in IGNORED_APPS:
                            combined = f"{current_summary}. {current_body}".strip().rstrip('.') + "."
                            # Urgency 2 = Critical
                            priority = "critical" if current_urgency == 2 else "normal"
                            dedup = f"notif_{app_lower}_{current_summary[:20]}"
                            log.info("Notification received from %s (urgency=%d): %s", current_app, current_urgency, combined)
                            # Classify notification: criticals (crashes, failures, high usage, low battery) get spoken via natural voice; routine noise is registered silently in context
                            await arbiter.handle_event(combined, source="notification", dedup_key=dedup, urgency=current_urgency)

        except asyncio.CancelledError:
            break
        except Exception as err:
            log.warning("D-Bus notification monitor error: %s", err)
            await asyncio.sleep(2.0)


# ============================================================================
# WATCHER 2: Hardware & Power (UPower + udevadm)
# ============================================================================
async def watch_upower_and_hardware(arbiter: SpeechArbiter):
    """Monitors power changes (AC adapter, battery thresholds) and USB devices."""
    log.info("Starting Hardware & Power watcher...")

    async def _battery_power_loop():
        from dbus_next.aio import MessageBus
        from dbus_next.constants import BusType

        last_online = None
        alerted_20 = False
        alerted_10 = False

        while True:
            try:
                bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
                # Line Power
                try:
                    intro_line = await bus.introspect('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/line_power_ADP1')
                    proxy_line = bus.get_proxy_object('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/line_power_ADP1', intro_line)
                    props_line = proxy_line.get_interface('org.freedesktop.DBus.Properties')
                except Exception:
                    props_line = None

                # Battery
                try:
                    intro_bat = await bus.introspect('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/battery_BAT0')
                    proxy_bat = bus.get_proxy_object('org.freedesktop.UPower', '/org/freedesktop/UPower/devices/battery_BAT0', intro_bat)
                    props_bat = proxy_bat.get_interface('org.freedesktop.DBus.Properties')
                except Exception:
                    props_bat = None

                while True:
                    await asyncio.sleep(5.0)
                    if props_line:
                        online_val = (await props_line.call_get('org.freedesktop.UPower.Device', 'Online')).value
                        if last_online is not None and online_val != last_online:
                            if online_val:
                                await arbiter.handle_event("Power cable connected. Charging battery.", priority="normal", source="power", dedup_key="ac_power")
                            else:
                                await arbiter.handle_event("Power cable disconnected. Running on battery.", priority="normal", source="power", dedup_key="ac_power")
                        last_online = online_val

                    if props_bat:
                        pct = (await props_bat.call_get('org.freedesktop.UPower.Device', 'Percentage')).value
                        state = (await props_bat.call_get('org.freedesktop.UPower.Device', 'State')).value
                        # State 2 = Discharging
                        if state == 2:
                            if pct <= 10.0 and not alerted_10:
                                alerted_10 = True
                                await arbiter.handle_event(f"Critical battery warning: {int(pct)} percent remaining.", priority="critical", source="power", dedup_key="bat_crit")
                            elif pct <= 20.0 and not alerted_20 and not alerted_10:
                                alerted_20 = True
                                await arbiter.handle_event(f"Battery is low at {int(pct)} percent.", priority="normal", source="power", dedup_key="bat_low")
                        else:
                            if pct > 25.0:
                                alerted_20 = False
                            if pct > 15.0:
                                alerted_10 = False

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("UPower monitor reconnecting: %s", e)
                await asyncio.sleep(6.0)

    async def _udev_loop():
        while True:
            try:
                proc = await asyncio.create_subprocess_exec(
                    'udevadm', 'monitor', '--udev', '-s', 'usb', '-s', 'sound',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL
                )
                while True:
                    line_bytes = await proc.stdout.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    # Example: UDEV  [1234.56] add      /devices/... (usb)
                    if 'add' in line and 'usb' in line:
                        await arbiter.handle_event("USB device connected.", priority="normal", source="hardware", dedup_key="udev_usb_add")
                    elif 'remove' in line and 'usb' in line:
                        await arbiter.handle_event("USB device disconnected.", priority="normal", source="hardware", dedup_key="udev_usb_rem")
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("udev monitor error: %s", e)
                await asyncio.sleep(4.0)

    await asyncio.gather(_battery_power_loop(), _udev_loop())


# ============================================================================
# WATCHER 3: Systemd & JARVIS Service Health
# ============================================================================
async def watch_systemd_health(arbiter: SpeechArbiter):
    """Monitors journald for failures in core JARVIS services."""
    log.info("Starting Systemd Service Health watcher...")
    WATCHED_UNITS = {
        'jarvis-voice.service',
        'jarvis-api-agent.service',
        'jarvis-device-bridge.service',
        'jarvis-widget-hud.service'
    }

    while True:
        try:
            proc = await asyncio.create_subprocess_exec(
                'journalctl', '--user', '-f', '-o', 'json',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )

            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                try:
                    entry = json.loads(line_bytes.decode('utf-8', errors='ignore'))
                    unit = entry.get('_SYSTEMD_USER_UNIT', '')
                    if unit in WATCHED_UNITS:
                        msg = entry.get('MESSAGE', '')
                        if 'Failed with result' in msg or 'Failed at step' in msg:
                            unit_name = unit.replace('.service', '').replace('jarvis-', '')
                            alert = f"System alert: Service {unit_name} encountered an error: {msg}."
                            await arbiter.handle_event(alert, priority="critical", source="systemd", dedup_key=f"systemd_{unit}")
                except Exception:
                    pass

        except asyncio.CancelledError:
            break
        except Exception as e:
            log.debug("Systemd health monitor error: %s", e)
            await asyncio.sleep(3.0)


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================
async def main():
    log.info("Initializing JARVIS OS Speaker Daemon...")
    client = SpeechClient()
    arbiter = SpeechArbiter(client)

    tasks = [
        asyncio.create_task(watch_dbus_notifications(arbiter)),
        asyncio.create_task(watch_upower_and_hardware(arbiter)),
        asyncio.create_task(watch_systemd_health(arbiter)),
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
