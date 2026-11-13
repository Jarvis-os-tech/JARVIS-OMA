"""Session-owned microphone AEC with direct, unfiltered speaker playback."""
import asyncio
import json
import logging
import uuid
from typing import Optional

from .playback import audio_environment, stop_process

log = logging.getLogger('voice_layer')


async def pactl(*args: str) -> str:
    process = await asyncio.create_subprocess_exec(
        'pactl', *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=audio_environment())
    try:
        out, err = await asyncio.wait_for(process.communicate(), 5)
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise
    if process.returncode:
        raise RuntimeError(f"pactl {args[0]} failed: {err.decode().strip()}")
    return out.decode().strip()


def monitor_properties(source: str, sink: str, name: str) -> dict:
    return {
        'monitor.mode': True,
        'audio.rate': 48000,
        'audio.channels': 1,
        'audio.position': ['MONO'],
        'aec.args': {
            'webrtc.noise_suppression': False,
            'webrtc.gain_control': False,
            'webrtc.high_pass_filter': True,
        },
        'capture.props': {'target.object': source, 'node.name': f'{name}_capture'},
        'source.props': {
            'node.name': name,
            'node.description': 'JARVIS echo-cancelled microphone',
            'priority.session': 0,
        },
        'sink.props': {'target.object': sink, 'node.name': f'{name}_reference'},
    }


class MonitorEchoCancellation:
    """Own a native PipeWire WebRTC AEC module without modifying system defaults."""

    def __init__(self):
        self.name = f'jarvis_aec_{uuid.uuid4().hex[:8]}'
        self.source = self.name
        self.sink = ''
        self.microphone = ''
        self._physical_muted = None
        self.process: Optional[asyncio.subprocess.Process] = None
        self.active = False

    async def start(self, microphone: Optional[str] = None, speaker: Optional[str] = None) -> bool:
        try:
            source = str(microphone) if microphone else await pactl('get-default-source')
            sink = str(speaker) if speaker else await pactl('get-default-sink')
            self.sink = sink
            self.microphone = source
            if source.endswith('.monitor'):
                raise RuntimeError('Echo cancellation requires a microphone, not a monitor source')

            self.process = await asyncio.create_subprocess_exec(
                'pw-cli', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL, env=audio_environment())

            command = 'load-module libpipewire-module-echo-cancel ' + json.dumps(
                monitor_properties(source, sink, self.source)) + '\n'
            self.process.stdin.write(command.encode())
            await self.process.stdin.drain()

            for _ in range(40):  # Wait up to 2 seconds
                if self.process.returncode is not None:
                    raise RuntimeError(f'PipeWire echo cancel exited with code {self.process.returncode}')
                available = await pactl('list', 'short', 'sources')
                if any(line.split()[1:2] == [self.source] for line in available.splitlines()):
                    # A new private AEC node can inherit an unrelated restored
                    # mute. Initialize it from its actual physical microphone
                    # initially; later physical mute transitions are mirrored.
                    sources = json.loads(await pactl('--format=json', 'list', 'sources'))
                    physical = next((item for item in sources if item.get('name') == source), None)
                    if physical is not None and type(physical.get('mute')) is bool:
                        await pactl('set-source-mute', self.source, '1' if physical['mute'] else '0')
                        self._physical_muted = physical['mute']
                    self.active = True
                    try:
                        await pactl('set-source-volume', self.source, '100%')
                    except Exception:
                        pass
                    log.info('PipeWire Monitor AEC active: mic=%s target=%s speaker=%s',
                             source, self.source, self.sink)
                    return True
                await asyncio.sleep(0.05)
            log.warning('Timed out waiting for PipeWire AEC virtual source')
            await self.close()
            return False
        except Exception as exc:
            log.warning('Unable to start PipeWire AEC: %s (falling back to direct microphone)', exc)
            await self.close()
            return False

    async def sync_microphone_mute(self):
        """Mirror physical mute transitions, leaving independent AEC mutes intact."""
        if not self.active or not self.microphone:
            return
        try:
            sources = json.loads(await pactl('--format=json', 'list', 'sources'))
            if not isinstance(sources, list) or any(not isinstance(item, dict) for item in sources):
                return
            physical = [item for item in sources if item.get('name') == self.microphone]
            owned = [item for item in sources if item.get('name') == self.source]
            if len(physical) != 1 or len(owned) != 1 or type(physical[0].get('mute')) is not bool:
                return
            muted = physical[0]['mute']
            if muted is self._physical_muted:
                return
            if self._physical_muted is not None:
                await pactl('set-source-mute', self.source, '1' if muted else '0')
            self._physical_muted = muted
        except (OSError, RuntimeError, ValueError, TypeError, TimeoutError):
            log.warning('Could not synchronize the private microphone mute', exc_info=True)

    async def close(self):
        self.active = False
        self.microphone = ''
        self._physical_muted = None
        process, self.process = self.process, None
        if process is not None:
            await stop_process(process)


EchoCancellation = MonitorEchoCancellation
