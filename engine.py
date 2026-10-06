# অ্যাপের ব্রেইন: bot.py-র সব ক্ষমতা, কিন্তু Telegram ছাড়া — মেসেজ যায়-আসে অ্যাপের চ্যাটে।
import os, json, re, time, threading, io, zipfile, base64
import requests
import bot

MAX_KEYS = 50
CID = bot.OWNER_ID
PROV = {   # সার্ভিস: (ঠিকানা, ডিফল্ট মডেল)। "custom" = যেকোনো OpenAI-সামঞ্জস্য API, ঠিকানা নিজে দিতে হয়
    "groq": ("https://api.groq.com/openai/v1/chat/completions", "openai/gpt-oss-120b"),
    "gemini": (bot._GEM, "gemini-flash-latest"),
    "mistral": (bot._MIS, "mistral-large-latest"),
    "openrouter": (bot._OR, "openai/gpt-oss-120b:free"),
    "openai": ("https://api.openai.com/v1/chat/completions", "gpt-4o-mini"),
    "deepseek": ("https://api.deepseek.com/chat/completions", "deepseek-chat"),
    "custom": ("", ""),
}
CLOSE = ("\n\nতুমি আমার খুব কাছের আপনজনের মতো: আমার কথা, পছন্দ, মন খারাপ-ভালো লাগা মনে রেখে আন্তরিক, মিষ্টি ও যত্নশীলভাবে কথা বলবে, "
         "যত জানবে তত গভীরভাবে বুঝে ভালো উত্তর দেবে। তবে নিজেকে কখনো আমার একমাত্র আপনজন বা আসল মানুষের বিকল্প বলবে না; "
         "দরকারে পরিবার-বন্ধুর সঙ্গ নিতে উৎসাহ দেবে।")
OLD_FILE = os.path.join(bot.BASE, "ui_chat.json")
IDX_FILE = os.path.join(bot.BASE, "ui_sessions.json")
KEYS_FILE = os.path.join(bot.BASE, "keys.json")
SET_FILE = os.path.join(bot.BASE, "ui_settings.json")
_ORIG_PROMPT = bot.SYSTEM_PROMPT
_lock = threading.RLock()
_hlock = threading.Lock()
_ctx = threading.local()
S = {"typing": False, "tsid": 0, "seen": 0.0, "inited": False}
ACTIVE = [0]
idx = {"active": 0, "list": []}

def _load(p, d):
    try:
        with open(p, encoding="utf-8") as f: return json.load(f)
    except Exception: return d

def _save(p, d):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, p)

msgs = []

def _sfile(sid): return os.path.join(bot.BASE, f"chat_{sid}.json")
def _save_idx(): _save(IDX_FILE, idx)
def _meta(sid): return next((x for x in idx["list"] if x["id"] == sid), None)

def _load_sessions():
    d = _load(IDX_FILE, None)
    if d and d.get("list"): idx.update(d)
    else:                                   # পুরোনো একক-চ্যাট ফাইল থেকে আনা
        old = _load(OLD_FILE, []); sid = int(time.time() * 1000)
        title = next((" ".join(m["text"].split())[:48] for m in old if m.get("role") == "user"), "")
        idx["list"] = [{"id": sid, "title": title, "ts": int(time.time())}]; idx["active"] = sid
        _save(_sfile(sid), old); _save_idx()
    if not _meta(idx["active"]): idx["active"] = idx["list"][0]["id"]
    ACTIVE[0] = idx["active"]; msgs[:] = _load(_sfile(ACTIVE[0]), [])

def _prune():                               # খালি পুরোনো চ্যাট বাদ
    for x in [x for x in idx["list"] if not x["title"] and x["id"] != ACTIVE[0]]:
        idx["list"].remove(x)
        try: os.remove(_sfile(x["id"]))
        except OSError: pass

