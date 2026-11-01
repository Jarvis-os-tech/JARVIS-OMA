"""Loopback-only multimodal input bar for an active JARVIS voice session."""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import secrets
import threading

MAX_BODY = 12 * 1024 * 1024
PAGE = b'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JARVIS Input Bar</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  width: 100%;
  height: 100%;
  background: transparent !important;
  color: #f1f5f9;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "JetBrains Mono", monospace;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  user-select: none;
}
.hud-bar {
  width: calc(100% - 8px);
  height: 44px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(9, 14, 26, 0.96);
  border: 1px solid rgba(0, 240, 255, 0.4);
  border-radius: 9999px;
  padding: 4px 6px 4px 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.8), 0 0 16px rgba(0, 240, 255, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.12);
  transition: border-color 0.18s, box-shadow 0.18s, background-color 0.18s;
}
.hud-bar:focus-within {
  border-color: rgba(0, 240, 255, 0.85);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.9), 0 0 25px rgba(0, 240, 255, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.18);
}
.hud-bar.dragover {
  border-color: #00f0ff;
  border-style: dashed;
  background: rgba(0, 240, 255, 0.15);
  box-shadow: 0 0 30px rgba(0, 240, 255, 0.5);
}
.hud-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  background: rgba(0, 240, 255, 0.1);
  border: 1px solid rgba(0, 240, 255, 0.3);
  border-radius: 9999px;
  color: #00f0ff;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
  transition: color 0.2s, border-color 0.2s;
}
.hud-dot {
  width: 6px;
  height: 6px;
  background: #00f0ff;
  border-radius: 50%;
  box-shadow: 0 0 8px #00f0ff;
  animation: pulse 1.8s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.8); }
}
.hud-badge.sending { color: #fbbf24; border-color: #fbbf24; }
.hud-badge.sending .hud-dot { background: #fbbf24; box-shadow: 0 0 8px #fbbf24; }
.hud-badge.sent { color: #34d399; border-color: #34d399; }
.hud-badge.sent .hud-dot { background: #34d399; box-shadow: 0 0 8px #34d399; }
.hud-badge.err { color: #f87171; border-color: #f87171; }
.hud-badge.err .hud-dot { background: #f87171; box-shadow: 0 0 8px #f87171; }

#t {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #f8fafc;
  font-size: 14px;
  font-family: inherit;
  padding: 4px;
  min-width: 0;
}
#t::placeholder { color: #64748b; }

.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 7px;
  background: rgba(0, 240, 255, 0.12);
  border: 1px solid rgba(0, 240, 255, 0.35);
  border-radius: 6px;
  color: #00f0ff;
  font-size: 11px;
  max-width: 140px;
  flex-shrink: 0;
}
.chip-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.chip-rm {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  padding: 0 1px;
}
.chip-rm:hover { color: #f43f5e; }

.btn-attach {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
  color: #94a3b8;
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.btn-attach:hover {
  color: #00f0ff;
  border-color: rgba(0, 240, 255, 0.45);
  background: rgba(0, 240, 255, 0.1);
  box-shadow: 0 0 10px rgba(0, 240, 255, 0.25);
}
.btn-attach.has-file {
  color: #00f0ff;
  border-color: #00f0ff;
  background: rgba(0, 240, 255, 0.15);
}

.btn-send {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 7px 15px;
  background: linear-gradient(135deg, #00f0ff 0%, #0284c7 100%);
  color: #030712;
  border: none;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all 0.15s ease;
  box-shadow: 0 0 14px rgba(0, 240, 255, 0.35);
  flex-shrink: 0;
}
.btn-send:hover {
  background: linear-gradient(135deg, #38bdf8 0%, #0ea5e9 100%);
  box-shadow: 0 0 20px rgba(0, 240, 255, 0.6);
  transform: translateY(-1px);
}
.btn-send:active { transform: translateY(0); }
.btn-send:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}
</style>
</head>
<body>
<div id="hud-bar" class="hud-bar">
  <div id="badge" class="hud-badge"><span class="hud-dot"></span><span id="badge-text">JARVIS</span></div>
  <input id="t" type="text" autofocus placeholder="Transmit to JARVIS... (Enter to send, Esc to close)" autocomplete="off" spellcheck="false">
  <div id="chip" class="chip" style="display:none">
    <span id="chip-name" class="chip-name"></span>
    <button id="chip-rm" class="chip-rm" type="button" title="Remove attachment">&times;</button>
  </div>
  <label id="btn-attach" for="f" class="btn-attach" title="Attach file (10MB max)">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
  </label>
  <input id="f" type="file" style="display:none">
  <button id="s" class="btn-send" title="Send (Enter)">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
    <span>SEND</span>
  </button>
</div>
<script>
const token = location.hash.slice(1);
const hudBar = document.getElementById('hud-bar');
const badge = document.getElementById('badge');
const badgeText = document.getElementById('badge-text');
const t = document.getElementById('t');
const f = document.getElementById('f');
const s = document.getElementById('s');
const chip = document.getElementById('chip');
const chipName = document.getElementById('chip-name');
const chipRm = document.getElementById('chip-rm');
const btnAttach = document.getElementById('btn-attach');

let activeFile = null;

function setBadge(state, text) {
  badge.className = 'hud-badge ' + (state || '');
  badgeText.textContent = text || 'JARVIS';
}

function setFile(file) {
  if (!file) {
    activeFile = null;
    chip.style.display = 'none';
    btnAttach.classList.remove('has-file');
    f.value = '';
    return;
  }
  if (file.size > 10485760) {
    setBadge('err', 'TOO LARGE');
    setTimeout(() => setBadge('', 'JARVIS'), 2500);
    return;
  }
  activeFile = file;
  chipName.textContent = file.name || 'file';
  chip.style.display = 'inline-flex';
  btnAttach.classList.add('has-file');
}

f.onchange = () => { if (f.files[0]) setFile(f.files[0]); };
chipRm.onclick = () => setFile(null);

window.ondragover = (e) => { e.preventDefault(); hudBar.classList.add('dragover'); };
window.ondragleave = (e) => { if (e.relatedTarget === null) hudBar.classList.remove('dragover'); };
window.ondrop = (e) => {
  e.preventDefault();
  hudBar.classList.remove('dragover');
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]) {
    setFile(e.dataTransfer.files[0]);
  }
};

window.addEventListener('paste', (e) => {
  if (e.clipboardData && e.clipboardData.files && e.clipboardData.files.length > 0) {
    e.preventDefault();
    setFile(e.clipboardData.files[0]);
  }
});

async function send() {
  const text = t.value;
  if (!text.trim() && !activeFile) return;
  s.disabled = true;
  setBadge('sending', 'SENDING');
  let data = null;
  if (activeFile) {
    try {
      data = await new Promise((ok, no) => {
        const r = new FileReader();
        r.onload = () => ok(r.result.split(',')[1]);
        r.onerror = no;
        r.readAsDataURL(activeFile);
      });
    } catch {
      setBadge('err', 'READ ERR');
      s.disabled = false;
      return;
    }
  }
  try {
    const res = await fetch('/submit', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Jarvis-Token': token
      },
      body: JSON.stringify({
        text: text,
        file: data,
        name: activeFile ? (activeFile.name || '') : '',
        mime: activeFile ? (activeFile.type || 'application/octet-stream') : ''
      })
    });
    if (res.ok) {
      setBadge('sent', 'SENT');
      t.value = '';
      setFile(null);
      setTimeout(() => setBadge('', 'JARVIS'), 2000);
    } else {
      setBadge('err', 'FAILED');
      setTimeout(() => setBadge('', 'JARVIS'), 2500);
    }
  } catch {
    setBadge('err', 'NET ERR');
    setTimeout(() => setBadge('', 'JARVIS'), 2500);
  } finally {
    s.disabled = false;
    t.focus();
  }
}

t.onkeydown = (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    send();
  } else if (e.key === 'Escape') {
    if (t.value || activeFile) {
      t.value = '';
      setFile(null);
      setBadge('', 'JARVIS');
    } else {
      window.close();
    }
  }
};

s.onclick = send;

setInterval(async () => {
  try {
    const res = await fetch('/status', { headers: { 'X-Jarvis-Token': token } });
    const j = await res.json();
    if (j.closing) {
      window.close();
    }
  } catch {}
}, 500);
</script>
</body>
</html>'''


class TestBar:
    def __init__(self):
        self.items = queue.Queue(maxsize=20)
        self.server = None
        self.thread = None
        self.token = ''
        self.closing = False

    def start(self):
        if self.server:
            return self.url
        self.token, self.closing = secrets.token_urlsafe(24), False
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def _auth(self): return secrets.compare_digest(self.headers.get('X-Jarvis-Token',''), owner.token)
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline'"); self.end_headers(); self.wfile.write(PAGE); return
                if self.path == '/status' and self._auth(): self._json(200, {'closing': owner.closing}); return
                self._json(404, {'error':'not found'})
            def do_POST(self):
                if self.path != '/submit' or not self._auth(): self._json(403, {'error':'forbidden'}); return
                try:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0 < length <= MAX_BODY: raise ValueError('invalid size')
                    value=json.loads(self.rfile.read(length)); text=value.get('text',''); encoded=value.get('file')
                    if not isinstance(text,str) or len(text)>100000: raise ValueError('invalid text')
                    data=base64.b64decode(encoded, validate=True) if encoded else b''
                    if len(data)>10*1024*1024 or (not text.strip() and not data): raise ValueError('empty input')
                    owner.items.put_nowait({'text':text.strip(),'data':data,'mime':str(value.get('mime',''))[:200],'name':str(value.get('name',''))[:255]})
                    self._json(202, {'status':'queued'})
                except (ValueError, TypeError, json.JSONDecodeError, queue.Full): self._json(400, {'error':'invalid or full'})
            def _json(self, code, value):
                raw=json.dumps(value).encode(); self.send_response(code); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.url=f'http://127.0.0.1:{self.server.server_port}/#{self.token}'
        return self.url

    def pop(self):
        try: return self.items.get_nowait()
        except queue.Empty: return None

    def close(self):
        if not self.server: return False
        self.closing=True
        server=self.server
        threading.Timer(1.5, server.shutdown).start()
        self.server=None
        return True
