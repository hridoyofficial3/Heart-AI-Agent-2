# অ্যাপের Activity: সার্ভিস চালু করে, পুরো স্ক্রিনে চ্যাট UI (WebView) দেখায়
import os, re, json, secrets, socket, threading, time, urllib.request
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.widget import Widget
from kivy.utils import platform

PORT = 8765
if platform == "android":
    from android.runnable import run_on_ui_thread
    from jnius import autoclass
else:
    def run_on_ui_thread(f): return f

class ChatApp(App):
    wv = None
    purpose = "file"

    def build(self):
        Window.clearcolor = (0.07, 0.07, 0.08, 1)
        Window.bind(on_keyboard=self.on_key)
        if platform == "android":
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"])
            tp = os.path.join(os.environ["ANDROID_PRIVATE"], "ui_token.txt")
            if not os.path.exists(tp):
                with open(tp, "w") as f: f.write(secrets.token_hex(16))
            with open(tp) as f: self.token = f.read().strip()
            autoclass("org.heart.dipanwita.ServiceBot").start(autoclass("org.kivy.android.PythonActivity").mActivity, "")
            self.make_webview()
            from android import activity; activity.bind(on_activity_result=self.on_result)
            threading.Thread(target=self.pick_loop, daemon=True).start()
            threading.Thread(target=self.wait_and_load, daemon=True).start()
        return Widget()

    @run_on_ui_thread
    def make_webview(self):
        act = autoclass("org.kivy.android.PythonActivity").mActivity
        W = autoclass("android.webkit.WebView"); W.setWebContentsDebuggingEnabled(False)   # রিলিজে ডিবাগ বন্ধ
        wv = W(act)
        st = wv.getSettings(); st.setJavaScriptEnabled(True); st.setDomStorageEnabled(True)
        st.setAllowFileAccess(False); st.setAllowContentAccess(False)   # শুধু লোকাল সার্ভার, ফোনের ফাইল নয়
        wv.setBackgroundColor(autoclass("android.graphics.Color").parseColor("#121214"))
        act.getWindow().setSoftInputMode(16)          # কীবোর্ড উঠলে লেআউট ছোট হবে
        act.addContentView(wv, autoclass("android.view.ViewGroup$LayoutParams")(-1, -1))
        wv.loadData("<body style='background:#121214;color:#999;font-family:sans-serif;text-align:center;padding-top:40vh'>চালু হচ্ছে…</body>",
                    "text/html; charset=utf-8", "UTF-8")
        self.wv = wv

    def wait_and_load(self):
        ok = False
        for _ in range(160):
            try: socket.create_connection(("127.0.0.1", PORT), 0.5).close(); ok = True; break
            except OSError: time.sleep(0.5)
        while self.wv is None: time.sleep(0.2)
        if ok: self.load(); time.sleep(3); self.ask_battery()
        else: self.fail()

    @run_on_ui_thread
    def ask_battery(self):            # ব্যাটারি সেভার সার্ভিস মারলে রিমাইন্ডার/শুভেচ্ছা মিস হয় — একবার অনুমতি চাই
        try:
            act = autoclass("org.kivy.android.PythonActivity").mActivity
            flag = os.path.join(os.environ["ANDROID_PRIVATE"], "battery_asked")
            pkg = act.getPackageName()
            pm = act.getSystemService(autoclass("android.content.Context").POWER_SERVICE)
            if os.path.exists(flag) or pm.isIgnoringBatteryOptimizations(pkg): return
            open(flag, "w").close()
            i = autoclass("android.content.Intent")("android.settings.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS")
            i.setData(autoclass("android.net.Uri").parse("package:" + pkg)); act.startActivity(i)
        except Exception: pass

    def pick_loop(self):              # UI "📎" চাপলে সার্ভার একটা ফ্ল্যাগ ফাইল বানায় — এখানে সেটা দেখে পিকার খুলি
        flag = os.path.join(os.environ["ANDROID_PRIVATE"], "pick_request")
        while True:
            if os.path.exists(flag):
                try:
                    self.purpose = open(flag).read().strip() or "file"; os.remove(flag)
                except OSError: pass
                self.open_picker()
            time.sleep(0.5)

    @run_on_ui_thread
    def open_picker(self):
        I = autoclass("android.content.Intent"); i = I(I.ACTION_GET_CONTENT)
        i.setType("*/*"); i.addCategory(I.CATEGORY_OPENABLE)
        autoclass("org.kivy.android.PythonActivity").mActivity.startActivityForResult(I.createChooser(i, "ছবি বা ফাইল বাছাই"), 7731)

    def on_result(self, req, res, intent):
        if req == 7731 and res == -1 and intent is not None and intent.getData() is not None:
            threading.Thread(target=self.save_upload, args=(intent.getData(),), daemon=True).start()

    def save_upload(self, uri):
        try:
            act = autoclass("org.kivy.android.PythonActivity").mActivity; cr = act.getContentResolver()
            if self.purpose == "avatar":          # প্রোফাইল ছবি: মাঝখান থেকে বর্গ কেটে ২৫৬px JPEG
                self.purpose = "file"
                BM = autoclass("android.graphics.Bitmap")
                bmp = autoclass("android.graphics.BitmapFactory").decodeStream(cr.openInputStream(uri))
                w, h = bmp.getWidth(), bmp.getHeight(); s = min(w, h)
                bmp = BM.createScaledBitmap(BM.createBitmap(bmp, (w - s) // 2, (h - s) // 2, s, s), 256, 256, True)
                out = autoclass("java.io.ByteArrayOutputStream")()
                bmp.compress(autoclass("android.graphics.Bitmap$CompressFormat").JPEG, 85, out)
                raw = bytes(bytearray([b & 0xff for b in out.toByteArray()]))
                ad = os.path.join(os.environ["ANDROID_PRIVATE"], "agent"); os.makedirs(ad, exist_ok=True)
                with open(os.path.join(ad, "avatar.jpg.tmp"), "wb") as f: f.write(raw)
                os.replace(os.path.join(ad, "avatar.jpg.tmp"), os.path.join(ad, "avatar.jpg")); return
            name = "ফাইল"
            c = cr.query(uri, None, None, None, None)
            if c is not None:
                if c.moveToFirst():
                    k = c.getColumnIndex("_display_name")
                    if k >= 0: name = c.getString(k) or name
                c.close()
            d = os.path.join(os.environ["ANDROID_PRIVATE"], "agent", "uploads"); os.makedirs(d, exist_ok=True)
            ext = os.path.splitext(name.lower())[1]
            if (cr.getType(uri) or "").startswith("image/"):       # বড় ছবি ছোট করে (১২৮০px) JPEG বানাই
                BM = autoclass("android.graphics.Bitmap")
                bmp = autoclass("android.graphics.BitmapFactory").decodeStream(cr.openInputStream(uri))
                w, h = bmp.getWidth(), bmp.getHeight(); sc = min(1.0, 1280.0 / max(w, h))
                if sc < 1: bmp = BM.createScaledBitmap(bmp, int(w * sc), int(h * sc), True)
                out = autoclass("java.io.ByteArrayOutputStream")()
                bmp.compress(autoclass("android.graphics.Bitmap$CompressFormat").JPEG, 80, out)
                data = bytes(bytearray([b & 0xff for b in out.toByteArray()]))
                name = os.path.splitext(name)[0] + ".jpg"; ext = ".jpg"
            else:
                pfd = cr.openFileDescriptor(uri, "r")
                with os.fdopen(pfd.detachFd(), "rb") as f: data = f.read(8_000_001)
            path = os.path.join(d, str(int(time.time() * 1000)) + (ext if re.fullmatch(r"\.\w{1,6}", ext) else ""))
            with open(path, "wb") as f: f.write(data)
            req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/upload", data=json.dumps({"name": name, "path": path}).encode(),
                                         headers={"X-T": self.token, "Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15).read()
        except Exception as ex:
            print("upload:", ex)

    @run_on_ui_thread
    def fail(self):
        self.wv.loadData("<body style='background:#121214;color:#ccc;font-family:sans-serif;text-align:center;padding:40vh 20px 0'>"
                         "সার্ভিস চালু হয়নি।<br>অ্যাপ বন্ধ করে আবার খোলো।</body>", "text/html; charset=utf-8", "UTF-8")

    @run_on_ui_thread
    def load(self):
        self.wv.loadUrl(f"http://127.0.0.1:{PORT}/?t={self.token}")

    def on_key(self, window, key, *a):
        if key == 27 and self.wv is not None:
            self.back(); return True

    @run_on_ui_thread
    def back(self):
        if self.wv.canGoBack(): self.wv.goBack()
        else: autoclass("org.kivy.android.PythonActivity").mActivity.moveTaskToBack(True)

    def on_pause(self): return True

if __name__ == "__main__":
    ChatApp().run()
