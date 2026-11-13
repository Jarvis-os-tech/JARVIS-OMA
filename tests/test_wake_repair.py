"""Wake controls must not reconnect into mute or confuse silence with a greeting."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from voice_layer.ipc import ControlServer
from voice_layer.standby import LocalPhraseDetector, StandbyController, WakeWordUnavailable


@pytest.mark.asyncio
@pytest.mark.parametrize('command', ['wake', 'standby off', 'resume', 'listen toggle',
    '{"command":"wake"}', '{"command":"standby_toggle"}'])
@pytest.mark.parametrize('muted', [False, True])
async def test_waking_from_standby_clears_soft_mute_without_toggling_it_back(command, muted):
    controller = StandbyController(detector=object())
    await controller.request()
    state = {'muted': muted}
    toggles = []
    def set_mute(value): state['muted'] = value
    def toggle_mute():
        toggles.append(True)
        state['muted'] = not state['muted']
        return state['muted']
    server = ControlServer(status_provider=lambda: {**state, 'standby': controller.engaged},
        wake_cb=controller.wake, standby_toggle_cb=controller.toggle,
        set_mute_cb=set_mute, toggle_mute_cb=toggle_mute)
    result = server._dispatch(command)
    if asyncio.iscoroutine(result): result = await result
    assert json.loads(result)['standby'] is False
    assert not controller.engaged
    assert state['muted'] is False
    assert not toggles


@pytest.mark.asyncio
async def test_standby_shortcut_recovers_muted_awake_voice_instead_of_sleeping():
    controller = StandbyController(detector=object())
    state = {'muted': True}
    server = ControlServer(status_provider=lambda: {**state, 'standby': controller.engaged},
        wake_cb=controller.wake, standby_toggle_cb=controller.toggle,
        set_mute_cb=lambda value: state.update(muted=value))
    result = json.loads(await server._dispatch('standby toggle'))
    assert result['standby'] is False and not state['muted']
    assert not controller.engaged


class Recognizer:
    def __init__(self, text, words, final):
        self.final = final
        self.result = json.dumps({('text' if final else 'partial'): text,
                                 ('result' if final else 'partial_result'): words})
        self.resets = 0
    def Reset(self): self.resets += 1
    def AcceptWaveform(self, pcm): return self.final
    def Result(self): return self.result
    def PartialResult(self): return self.result


@pytest.mark.parametrize('phrase', ['hey jarvis', 'hello jarvis'])
@pytest.mark.parametrize('final', [False, True])
def test_both_greetings_require_identified_words_with_confidence(phrase, final):
    recognizer = Recognizer(phrase, [{'word': w, 'conf': .95} for w in phrase.split()], final)
    detector = LocalPhraseDetector(recognizer=recognizer)
    assert detector.process(bytes(640))
    assert detector.last_phrase == phrase
    detector.reset()
    assert detector.last_phrase == '' and recognizer.resets == 2


@pytest.mark.parametrize('phrase,words', [
    ('hello there', [{'word': 'hello', 'conf': 1}, {'word': 'there', 'conf': 1}]),
    ('jarvis', [{'word': 'jarvis', 'conf': 1}]),
    ('goodbye jarvis', [{'word': 'goodbye', 'conf': 1}, {'word': 'jarvis', 'conf': 1}]),
    ('hello jarvis', []),
    ('hey jarvis', [{'word': 'hey', 'conf': .9}, {'word': 'jarvis', 'conf': .5}]),
    ('hey jarvis', [{'word': 'hey', 'conf': .9}, {'word': 'jarvis', 'conf': True}]),
    ('hey jarvis', [{'word': 'hey', 'conf': .9}, {'word': 'jarvis', 'conf': float('nan')}]),
])
def test_partial_or_uncertain_greetings_do_not_wake(phrase, words):
    detector = LocalPhraseDetector(recognizer=Recognizer(phrase, words, False))
    assert not detector.process(bytes(640))


@pytest.mark.asyncio
async def test_capture_eof_is_a_failure_not_a_successful_wake():
    stream = asyncio.StreamReader()
    stream.feed_eof()
    controller = StandbyController(detector=SimpleNamespace(reset=lambda: None), arming_delay=0)
    await controller.request()
    with pytest.raises(WakeWordUnavailable, match='microphone stream ended'):
        await controller.listen_for_wake_word(stream)
