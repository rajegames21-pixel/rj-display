"""Diagnóstico temporário: de onde o piauinoticias.com (SPA) busca as notícias?"""
import re, sys, urllib.request, urllib.parse
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")
home = get("https://piauinoticias.com/")
print(home)
scripts = re.findall(r'<script[^>]+src="([^"]+)"', home)
for src in scripts:
    url = urllib.parse.urljoin("https://piauinoticias.com/", src)
    js = get(url)
    print("== bundle", url, len(js))
    urls = sorted(set(re.findall(r'https?://[a-zA-Z0-9._-]+(?:/[^\s"\'`<>)]{0,80})?', js)))
    for u in urls:
        if not any(x in u for x in ("w3.org", "reactjs", "github.com/", "mozilla", "schema.org")):
            print("   url:", u)
    for kw in ("supabase", "firebase", "/api/", "wp-json", "graphql", "anon", "apikey", "rest/v1", "from(\"", "from('"):
        for m in list(re.finditer(re.escape(kw), js))[:3]:
            print(f"   [{kw}]", repr(js[max(0, m.start()-120):m.end()+160]))
