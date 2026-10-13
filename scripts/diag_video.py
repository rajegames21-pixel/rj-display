"""Diagnóstico temporário: os MP4 do g1 tocam fora do g1?"""
import re, sys, urllib.request
sys.path.insert(0, "scripts")
import fetch_news as f

feed = "https://g1.globo.com/rss/g1/"
links = [n["link"] for n in f.parse(f.fetch(feed), feed)][:12]
tested = 0
for link in links:
    html = f.fetch(link, timeout=15).decode("utf-8", "replace")
    mp4s = re.findall(r'itemprop="contentUrl" content="([^"]+\.mp4)"', html)
    subs = re.findall(r'subscriber-only="(\w+)"', html)
    thumbs = re.findall(r'itemprop="thumbnailUrl" content="([^"]+)"', html)
    print(link, "\n  mp4:", len(mp4s), "subscriber-only:", subs, "thumbs:", thumbs[:2])
    for url in mp4s[:1]:
        for ref in (None, "https://rajegames21-pixel.github.io/"):
            headers = {"User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)", "Range": "bytes=0-1023"}
            if ref:
                headers["Referer"] = ref
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as r:
                    print(f"  GET ref={ref}: {r.status} {r.headers.get('Content-Type')} {r.headers.get('Content-Range')} acao={r.headers.get('Access-Control-Allow-Origin')}")
            except Exception as e:
                print(f"  GET ref={ref}: FAIL {e}")
        x720 = re.sub(r"/x240/", "/x720/", thumbs[0]) if thumbs else ""
        if x720:
            try:
                with urllib.request.urlopen(urllib.request.Request(x720, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
                    print("  poster x720:", r.status, r.headers.get("Content-Type"))
            except Exception as e:
                print("  poster x720: FAIL", e)
        tested += 1
    if tested >= 5:
        break
