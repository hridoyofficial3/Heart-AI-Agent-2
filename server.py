# অ্যাপের ভেতরের লোকাল সার্ভার (শুধু 127.0.0.1) — UI এর সঙ্গে ব্রেইনের যোগাযোগ
import os, json, time, hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import engine

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8765
_priv = os.environ.get("ANDROID_PRIVATE") or HERE
with open(os.path.join(_priv, "ui_token.txt")) as _f: TOKEN = _f.read().strip()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _out(self, body, code=200, ctype="application/json; charset=utf-8"):
        if not isinstance(body, bytes): body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)
    def _auth(self): return hmac.compare_digest(self.headers.get("X-T", ""), TOKEN)
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path == "/":
            if not hmac.compare_digest(q.get("t", [""])[0], TOKEN): return self._out({"err": "auth"}, 403)
            with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
                return self._out(f.read().replace("__TOKEN__", TOKEN).encode("utf-8"), 200, "text/html; charset=utf-8")
        if u.path == "/avatar.jpg":
            if not hmac.compare_digest(q.get("t", [""])[0], TOKEN) or not engine.avatar_v(): return self._out({"err": "none"}, 404)
            with open(engine.AVATAR, "rb") as f: return self._out(f.read(), 200, "image/jpeg")
        if not self._auth(): return self._out({"err": "auth"}, 403)
        if u.path == "/api/avatar": return self._out({"v": engine.avatar_v()})
        if u.path == "/api/messages":
            engine.S["seen"] = time.time()
            try: after = int(q.get("after", ["0"])[0])
            except ValueError: after = 0
            try: sid = int(q.get("sid", ["0"])[0])
            except ValueError: sid = 0
            return self._out(engine.since(after, sid))
        if u.path == "/api/sessions": return self._out(engine.sessions(q.get("q", [""])[0]))
        if u.path == "/api/settings": return self._out(engine.settings())
        if u.path == "/api/keys": return self._out(engine.key_list())
        self._out({"err": "not found"}, 404)
    def do_POST(self):
        if not self._auth(): return self._out({"err": "auth"}, 403)
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 100000)
            d = json.loads(self.rfile.read(n) or b"{}")
        except Exception: d = {}
        p = urlparse(self.path).path
        if p == "/api/send": return self._out(engine.send_user(d.get("text")))
        if p == "/api/settings": return self._out(engine.save_settings(d))
        if p == "/api/keys": return self._out(engine.key_action(d))
        if p == "/api/sessions":
            a = d.get("action")
            if a == "new": engine.new_session()
            elif a == "open": engine.open_session(d.get("id"))
            elif a == "delete": engine.delete_session(d.get("id"))
            elif a == "rename": engine.rename_session(d.get("id"), d.get("title"))
            return self._out({"ok": True})
        if p == "/api/pick":
            open(os.path.join(_priv, "pick_request"), "w").write(str(d.get("purpose") or "file")[:10]); return self._out({"ok": True})
        if p == "/api/upload": return self._out(engine.send_file(d.get("name"), d.get("path")))
        if p == "/api/avatar_set": return self._out(engine.avatar_set(d.get("data")))
        if p == "/api/avatar_clear": return self._out(engine.avatar_clear())
        if p == "/api/clear": engine.clear(); return self._out({"ok": True})
        self._out({"err": "not found"}, 404)

class Srv(ThreadingHTTPServer):
    daemon_threads = True; allow_reuse_address = True

def run():
    Srv(("127.0.0.1", PORT), H).serve_forever()
