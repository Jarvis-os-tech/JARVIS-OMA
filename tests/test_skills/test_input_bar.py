import asyncio
import base64
import json
import unittest
from unittest.mock import AsyncMock
from urllib.request import Request, urlopen

try:
    from skills.input_bar import TestBar as InputBar
except ImportError:
    from test_bar import TestBar as InputBar
from skills import DesktopSkills
from agent import LiveVoice


class InputBarTests(unittest.TestCase):
    def test_loopback_submission_and_voice_close(self):
        bar = InputBar()
        try: url = bar.start()
        except PermissionError: self.skipTest('loopback sockets unavailable in sandbox')
        self.addCleanup(bar.close)
        self.assertTrue(url.startswith('http://127.0.0.1:'))
        endpoint, token = url.split('/#')
        payload = json.dumps({'text':'inspect this','file':base64.b64encode(b'abc').decode(),
                              'name':'sample.bin','mime':'application/octet-stream'}).encode()
        request = Request(endpoint + '/submit', data=payload, method='POST',
                          headers={'Content-Type':'application/json','X-Jarvis-Token':token})
        self.assertEqual(urlopen(request, timeout=2).status, 202)
        self.assertEqual(bar.pop()['data'], b'abc')
        self.assertTrue(bar.close())

    def test_manifest_and_forwarding(self):
        async def run():
            skills = DesktopSkills()
            self.assertIn('open_input_bar', {item['name'] for item in skills.declarations})
            skills.test_bar.items.put({'text':'hello','data':b'','mime':'','name':''})
            player = AsyncMock(); voice = LiveVoice(player, skills=skills)
            session = AsyncMock()
            task = asyncio.create_task(voice.send_input_bar(session))
            await asyncio.sleep(.15); task.cancel()
            with self.assertRaises(asyncio.CancelledError): await task
            session.send_client_content.assert_awaited_once()
            await skills.close_agent_jobs()
        asyncio.run(run())


if __name__ == '__main__': unittest.main()
