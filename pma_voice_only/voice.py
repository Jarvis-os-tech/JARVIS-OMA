"""Speech-only Gemini transport derived from PMA's voice path.

There is no tool registry, executor, desktop discovery, browser, task runner,
vision client, planner, transcript persistence or screen capture here.
"""
import asyncio
import base64
import contextlib
import json
import os
import signal
import time
from urllib.parse import quote
import websockets

from .audio import Speaker, frame_level, _terminate
from .config import RUNTIME_DIR, STATE_FILE, LEVEL_FILE
from .session import ControlServer

ENDPOINT = 'wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent'
PROMPT = ('You are OMA, a voice conversation assistant. Speak naturally and concisely. '
          'You can only hear microphone audio and speak replies. You have no tools, '
          'no computer controls, no browser, no files, no camera and no background tasks. '
          'Never claim to have performed a computer action or searched the web. '
          'Wait quietly for the user to speak; do not give an unsolicited greeting.')

def setup_message(config):
    return {'setup': {
        'model': config.model if config.model.startswith('models/') else 'models/'+config.model,
        'generationConfig': {'responseModalities':['AUDIO'],
            'speechConfig': {'voiceConfig': {'prebuiltVoiceConfig': {'voiceName':config.voice}}}},
        'systemInstruction': {'parts':[{'text':PROMPT}]},
        'tools': [],
    }}

def safe_error(exc):
    text = str(exc)
    for name in ('GEMINI_API_KEY','GOOGLE_API_KEY'):
        if os.environ.get(name):
            text = text.replace(os.environ[name], '[redacted]')
    return type(exc).__name__ + ': ' + text[:400]

