# ব্যাকগ্রাউন্ড ফোরগ্রাউন্ড সার্ভিস: ব্রেইন + লোকাল সার্ভার + সময়মতো কাজ (রিমাইন্ডার, শুভেচ্ছা)
import os, sys, time, traceback
priv = os.environ.get("ANDROID_PRIVATE") or os.getcwd()
os.environ["HOME"] = priv                       # বটের ~/agent তখন অ্যাপের নিজস্ব ফোল্ডারে
os.makedirs(os.path.join(priv, "agent"), exist_ok=True)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
tp = os.path.join(priv, "ui_token.txt")
if not os.path.exists(tp):
    import secrets
    with open(tp, "w") as f: f.write(secrets.token_hex(16))

while True:
    try:
        import engine, server
        engine.init()
        server.run()
    except Exception:
        traceback.print_exc()
    time.sleep(10)