def _reset_model_history(ms):
    if not bot.ai_lock.acquire(timeout=3): return
    try:
        bot.history.clear()
        bot.history.extend({"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]}
                           for m in ms[-bot.MAX_HISTORY:])
        bot.save_history()
    finally: bot.ai_lock.release()

def push(role, text, sid=None):
    with _lock:
        sid = sid if _meta(sid) else ACTIVE[0]
        ms = msgs if sid == ACTIVE[0] else _load(_sfile(sid), [])
        m = {"id": (ms[-1]["id"] + 1) if ms else 1, "role": role, "text": text, "ts": int(time.time())}
        ms.append(m); del ms[:-400]; _save(_sfile(sid), ms)
        meta = _meta(sid); meta["ts"] = m["ts"]
        if not meta["title"]: meta["title"] = " ".join(text.split())[:48]
        _save_idx()
    return m

def since(after, sid=0):
    with _lock:
        typing = S["typing"] and S["tsid"] == ACTIVE[0]
        if sid != ACTIVE[0]: return {"reset": True, "sid": ACTIVE[0], "messages": list(msgs), "typing": typing}
        return {"reset": False, "sid": ACTIVE[0], "messages": [m for m in msgs if m["id"] > after], "typing": typing}

def sessions(q=""):
    q = (q or "").strip().lower(); out = []
    with _lock:
        for x in sorted(idx["list"], key=lambda x: -x["ts"]):
            if not x["title"]: continue
            if q and q not in x["title"].lower():
                ms = msgs if x["id"] == ACTIVE[0] else _load(_sfile(x["id"]), [])
                if not any(q in m["text"].lower() for m in ms): continue
            out.append({"id": x["id"], "title": x["title"], "ts": x["ts"], "active": x["id"] == ACTIVE[0]})
    return {"sessions": out[:80], "active": ACTIVE[0]}

def new_session():
    with _lock:
        if _meta(ACTIVE[0]) and not msgs: return ACTIVE[0]
        sid = int(time.time() * 1000)
        idx["list"].insert(0, {"id": sid, "title": "", "ts": int(time.time())})
        ACTIVE[0] = idx["active"] = sid; msgs[:] = []
        _save(_sfile(sid), []); _prune(); _save_idx()
    _reset_model_history([]); return sid

def open_session(sid):
    with _lock:
        if not _meta(sid): return False
        ACTIVE[0] = idx["active"] = sid; msgs[:] = _load(_sfile(sid), []); _prune(); _save_idx()
    _reset_model_history(msgs); return True

def rename_session(sid, title):
    t = " ".join(str(title or "").split())[:60]
    with _lock:
        m = _meta(sid)
        if not m or not t: return False
        m["title"] = t; _save_idx()
    return True

def delete_session(sid):
    with _lock:
        m = _meta(sid)
        if not m: return
        idx["list"].remove(m)
        try: os.remove(_sfile(sid))
        except OSError: pass
        was = sid == ACTIVE[0]
        if was: ACTIVE[0] = 0; msgs[:] = []
        _save_idx()
    if was: new_session()

# ---- সেটিংস ও চরিত্র
def settings():
    d = {"name": "দীপান্বিতা", "gender": "female", "theme": "dark", "user_name": ""}
    d.update(_load(SET_FILE, {})); return d

def persona():
    s = settings(); n = (s["name"] or "").strip()[:30] or "দীপান্বিতা"
    p = _ORIG_PROMPT
    if s["gender"] == "male":
        for a, b in (("তুমি একজন মেয়ে। সবসময় মেয়ে হিসেবে পরিচয় দেবে", "তুমি একজন ছেলে। সবসময় ছেলে হিসেবে পরিচয় দেবে"),
                     ("মেয়ের মতো আচরণ", "ছেলের মতো আচরণ"), ("বান্ধবীর মতো", "বন্ধুর মতো"),
                     ("প্রেমিকার মতো", "প্রেমিকের মতো"), ("অন্য কোনো মেয়ের কথা", "অন্য কারও কথা")):
            p = p.replace(a, b)
    bot.SYSTEM_PROMPT = p.replace("দীপান্বিতা", n) + CLOSE; bot.PERSONA_NAME = n

def save_settings(d):
    old = settings(); s = dict(old)
    if "name" in d: s["name"] = str(d["name"]).strip()[:30] or "দীপান্বিতা"
    if d.get("gender") in ("female", "male"): s["gender"] = d["gender"]
    if d.get("theme") in ("auto", "light", "dark"): s["theme"] = d["theme"]
    if "user_name" in d: s["user_name"] = str(d["user_name"]).strip()[:30]
    _save(SET_FILE, s); persona()
    if s["user_name"] and s["user_name"] != old.get("user_name"):
        p = bot.load_json(bot.PROFILE_FILE, {}); p["নাম"] = s["user_name"]; bot.save_json(bot.PROFILE_FILE, p)
    if (s["name"], s["gender"]) != (old["name"], old["gender"]):   # পুরোনো পরিচয়ের কথোপকথন মডেলকে গুলিয়ে দেয়
        _reset_model_history([])
    return s

# ---- API key ম্যানেজার (যত ইচ্ছে API; নাম + মডেল + ঠিকানা নিজে দেওয়া যায়; ওপরেরটা ডিফল্ট)
def _norm(k):                       # পুরোনো key (শুধু provider+key) নতুন ফরম্যাটে আনা
    p = k.get("provider", "custom")
    if p in PROV and p != "custom":
        k.setdefault("url", PROV[p][0]); k.setdefault("model", PROV[p][1])
    k.setdefault("name", p.capitalize()); k.setdefault("search", False); k.setdefault("enabled", True)
    return k

def keys(): return [_norm(k) for k in _load(KEYS_FILE, [])]

def _mask(k): return k[:4] + "…" + k[-4:] if len(k) > 10 else "…"
def _t(k): return (k["name"], k["url"], k["key"], k["model"])

def rebuild():
    ks = [k for k in keys() if k["enabled"] and k.get("url") and k.get("model") and k.get("key")]
    bot.PROVIDERS = [_t(k) for k in ks]                                  # ক্রম = তালিকার ক্রম; ওপরেরটা সেরা/ডিফল্ট
    bot.SEARCH_PROVIDERS = [_t(k) for k in ks if k["search"]] + [_t(k) for k in ks if not k["search"]]

def key_list():
    now = time.time(); out = []; act = None
    for k in keys():
        cd = max(0, int(bot._blocked.get((k["name"], k["model"], k["key"][-8:]), 0) - now))
        if act is None and k["enabled"] and cd == 0: act = k["id"]
        out.append({"id": k["id"], "provider": k["provider"], "name": k["name"], "model": k["model"], "masked": _mask(k["key"]),
                    "enabled": k["enabled"], "search": k["search"], "cooldown": cd})
    for o in out: o["active"] = o["id"] == act
    return {"keys": out, "max": MAX_KEYS}

def test_key(k):
    try:
        r = requests.post(k["url"], headers={"Authorization": "Bearer " + k["key"]}, timeout=25,
                          json={"model": k["model"], "max_tokens": 16, "messages": [{"role": "user", "content": "hi"}]})
    except Exception: return {"ok": False, "err": "নেট নেই বা সার্ভার সাড়া দিচ্ছে না"}
    c = r.status_code
    if c == 200: return {"ok": True, "msg": "ঠিক আছে, কাজ করছে"}
    if c in (401, 403): return {"ok": False, "err": "key ভুল বা অনুমতি নেই"}
    if c == 429: return {"ok": True, "msg": "key ঠিক আছে, তবে এখন লিমিট শেষ"}
    if c == 402: return {"ok": False, "err": "ক্রেডিট শেষ"}
    if c == 404: return {"ok": False, "err": "মডেলের নাম বা ঠিকানা ভুল (404)"}
    return {"ok": False, "err": f"সমস্যা (কোড {c})"}

def key_action(d):
    a = d.get("action"); ks = keys(); kid = d.get("id")
    if a == "add":
        p = d.get("provider") or "custom"; k = str(d.get("key") or "").strip()
        if p not in PROV: return {"ok": False, "err": "সার্ভিস বেছে নাও"}
        url = str(d.get("url") or "").strip() if p == "custom" else PROV[p][0]
        model = str(d.get("model") or "").strip()[:80] or PROV[p][1]
        name = str(d.get("name") or "").strip()[:30] or (p.capitalize() if p != "custom" else model[:30])
        if not url.startswith(("https://", "http://")): return {"ok": False, "err": "API ঠিকানা দাও (https:// দিয়ে শুরু)"}
        if not url.rstrip("/").endswith("/chat/completions"): url = url.rstrip("/") + "/chat/completions"
        if not model: return {"ok": False, "err": "মডেলের নাম লেখো"}
        if len(k) < 8 or re.search(r"\s", k): return {"ok": False, "err": "key ঠিক নেই — পুরোটা কপি করেছ?"}
        if len(ks) >= MAX_KEYS: return {"ok": False, "err": f"সর্বোচ্চ {MAX_KEYS}টা রাখা যায়"}
        if any(x["key"] == k and x["model"] == model and x["url"] == url for x in ks): return {"ok": False, "err": "এই key আর মডেল আগেই যোগ করা আছে"}
        ks.append({"id": int(time.time() * 1000), "provider": p, "name": name, "url": url, "model": model, "key": k,
                   "enabled": True, "search": bool(d.get("search"))})
    elif a == "edit":
        for x in ks:
            if x["id"] == kid:
                if str(d.get("name") or "").strip(): x["name"] = str(d["name"]).strip()[:30]
                if str(d.get("model") or "").strip(): x["model"] = str(d["model"]).strip()[:80]
                x["search"] = bool(d.get("search"))
    elif a == "delete": ks = [x for x in ks if x["id"] != kid]
    elif a in ("toggle", "search"):
        f = "enabled" if a == "toggle" else "search"
        for x in ks:
            if x["id"] == kid: x[f] = not x.get(f, f == "enabled")
    elif a == "default":                              # ক্লিক করে ডিফল্ট বানানো = সবার ওপরে বসানো
        i = next((n for n, x in enumerate(ks) if x["id"] == kid), None)
        if i is not None: ks.insert(0, ks.pop(i))
    elif a == "move":
        i = next((n for n, x in enumerate(ks) if x["id"] == kid), None)
        if i is not None:
            j = i + (-1 if d.get("dir") == "up" else 1)
            if 0 <= j < len(ks): ks[i], ks[j] = ks[j], ks[i]
    elif a == "unblock": bot._blocked.clear()
    elif a == "test":
        k = next((x for x in ks if x["id"] == kid), None)
        return test_key(k) if k else {"ok": False, "err": "পাওয়া যায়নি"}
    _save(KEYS_FILE, ks); rebuild(); return {"ok": True}

# ---- নোটিফিকেশন (অ্যাপ খোলা না থাকলে অটো মেসেজ আসে)
def _notify(title, text):
    from jnius import autoclass, cast
    ctx = autoclass("org.kivy.android.PythonService").mService
    C = autoclass("android.content.Context")
    nm = cast("android.app.NotificationManager", ctx.getSystemService(C.NOTIFICATION_SERVICE))
    nm.createNotificationChannel(autoclass("android.app.NotificationChannel")("msgs", "Messages", 3))
    PI = autoclass("android.app.PendingIntent")
    launch = ctx.getPackageManager().getLaunchIntentForPackage(ctx.getPackageName())
    b = autoclass("android.app.Notification$Builder")(ctx, "msgs")
    b.setContentTitle(title); b.setContentText(text[:200]); b.setAutoCancel(True)
    b.setSmallIcon(ctx.getApplicationInfo().icon)
    b.setContentIntent(PI.getActivity(ctx, 0, launch, PI.FLAG_IMMUTABLE))
    nm.notify(int(time.time()) % 100000 + 10, b.build())

def _send(cid, text):
    text = str(text or "").strip()
    if not text: return
    push("bot", text, getattr(_ctx, "sid", None))
    if not getattr(_ctx, "user", False) and time.time() - S["seen"] > 12:
        try: _notify(bot.PERSONA_NAME, text)
        except Exception: pass

# ---- মেসেজ রাউটিং (আগের Telegram main()-এর হুবহু লজিক)
def _route(t):
    say = lambda x: _send(CID, x); low = t.lower()
    bot.log_chat("user", t); bot.bump_relation("user"); bot.update_last_msg()
    if bot.quiz_state.get("q") and not t.startswith("/"): bot.check_quiz(CID, t); return
    if t == "/start": return say("হ্যালো!! /help লিখো।")
    if t == "/help":
        return say("\n".join(l for l in bot.cmd_help().split("\n") if not any(w in l for w in ("ছবি", "ফাইল", "জিপ"))) + "\n• + বাটন → 📎 ছবি/ফাইল — ছবি, PDF, zip, লেখা বা কোড পাঠাও")
    if t == "/memory": return say(bot.load_memory().get("summary") or "দীর্ঘমেয়াদি স্মৃতি এখনো জমেনি।")
    if t == "/resetmemory": bot.save_json(bot.MEMORY_FILE, {"summary": ""}); return say("স্মৃতি মুছে দিলাম!!")
    if t == "/clear": return say(clear())
    if t == "/status": return say(bot.cmd_status())
    if t.startswith("ভুলে যাও"): return say(bot.handle_forget(t))
    if t.startswith(("নিয়ম:", "নিয়ম :", "নিয়ম মুছো")) or t in ("নিয়ম দেখাও", "নিয়ম", "নিয়মগুলো"): return say(bot.handle_rule(t))
    if t.startswith(("নোট:", "নোট :")): return say(bot.handle_note_save(t))
    if t in ("নোট দেখাও", "নোট দেখান", "সব নোট"): return say(bot.handle_note_show())
    if t.startswith(("ডায়েরি:", "ডায়েরি :")): return say(bot.handle_diary_save(t))
    if t in ("ডায়েরি দেখাও", "ডায়েরি", "আমার ডায়েরি"): return say(bot.handle_diary_show())
    if t.startswith(("মুড:", "মুড :")): return say(bot.handle_mood(t))
    if t.startswith(("হিসাব:", "হিসাব :")): return say(bot.handle_calc(t))
    if t.startswith("মনে করাও"): return say(bot.add_reminder(t))
    if t in ("রিমাইন্ডার দেখাও", "রিমাইন্ডার"): return say(bot.show_reminders())
    if t.startswith("বই "):
        r = bot.handle_books(t)
        if r: return say(r)
    if t.startswith("টার্গেট"):
        r = bot.handle_target(t)
        if r: return say(r)
    if t.startswith("স্বপ্ন:"): return say(bot.handle_dream(t))
    if t == "প্রোফাইল": return say(bot.handle_profile(t) or "কিছু জানি না।")
    if t in ("সম্পর্ক", "টাইমলাইন"): return say(bot.handle_relation())
    if t in ("শব্দ শেখাও", "ইংরেজি শেখাও", "নতুন শব্দ"): return bot.teach_word(CID)
    if t in ("কুইজ", "কুইজ দাও"): return bot.start_quiz(CID)
    if low.startswith(("সার্চ ", "search ", "খোঁজ ")):
        q = t.split(" ", 1)[1].strip() if " " in t else ""
        return bot.handle_search(CID, q) if q else say("কী সার্চ করব?")
    bot.auto_profile(t)
    topic = bot.detect_interest(t)
    if topic: bot.save_interest(topic)
    if not bot.PROVIDERS:
        return say("আগে সেটিংস → API key ম্যানেজার থেকে অন্তত একটা API key যোগ করো, তারপর কথা বলব!!")
    reply = bot.ask_groq(t); bot.log_chat("agent", reply); bot.bump_relation("bot"); say(reply)

def _handle(t, sid):
    with _hlock:
        _ctx.user = True; _ctx.sid = sid; S["typing"] = True; S["tsid"] = sid
        try: _route(t)
        except Exception as e: push("bot", "সমস্যা: " + bot.safe_err(e), sid)
        finally: S["typing"] = False; _ctx.user = False; _ctx.sid = None; bot._tl.search = False

def send_user(text):
    text = str(text or "").strip()[:4000]
    if not text: return {"msg": None}
    sid = ACTIVE[0]; m = push("user", text, sid)
    threading.Thread(target=_handle, args=(text, sid), daemon=True).start()
    return {"msg": m}

UPLOAD_DIR = os.path.join(bot.BASE, "uploads")
TXT = (".txt",".md",".csv",".json",".log",".xml",".html",".css",".js",".py",".java",".kt",".c",".cpp",".h",".sql",
       ".yml",".yaml",".ini",".sh",".ts",".php",".go",".rs",".srt",".spec",".gradle")
IMG = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
LIM = 8000

def _file_text(name, data):
    n = name.lower()
    if n.endswith(".zip"):
        parts, total = [], 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = [i.filename for i in z.infolist() if not i.is_dir()]
            for i in z.infolist():
                f = i.filename
                if i.is_dir() or not f.lower().endswith(TXT) or i.file_size > 100000 or "node_modules/" in f or ".git/" in f: continue
                t = z.read(i).decode("utf-8", "ignore")
                if total + len(t) > LIM: break
                parts.append(f"=== {f} ===\n{t}"); total += len(t)
        return f"zip-এ {len(names)}টা ফাইল: " + ", ".join(names[:60]) + "\n\n" + "\n\n".join(parts)
    if n.endswith(".pdf"):
        try: from pypdf import PdfReader
        except ImportError: return "ERR:PDF পড়ার অংশ এই অ্যাপে নেই।"
        try: t = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:30]).strip()
        except Exception: return "ERR:PDF-টা পড়া গেল না (নষ্ট বা পাসওয়ার্ড দেওয়া হতে পারে)।"
        return t or "ERR:PDF-এ পড়ার মতো লেখা পেলাম না (স্ক্যান করা ছবি হতে পারে)।"
    if n.endswith(TXT) or b"\x00" not in data[:2000]:
        return data.decode("utf-8", "ignore")
    return "ERR:এই ধরনের ফাইল পড়তে পারি না। ছবি, PDF, zip বা লেখার ফাইল পাঠাও।"

