"""Single-pass Gemini Decision 1 router for JARVIS-OMA.

Evaluates addressability (is_for_jarvis), situational spoken acknowledgement (ack_clip),
subsystem route (route), and desktop safety policy (requires_confirmation) in a single
fast API pass (~150-250 ms) with zero output tokens.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
import io
import logging
import os
import re
import time
from typing import Any, Dict, Optional, Union
import wave

from jarvis_control.execution_policy import (
    CONFIRMATION_DECISION_CRITERIA,
    requires_confirmation as policy_requires_confirmation,
)
from orchestration.model_routes import SUBSYSTEM_ROUTES
from voice_layer.acknowledgements import (
    DECISION_ACK_CRITERIA,
    is_conversational_inquiry,
    select_ack,
)

log = logging.getLogger(__name__)


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Pack raw 16-bit mono PCM into standard WAV bytes."""
    if pcm_data.startswith(b'RIFF'):
        return pcm_data
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


@dataclass
class DecisionResult:
    """Structured decision output from gemini-decision-1."""
    is_for_jarvis: bool = True
    ack_clip: str = 'ack_short_sure'
    route: str = 'gemini_live'
    requires_confirmation: bool = False
    confidence: Dict[str, float] = field(default_factory=dict)
    raw_answers: Dict[str, Any] = field(default_factory=dict)
    elapsed_ms: int = 0


