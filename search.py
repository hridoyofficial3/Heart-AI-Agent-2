# সহজ ওয়েব সার্চ (DuckDuckGo)। নিজের search.py থাকলে এটা সেটা দিয়ে বদলে দাও।
import re, html, requests
from urllib.parse import unquote, parse_qs, urlparse

def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

def web_search(q):
    try:
        r = requests.post("https://html.duckduckgo.com/html/", data={"q": q},
                          headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        out = []
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*?)(?=class="result__a"|$)', r.text, re.S):
            href, title, rest = m.group(1), _clean(m.group(2)), m.group(3)
            u = parse_qs(urlparse(href).query).get("uddg")
            if u: href = unquote(u[0])
            sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', rest, re.S)
            out.append(f"{title}\n{_clean(sn.group(1)) if sn else ''}\n{href}")
            if len(out) >= 5: break
        return "\n\n".join(out) or "কোনো ফলাফল পাওয়া যায়নি।"
    except Exception as e:
        return "সার্চ ব্যর্থ: " + str(e)[:100]
