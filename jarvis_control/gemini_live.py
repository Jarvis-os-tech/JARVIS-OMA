"""Gemini Multimodal Live API engine: speech in, speech out, tools in between.

Uses Google Gemini's Multimodal Live API (bidirectional WebSockets) for real-time
speech-to-speech interaction, with tool calling gated by tools.Executor.

    pw-record (16kHz) ──▶ websocket ──▶ gemini-3.8-live ──▶ audio (24kHz) ──▶ pw-cat
                                              │
                                              ▼  toolCall
                                        policy gate ──▶ denied / held
                                              │
                                              ▼
                                 hyprctl · omarchy · wtype · uwsm-app
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import shutil
import sys
import time
from typing import Any

import websockets

from . import capabilities
from .config import Config, CONFIG_DIR, ENV_FILE, SAFETY_ID_FILE
from .feedback import Feedback
from .persona import PERSONA
from .realtime import (
    GATE_TOOLS,
    REALTIME_PERSONA,
    ECHO_TAIL_SECONDS,
    RECONNECT_ATTEMPTS,
    RECONNECT_BASE_DELAY,
    RECONNECT_MAX_DELAY,
    RECONNECT_HEALTHY_SECONDS,
    STATE_REFRESH_SECONDS,
    Speaker,
    frame_level,
    _terminate,
)
from .session import ControlServer, _matches
from .tools import TOOL_SCHEMAS, Executor, tools_for

# Gemini Live input PCM is 16kHz mono 16-bit.
# 100 ms of 16 kHz mono PCM16 = 3200 bytes.
INPUT_SAMPLE_RATE = 16000
INPUT_FRAME_BYTES = 3200
OUTPUT_SAMPLE_RATE = 24000

GEMINI_LIVE_WS_BASE = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"


class GeminiLiveUnavailable(RuntimeError):
    """Something the Gemini Live path needs is missing."""


def clean_schema(s: Any) -> Any:
    """Strip properties unsupported by Gemini's schema parser."""
    if not isinstance(s, dict):
        return s
    cleaned: dict[str, Any] = {}
    for k, v in s.items():
        if k in ("additionalProperties", "$schema"):
            continue
        if k == "enum" and isinstance(v, list):
            non_empty = [x for x in v if x != ""]
            cleaned[k] = non_empty if non_empty else ["none"]
        elif isinstance(v, dict):
            cleaned[k] = clean_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_schema(x) for x in v]
        else:
            cleaned[k] = v
    return cleaned


def to_gemini_tools(schemas: list[dict] | None = None) -> list[dict]:
    """Convert executor schemas to Gemini functionDeclarations."""
    fns = []
    for schema in schemas if schemas is not None else TOOL_SCHEMAS:
        fns.append({
            "name": schema["name"],
            "description": schema["description"],
            "parameters": clean_schema(schema["input_schema"]),
        })
    for tool in GATE_TOOLS:
        fns.append({
            "name": tool["name"],
            "description": tool["description"],
            "parameters": clean_schema(tool["parameters"]),
        })
    return [{"functionDeclarations": fns}]


def check_ready(config: Config) -> list[str]:
    """Check prerequisites for the Gemini Live daemon."""
    problems = []
    key = os.environ.get(config.gemini_api_key_env, "")
    if not key:
        problems.append(f"{config.gemini_api_key_env} is not set (put it in {ENV_FILE})")
    for prog in ("pw-record", "pw-cat"):
        if not shutil.which(prog):
            problems.append(f"{prog} is missing — install pipewire-audio")
    return problems


