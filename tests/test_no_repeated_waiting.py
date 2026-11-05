from jarvis_voice.daemon import LiveVoice, build_instruction
from jarvis_voice.playback import Playback


def test_waiting_recording_cannot_be_reintroduced_by_any_caller():
    voice = LiveVoice(Playback('test'))
    voice._reply_authorized = True
    voice._reply_notices['reply_waiting'] = bytes(48000)
    for _ in range(3):
        assert voice._play_reply_notice('reply_waiting') == 0
    assert voice.player.queue.empty()


def test_provider_is_told_to_return_results_instead_of_repeated_waiting():
    instruction = build_instruction()
    assert "Never say 'I am still working on your request'" in instruction
    assert 'verify an active tool or job' in instruction


def test_general_acknowledgements_do_not_repeat_the_same_word_every_turn():
    voice = LiveVoice(Playback('test'))
    clips = []
    for _ in range(3):
        voice._start_reply_watch()
        voice._reply_authorized = True
        assert voice._play_filler_reflex()
        queued = b''.join(chunk for _, chunk in voice.player.queue._queue)
        clips.append(next(name for name, pcm in voice._reply_notices.items() if pcm == queued))
        voice.player.cancel_pending()
    assert len(set(clips)) == 3
