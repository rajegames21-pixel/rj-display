"""Diagnóstico temporário: por que os MP4 do g1 dão 400?"""
import re, sys, urllib.request, urllib.error
sys.path.insert(0, "scripts")
import fetch_news as f

feed = "https://g1.globo.com/rss/g1/"
links = [n["link"] for n in f.parse(f.fetch(feed), feed)][:10]
done = 0
for link in links:
    page = f.fetch(link, timeout=15).decode("utf-8", "replace")
    mp4s = re.findall(r'itemprop="contentUrl" content="([^"]+\.mp4[^"]*)"', page)
    if not mp4s:
        continue
    url = mp4s[0]
    print("URL:", url)
    vid = re.search(r"/(\d+)[_-]", url).group(1)
    for m in re.finditer(r"vodstreaming[^\"' ]{0,300}", page):
        print("  ocorrência:", m.group(0)[:300])
        break
    for label, headers, method in [
        ("GET sem range", {"User-Agent": "Mozilla/5.0"}, "GET"),
        ("HEAD", {"User-Agent": "Mozilla/5.0"}, "HEAD"),
        ("GET referer g1", {"User-Agent": "Mozilla/5.0", "Referer": "https://g1.globo.com/", "Range": "bytes=0-1023"}, "GET"),
    ]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method=method), timeout=15) as r:
                print(f"  {label}: {r.status} {r.headers.get('Content-Type')} len={r.headers.get('Content-Length')}")
        except urllib.error.HTTPError as e:
            print(f"  {label}: HTTP {e.code} body={e.read()[:200]!r}")
        except Exception as e:
            print(f"  {label}: FAIL {e}")
    # API pública de vídeo da Globo
    for api in [f"https://api.video.globo.com/videos/{vid}.json", f"https://playback.video.globo.com/v4/video-session"]:
        try:
            with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"}), timeout=15) as r:
                print(f"  {api}: {r.status} {r.read()[:300]!r}")
        except urllib.error.HTTPError as e:
            print(f"  {api}: HTTP {e.code}")
        except Exception as e:
            print(f"  {api}: FAIL {e}")
    done += 1
    if done >= 2:
        break
