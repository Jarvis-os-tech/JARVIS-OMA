from voice_layer.daemon import build_instruction


def test_youtube_connection_claim_requires_observed_status():
    instruction = build_instruction([{'function_declarations': [{'name': 'yt_brain_status'}]}])
    assert 'call yt_brain_status first' in instruction
    assert 'only when the worker is reachable and reports success' in instruction
    assert 'confirm warmly and directly that you are connected' not in instruction
    assert 'You ARE directly connected' not in instruction
