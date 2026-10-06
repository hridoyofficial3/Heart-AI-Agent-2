# Termux/কম্পিউটারে সরাসরি চালানোর জন্য (APK ছাড়া):  python run_local.py
# তারপর যে লিংক দেখাবে সেটা Chrome-এ খোলো। ডাটা থাকবে ~/agent ফোল্ডারে।
import os, sys, secrets
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
os.makedirs(os.path.expanduser("~/agent"), exist_ok=True)
tp = os.path.join(here, "ui_token.txt")
if not os.path.exists(tp):
    with open(tp, "w") as f: f.write(secrets.token_hex(16))
import engine, server
engine.init()
print("\nচালু! এই লিংক Chrome-এ খোলো:\n  http://127.0.0.1:%d/?t=%s\n(বন্ধ করতে Ctrl+C)\n" % (server.PORT, open(tp).read().strip()))
server.run()