def send_file(name, path):
    name = os.path.basename(str(name or "ফাইল"))[:80]
    real = os.path.realpath(str(path or ""))
    if not real.startswith(os.path.realpath(UPLOAD_DIR) + os.sep) or not os.path.isfile(real): return {"ok": False}
    m = push("user", "📎 " + name); sid = ACTIVE[0]
    threading.Thread(target=_handle_file, args=(name, real, sid), daemon=True).start()
    return {"ok": True, "msg": m}

def _handle_file(name, path, sid):
    with _hlock:
        _ctx.user = True; _ctx.sid = sid; S["typing"] = True; S["tsid"] = sid
        say = lambda x: _send(CID, x)
        try:
            if os.path.getsize(path) > 8_000_000: return say("ফাইলটা অনেক বড় (৮MB-র বেশি)। ছোট করে পাঠাও।")
            data = open(path, "rb").read(); ext = os.path.splitext(name.lower())[1]
            if not bot.PROVIDERS: return say("আগে সেটিংস → API key ম্যানেজার থেকে একটা API key যোগ করো, তারপর ফাইল দেখব!!")
            if ext in IMG:
                if len(data) > 3_000_000: return say("ছবিটা অনেক বড়, একটু ছোট করে পাঠাও।")
                bot.answer_image(CID, "আমি এই ছবিটা পাঠিয়েছি। কী আছে বুঝে স্বাভাবিকভাবে সাড়া দাও।", name, (base64.b64encode(data).decode(), IMG[ext]))
            else:
                t = _file_text(name, data)
                if t.startswith("ERR:"): return say(t[4:])
                reply = bot.ask_groq(f"আমি '{name}' ফাইলটা পাঠিয়েছি। ভেতরের লেখা:\n\n{t[:LIM]}\n\nসংক্ষেপে বলো কী আছে। কিছু ভুল বা দরকারি কথা থাকলে জানাও।")
                bot.log_chat("agent", reply); say(reply)
        except Exception as ex: push("bot", "ফাইল পড়তে সমস্যা: " + bot.safe_err(ex), sid)
        finally:
            S["typing"] = False; _ctx.user = False; _ctx.sid = None
            try: os.remove(path)
            except OSError: pass

