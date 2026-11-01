from jarvis_voice.daemon import build_instruction


def test_android_control_is_distinguished_from_bluetooth_calls():
    prompt = build_instruction([{'function_declarations': [{'name': 'phone_control'}, {'name': 'phone_status'}]}])
    assert 'PAIRED ANDROID PHONE CONTROL' in prompt
    assert 'disconnected Bluetooth calling gateway does NOT' in prompt
    assert 'phone_control(action=status)' in prompt
    assert 'list_workspaces, launch_app and read_screen act on the PC' in prompt


def test_unattached_android_control_is_not_claimed():
    prompt = build_instruction([{'function_declarations': [{'name': 'phone_status'}]}])
    assert 'PAIRED ANDROID PHONE CONTROL' not in prompt


def test_pc_keeps_omyphone_calls_and_routes_explicit_phone_calls_natively():
    prompt = build_instruction([{'function_declarations': [{'name': 'phone_control'}, {'name': 'phone_call'}]}])
    assert 'Normal PC call requests continue to use OMyPhone/phone_call' in prompt
    assert 'phone_control(action=call_contact' in prompt