class DecisionRouter:
    """Fast, single-turn Decision Gate powered by gemini-decision-1."""

    def __init__(
        self,
        config: Any = None,
        api_key: Optional[str] = None,
        client: Any = None,
        model: str = 'gemini-decision-1',
        timeout_seconds: float = 2.5,
    ) -> None:
        self.config = config
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        self._client = client
        self._provided_client = client is not None
        self.model = getattr(config, 'model', model)
        self.timeout_seconds = getattr(config, 'timeout_seconds', timeout_seconds)
        self.last_decision_ms: Optional[int] = None
        self.decisions_count: int = 0

    async def close(self) -> None:
        """Close the underlying client connections."""
        if self._client is not None and not self._provided_client and hasattr(self._client, 'aio'):
            try:
                await self._client.aio.aclose()
            except Exception:
                pass
            self._client = None

    def _get_client(self) -> Any:
        if self._client is not None and self._provided_client:
            return self._client
        loop = asyncio.get_running_loop()
        if self._client is not None and getattr(self, '_loop', None) is loop:
            return self._client
        from google import genai
        key = self.api_key or os.environ.get('GEMINI_API_KEY', '')
        if not key:
            raise ValueError('GEMINI_API_KEY is not configured for DecisionRouter')
        self._loop = loop
        self._client = genai.Client(api_key=key, http_options={'api_version': 'v1beta'})
        return self._client

    def _build_questions(self) -> Dict[str, Dict[str, Any]]:
        return {
            'is_for_jarvis': {
                'type': 'noul',
                'instructions': (
                    'Is this utterance directed at the JARVIS assistant, rather than ambient '
                    'room noise, background speech, side conversation, or speech directed at someone else?'
                ),
                'criteria': {
                    'true_description': 'Speech intentionally directed at JARVIS as a command, inquiry, prompt, or follow-up.',
                    'false_description': 'Background room chatter, ambient noise, coughing, TV audio, or speech not meant for JARVIS.',
                },
            },
            'ack_clip': {
                'type': 'choice',
                'instructions': (
                    'Select the most appropriate pre-rendered spoken acknowledgement audio clip '
                    'to immediately play to the user while processing this request.'
                ),
                'criteria': dict(DECISION_ACK_CRITERIA),
            },
            'route': {
                'type': 'choice',
                'instructions': 'Select the subsystem route that should process and execute this request.',
                'criteria': dict(SUBSYSTEM_ROUTES),
            },
            'requires_confirmation': {
                'type': 'noul',
                'instructions': (
                    'Does this request involve a destructive, irreversible, or high-impact desktop '
                    'operation (e.g. system poweroff, reboot, system updates, formatting disks, '
                    'deleting files, terminating processes, privileged commands) that requires user '
                    'confirmation before execution?'
                ),
                'criteria': dict(CONFIRMATION_DECISION_CRITERIA),
            },
        }

    async def evaluate(
        self,
        input_data: Union[str, bytes],
        text: Optional[str] = None,
    ) -> DecisionResult:
        """Evaluate input audio buffer or transcript in a single pass."""
        started = time.monotonic()
        transcript = text or (input_data if isinstance(input_data, str) else '')

        # Construct decision input payload
        if isinstance(input_data, (bytes, bytearray)) and len(input_data) > 0:
            if not transcript or not transcript.strip():
                # Pass raw WAV audio directly to decisions API
                wav_bytes = pcm_to_wav(bytes(input_data))
                b64_audio = base64.b64encode(wav_bytes).decode('ascii')
                input_param = {
                    'type': 'audio',
                    'mime_type': 'audio/wav',
                    'data': b64_audio,
                    'sample_rate': 16000,
                    'channels': 1,
                }
            else:
                input_param = transcript.strip()
        elif isinstance(input_data, str) and input_data.strip():
            input_param = input_data.strip()
        elif transcript and transcript.strip():
            input_param = transcript.strip()
        else:
            # Empty input - default safe fallback
            return DecisionResult(
                is_for_jarvis=False,
                ack_clip='none',
                route='gemini_live',
                requires_confirmation=False,
                elapsed_ms=0,
            )

        questions = self._build_questions()

        try:
            client = self._get_client()
            async with asyncio.timeout(self.timeout_seconds):
                response = await client.aio.decisions.create(
                    model=self.model,
                    input=input_param,
                    questions=questions,
                )

            elapsed_ms = round((time.monotonic() - started) * 1000)
            self.last_decision_ms = elapsed_ms
            self.decisions_count += 1

            answers = getattr(response, 'answers', {}) or {}
            
            # Extract is_for_jarvis
            is_for_jarvis = True
            conf_for_jarvis = 1.0
            if 'is_for_jarvis' in answers:
                ans = answers['is_for_jarvis']
                val = getattr(ans, 'noul', None)
                if isinstance(val, (int, float)):
                    is_for_jarvis = val >= 0.5
                elif isinstance(val, bool):
                    is_for_jarvis = val
                conf_for_jarvis = float(getattr(ans, 'confidence', 1.0) or 1.0)

            # Extract ack_clip
            ack_clip = 'ack_short_sure'
            conf_ack = 1.0
            if 'ack_clip' in answers:
                ans = answers['ack_clip']
                ack_clip = str(getattr(ans, 'choice', 'ack_short_sure') or 'ack_short_sure')
                conf_ack = float(getattr(ans, 'confidence', 1.0) or 1.0)

            # Extract route
            route = 'gemini_live'
            conf_route = 1.0
            if 'route' in answers:
                ans = answers['route']
                route = str(getattr(ans, 'choice', 'gemini_live') or 'gemini_live')
                conf_route = float(getattr(ans, 'confidence', 1.0) or 1.0)

            # Extract requires_confirmation
            requires_confirmation = False
            conf_confirm = 1.0
            if 'requires_confirmation' in answers:
                ans = answers['requires_confirmation']
                val = getattr(ans, 'noul', None)
                if isinstance(val, (int, float)):
                    requires_confirmation = val >= 0.5
                elif isinstance(val, bool):
                    requires_confirmation = val
                conf_confirm = float(getattr(ans, 'confidence', 1.0) or 1.0)

            # Re-enforce local desktop safety policy check on top of model output
            if transcript and not requires_confirmation:
                requires_confirmation = policy_requires_confirmation(transcript)

            result = DecisionResult(
                is_for_jarvis=is_for_jarvis,
                ack_clip=ack_clip,
                route=route,
                requires_confirmation=requires_confirmation,
                confidence={
                    'is_for_jarvis': conf_for_jarvis,
                    'ack_clip': conf_ack,
                    'route': conf_route,
                    'requires_confirmation': conf_confirm,
                },
                raw_answers=answers,
                elapsed_ms=elapsed_ms,
            )
            log.info(
                'Gemini Decision 1: route=%s, ack=%s, for_jarvis=%s, confirm=%s (%d ms)',
                result.route, result.ack_clip, result.is_for_jarvis, result.requires_confirmation, elapsed_ms,
            )
            return result

        except Exception as error:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            log.warning('Gemini Decision 1 call failed (%s); using local heuristic fallback: %s', type(error).__name__, error)
            return self._fallback_decision(transcript, elapsed_ms)

    def _fallback_decision(self, transcript: str, elapsed_ms: int) -> DecisionResult:
        """Deterministic local fallback when Decisions API is unavailable or offline."""
        text = transcript.strip().lower() if transcript else ''
        
        # Local policy confirmation
        requires_confirmation = policy_requires_confirmation(text)

        # Local ack clip selection
        if is_conversational_inquiry(text):
            ack_clip = 'ack_short_hmm'
        elif any(w in text for w in ('search', 'look up', 'google')):
            ack_clip = 'ack_search'
        elif any(w in text for w in ('screen', 'display')):
            ack_clip = 'ack_screen'
        elif any(w in text for w in ('browser', 'chrome', 'firefox', 'website', 'url')):
            ack_clip = 'ack_browser'
        elif any(w in text for w in ('terminal', 'shell', 'command', 'run')):
            ack_clip = 'ack_terminal'
        elif any(w in text for w in ('agent', 'hermes', 'workflow', 'kanban')):
            ack_clip = 'ack_agent'
        elif any(w in text for w in ('open', 'launch', 'app')):
            ack_clip = 'ack_app'
        else:
            ack_clip = select_ack('generic_deep_thought', text)

        # Local route selection
        if any(w in text for w in ('remember', 'recall', 'preference', 'note that', 'memory')):
            route = 'jarvis_memory'
        elif any(w in text for w in ('slack', 'github', 'linkedin', 'notion', 'spotify')):
            route = 'connectors_reach'
        elif any(w in text for w in ('subagent', 'hermes', 'kanban', 'cron schedule', 'coding agent', 'workflow')):
            route = 'hermes_agents'
        elif any(w in text for w in (
            'volume', 'brightness', 'workspace', 'launch', 'close', 'open', 'app',
            'system', 'window', 'terminal', 'screen', 'desktop', 'browser', 'click'
        )):
            route = 'jarvis_control'
        else:
            route = 'gemini_live'

        return DecisionResult(
            is_for_jarvis=True,
            ack_clip=ack_clip,
            route=route,
            requires_confirmation=requires_confirmation,
            confidence={'fallback': 1.0},
            raw_answers={},
            elapsed_ms=elapsed_ms,
        )
