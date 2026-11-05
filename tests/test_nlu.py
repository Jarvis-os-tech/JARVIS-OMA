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


@pytest.mark.parametrize('phrase', [
    "Don't speak until I call you", 'Do not talk until I wake you',
    'Don’t respond again until I say Hey Jarvis',
])
def test_natural_request_to_wait_until_recalled_is_allowed(phrase):
    assert NLUEngine.analyze(phrase).category == IntentCategory.STANDBY
    assert NLUEngine.validate_tool_intent('enter_standby', {}, phrase)[0]


@pytest.mark.parametrize('phrase', [
    'Stop talking', "That's enough", 'Wait, I meant the other window',
    "Don't speak until I finish this sentence",
])
def test_stopping_current_answer_does_not_authorize_standby(phrase):
    assert not NLUEngine.validate_tool_intent('enter_standby', {}, phrase)[0]


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


def test_validate_tool_intent_redirects_website_for_platform_connect():
    user_text = "Jarvis, connect to LinkedIn"
    allowed, guidance = NLUEngine.validate_tool_intent("open_website", {"url": "https://linkedin.com"}, user_text)
    assert allowed is False
    assert "connect_platform" in guidance
    assert "linkedin" in guidance


def test_validate_tool_intent_redirects_for_authorization_page():
    user_text = "Open specific platform authorization page"
    allowed, guidance = NLUEngine.validate_tool_intent("open_website", {"url": "https://example.com"}, user_text)
    assert allowed is False
    assert "open_platform_authorization" in guidance or "connect_platform" in guidance


def test_validate_tool_intent_redirects_for_connection_status():
    user_text = "Is LinkedIn connected or not?"
    allowed, guidance = NLUEngine.validate_tool_intent("open_website", {"url": "https://linkedin.com"}, user_text)
    assert allowed is False
    assert "check_platform_connection" in guidance


def test_validate_tool_intent_allows_platform_tools():
    assert NLUEngine.validate_tool_intent("connect_platform", {"platform": "linkedin"}, "connect to linkedin")[0] is True
    assert NLUEngine.validate_tool_intent("open_platform_authorization", {"platform": "slack"}, "open slack auth page")[0] is True
    assert NLUEngine.validate_tool_intent("check_platform_connection", {"platform": "slack"}, "is slack connected")[0] is True


def test_validate_tool_intent_native_github_and_google_routing():
    # GitHub auth words allow native github_authorize
    assert NLUEngine.validate_tool_intent("github_authorize", {}, "open github auth page")[0] is True
    assert NLUEngine.validate_tool_intent("github_authorize", {}, "authorize github account")[0] is True
    assert NLUEngine.validate_tool_intent("github_authorize", {}, "connect github")[0] is True

    # Google auth words allow native google_authorize
    assert NLUEngine.validate_tool_intent("google_authorize", {}, "open google authorization page")[0] is True
    assert NLUEngine.validate_tool_intent("google_authorize", {}, "connect google workspace")[0] is True

    # Composio auth tools for GitHub and Google must redirect to native tools
    allowed_gh, msg_gh = NLUEngine.validate_tool_intent("open_platform_authorization", {"platform": "github"}, "open github auth page")
    assert allowed_gh is False
    assert "github_authorize" in msg_gh

    allowed_gw, msg_gw = NLUEngine.validate_tool_intent("open_platform_authorization", {"platform": "google"}, "open google auth page")
    assert allowed_gw is False
    assert "google_authorize" in msg_gw

    # Composio status tool for GitHub and Google must redirect to native status tools
    allowed_gh_s, msg_gh_s = NLUEngine.validate_tool_intent("check_platform_connection", {"platform": "github"}, "check github status")
    assert allowed_gh_s is False
    assert "github_connection_status" in msg_gh_s

    allowed_gw_s, msg_gw_s = NLUEngine.validate_tool_intent("check_platform_connection", {"platform": "google"}, "check google status")
    assert allowed_gw_s is False
    assert "google_connection_status" in msg_gw_s


def test_validate_tool_intent_blocks_auth_page_without_auth_keyword():
    # User asks general repo/calendar question without auth keyword -> auth page tools blocked
    allowed_gh, msg_gh = NLUEngine.validate_tool_intent("github_authorize", {}, "what repositories do i have on github?")
    assert allowed_gh is False
    assert "Do NOT invoke github_authorize" in msg_gh

    allowed_gw, msg_gw = NLUEngine.validate_tool_intent("google_authorize", {}, "show my calendar events on google")
    assert allowed_gw is False
    assert "did not mention any authorization-related keyword" in msg_gw

    allowed_pl, msg_pl = NLUEngine.validate_tool_intent("open_platform_authorization", {"platform": "spotify"}, "play music on spotify")
    assert allowed_pl is False
    assert "did not mention any authorization-related keyword" in msg_pl


def test_validate_tool_intent_blocks_auth_page_on_status_inquiries():
    # Asking whether it is connected or connecting must NOT open the authorization page
    for phrase in [
        "is it connecting to those or not",
        "check if github is connected or not",
        "connecting to those or not",
        "is github connected",
    ]:
        allowed_gh, msg_gh = NLUEngine.validate_tool_intent("github_authorize", {}, phrase)
        assert allowed_gh is False
        assert "github_connection_status" in msg_gh

    for phrase in [
        "is google connected or not",
        "is google connecting or not",
        "check connection status of google",
    ]:
        allowed_gw, msg_gw = NLUEngine.validate_tool_intent("google_authorize", {}, phrase)
        assert allowed_gw is False
        assert "google_connection_status" in msg_gw

    for phrase in [
        "is notion connected or connecting",
        "is linkedin connecting to those or not",
        "check connection status of slack",
    ]:
        allowed_p, msg_p = NLUEngine.validate_tool_intent("open_platform_authorization", {"platform": "notion"}, phrase)
        assert allowed_p is False
        assert "check_platform_connection" in msg_p


@pytest.mark.parametrize("text,expected_action", [
    ("shudown the pc", "shutdown"),
    ("shut down the computer", "shutdown"),
    ("power off", "shutdown"),
    ("restart the pc", "restart"),
    ("reboot the computer", "restart"),
    ("reboot the system", "restart"),
    ("lock the screnn", "lock_screen"),
    ("lock screen", "lock_screen"),
    ("lock the screen", "lock_screen"),
    ("lock pc", "lock_screen"),
    ("confirm", "confirm_action"),
    ("yes", "confirm_action"),
    ("proceed", "confirm_action"),
    ("cancel", "cancel_action"),
    ("abort", "cancel_action"),
])
def test_power_and_confirmation_nlu_classification(text, expected_action):
    result = NLUEngine.analyze(text)
    assert result.category == IntentCategory.SYSTEM_CONTROL
    assert result.suggested_action == expected_action


def test_phonetic_misspellings_power_and_confirmation():
    assert "shutdown" in NLUEngine.normalize_text("shudown the computer")
    assert "screen" in NLUEngine.normalize_text("lock the screnn")
    assert "confirmation" in NLUEngine.normalize_text("with conformation")




