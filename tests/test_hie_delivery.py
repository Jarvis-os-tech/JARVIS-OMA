"""Delivery guidance is included in the native voice instruction."""

from voice_layer.daemon import build_instruction


def test_compiled_voice_guides_natural_task_and_explanation_delivery():
    instruction = ' '.join(build_instruction().split())

    assert 'Vary sentence length and pauses to fit the meaning' in instruction
    assert 'Keep task results concise' in instruction
    assert 'explain technical choices only as much as the question calls for' in instruction
    assert 'Keep the same JARVIS identity and conversational tone across turns and reconnects' in instruction


def test_explicit_distress_is_met_with_care_without_pitch_based_diagnosis():
    instruction = ' '.join(build_instruction().split())

    assert 'When the user explicitly says they are distressed' in instruction
    assert 'respond gently and address what they said' in instruction
    assert 'Do not infer their emotional state from pitch, loudness, accent or speaking speed' in instruction


def test_context_resolution_and_no_duplicate_acknowledgement_reach_live_instruction():
    instruction = ' '.join(build_instruction(['set_volume']).split())

    assert "Use the current conversation and fresh observations to resolve 'that', 'it'" in instruction
    assert 'ask only for the missing distinction' in instruction
    assert 'Do not speak a second acknowledgement' in instruction