class VoiceSession:
    def __init__(self, config, speaker=None):
        self.config = config
        self.speaker = speaker or Speaker(24000)
        self.loop = None
        self.ws = None
        self.mic = None
        self.active = False
        self.connected = False
        self.quitting = False
        self.wanted = asyncio.Event()
        self.send_lock = asyncio.Lock()
        self.mic_task = None
        self.last_error = ''
        self.stats = dict(input_bytes=0, output_bytes=0, blocked_tool_calls=0, interruptions=0,
                          connections=0, last_audio_at=0)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
        RUNTIME_DIR.chmod(0o700)

    def status(self):
        return dict(mode='voice-only', provider='gemini', model=self.config.model,
                    voice=self.config.voice, listening=self.active and self.connected,
                    connected=self.connected, requested_listening=self.active,
                    tools_enabled=False, features=['microphone','speech','playback','interruptions'],
                    microphone_pid=self.mic.pid if self.mic and self.mic.returncode is None else 0,
                    playback_pid=self.speaker._proc.pid if getattr(self.speaker,'_proc',None) and self.speaker._proc.returncode is None else 0,
                    barge_in=self.config.barge_in, error=self.last_error, **self.stats)

    def publish(self, label=None):
        state = label or ('listening' if self.active and self.connected else 'thinking' if self.active else 'idle')
        payload = dict(status=state, icon='󰍬', text='Voice only', updated=time.time(), **self.status())
        temp = STATE_FILE.with_suffix('.tmp')
        temp.write_text(json.dumps(payload))
        temp.chmod(0o600)
        temp.replace(STATE_FILE)

    def level(self, mic=0.0, voice=0.0):
        temp = LEVEL_FILE.with_suffix('.tmp')
        temp.write_text(f'{mic:.3f} {voice:.3f}')
        temp.chmod(0o600)
        temp.replace(LEVEL_FILE)

    async def send(self, payload):
        async with self.send_lock:
            if self.ws is not None and self.connected:
                await self.ws.send(json.dumps(payload))

    async def set_active(self, active):
        self.active = bool(active)
        self.last_error = ''
        if self.active:
            self.wanted.set()
        else:
            self.wanted.clear()
            # Stop capture before announcing audio end, then drop the connection.
            await self.stop_capture()
            await self.speaker.interrupt()
            if self.ws:
                with contextlib.suppress(Exception):
                    await self.send({'realtimeInput': {'audioStreamEnd': True}})
                    await self.ws.close()
            self.level()
        self.publish()
        return 'listening' if self.active and self.connected else 'connecting' if self.active else 'idle'

    async def interrupt(self):
        await self.speaker.interrupt()
        # Reset the voice connection so late chunks cannot resume cancelled speech.
        if self.ws:
            await self.ws.close()
        return 'speech stopped'

    async def say(self, text):
        if not self.connected:
            return 'error: voice is not connected; start listening first'
        await self.send({'clientContent': {'turns':[{'role':'user','parts':[{'text':text}]}], 'turnComplete':True}})
        return 'sent'

    async def quit(self):
        self.quitting = True
        await self.set_active(False)
        self.wanted.set()

    def control(self, command):
        verb, _, text = command.partition(' ')
        if verb == 'status':
            return json.dumps(self.status())
        if self.loop is None:
            return 'not ready'
        if verb in ('start','stop','toggle'):
            action = self.set_active(not self.active if verb == 'toggle' else verb == 'start')
        elif verb in ('cancel','interrupt'):
            action = self.interrupt()
        elif verb == 'say' and text.strip():
            action = self.say(text[:4000])
        elif verb == 'quit':
            action = self.quit()
        else:
            return 'error: only voice start, stop, toggle, cancel, say, status and quit are supported'
        future = asyncio.run_coroutine_threadsafe(action,self.loop)
        try:
            return str(future.result(timeout=12))
        except Exception as exc:
            future.cancel()
            return 'error: '+safe_error(exc)

    async def stop_capture(self):
        task, self.mic_task = self.mic_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        proc, self.mic = self.mic, None
        if proc and proc.returncode is None:
            await _terminate(proc)

    async def capture(self):
        # PMA's Gemini path: 16 kHz mono PCM16, 100 ms messages, speaker echo gate.
        command = ['pw-record','--rate','16000','--channels','1','--format','s16','--latency','20ms']
        if self.config.device:
            command += ['--target',self.config.device]
        proc = await asyncio.create_subprocess_exec(*command,'-',stdout=asyncio.subprocess.PIPE,
                                                   stderr=asyncio.subprocess.DEVNULL)
        self.mic = proc
        self.publish()
        pending = b''
        frames = 0
        try:
            while self.active and self.connected:
                chunk = await proc.stdout.read(3200)
                if not chunk:
                    if self.active:
                        raise RuntimeError('microphone capture ended unexpectedly')
                    break
                chunk = pending + chunk
                size = len(chunk)//2*2
                pending, chunk = chunk[size:],chunk[:size]
                if not chunk:
                    continue
                held = not self.config.barge_in and self.speaker.is_playing(.35)
                if held:
                    chunk = bytes(len(chunk))
                self.level(0 if held else frame_level(chunk),self.speaker.level_now())
                await self.send({'realtimeInput': {'audio': {
                    'data':base64.b64encode(chunk).decode('ascii'),'mimeType':'audio/pcm;rate=16000'}}})
                self.stats['input_bytes'] += len(chunk)
                frames += 1
                if frames % 10 == 0:
                    self.publish('speaking' if self.speaker.is_playing() else 'listening')
        finally:
            if proc.returncode is None:
                await _terminate(proc)
            if self.mic is proc:
                self.mic = None
            self.level()

    async def handle(self, raw):
        message = json.loads(raw)
        if 'toolCall' in message:
            calls = message['toolCall'].get('functionCalls',[])
            self.stats['blocked_tool_calls'] += len(calls)
            # Fail closed even if the provider sends an undeclared tool request.
            if calls:
                await self.send({'toolResponse': {'functionResponses': [
                    {'id':c.get('id',''),'name':c.get('name',''),
                     'response':{'error':'Unavailable: this service supports voice conversation only.'}} for c in calls]}})
        if 'error' in message:
            raise RuntimeError('voice provider returned an error')
        content = message.get('serverContent',{})
        if content.get('interrupted'):
            self.stats['interruptions'] += 1
            await self.speaker.interrupt()
        if self.active and not content.get('interrupted'):
            for part in content.get('modelTurn',{}).get('parts',[]):
                inline = part.get('inlineData',{})
                if inline.get('data') and inline.get('mimeType','').startswith('audio/pcm'):
                    pcm = base64.b64decode(inline['data'],validate=True)
                    if len(pcm)%2:
                        raise ValueError('incomplete PCM16 audio from provider')
                    await self.speaker.write(pcm)
                    self.stats['output_bytes'] += len(pcm)
                    self.stats['last_audio_at'] = time.time()
                    self.publish('speaking')
        if content.get('turnComplete'):
            self.publish()

    async def connect(self, key):
        url = ENDPOINT+'?key='+quote(key,safe='')
        async with websockets.connect(url,ping_interval=20,ping_timeout=20,open_timeout=20,close_timeout=3) as ws:
            self.ws = ws
            await ws.send(json.dumps(setup_message(self.config)))
            reply = json.loads(await asyncio.wait_for(ws.recv(),20))
            if 'setupComplete' not in reply:
                raise RuntimeError('provider did not acknowledge voice setup')
            self.connected = True
            self.last_error = ''
            self.stats['connections'] += 1
            self.publish('listening')
            self.mic_task = asyncio.create_task(self.capture())
            reader = asyncio.create_task(self.read_messages(ws))
            try:
                done, _ = await asyncio.wait({self.mic_task,reader},return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    if task.cancelled() and not self.active:
                        continue
                    await task
            finally:
                reader.cancel()
                await asyncio.gather(reader,return_exceptions=True)
                await self.stop_capture()

    async def read_messages(self, ws):
        async for raw in ws:
            await self.handle(raw)

    async def run(self):
        self.loop = asyncio.get_running_loop()
        key = os.environ.get(self.config.api_key_env,'')
        if not key:
            raise RuntimeError('Gemini credential is not configured')
        control = ControlServer(self.control)
        control.start()
        for sig in (signal.SIGTERM,signal.SIGINT):
            self.loop.add_signal_handler(sig,lambda: asyncio.create_task(self.quit()))
        self.publish('idle')
        if self.config.autostart_listening:
            await self.set_active(True)
        failures = 0
        try:
            while not self.quitting:
                await self.wanted.wait()
                if self.quitting:
                    break
                began = time.monotonic()
                try:
                    await self.connect(key)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if self.active:
                        self.last_error = safe_error(exc)
                        print(self.last_error,flush=True)
                finally:
                    self.ws = None
                    self.connected = False
                    await self.stop_capture()
                    await self.speaker.close()
                if self.active:
                    failures = 0 if time.monotonic()-began > 60 else failures+1
                    if failures >= 6:
                        self.active = False
                        self.wanted.clear()
                        self.last_error = 'Connection retries exhausted; toggle listening to retry'
                    self.publish('error' if self.last_error else None)
                    if self.active:
                        await asyncio.sleep(min(2**max(failures,1),30))
                else:
                    failures = 0
                    self.publish('idle')
        finally:
            await self.stop_capture()
            await self.speaker.close()
            await asyncio.to_thread(control.stop)
            self.level()
            self.active = self.connected = False
            self.publish('idle')

async def probe(config):
    """A bounded synthetic text/audio check. No microphone, playback or tools."""
    key = os.environ.get(config.api_key_env,'')
    if not key:
        raise RuntimeError('Gemini credential is not configured')
    audio = 0
    async with websockets.connect(ENDPOINT+'?key='+quote(key,safe=''),open_timeout=20,close_timeout=3) as ws:
        await ws.send(json.dumps(setup_message(config)))
        first = json.loads(await asyncio.wait_for(ws.recv(),20))
        if 'setupComplete' not in first:
            raise RuntimeError('Voice setup was not accepted')
        await ws.send(json.dumps({'clientContent':{'turns':[{'role':'user','parts':[{'text':'Say only: Voice only is ready.'}]}],'turnComplete':True}}))
        async with asyncio.timeout(35):
            async for raw in ws:
                data = json.loads(raw)
                if 'toolCall' in data:
                    raise RuntimeError('Unexpected tool call during voice-only probe')
                content = data.get('serverContent',{})
                for part in content.get('modelTurn',{}).get('parts',[]):
                    inline = part.get('inlineData',{})
                    if inline.get('mimeType','').startswith('audio/pcm'):
                        audio += len(base64.b64decode(inline.get('data','')))
                if content.get('turnComplete'):
                    break
    if not audio:
        raise RuntimeError('No spoken audio received')
    return {'setup_accepted':True,'audio_bytes':audio,'tools':0,'microphone_used':False,'playback_used':False}
