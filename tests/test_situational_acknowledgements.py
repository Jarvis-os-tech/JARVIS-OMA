from types import SimpleNamespace as NS

import pytest

from voice_layer.acknowledgements import PHRASES, select_ack, short_ack
from voice_layer.daemon import LiveVoice
from voice_layer.playback import Playback


@pytest.mark.parametrize('tool,args,expected', [
    ('web_search', {}, 'ack_search'), ('read_file', {}, 'ack_file'),
    ('search_files', {}, 'ack_files'),
    ('read_screen', {}, 'ack_screen'), ('run_in_terminal', {}, 'ack_terminal'),
    ('start_hermes_goal', {}, 'ack_agent'), ('launch_app', {}, 'ack_app'),
    ('open_application', {}, 'ack_app'), ('set_volume', {}, 'ack_volume'),
    ('set_brightness', {}, 'ack_brightness'), ('switch_workspace', {}, 'ack_workspace'),
    ('inspect_screen', {}, 'ack_screen'), ('internet_search', {}, 'ack_search'),
    ('system_control', {'action': 'volume_set'}, 'ack_volume'),
    ('system_control', {'action': 'volume_get'}, 'ack_general_2'),
    ('system_control', {'action': 'brightness_adjust'}, 'ack_brightness'),
    ('system_control', {'action': 'workspace_switch'}, 'ack_workspace'),
])
def test_phrase_describes_the_admitted_task(tool, args, expected):
    assert select_ack(tool, arguments=args) == expected


@pytest.mark.parametrize('text,expected', [
    ('Please analyze the report', 'ack_general_0'),
    ('Look up the weather', 'ack_general_0'),
    ('Do not search online', 'ack_general_0'),
    ('dont search online', 'ack_general_0'),
    ('Explain what search means', 'ack_general_0'),
    ('What do you think?', 'ack_general_0'),
])
def test_transcript_hints_do_not_turn_negation_into_actions(text, expected):
    assert select_ack('generic_deep_thought', text) == expected


def test_admitted_contextual_phrase_is_queued_immediately_and_only_once():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    contextual_pcm = b'\x03\x00' * 480
    voice._reply_notices = {'ack_search': contextual_pcm, 'ack_short_on_it': b'\x04\x00' * 480}
    assert voice._acknowledge_task_start('web_search')
    assert voice.player.queue.get_nowait()[1] == contextual_pcm
    assert voice.last_acknowledgement == PHRASES['ack_search']
    assert not voice._reply_started
    assert not voice._acknowledge_task_start('web_search')
    assert voice.player.queue.empty()


def test_generic_transcript_does_not_select_action_claim():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    voice._user_text = 'Please analyze the report and look up the weather'
    generic_pcm = b'\x05\x00' * 480
    voice._reply_notices = {'ack_short_sure': generic_pcm}
    assert voice._play_filler_reflex('generic_deep_thought')
    assert voice.player.queue.get_nowait()[1] == generic_pcm
    assert voice.last_acknowledgement in {
        PHRASES['ack_short_sure'], PHRASES['ack_short_hmm'],
        PHRASES['ack_short_okay'],
    }


def test_conversational_questions_do_not_select_action_assents():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    voice._user_text = 'What time is it?'
    hmm_pcm = b'\x06\x00' * 480
    voice._reply_notices = {'ack_short_hmm': hmm_pcm, 'ack_short_sure': b'\x05\x00' * 480}
    assert voice._play_filler_reflex('generic_deep_thought')
    assert voice.player.queue.get_nowait()[1] == hmm_pcm
    assert voice.last_acknowledgement == PHRASES['ack_short_hmm']
    assert voice.last_acknowledgement != PHRASES['ack_short_sure']
    assert voice.last_acknowledgement != PHRASES['ack_short_okay']


def test_meaningful_speech_is_not_replaced_with_a_filler():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = voice._reply_started = True
    assert not voice._acknowledge_task_start('web_search')
    assert voice.player.queue.empty()


def test_same_task_varies_short_words_across_turns():
    previous = ''
    clips = []
    for _ in range(8):
        previous = short_ack('ack_search', previous)
        clips.append(previous)
    assert all(a != b for a, b in zip(clips, clips[1:]))
    assert len(set(clips)) == 4


def test_all_contextual_phrases_are_cached_as_non_silent_pcm():
    import json
    import hashlib
    from pathlib import Path
    import struct
    root = Path(__file__).resolve().parents[1] / 'voice_layer/assets'
    manifest = json.loads((root / 'acknowledgements.json').read_text())
    assert set(manifest) == set(PHRASES)
    for name, text in PHRASES.items():
        pcm = (root / (name + '.pcm')).read_bytes()
        assert manifest[name]['text'] == text
        assert manifest[name]['sha256'] == hashlib.sha256(pcm).hexdigest()
        assert 960 <= len(pcm) <= 240000 and len(pcm) % 2 == 0
        assert max(abs(sample[0]) for sample in struct.iter_unpack('<h', pcm)) > 100


def test_generic_wait_words_do_not_promise_execution():
    previous = ''
    for _ in range(6):
        previous = short_ack('ack_general_0', previous)
        assert previous in {'ack_short_sure', 'ack_short_okay', 'ack_short_hmm'}
