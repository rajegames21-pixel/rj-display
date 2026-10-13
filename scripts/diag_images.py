"""Diagnóstico temporário: fontes de imagem para notícias sem foto."""
import json, re, sys, urllib.parse, urllib.request
sys.path.insert(0, "scripts")
import fetch_news as f

def show(url):
    try:
        items = f.parse(f.fetch(url), url)
        print(f"ok {len(items):3d} itens, {sum(1 for i in items if i['image']):3d} com imagem  {url}")
        for i in items[:2]:
            print("    ", i["title"][:70], "|", i["link"][:110], "|", i["image"][:90])
    except Exception as e:
        print("FAIL", url, e)

# 1) Feeds da Globo com foto
for u in ["https://ge.globo.com/rss/ge/", "https://gshow.globo.com/rss/gshow/", "https://g1.globo.com/rss/g1/pop-arte/",
          "https://g1.globo.com/rss/g1/sp/sao-paulo/policia/"]:
    show(u)

# 2) Bing Notícias (RSS com imagem)
for q in ["esportes", "famosos", "polícia"]:
    url = f"https://www.bing.com/news/search?q={urllib.parse.quote(q)}&format=rss&setlang=pt-br&cc=BR&mkt=pt-BR"
    try:
        raw = f.fetch(url).decode("utf-8", "replace")
        print("BING", q, "len", len(raw), "itens", raw.count("<item>"), "imagens", raw.count("News:Image"))
        m = re.search(r"<item>.*?</item>", raw, re.S)
        print("    ", (m.group(0) if m else raw[:500])[:700])
    except Exception as e:
        print("FAIL BING", q, e)

# 3) Google Notícias: descobrir o link original e pegar og:image
g = f"{f.GOOGLE}/headlines/section/topic/SPORTS?{f.GOOGLE_PARAMS}"
items = f.parse(f.fetch(g), g)[:3]
for it in items:
    link = it["link"]
    try:
        page = f.fetch(link).decode("utf-8", "replace")
        sg = re.search(r'data-n-a-sg="([^"]+)"', page)
        ts = re.search(r'data-n-a-ts="([^"]+)"', page)
        aid = link.split("/articles/")[1].split("?")[0]
        print("GOOGLE", aid[:40], "sg", bool(sg), "ts", bool(ts), "len", len(page))
        if sg and ts:
            req = [[["Fbv4je", json.dumps(["garturlreq", [["X", "X", ["X", "X"], None, None, 1, 1, "US:en", None, 1, None, None, None, None, None, 0, 1], "X", "X", 1, [1, 1, 1], 1, 1, None, 0, 0, None, 0], aid, int(ts.group(1)), sg.group(1)]), None, "generic"]]]
            body = urllib.parse.urlencode({"f.req": json.dumps(req)}).encode()
            r = urllib.request.Request("https://news.google.com/_/DotsSplashUi/data/batchexecute", data=body,
                                       headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8", "User-Agent": "Mozilla/5.0"})
            out = urllib.request.urlopen(r, timeout=15).read().decode()
            real = re.search(r'garturlres\\",\\"(https?://[^\\"]+)', out)
            print("    real:", real.group(1) if real else out[:300])
            if real:
                art = f.fetch(real.group(1)).decode("utf-8", "replace")
                og = re.search(r'property="og:image"\s+content="([^"]+)"', art) or re.search(r'content="([^"]+)"\s+property="og:image"', art)
                print("    og:image:", og.group(1) if og else None)
    except Exception as e:
        print("FAIL GOOGLE", link[:80], e)
