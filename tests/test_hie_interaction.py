import pytest

from voice_layer.config import Config
from voice_layer.interaction import InteractionPolicy
from voice_layer.speech import SpeechTurnGate


def test_long_narrative_gets_one_sparse_backchannel():
    policy = InteractionPolicy()
    candidate = policy.candidate(1, 'I was walking home when the rain started.', 90, 100, .8, .4)
    assert candidate == 'ack_short_hmm'
    policy.mark_played(1, 100)
    assert policy.candidate(1, 'I kept thinking about that evening.', 90, 101, .8, .4) is None
    assert policy.candidate(2, 'I was still talking through the story.', 100, 110, .8, .4) is None
    assert policy.candidate(2, 'I was still talking through the story.', 100, 121, .8, .4) == 'ack_short_hmm'


@pytest.mark.parametrize('text', [
    '', 'What happened next?', 'Could you search for it?',
    'I need you to open the file.', 'I do not want that.', 'I never asked for it.',
])
def test_questions_requests_and_negation_never_get_backchannels(text):
    assert InteractionPolicy().candidate(1, text, 90, 100, .8, .4) is None


@pytest.mark.parametrize('turn_seconds,quiet_seconds', [(7.99, .8), (9, .39)])
def test_backchannel_requires_a_long_turn_and_safe_pause(turn_seconds, quiet_seconds):
    assert InteractionPolicy().candidate(1, 'I was telling a story.', 100-turn_seconds,
                                         100, quiet_seconds, .4) is None


def test_privacy_or_disabled_setting_blocks_backchannel():
    assert InteractionPolicy().candidate(1, 'I was telling a story.', 90, 100, .8,
                                         .4, allowed=False) is None
    assert InteractionPolicy(False).candidate(
        1, 'I was telling a story.', 90, 100, .8, .4) is None


def test_default_speech_gate_keeps_short_thinking_pauses():
    assert Config().turn_silence_frames == 60
    gate = SpeechTurnGate(silence_frames=Config().turn_silence_frames)
    assert gate.silence_frames == 60


def test_missing_cache_or_privacy_can_leave_candidate_unmarked():
    policy = InteractionPolicy()
    assert policy.candidate(1, 'I was telling a story.', 90, 100, .8, .4) == 'ack_short_hmm'
    # The caller marks only after the clip is queued; an unused candidate consumes no cooldown.
    assert policy.candidate(2, 'I was telling a story.', 91, 101, .8, .4) == 'ack_short_hmm'