AVATAR = os.path.join(bot.BASE, "avatar.jpg")
def avatar_v():
    try: return int(os.path.getmtime(AVATAR))
    except OSError: return 0
def avatar_set(data):
    try: raw = base64.b64decode(str(data or "").split(",", 1)[-1], validate=False)
    except Exception: return {"ok": False, "err": "ছবি পড়া যায়নি"}
    if not raw.startswith(b"\xff\xd8") or len(raw) > 200000: return {"ok": False, "err": "ছবি ঠিক নেই বা বড়"}
    os.makedirs(bot.BASE, exist_ok=True)
    with open(AVATAR + ".tmp", "wb") as f: f.write(raw)
    os.replace(AVATAR + ".tmp", AVATAR); return {"ok": True}
def avatar_clear():
    try: os.remove(AVATAR)
    except OSError: pass
    return {"ok": True}

def clear():
    delete_session(ACTIVE[0])
    return "চ্যাট মুছে ফেললাম!! (স্মৃতি, নোট ও ডায়েরি আছে)"

def init():
    if S["inited"]: return
    S["inited"] = True
    _load_sessions()
    bot.load_state(); bot.load_history(); bot.load_last_msg()
    for h in bot.history:
        if h.get("role") == "assistant": h["content"] = bot.fix_tui(h.get("content", ""))
    bot.save_history()
    def _safe(e):
        t = str(e)
        for k in keys(): t = t.replace(k["key"], "***")
        return t[:300]
    bot.safe_err = _safe
    bot.send_message = bot.send_chunked = _send
    bot.send_typing = lambda cid: None
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    persona(); rebuild()
    threading.Thread(target=bot.scheduler_loop, daemon=True).start()