class GeminiLiveSession:
    def __init__(self, config: Config):
        self.config = config
        self.feedback = Feedback(config)
        self.executor = Executor(config, on_action=self._on_action)
        self.speaker = Speaker(OUTPUT_SAMPLE_RATE)
        self.active = False
        self.ws: Any = None
        self.loop: asyncio.AbstractEventLoop | None = None
        self._send_lock = asyncio.Lock()
        self._active_event = asyncio.Event()
        self._stop = asyncio.Event()
        self._mic: asyncio.subprocess.Process | None = None
        self._transcript = ""
        self._state_refreshed = 0.0
        self._refreshing = False
        self._last_state_hash = ""
        self._refresh_task: asyncio.Task | None = None
        self._held_frames = 0
        self._tool_rounds = 0
        self._user_quit = False
        self._dropped = False
        self._exit_code = 0

    def _on_action(self, name: str, description: str = "") -> None:
        desc = description or name
        self.feedback.state("acting", desc)
        self.feedback.log(f"action  {desc}")

    async def _send(self, payload: dict) -> None:
        ws = self.ws
        if ws is None:
            return
        async with self._send_lock:
            try:
                await ws.send(json.dumps(payload))
            except Exception as exc:
                self.feedback.log(f"error   send: {type(exc).__name__}: {exc}")
                self._dropped = True
                self._stop.set()

    async def _instructions(self) -> str:
        from .tasks import ROUTING
        from .vision import ROUTING as VISION_ROUTING
        manifest, live = await asyncio.gather(
            asyncio.to_thread(capabilities.manifest),
            asyncio.to_thread(capabilities.live_state),
        )
        self._state_refreshed = time.monotonic()
        return "\n\n".join(p for p in [
            PERSONA,
            REALTIME_PERSONA,
            ROUTING if self.config.tasks_enabled else "",
            VISION_ROUTING if self.config.vision_enabled else "",
            manifest,
            "# The desktop right now\n\n" + live,
        ] if p)

    async def _build_setup_message(self) -> dict:
        model = self.config.realtime_model
        if not model.startswith("models/"):
            model = f"models/{model}"
        voice = self.config.realtime_voice or "Puck"
        tools = to_gemini_tools(tools_for(self.config))
        system_instruction = await self._instructions()
        return {
            "setup": {
                "model": model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": voice,
                            }
                        }
                    },
                },
                "systemInstruction": {
                    "parts": [{"text": system_instruction}],
                },
                "tools": tools,
            }
        }

    # -- control socket -----------------------------------------------------
    def _control(self, command: str) -> str:
        if self.loop is None:
            return "not ready"
        verb, _, rest = command.partition(" ")
        if verb == "toggle":
            future = asyncio.run_coroutine_threadsafe(self._toggle(), self.loop)
        elif verb in ("start", "stop"):
            future = asyncio.run_coroutine_threadsafe(
                self._set_active(verb == "start"), self.loop)
        elif verb == "say":
            future = asyncio.run_coroutine_threadsafe(self._inject(rest), self.loop)
        elif verb == "confirm":
            future = asyncio.run_coroutine_threadsafe(self._local_confirm(), self.loop)
        elif verb == "cancel":
            future = asyncio.run_coroutine_threadsafe(self._local_cancel(), self.loop)
        elif verb == "quit":
            self._user_quit = True
            self.loop.call_soon_threadsafe(self._stop.set)
            return "stopping"
        else:
            return f"unknown command {verb!r}"
        try:
            return future.result(timeout=10)
        except Exception as exc:
            return f"error: {type(exc).__name__}: {exc}"

    async def _toggle(self) -> str:
        return await self._set_active(not self.active)

    async def _set_active(self, active: bool) -> str:
        self.active = active
        if active:
            self._active_event.set()
        else:
            self._active_event.clear()
            await self._send({"realtimeInput": {"audioStreamEnd": True}})
            await self._kill_mic()
            await self.speaker.interrupt()
            await asyncio.to_thread(self.executor.vision.stop_owned)
        self.feedback.state("listening" if active else "idle")
        self.feedback.notify("Listening" if active else "Sleeping")
        self.feedback.log(f"gate    {'listening' if active else 'muted'}")
        return "listening" if active else "idle"

    async def _inject(self, text: str) -> str:
        text = text.strip()
        if not text:
            return "nothing to say"
        self._tool_rounds = 0
        self.feedback.log(f"typed   {text!r}")
        await self._refresh_state(force=True)
        await self._send({"realtimeInput": {"text": text}})
        return "sent"

    async def _local_confirm(self) -> str:
        if not self.executor.pending:
            return "nothing to confirm"
        held = self.executor.describe(*self.executor.pending)
        self.feedback.log(f"confirm local release: {held}")
        result = await asyncio.to_thread(self.executor.run_pending)
        self._settle()
        return result.as_tool_result()

    async def _local_cancel(self) -> str:
        held = self.executor.drop_pending()
        if held is None:
            return "nothing to cancel"
        self.feedback.log(f"cancel  {held}")
        self._settle()
        return f"Cancelled: {held}. It was not run."

    # -- state sync ---------------------------------------------------------
    async def _refresh_state(self, force: bool = False) -> None:
        if self._refreshing:
            return
        if not force and time.monotonic() - self._state_refreshed < STATE_REFRESH_SECONDS:
            return
        self._refreshing = True
        try:
            live = await asyncio.to_thread(capabilities.live_state)
            self._state_refreshed = time.monotonic()
            h = hash(live)
            if not force and h == self._last_state_hash:
                return
            self._last_state_hash = h
            await self._send({
                "realtimeInput": {
                    "text": (
                        "# The desktop right now (current as of this turn)\n\n"
                        + live +
                        "\n\nThis snapshot is fresh. Trust it for workspaces, monitors "
                        "and window addresses instead of calling hypr_query again."
                    )
                }
            })
        except Exception as exc:
            self.feedback.log(f"error   state refresh: {type(exc).__name__}: {exc}")
        finally:
            self._refreshing = False

    async def _refresh_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.sleep(STATE_REFRESH_SECONDS)
                if self.active and not self._stop.is_set():
                    await self._refresh_state()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    # -- microphone pump ----------------------------------------------------
    async def _mic_loop(self) -> None:
        while not self._stop.is_set():
            waiter = asyncio.create_task(self._active_event.wait())
            stopper = asyncio.create_task(self._stop.wait())
            done, pending = await asyncio.wait(
                {waiter, stopper}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            if self._stop.is_set():
                return

            cmd = ["pw-record", "--rate", str(INPUT_SAMPLE_RATE),
                   "--channels", "1", "--format", "s16", "--latency", "20ms"]
            if self.config.device:
                cmd += ["--target", self.config.device]
            cmd.append("-")
            try:
                self._mic = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL)
            except FileNotFoundError:
                self.feedback.log("error   pw-record is missing — install pipewire-audio")
                self._stop.set()
                self._exit_code = 1
                return

            self.feedback.log("mic     started (16kHz PCM16)")
            stdout = self._mic.stdout
            assert stdout is not None
            try:
                while self._active_event.is_set() and not self._stop.is_set():
                    chunk = await stdout.read(INPUT_FRAME_BYTES)
                    if not chunk:
                        if self._active_event.is_set() and not self._stop.is_set():
                            self.feedback.log("error   pw-record ended unexpectedly")
                            self._exit_code = 1
                            self._stop.set()
                        break

                    held = not self.config.barge_in and self.speaker.is_playing(ECHO_TAIL_SECONDS)
                    if held:
                        self._held_frames += 1
                        chunk = bytes(len(chunk))
                        level = 0.0
                    else:
                        if self._held_frames:
                            self.feedback.log(f"mic     held {self._held_frames} frames while speaking")
                            self._held_frames = 0
                        level = frame_level(chunk)

                    self.feedback.level(level, self.speaker.level_now())
                    b64 = base64.b64encode(chunk).decode("ascii")
                    await self._send({
                        "realtimeInput": {
                            "audio": {
                                "data": b64,
                                "mimeType": f"audio/pcm;rate={INPUT_SAMPLE_RATE}"
                            }
                        }
                    })
            finally:
                await self._kill_mic()
                self.feedback.level(0.0)
                self.feedback.log("mic     stopped")

    async def _kill_mic(self) -> None:
        proc, self._mic = self._mic, None
        if proc is None or proc.returncode is not None:
            return
        await _terminate(proc)

    # -- incoming message handling ------------------------------------------
    async def _on_message(self, raw: str | bytes) -> None:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        if "setupComplete" in msg:
            self.feedback.log("setup   Gemini Live ready")
            return

        if "toolCall" in msg:
            calls = msg["toolCall"].get("functionCalls", [])
            responses = []
            for fc in calls:
                name = fc.get("name", "")
                call_id = fc.get("id", "")
                args = fc.get("args") or {}
                self.feedback.log(f"tool    {name} {args}")
                try:
                    if name == "confirm_last":
                        outcome_text = await self._confirm(str(args.get("heard_phrase", "")))
                    elif name == "cancel_last":
                        outcome_text = self._cancel()
                    else:
                        outcome = await asyncio.to_thread(self.executor.call, name, args)
                        outcome_text = outcome.as_tool_result()
                except Exception as exc:
                    self.feedback.log(f"error   tool {name}: {type(exc).__name__}: {exc}")
                    outcome_text = f"ERROR executing {name}: {exc}"

                responses.append({
                    "name": name,
                    "id": call_id,
                    "response": {"output": {"result": outcome_text}}
                })

            self._tool_rounds += 1
            if self._tool_rounds >= self.config.gemini_max_turns:
                self.feedback.log(f"guard   stopped after {self._tool_rounds} rounds")
                self.feedback.notify("OMA stopped", "Too many steps on that turn.")
                self._settle()
                return

            await self._send({"toolResponse": {"functionResponses": responses}})
            return

        if "serverContent" in msg:
            sc = msg["serverContent"]
            if sc.get("interrupted"):
                self.feedback.log("interrupted")
                await self.speaker.interrupt()
                return

            if "modelTurn" in sc:
                for part in sc["modelTurn"].get("parts", []):
                    if "inlineData" in part:
                        b64 = part["inlineData"].get("data", "")
                        if b64:
                            pcm = base64.b64decode(b64)
                            await self.speaker.write(pcm)
                    if "text" in part and part["text"]:
                        text = part["text"].strip()
                        self.feedback.log(f"reply   {text!r}")
                        self.feedback.notify(text)

            if "outputTranscription" in sc:
                trans = sc["outputTranscription"].get("text", "").strip()
                if trans:
                    self.feedback.log(f"said    {trans!r}")

            if sc.get("turnComplete"):
                self._settle()

    def _settle(self) -> None:
        if self.executor.pending:
            held = self.executor.describe(*self.executor.pending)
            self.feedback.state("confirm", held)
            self.feedback.notify("Waiting for confirmation", held, urgency="normal")
        else:
            self.feedback.state("listening" if self.active else "idle")

    async def _confirm(self, heard_phrase: str) -> str:
        if not self.executor.pending:
            return "ERROR: nothing is waiting for confirmation. Do not call this again."
        held = self.executor.describe(*self.executor.pending)
        if not _matches(heard_phrase, self.config.confirm_words, allow_negation=False):
            self.feedback.log(f"reject  {heard_phrase!r} is not a confirmation of: {held}")
            phrases = ", ".join(f'"{w}"' for w in self.config.confirm_words)
            return (f"ERROR: {heard_phrase!r} is not a confirmation phrase, so {held} is "
                    f"still held. Ask the user to say one of: {phrases}.")
        self.feedback.log(f"confirm {heard_phrase!r} released: {held}")
        result = await asyncio.to_thread(self.executor.run_pending)
        self._settle()
        return result.as_tool_result()

    def _cancel(self) -> str:
        held = self.executor.drop_pending()
        if held is None:
            return "Nothing was being held."
        self.feedback.log(f"cancel  {held}")
        self._settle()
        return f"Cancelled: {held}. It was not run."

    # -- connection lifecycle -----------------------------------------------
    async def _open_one(self, url: str) -> None:
        self.feedback.log(f"connect {url.split('?')[0]}")
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            self.ws = ws
            setup = await self._build_setup_message()
            await ws.send(json.dumps(setup))
            self.feedback.log("setup   sent Gemini Live configuration")

            mic_task = asyncio.create_task(self._mic_loop())
            try:
                while not self._stop.is_set():
                    try:
                        raw = await ws.recv()
                    except websockets.exceptions.ConnectionClosed:
                        self.feedback.log("closed  websocket connection closed")
                        self._dropped = True
                        break
                    await self._on_message(raw)
            finally:
                mic_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await mic_task
                self.ws = None

    async def _serve(self, url: str) -> None:
        delay = RECONNECT_BASE_DELAY
        attempt = 0
        while not self._user_quit:
            self._dropped = False
            self._stop.clear()
            connected_at = time.monotonic()
            try:
                await self._open_one(url)
            except (GeminiLiveUnavailable, asyncio.CancelledError):
                raise
            except Exception as exc:
                self._dropped = True
                self.feedback.log(f"error   {type(exc).__name__}: {exc}")

            if time.monotonic() - connected_at >= RECONNECT_HEALTHY_SECONDS:
                attempt = 0
                delay = RECONNECT_BASE_DELAY

            if self._user_quit or not self._dropped:
                return
            attempt += 1
            if attempt > RECONNECT_ATTEMPTS:
                self.feedback.log(f"stop    gave up after {RECONNECT_ATTEMPTS} reconnects")
                self.feedback.notify(
                    "Voice control stopped",
                    "Lost connection to Gemini Live and could not reconnect.",
                    urgency="normal"
                )
                self._exit_code = 1
                return

            was_listening, self.active = self.active, False
            self._active_event.clear()
            self.feedback.state("error", f"reconnecting ({attempt}/{RECONNECT_ATTEMPTS})")
            self.feedback.log(f"retry   reconnecting in {delay:.0f}s ({attempt}/{RECONNECT_ATTEMPTS})")
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)
            if was_listening:
                self.active = True
                self._active_event.set()
                self.feedback.state("listening")
            else:
                self.feedback.state("idle")

    async def run(self) -> int:
        self.loop = asyncio.get_running_loop()
        key = os.environ.get(self.config.gemini_api_key_env, "")
        if not key:
            raise GeminiLiveUnavailable(
                f"{self.config.gemini_api_key_env} is not set — "
                f"put it in {ENV_FILE}"
            )
        url = f"{GEMINI_LIVE_WS_BASE}?key={key}"

        control = ControlServer(self._control)
        control.start()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        self.feedback.state("listening" if self.active else "idle")
        self.feedback.log(
            f"start   engine=gemini-live model={self.config.realtime_model} "
            f"voice={self.config.realtime_voice}"
        )
        self.feedback.log("gate    muted — press SUPER + SHIFT + V to start listening")

        if self.config.autostart_listening:
            await self._set_active(True)

        try:
            await self._serve(url)
        except GeminiLiveUnavailable:
            raise
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.feedback.state("error", str(exc))
            self.feedback.log(f"error   {type(exc).__name__}: {exc}")
            print(f"gemini live session failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 1
        finally:
            self._stop.set()
            if self._refresh_task is not None:
                self._refresh_task.cancel()
            await self._kill_mic()
            await self.speaker.close()
            await asyncio.to_thread(control.stop)
            self.feedback.state("idle")
            self.ws = None

        return 0 if self._user_quit else self._exit_code


def run(config: Config) -> int:
    """Run the Gemini Live daemon."""
    problems = check_ready(config)
    if problems:
        for p in problems:
            print(f"error: {p}", file=sys.stderr)
        return 1
    session = GeminiLiveSession(config)
    try:
        return asyncio.run(session.run())
    except KeyboardInterrupt:
        return 0
