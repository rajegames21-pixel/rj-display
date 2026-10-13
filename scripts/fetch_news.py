#!/usr/bin/env python3
"""Busca as notícias (g1 + Google Notícias) de cada estado e salva em JSON.

Roda no GitHub Actions (sem restrição de CORS). O site lê os arquivos
gerados em news/<UF>.json a partir da branch `news-data`.
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path

REGIONS = {
    "AC": ("Acre", "acre"), "AL": ("Alagoas", "alagoas"), "AP": ("Amapá", "amapa"),
    "AM": ("Amazonas", "amazonas"), "BA": ("Bahia", "bahia"), "CE": ("Ceará", "ceara"),
    "DF": ("Distrito Federal", "distrito-federal"), "ES": ("Espírito Santo", "espirito-santo"),
    "GO": ("Goiás", "goias"), "MA": ("Maranhão", "maranhao"), "MT": ("Mato Grosso", "mato-grosso"),
    "MS": ("Mato Grosso do Sul", "mato-grosso-do-sul"), "MG": ("Minas Gerais", "minas-gerais"),
    "PA": ("Pará", "para"), "PB": ("Paraíba", "paraiba"), "PR": ("Paraná", "parana"),
    "PE": ("Pernambuco", "pernambuco"), "PI": ("Piauí", "piaui"), "RJ": ("Rio de Janeiro", "rio-de-janeiro"),
    "RN": ("Rio Grande do Norte", "rio-grande-do-norte"), "RS": ("Rio Grande do Sul", "rio-grande-do-sul"),
    "RO": ("Rondônia", "rondonia"), "RR": ("Roraima", "roraima"), "SC": ("Santa Catarina", "santa-catarina"),
    "SP": ("São Paulo", "sao-paulo"), "SE": ("Sergipe", "sergipe"), "TO": ("Tocantins", "tocantins"),
}
GOOGLE = "https://news.google.com/rss"
GOOGLE_PARAMS = "hl=pt-BR&gl=BR&ceid=BR:pt-419"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
MAX_NEWS = 80
OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "news")


def feeds_for(code):
    if code == "BR":
        return [
            "https://g1.globo.com/rss/g1/",
            f"{GOOGLE}?{GOOGLE_PARAMS}",
            f"{GOOGLE}/headlines/section/topic/NATION?{GOOGLE_PARAMS}",
        ]
    name, slug = REGIONS[code]
    query = urllib.parse.quote(f'"{name}" when:2d')
    return [
        f"https://g1.globo.com/rss/g1/{code.lower()}/{slug}/",
        f"{GOOGLE}/search?q={query}&{GOOGLE_PARAMS}",
    ]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RJC Display news bot)"})
    with urllib.request.urlopen(req, timeout=20) as res:
        return res.read()


def html_to_text(raw):
    text = re.sub(r"<[^>]+>", " ", raw or "")
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def find_image(item, description):
    for tag in ("content", "thumbnail"):
        el = item.find(MEDIA_NS + tag)
        if el is not None and el.get("url"):
            return el.get("url")
    enc = item.find("enclosure")
    if enc is not None and (enc.get("type") or "").startswith("image/") and enc.get("url"):
        return enc.get("url")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description or "", re.I)
    return html.unescape(m.group(1)) if m else ""


def parse(xml_bytes, url):
    root = ET.fromstring(xml_bytes)
    is_google = "news.google.com" in url
    default_source = "Google Notícias" if is_google else "g1"
    items = []
    for item in root.iter("item"):
        get = lambda tag: (item.findtext(tag) or "").strip()
        title, link, description = get("title"), get("link"), get("description")
        source = get("source") or default_source
        if is_google:
            cut = title.rfind(" - ")
            if cut > 0:
                if source == default_source:
                    source = title[cut + 3:]
                title = title[:cut]
        summary = "" if is_google else html_to_text(description)
        if len(summary) > 240:
            summary = summary[:237].rstrip() + "…"
        if summary == title:
            summary = ""
        try:
            date = int(parsedate_to_datetime(get("pubDate")).timestamp() * 1000)
        except Exception:
            date = 0
        if title and link:
            items.append({
                "id": link, "link": link, "title": title, "summary": summary,
                "source": source, "image": find_image(item, description), "date": date,
            })
    return items


def norm(title):
    t = unicodedata.normalize("NFD", title.lower())
    return re.sub(r"[^a-z0-9 ]", "", t)[:60]


def load_feed(url):
    try:
        items = parse(fetch(url), url)
        print(f"ok   {len(items):3d}  {url}")
        return items
    except Exception as err:
        print(f"FAIL      {url}: {err}")
        return []


def build(code):
    seen, news = set(), []
    for items in map(load_feed, feeds_for(code)):
        for n in items:
            key = norm(n["title"])
            if key not in seen:
                seen.add(key)
                news.append(n)
    news.sort(key=lambda n: n["date"], reverse=True)
    return news[:MAX_NEWS]


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    codes = ["BR", *REGIONS]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(zip(codes, pool.map(build, codes)))
    updated = int(time.time() * 1000)
    for code, news in results.items():
        (OUT_DIR / f"{code}.json").write_text(
            json.dumps({"updated": updated, "items": news}, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in results.values())
    print(f"\n{total} notícias salvas em {OUT_DIR}/")
    if results["BR"] == []:
        sys.exit("Nenhuma notícia nacional carregada")


if __name__ == "__main__":
    main()
