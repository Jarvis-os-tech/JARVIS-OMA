import pytest
from jarvis_control.nlu import NLUEngine, IntentCategory


def test_phonetic_normalization():
    assert NLUEngine.normalize_text("Gervais, what time is it?") == "Jarvis, what time is it?"
    assert NLUEngine.normalize_text("Hey Gervais") == "Hey Jarvis"
    assert NLUEngine.normalize_text("The reason why it's showingspot") == "The reason why it's hotspot"
    assert NLUEngine.normalize_text("Tell me about padmasana") == "Tell me about Padmasana lotus pose"


def test_hinglish_inquiry_analysis():
    res = NLUEngine.analyze("Hum kya kare ringtone")
    assert res.category == IntentCategory.CONVERSATIONAL
    assert res.is_conversational_inquiry is True
    assert res.entities.get('topic') == 'ringtone'


def test_connection_problem_report_analysis():
    res = NLUEngine.analyze("But it's still showing the PC unavailable connection. The reason why it's showingspot")
    assert res.category == IntentCategory.CONVERSATIONAL
    assert res.is_conversational_inquiry is True
    assert res.entities.get('topic') == 'network_connection'


def test_explicit_pairing_analysis():
    res1 = NLUEngine.analyze("Open the QR code.")
    assert res1.category == IntentCategory.PHONE_PAIRING
    assert res1.suggested_action == "phone_pair"

    res2 = NLUEngine.analyze("Pair my phone")
    assert res2.category == IntentCategory.PHONE_PAIRING
    assert res2.suggested_action == "phone_pair"


def test_hinglish_control_commands():
    res_vol = NLUEngine.analyze("Awaaz badhao")
    assert res_vol.category == IntentCategory.SYSTEM_CONTROL
    assert res_vol.suggested_action == "volume_up"

    res_stop = NLUEngine.analyze("Chup raho")
    assert res_stop.category == IntentCategory.STANDBY
    assert res_stop.suggested_action == "enter_standby"


def test_validate_tool_intent_blocks_unwanted_pairing():
    # User is explaining a connection issue, model tries to call phone_pair
    user_text = "But it's still showing the PC unavailable connection. The reason why it's showingspot"
    allowed, guidance = NLUEngine.validate_tool_intent("phone_pair", {}, user_text)
    assert allowed is False
    assert "The user did NOT command to open or scan the pairing QR code" in guidance


def test_validate_tool_intent_allows_explicit_pairing():
    user_text = "Please open the QR code to pair my phone"
    allowed, guidance = NLUEngine.validate_tool_intent("phone_pair", {}, user_text)
    assert allowed is True
    assert guidance == ""


def test_validate_tool_intent_blocks_intrusive_tools_for_conversational_questions():
    user_text = "Hum kya kare ringtone"
    allowed_contacts, guidance1 = NLUEngine.validate_tool_intent("phone_list_contacts", {}, user_text)
    assert allowed_contacts is False
    assert "The user is asking a conversational question" in guidance1

    allowed_media, guidance2 = NLUEngine.validate_tool_intent("system_control_extension", {"action": "list", "category": "media"}, user_text)
    assert allowed_media is False
    assert "The user is asking a conversational question" in guidance2


def test_validate_tool_intent_blocks_github_authorize_on_repo_scan():
    user_text = "Jarvis, to scan the agent's repository and provide the clear report on that."
    allowed, guidance = NLUEngine.validate_tool_intent("github_authorize", {}, user_text)
    assert allowed is False
    assert "Do NOT invoke github_authorize" in guidance
    assert "local on this PC" in guidance


def test_validate_tool_intent_allows_explicit_github_login():
    user_text = "Please authorize github so we can sync issues"
    allowed, guidance = NLUEngine.validate_tool_intent("github_authorize", {}, user_text)
    assert allowed is True
    assert guidance == ""


def test_standby_farewells():
    for phrase in ["I have to go.", "Goodbye Jarvis", "Bye bye", "See you later", "Chalta hoon"]:
        res = NLUEngine.analyze(phrase)
        assert res.category == IntentCategory.STANDBY
        allowed, _ = NLUEngine.validate_tool_intent("enter_standby", {}, phrase)
        assert allowed is True


@pytest.mark.parametrize('text', [
    'Could you increase the volume?', 'Jarvis, please open the browser.',
    'Can you set brightness to forty percent?', 'First send hi message to me.',
    'Please play the next song.',
])
def test_polite_action_requests_are_not_classified_as_advice(text):
    result = NLUEngine.analyze(text)
    assert not result.is_conversational_inquiry
    allowed, _ = NLUEngine.validate_tool_intent(
        'system_control_extension', {'action': 'next', 'category': 'media'}, text)
    assert allowed


@pytest.mark.parametrize('text', [
    '', 'Open WhatsApp', 'Increase volume', 'What is my PC connection status?',
    'Open the browser, not on my phone', 'Do not use my phone; open the browser on my PC',
    'Type "open it on my phone" in the editor',
])
def test_phone_control_requires_explicit_current_phone_target(text):
    allowed, guidance = NLUEngine.validate_tool_intent('phone_control', {'action': 'status'}, text)
    assert not allowed
    assert 'PC' in guidance


@pytest.mark.parametrize('text', [
    'Open WhatsApp on my phone', 'On my mobile, open the browser',
    'Check my Android phone connection', 'Increase volume on my phone',
])
def test_explicit_phone_target_allows_phone_tools(text):
    assert NLUEngine.validate_tool_intent('phone_control', {'action': 'status'}, text)[0]


def test_phone_domain_wrapper_cannot_bypass_device_routing():
    args = {'domain': 'phone', 'tool_name': 'phone_pair', 'arguments_json': '{}'}
    assert not NLUEngine.validate_tool_intent('execute_domain_tool', args, 'Open the browser')[0]


def test_explicit_phone_app_request_cannot_use_pc_launcher():
    assert not NLUEngine.validate_tool_intent('launch_app', {'app': 'WhatsApp'},
                                            'Open WhatsApp on my phone')[0]


def test_troubleshooting_with_embedded_action_stays_conversational():
    result = NLUEngine.analyze('Why does increasing the volume not work?')
    assert result.is_conversational_inquiry


@pytest.mark.parametrize('text,expected_action', [
    ('actavtethe testing mood', 'switch_to_test_mode'),
    ('activate the testing mood', 'switch_to_test_mode'),
    ('activate testing mode', 'switch_to_test_mode'),
    ('switch to dev mode', 'switch_to_test_mode'),
    ('activate production mode', 'switch_to_production_mode'),
    ('switch to production mode', 'switch_to_production_mode'),
    ('what mode are you in', 'get_jarvis_mode'),
    ('jarvis mode status', 'get_jarvis_mode'),
    ('check mode', 'get_jarvis_mode'),
])
def test_jarvis_mode_voice_phrases(text, expected_action):
    result = NLUEngine.analyze(text)
    assert result.category == IntentCategory.SYSTEM_CONTROL
    assert result.suggested_action == expected_action


