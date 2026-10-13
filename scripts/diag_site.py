"""Diagnóstico temporário: formato do /api/home-news do piauinoticias.com."""
import json, re, urllib.request
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return r.read().decode("utf-8", "replace")
data = json.loads(get("https://piauinoticias.com/api/home-news"))
print("chaves:", list(data.keys()))
for k, v in data.items():
    if isinstance(v, dict):
        print(f"{k}: dict com chaves {list(v.keys())[:20]}")
        for kk, vv in list(v.items())[:2]:
            print(f"   {kk}: {type(vv).__name__} len={len(vv) if hasattr(vv,'__len__') else ''}")
            if isinstance(vv, list) and vv:
                print("     exemplo:", json.dumps(vv[0], ensure_ascii=False)[:700])
    elif isinstance(v, list):
        print(f"{k}: lista len={len(v)}")
        if v:
            print("   exemplo:", json.dumps(v[0], ensure_ascii=False)[:700])
total = sum(len(vv) for v in data.values() if isinstance(v, dict) for vv in v.values() if isinstance(vv, list))
print("total em news:", total)
js = get("https://piauinoticias.com/assets/" + re.search(r'/assets/(index-[^"]+\.js)', get("https://piauinoticias.com/")).group(1))
for m in list(re.finditer(r'(path:"[^"]{1,60}"|to:`/[^`]{1,60}`|"/api/[a-z0-9\-/]{1,40}")', js))[:40]:
    print("  rota:", m.group(1))
