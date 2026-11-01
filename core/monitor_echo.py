"""Session-owned microphone AEC with direct, unfiltered speaker playback."""
import asyncio
import json
import logging

from core.secret_env import sanitized_subprocess_env
from core.stable_echo_cancel import EchoCancellation, pactl

log = logging.getLogger('gemini_voice')


def monitor_properties(source, sink, name):
    return {
        'monitor.mode': True,
        'audio.rate': 48000, 'audio.channels': 1, 'audio.position': ['MONO'],
        'aec.args': {'webrtc.noise_suppression': False, 'webrtc.gain_control': False,
                     'webrtc.high_pass_filter': True},
        'capture.props': {'target.object': source, 'node.name': name + '_capture'},
        'source.props': {'node.name': name, 'node.description': 'JARVIS echo-cancelled microphone',
                         'priority.session': 0},
        'sink.props': {'target.object': sink, 'node.name': name + '_reference'},
    }


class MonitorEchoCancellation(EchoCancellation):
    """Own a native PipeWire module without changing defaults or system config."""
    def __init__(self):
        super().__init__()
        self.process = None

    async def start(self, microphone=None, volume_percent=None):
        source = str(microphone) if microphone else await pactl('get-default-source')
        sink = await pactl('get-default-sink')
        sources = json.loads(await pactl('--format=json', 'list', 'sources'))
        if source.endswith('.monitor') or source not in {item['name'] for item in sources}:
            raise RuntimeError('Echo cancellation requires an available microphone, not an output monitor')
        try:
            if volume_percent is not None:
                await self._limit_microphone(source, volume_percent)
            self.sink = sink  # Audio never traverses the echo-canceller's output.
            self.process = await asyncio.create_subprocess_exec(
                'pw-cli', stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL, env=sanitized_subprocess_env())
            command = 'load-module libpipewire-module-echo-cancel ' + json.dumps(
                monitor_properties(source, sink, self.source)) + '\n'
            self.process.stdin.write(command.encode())
            await self.process.stdin.drain()
            async with asyncio.timeout(5):
                while True:
                    if self.process.returncode is not None:
                        raise RuntimeError('PipeWire monitor echo-cancellation process exited')
                    available = await pactl('list', 'short', 'sources')
                    if any(line.split()[1:2] == [self.source] for line in available.splitlines()):
                        break
                    await asyncio.sleep(.05)
            log.info('Monitor AEC ready: microphone=%s source=%s direct_speaker=%s',
                     source, self.source, self.sink)
        except BaseException:
            await self.close()
            raise

    async def close(self):
        process, self.process = self.process, None
        try:
            if process is not None:
                if process.returncode is None:
                    process.stdin.close()
                    try:
                        process.terminate()
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(process.wait(), 2)
                except TimeoutError:
                    process.kill()
                    await process.wait()
        finally:
            await super().close()
