"""Diagnóstico temporário: onde está o feed do piauinoticias.com?"""
import re, sys, urllib.request, urllib.error
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
for url in ["https://piauinoticias.com/", "https://piauinoticias.com/feed/", "https://piauinoticias.com/rss",
            "https://piauinoticias.com/feed", "https://piauinoticias.com/rss.xml", "https://piauinoticias.com/?feed=rss2"]:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            body = r.read(400000).decode("utf-8", "replace")
            print(f"{r.status} {url} -> {r.geturl()} type={r.headers.get('Content-Type')} server={r.headers.get('Server')} len={len(body)}")
            print("   início:", repr(body[:200]))
            for m in re.findall(r'<link[^>]+(?:rss|atom)[^>]*>', body, re.I)[:5]:
                print("   feed link:", m[:200])
            if "generator" in body:
                g = re.search(r'<meta name="generator" content="([^"]+)"', body)
                print("   generator:", g.group(1) if g else None)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} {url} server={e.headers.get('Server')} body={e.read(200)!r}")
    except Exception as e:
        print(f"FAIL {url}: {e}")
