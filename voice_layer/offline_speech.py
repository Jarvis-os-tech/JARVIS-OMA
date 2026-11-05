"""Small offline voice used only for grounded local command results."""
import ctypes
from pathlib import Path


class OfflineSpeech:
    def __init__(self):
        import espeakng_loader
        self.library = espeakng_loader.load_library()
        if self.library is None:
            raise RuntimeError('Offline speech library unavailable')
        lib = self.library
        lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
        lib.espeak_Initialize.restype = ctypes.c_int
        parent = str(Path(espeakng_loader.get_data_path()).parent).encode()
        self.sample_rate = lib.espeak_Initialize(2, 0, parent, 0x8000)
        if self.sample_rate <= 0:
            raise RuntimeError('Offline speech initialization failed')
        lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
        if lib.espeak_SetVoiceByName(b'en-us') != 0:
            raise RuntimeError('Offline English voice unavailable')
        self._chunks = []
        callback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
        def collect(samples, count, events):
            if samples and count:
                self._chunks.append(ctypes.string_at(samples, count * 2))
            return 0
        self._callback = callback(collect)
        lib.espeak_SetSynthCallback.argtypes = [callback]
        lib.espeak_SetSynthCallback(self._callback)
        lib.espeak_Synth.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint, ctypes.c_int,
                                    ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
        lib.espeak_Synth.restype = ctypes.c_int

    def synthesize(self, text):
        if not isinstance(text, str) or not text or len(text) > 180:
            raise ValueError('Invalid bounded speech text')
        import numpy as np
        self._chunks = []
        data = text.encode('utf-8') + b'\0'
        if self.library.espeak_Synth(data, len(data), 0, 1, 0, 1, None, None) != 0:
            raise RuntimeError('Offline speech synthesis failed')
        pcm = np.frombuffer(b''.join(self._chunks), dtype='<i2')
        if not len(pcm):
            return b''
        count = round(len(pcm) * 24000 / self.sample_rate)
        return np.interp(np.arange(count) * self.sample_rate / 24000,
                         np.arange(len(pcm)), pcm).astype('<i2').tobytes()


def result_text(name, arguments, outcome):
    if not outcome.completed:
        return 'I could not verify that the local command completed.'
    if name == 'launch_app':
        return 'The requested application is open.'
    if name == 'system_control':
        action = arguments.get('action', '')
        if action in ('volume_set', 'brightness_set'):
            return f"{action.split('_')[0].capitalize()} set to {arguments['value']} percent."
        if action in ('volume_adjust', 'brightness_adjust'):
            direction = 'increased' if arguments['value'] > 0 else 'decreased'
            return f"{action.split('_')[0].capitalize()} {direction}."
        if action == 'workspace_switch':
            return f"Switched to workspace {arguments['workspace']}."
        if action == 'mute_set':
            return 'Speakers muted.' if arguments['enabled'] else 'Speakers unmuted.'
    return 'The local command completed.'
