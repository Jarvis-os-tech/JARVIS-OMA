from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from jarvis_control import web_text
from jarvis_control.tools import Executor, Result
from jarvis_control.config import Config


def response(body, content_type='text/html'):
    result = BytesIO(body)
    result.headers = Message()
    result.headers['Content-Type'] = content_type
    result.geturl = lambda: 'https://example.com/'
    return result


def test_public_html_read_is_bounded_and_strips_scripts(monkeypatch):
    monkeypatch.setattr(web_text, 'public_url', lambda url: url)
    opener = Mock()
    opener.open.return_value = response(b'<h1>Example Domain</h1><script>steal secrets</script><p>Public test reference.</p><a href="/about">About</a>')
    monkeypatch.setattr(web_text, 'build_opener', lambda *args: opener)
    text = web_text.fetch_page_text('https://example.com/')
    assert 'Example Domain' in text and 'Public test reference.' in text
    assert 'steal secrets' not in text
    assert 'https://example.com/about' in text
    assert 'untrusted reference' in text


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://user:password@example.com'])
def test_fetch_rejects_nonpublic_protocol_or_embedded_credentials(url):
    with pytest.raises(web_text.PageReadError):
        web_text.public_url(url)


def test_fetch_rejects_private_dns_targets(monkeypatch):
    monkeypatch.setattr(web_text.socket, 'getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('127.0.0.1', 80))])
    with pytest.raises(web_text.PageReadError, match='public addresses'):
        web_text.public_url('http://private.example/')


@pytest.mark.parametrize('body,kind', [(b'x' * (web_text.MAX_BYTES + 1), 'text/html'), (b'%PDF test', 'application/pdf'), (b'Please verify you are human before continuing', 'text/html')])
def test_fetch_rejects_oversize_binary_and_challenge_pages(monkeypatch, body, kind):
    monkeypatch.setattr(web_text, 'public_url', lambda url: url)
    opener = Mock()
    opener.open.return_value = response(body, kind)
    monkeypatch.setattr(web_text, 'build_opener', lambda *args: opener)
    with pytest.raises(web_text.PageReadError):
        web_text.fetch_page_text('https://example.com/')


def test_short_valid_selection_is_preserved(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr('jarvis_control.tools.time.sleep', lambda _: None)
    monkeypatch.setattr(executor, '_exact_page_text', lambda target: Result(True, 'A short valid page'))
    assert executor._read_web_window({'address': '0xabc'}).output == 'A short valid page'


def test_unreadable_page_is_not_reported_as_success(monkeypatch):
    executor = Executor(Config())
    monkeypatch.setattr(executor, '_open_web_window', lambda *args, **kwargs: ({'address': '0xabc'}, ''))
    monkeypatch.setattr(executor, '_read_web_window', lambda *args, **kwargs: Result(False, 'no readable text'))
    assert not executor._tool_open_page('https://example.com').ok
    def unavailable(url):
        raise web_text.PageReadError('fixture network unavailable')
    monkeypatch.setattr(web_text, 'bounded_page_text', unavailable)
    assert not executor._tool_web_search('public information', background=False).ok



def test_dns_and_http_share_a_hard_process_deadline(monkeypatch):
    import subprocess
    def deadline(*args, **kwargs):
        assert kwargs['timeout'] == 7
        raise subprocess.TimeoutExpired(args[0], 7)
    monkeypatch.setattr(subprocess, 'run', deadline)
    with pytest.raises(web_text.PageReadError, match='deadline exceeded'):
        web_text.bounded_page_text('https://example.com')


def test_actual_private_peer_is_rejected_even_after_public_dns_check():
    connection = Mock()
    connection.sock.getpeername.return_value = ('127.0.0.1', 443)
    with pytest.raises(web_text.PageReadError, match='non-public page connection'):
        web_text.public_peer(connection)
    connection.close.assert_called_once()


def test_invalid_url_port_has_a_controlled_error():
    with pytest.raises(web_text.PageReadError):
        web_text.public_url('https://example.com:not-a-port')
