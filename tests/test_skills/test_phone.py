import asyncio
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from connectors.phone import PhoneConnector, PhoneError, clean_phone_number
from skills import DesktopSkills


class PhoneConnectorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.contacts_path = Path(self.temp_dir.name) / "contacts.json"
        self.history_path = Path(self.temp_dir.name) / "history.json"

        # Mock contacts data
        contacts_data = {
            "contacts": [
                {
                    "name": "Dad",
                    "numbers": [{"type": "mobile", "number": "+91 99496 17551"}]
                },
                {
                    "name": "China Mama",
                    "numbers": [{"type": "mobile", "number": "0987654321"}]
                },
                {
                    "name": "Office Tech Support",
                    "numbers": [{"type": "work", "number": "+1-800-555-0199"}]
                }
            ]
        }
        self.contacts_path.write_text(json.dumps(contacts_data), encoding="utf-8")

        # Mock history data
        history_data = {
            "calls": [
                {
                    "name": "Dad",
                    "number": "+91 99496 17551",
                    "direction": "incoming",
                    "duration": 45,
                    "timestamp": 1729350000
                },
                {
                    "name": "Unknown",
                    "number": "+91 88888 77777",
                    "direction": "missed",
                    "duration": 0,
                    "timestamp": 1729353600
                }
            ]
        }
        self.history_path.write_text(json.dumps(history_data), encoding="utf-8")

        self.connector = PhoneConnector(
            contacts_path=self.contacts_path,
            history_path=self.history_path
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_clean_phone_number(self):
        self.assertEqual(clean_phone_number("+91 99496-17551"), "+919949617551")
        self.assertEqual(clean_phone_number("(800) 555-0199 ext 123"), "8005550199")
        self.assertEqual(clean_phone_number(""), "")

    def test_contact_resolution(self):
        # By exact name
        name, number = self.connector.resolve_contact("Dad")
        self.assertEqual(name, "Dad")
        self.assertEqual(clean_phone_number(number), "+919949617551")

        # Case insensitive substring
        name, number = self.connector.resolve_contact("china mama")
        self.assertEqual(name, "China Mama")
        self.assertEqual(clean_phone_number(number), "0987654321")

        # Direct phone number
        name, number = self.connector.resolve_contact("+1234567890")
        self.assertEqual(clean_phone_number(number), "+1234567890")

    def test_reverse_lookup(self):
        self.assertEqual(self.connector.resolve_number_to_name("+919949617551"), "Dad")
        self.assertEqual(self.connector.resolve_number_to_name("9949617551"), "Dad")
        self.assertEqual(self.connector.resolve_number_to_name("0000000000"), "")

    def test_list_contacts_and_history(self):
        contacts = self.connector.list_contacts(query="Dad")
        self.assertEqual(len(contacts), 1)
        self.assertEqual(contacts[0]["name"], "Dad")

        missed = self.connector.get_recent_calls(filter_type="missed")
        self.assertEqual(len(missed), 1)
        self.assertEqual(missed[0]["direction"], "missed")

    async def test_dial_success(self):
        with patch.object(self.connector, "get_gateways", new=AsyncMock(return_value=["/org/pipewire/Telephony/ag0"])), \
             patch.object(self.connector, "_run_busctl", new=AsyncMock(return_value=(0, "o /org/pipewire/Telephony/ag0/call0", ""))) as mock_busctl:
            res = await self.connector.dial("Dad")
            self.assertEqual(res["status"], "dialing")
            self.assertEqual(res["name"], "Dad")
            self.assertEqual(res["number"], "+919949617551")
            mock_busctl.assert_awaited_once()

    async def test_gateway_and_call_discovery_use_dynamic_service_methods(self):
        gateway = '/org/pipewire/Telephony/ag1'
        call = gateway + '/call2'
        replies = [
            (0, json.dumps({'type': 'a{oa{sv}}', 'data': [{gateway: {}}]}), ''),
            (0, json.dumps({'type': 'a{oa{sv}}', 'data': [{call: {
                'State': {'type': 's', 'data': 'incoming'},
                'LineIdentification': {'type': 's', 'data': '+18005550199'},
            }}]}), ''),
        ]
        with patch.object(self.connector, '_run_busctl', new=AsyncMock(side_effect=replies)) as run:
            calls = await self.connector.get_calls()
        self.assertEqual(calls, [{'path': call, 'number': '+18005550199',
                                 'name': 'Office Tech Support', 'state': 'incoming'}])
        self.assertEqual([c.args[0][-1] for c in run.await_args_list], ['GetModems', 'GetCalls'])
        self.assertTrue(all(c.args[0][0] == '--json=short' for c in run.await_args_list))

    async def test_phone_discovery_distinguishes_disconnection_from_failure(self):
        with patch.object(self.connector, '_run_busctl', new=AsyncMock(
                return_value=(0, '{"type":"a{oa{sv}}","data":[{}]}', ''))):
            self.assertEqual(await self.connector.get_gateways(), [])
        for reply in ((1, '', 'service unavailable'), (0, 'invalid json', '')):
            with self.subTest(reply=reply), patch.object(self.connector, '_run_busctl',
                    new=AsyncMock(return_value=reply)):
                with self.assertRaises(PhoneError):
                    await self.connector.get_gateways()

    async def test_missing_call_state_is_unknown_not_assumed_active(self):
        gateway = '/org/pipewire/Telephony/ag1'
        with patch.object(self.connector, 'get_gateways', new=AsyncMock(return_value=[gateway])), \
             patch.object(self.connector, '_get_objects', new=AsyncMock(return_value={gateway + '/call0': {}})):
            calls = await self.connector.get_calls()
        self.assertEqual(calls[0]['state'], 'unknown')

    async def test_answer_and_hangup(self):
        mock_calls = [{"path": "/org/pipewire/Telephony/ag0/call0", "state": "incoming", "number": "+919949617551", "name": "Dad"}]
        with patch.object(self.connector, "get_calls", new=AsyncMock(return_value=mock_calls)), \
             patch.object(self.connector, "_run_busctl", new=AsyncMock(return_value=(0, "", ""))) as mock_busctl:
            ans = await self.connector.answer()
            self.assertEqual(ans["status"], "answered")

            hup = await self.connector.hangup()
            self.assertEqual(hup["status"], "hung_up")

    async def test_send_tones(self):
        with patch.object(self.connector, "get_gateways", new=AsyncMock(return_value=["/org/pipewire/Telephony/ag0"])), \
             patch.object(self.connector, "_run_busctl", new=AsyncMock(return_value=(0, "", ""))) as mock_busctl:
            res = await self.connector.send_tones("123#")
            self.assertEqual(res["status"], "sent")
            self.assertEqual(res["digits"], "123#")


class PhoneSkillIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_file_readers_do_not_block_event_loop(self):
        skills = object.__new__(DesktopSkills)
        skills._phone = MagicMock()

        def slow_contacts(**_kwargs):
            time.sleep(0.05)
            return [{"name": "Alice"}]

        def slow_calls(**_kwargs):
            time.sleep(0.05)
            return [{"name": "Alice", "direction": "incoming"}]

        ticks = 0

        async def heartbeat():
            nonlocal ticks
            deadline = asyncio.get_running_loop().time() + 0.08
            while asyncio.get_running_loop().time() < deadline:
                ticks += 1
                await asyncio.sleep(0.005)

        with patch.object(skills.phone, "list_contacts", side_effect=slow_contacts), \
             patch.object(skills.phone, "get_recent_calls", side_effect=slow_calls):
            contacts, calls, _ = await asyncio.gather(
                skills._adapter_phone_list_contacts(),
                skills._adapter_phone_recent_calls(),
                heartbeat(),
            )

        self.assertEqual(contacts["count"], 1)
        self.assertEqual(calls["count"], 1)
        self.assertGreaterEqual(ticks, 5)

    async def test_phone_skills_registered_and_executable(self):
        skills = DesktopSkills()
        declared_names = {s["name"] for s in skills.declarations}
        expected = {
            "phone_call", "phone_answer", "phone_hangup", "phone_decline",
            "phone_mute", "phone_send_tones", "phone_list_contacts",
            "phone_recent_calls", "phone_status", "phone_open", "phone_close"
        }
        self.assertTrue(expected.issubset(declared_names), f"Missing skills: {expected - declared_names}")

        # Test phone_call execution via mock
        with patch.object(skills.phone, "dial", new=AsyncMock(return_value={"status": "dialing", "phone_number": "123"})) as mock_dial:
            res = await skills.execute("phone_call", {"recipient": "123"})
            self.assertEqual(res["status"], "dialing")
            mock_dial.assert_awaited_once_with("123")

        # Test phone_answer execution
        with patch.object(skills.phone, "answer", new=AsyncMock(return_value={"status": "answered"})) as mock_ans:
            res = await skills.execute("phone_answer", {})
            self.assertEqual(res["status"], "answered")
            mock_ans.assert_awaited_once_with(call_path=None)

        # Test phone_mute execution
        with patch.object(skills.phone, "set_mute", new=AsyncMock(return_value={"status": "muted"})) as mock_mute:
            res = await skills.execute("phone_mute", {"action": "mute"})
            self.assertEqual(res["status"], "muted")
            mock_mute.assert_awaited_once_with("mute")

        # Test phone_list_contacts execution
        with patch.object(skills.phone, "list_contacts", return_value=[{"name": "Alice"}]) as mock_list:
            res = await skills.execute("phone_list_contacts", {"query": "Alice"})
            self.assertEqual(res["count"], 1)
            self.assertEqual(res["contacts"][0]["name"], "Alice")

    async def test_monitor_phone_calls_queues_notice(self):
        from core.agent import LiveVoice
        skills = DesktopSkills()
        voice = LiveVoice(None, skills=skills)

        # The monitor stays alive after a listener disconnects.
        async def fake_listen(callback, stop_event):
            await callback({
                "event": "incoming_call",
                "call_path": "/org/pipewire/Telephony/ag0/call1",
                "number": "+919949617551",
                "name": "Dad"
            })

        with patch.object(skills.phone, "listen_for_calls", side_effect=fake_listen):
            monitor = asyncio.create_task(voice.monitor_phone_calls())
            try:
                await asyncio.wait_for(voice._notice_event.wait(), 1)
            finally:
                monitor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await monitor

        self.assertEqual(len(voice._notices), 1)
        notice_item = voice._notices[0]
        notice_text = notice_item if isinstance(notice_item, str) else notice_item["text"]
        self.assertIn("INCOMING PHONE CALL ALERT", notice_text)
        self.assertIn("Dad", notice_text)
        self.assertIn("+919949617551", notice_text)

    async def test_outgoing_call_hung_off_queues_proactive_notice(self):
        from core.agent import LiveVoice
        skills = DesktopSkills()
        voice = LiveVoice(None, skills=skills)

        async def fake_listen(callback, stop_event):
            await callback({
                "event": "outgoing_disconnected",
                "call_path": "/org/pipewire/Telephony/ag0/call2",
                "number": "+917680935265",
                "name": "Nagendra",
                "reason": "unanswered_or_rejected",
            })

        with patch.object(skills.phone, "listen_for_calls", side_effect=fake_listen):
            monitor = asyncio.create_task(voice.monitor_phone_calls())
            try:
                await asyncio.wait_for(voice._notice_event.wait(), 1)
            finally:
                monitor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await monitor

        self.assertEqual(len(voice._notices), 1)
        notice_item = voice._notices[0]
        notice_text = notice_item if isinstance(notice_item, str) else notice_item["text"]
        self.assertIn("OUTGOING PHONE CALL UPDATE", notice_text)
        self.assertIn("Nagendra", notice_text)
        self.assertIn("hung off", notice_text)

    async def test_incoming_missed_call_queues_proactive_notice(self):
        from core.agent import LiveVoice
        skills = DesktopSkills()
        voice = LiveVoice(None, skills=skills)

        async def fake_listen(callback, stop_event):
            await callback({
                "event": "incoming_missed",
                "call_path": "/org/pipewire/Telephony/ag0/call3",
                "number": "+919949617551",
                "name": "Dad",
            })

        with patch.object(skills.phone, "listen_for_calls", side_effect=fake_listen):
            monitor = asyncio.create_task(voice.monitor_phone_calls())
            try:
                await asyncio.wait_for(voice._notice_event.wait(), 1)
            finally:
                monitor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await monitor

        self.assertEqual(len(voice._notices), 1)
        notice_item = voice._notices[0]
        notice_text = notice_item if isinstance(notice_item, str) else notice_item["text"]
        self.assertIn("MISSED PHONE CALL ALERT", notice_text)
        self.assertIn("Dad", notice_text)
        self.assertIn("hung up", notice_text)

    async def test_call_connected_and_ended_queues_notices(self):
        from core.agent import LiveVoice
        skills = DesktopSkills()
        voice = LiveVoice(None, skills=skills)

        events_to_send = [
            {"event": "call_connected", "number": "+919949617551", "name": "Dad"},
            {"event": "call_ended", "number": "+919949617551", "name": "Dad", "duration": 42},
        ]

        async def fake_listen(callback, stop_event):
            for ev in events_to_send:
                await callback(ev)

        with patch.object(skills.phone, "listen_for_calls", side_effect=fake_listen):
            monitor = asyncio.create_task(voice.monitor_phone_calls())
            try:
                await asyncio.sleep(0.1)
            finally:
                monitor.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await monitor

        self.assertEqual(len(voice._notices), 2)
        connected_notice = voice._notices[0] if isinstance(voice._notices[0], str) else voice._notices[0]["text"]
        ended_notice = voice._notices[1] if isinstance(voice._notices[1], str) else voice._notices[1]["text"]
        self.assertIn("PHONE CALL CONNECTED", connected_notice)
        self.assertIn("PHONE CALL ENDED", ended_notice)
        self.assertIn("42 seconds", ended_notice)

    async def test_watch_recents_detects_hung_off_outgoing_call(self):
        temp_dir = tempfile.TemporaryDirectory()
        try:
            recents_file = Path(temp_dir.name) / "recents.json"
            recents_file.write_text("[]", encoding="utf-8")

            connector = PhoneConnector(recents_path=recents_file)
            received = []

            async def mock_callback(event_data):
                received.append(event_data)

            stop_event = asyncio.Event()
            watch_task = asyncio.create_task(connector._watch_recents(mock_callback, stop_event))

            await asyncio.sleep(0.1)

            # Simulate omyphone-helper writing a hung-off call record
            new_record = [{"number": "+917680935265", "direction": "outgoing", "start": 1792492897, "duration": 0}]
            recents_file.write_text(json.dumps(new_record), encoding="utf-8")

            # Allow watcher loop to process the file change
            for _ in range(20):
                if received:
                    break
                await asyncio.sleep(0.1)

            stop_event.set()
            await watch_task

            self.assertEqual(len(received), 1)
            self.assertEqual(received[0]["event"], "outgoing_disconnected")
            self.assertEqual(received[0]["number"], "+917680935265")
            self.assertEqual(received[0]["duration"], 0)
        finally:
            temp_dir.cleanup()

    async def test_handle_call_terminated_outgoing_unanswered(self):
        connector = PhoneConnector()
        received = []

        async def mock_callback(event_data):
            received.append(event_data)

        info = {
            "path": "/org/pipewire/Telephony/ag0/call1",
            "number": "+917680935265",
            "name": "Nagendra",
            "incoming": False,
            "answered": False,
            "declined": False,
            "hung_up_by_user": False,
            "active_at": None,
        }

        await connector._handle_call_terminated(info, info["path"], mock_callback)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["event"], "outgoing_disconnected")
        self.assertEqual(received[0]["name"], "Nagendra")
        self.assertEqual(received[0]["reason"], "unanswered_or_rejected")


if __name__ == "__main__":
    unittest.main()
