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
