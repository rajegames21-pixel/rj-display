"""Diagnóstico temporário: como os vídeos aparecem nas matérias do g1."""
import re, sys
sys.path.insert(0, "scripts")
import fetch_news as f

links = []
for feed in ["https://g1.globo.com/rss/g1/", "https://g1.globo.com/rss/g1/sp/sao-paulo/", "https://g1.globo.com/rss/g1/politica/"]:
    links += [n["link"] for n in f.parse(f.fetch(feed), feed)][:25]
pats = ["og:video", "globoplay", "youtube", "<iframe", "data-video", "videoId", "video-id", "content-video", "playback", ".m3u8", ".mp4", "player.glb", "s04.video"]
shown = {p: 0 for p in pats}
with_video = 0
for link in links:
    try:
        html = f.fetch(link, timeout=15).decode("utf-8", "replace")
    except Exception as e:
        print("FAIL", link, e); continue
    hits = {p: len(re.findall(re.escape(p), html, re.I)) for p in pats}
    if any(hits[p] for p in ("content-video", "data-video", "videoId", "globoplay", "youtube")):
        with_video += 1
    print(link, {k: v for k, v in hits.items() if v})
    for p in pats:
        if hits[p] and shown[p] < 3:
            shown[p] += 1
            m = re.search(re.escape(p), html, re.I)
            print(f"   [{p}] ...{html[max(0, m.start()-250):m.end()+350]!r}...")
print("matérias com sinais de vídeo:", with_video, "de", len(links))
