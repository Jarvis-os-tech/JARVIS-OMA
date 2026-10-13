"""Loopback-only multimodal input bar for an active JARVIS voice session."""
from __future__ import annotations

import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import queue
import secrets
import threading

MAX_BODY = 12 * 1024 * 1024
PAGE = b'''<!doctype html><meta charset="utf-8"><title>JARVIS Input Bar</title>
<style>body{margin:0;background:#090d16;color:#eef3ff;font:16px system-ui;display:grid;place-items:center;height:100vh}main{width:min(850px,92vw);background:#111827;border:1px solid #334155;border-radius:18px;padding:22px;box-shadow:0 20px 70px #0008}textarea{box-sizing:border-box;width:100%;min-height:120px;background:#070b12;color:white;border:1px solid #475569;border-radius:12px;padding:14px;resize:vertical}section{display:flex;gap:12px;margin-top:12px;align-items:center}button{margin-left:auto;background:#6366f1;color:white;border:0;border-radius:10px;padding:11px 22px;font-weight:700}small{color:#94a3b8}#status{color:#86efac}</style>
<main><h2>JARVIS Input Bar</h2><textarea id=t autofocus placeholder="Type or paste anything for Jarvis..."></textarea><section><input id=f type=file><small>Text, image, audio, PDF, or another file (10 MiB max)</small><button id=s>Send</button></section><p id=status>Ready</p></main>
<script>const token=location.hash.slice(1);s.onclick=async()=>{let file=f.files[0],data=null;if(file){if(file.size>10485760){status.textContent='File too large';return}data=await new Promise((ok,no)=>{let r=new FileReader;r.onload=()=>ok(r.result.split(',')[1]);r.onerror=no;r.readAsDataURL(file)})}s.disabled=true;let r=await fetch('/submit',{method:'POST',headers:{'Content-Type':'application/json','X-Jarvis-Token':token},body:JSON.stringify({text:t.value,file:data,name:file?.name||'',mime:file?.type||'application/octet-stream'})});status.textContent=r.ok?'Sent to Jarvis':'Send failed';if(r.ok){t.value='';f.value=''}s.disabled=false};setInterval(async()=>{try{let r=await fetch('/status',{headers:{'X-Jarvis-Token':token}}),j=await r.json();if(j.closing){status.textContent='Closed by voice';window.close()}}catch{}},500)</script>'''


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
