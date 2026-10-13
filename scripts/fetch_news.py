#!/usr/bin/env python3
"""Busca as notícias (g1 + Google Notícias) de cada estado e salva em JSON.

Roda no GitHub Actions (sem restrição de CORS). O site lê os arquivos
gerados em news/<UF>.json a partir da branch `news-data`.

Para as matérias do g1, também abre a página da notícia e salva o texto
completo e as fotos em news/articles/<id>.json. Matérias já baixadas em
execuções anteriores são reaproveitadas (pasta passada como 2º argumento).
"""
import hashlib
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
from html.parser import HTMLParser
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
# Categorias: slug -> (seção do g1 ou None, busca/tópico do Google Notícias)
# Tópicos do Google começam com "topic:"; o resto é termo de busca.
CATEGORIES = {
    "politica": ("politica", "política"),
    "economia": ("economia", "topic:BUSINESS"),
    "mundo": ("mundo", "topic:WORLD"),
    "tecnologia": ("tecnologia", "topic:TECHNOLOGY"),
    "ciencia": ("ciencia", "topic:SCIENCE"),
    "saude": ("saude", "topic:HEALTH"),
    "esportes": (None, "topic:SPORTS"),
    "cinema": ("pop-arte/cinema", "cinema OR filme OR série OR streaming"),
    "musica": ("pop-arte/musica", "música OR cantor OR cantora OR show"),
    "famosos": (None, "famosos OR celebridades OR fofoca OR BBB"),
    "games": ("pop-arte/games", "games OR videogame OR PlayStation OR Xbox OR Nintendo"),
    "educacao": ("educacao", "educação OR Enem OR escola OR universidade"),
    "meio-ambiente": ("meio-ambiente", "meio ambiente OR clima OR desmatamento"),
    "carros": ("carros", "carros OR automóvel OR montadora"),
    "agro": ("economia/agronegocios", "agronegócio OR safra OR agro"),
    "turismo": ("turismo-e-viagem", "turismo OR viagem OR destino"),
    "concursos": ("trabalho-e-carreira/concursos", "concurso público OR edital"),
    "policia": (None, "polícia OR crime OR operação policial"),
}
GOOGLE = "https://news.google.com/rss"
GOOGLE_PARAMS = "hl=pt-BR&gl=BR&ceid=BR:pt-419"
MEDIA_NS = "{http://search.yahoo.com/mrss/}"
MAX_NEWS = 150
MAX_ARTICLE_FETCHES = 400   # matérias novas baixadas por execução
MAX_ARTICLE_CHARS = 12000
MAX_IMAGES = 6
ARTICLE_VERSION = 3         # mude para rebaixar todas as matérias
MAX_VIDEOS = 3
VIDEO_URL = re.compile(r'itemprop="contentUrl"\s+content="(https://[^"]+\.mp4)"')
VIDEO_THUMB = re.compile(r'itemprop="thumbnailUrl"\s+content="(https://[^"]+)"')
VIDEO_NAME = re.compile(r'itemprop="name"\s+content="([^"]*)"')
# Fotos que não são da matéria: miniaturas de vídeo, outros sites da Globo
# e os cartões de "veja também" (recorte 810x456)
NOT_ARTICLE_IMAGE = re.compile(r"video\.glbimg|s2-ge\.|s2-gshow\.|s2-globo|s2-valor|810x456/top|logo|icon|avatar|sprite", re.I)
OUT_DIR = Path(sys.argv[1] if len(sys.argv) > 1 else "news")
PREV_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else None


def feeds_for(code):
    if code.startswith("cat:"):
        section, google = CATEGORIES[code[4:]]
        feeds = [f"https://g1.globo.com/rss/g1/{section}/"] if section else []
        if google.startswith("topic:"):
            feeds.append(f"{GOOGLE}/headlines/section/topic/{google[6:]}?{GOOGLE_PARAMS}")
        else:
            feeds.append(f"{GOOGLE}/search?q={urllib.parse.quote(google + ' when:1d')}&{GOOGLE_PARAMS}")
        return feeds
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


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (RJC Display news bot)"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
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


class ArticleParser(HTMLParser):
    """Extrai parágrafos e fotos de uma matéria do g1."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs, self.fallback, self.images = [], [], []
        self._p = None          # texto do <p> atual
        self._p_main = False    # <p> é do corpo da matéria (content-text)
        self._skip = 0          # dentro de <script>/<style>
        self._media = []        # pilha de <div>/<figure>: True se é bloco de foto

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = a.get("class") or ""
        if tag in ("script", "style", "noscript"):
            self._skip += 1
        elif tag == "p":
            self._p, self._p_main = [], "content-text" in cls
        elif tag == "meta" and a.get("property") == "og:image" and a.get("content"):
            self.images.insert(0, a["content"])
        elif tag in ("div", "figure"):
            self._media.append(tag == "figure" or "content-media" in cls)
        elif tag in ("img", "amp-img"):
            # Só fotos dentro do corpo da matéria (blocos de mídia/figure)
            src = a.get("src") or a.get("data-src") or ""
            in_media = any(self._media) or "content-media" in cls
            if in_media and src.startswith("http") and "glbimg.com" in src and not NOT_ARTICLE_IMAGE.search(src):
                self.images.append(src)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("div", "figure"):
            if self._media:
                self._media.pop()
        elif tag == "p" and self._p is not None:
            text = re.sub(r"\s+", " ", "".join(self._p)).strip()
            if text:
                (self.paragraphs if self._p_main else self.fallback).append(text)
            self._p = None

    def handle_data(self, data):
        if self._p is not None and not self._skip:
            self._p.append(data)


def image_key(url):
    # A mesma foto aparece em vários tamanhos; compara pelo nome do arquivo
    return url.split("?")[0].rsplit("/", 1)[-1]


def find_videos(page):
    """Vídeos da matéria: o g1 publica o MP4 (360p) em metadados VideoObject."""
    videos, seen = [], set()
    for m in VIDEO_URL.finditer(page):
        src = html.unescape(m.group(1))
        vid = re.search(r"/(\d+)[_-]", src)
        key = vid.group(1) if vid else src
        if key in seen:
            continue
        seen.add(key)
        before = page[max(0, m.start() - 2000):m.start()]
        thumbs = VIDEO_THUMB.findall(before)
        names = VIDEO_NAME.findall(before)
        poster = thumbs[-1].replace("/x240/", "/x720/") if thumbs else ""
        videos.append({"src": src, "poster": poster, "title": html.unescape(names[-1]) if names else ""})
    return videos[:MAX_VIDEOS]


def fetch_article(link):
    parser = ArticleParser()
    page = fetch(link, timeout=15).decode("utf-8", "replace")
    parser.feed(page)
    paragraphs = parser.paragraphs or [p for p in parser.fallback if len(p) > 80]
    text, total = [], 0
    for p in paragraphs:
        if total + len(p) > MAX_ARTICLE_CHARS:
            break
        text.append(p)
        total += len(p)
    seen, images = set(), []
    for img in parser.images:
        key = image_key(img)
        if key not in seen:
            seen.add(key)
            images.append(img)
    return {"v": ARTICLE_VERSION, "paragraphs": text, "images": images[:MAX_IMAGES], "videos": find_videos(page)}


def article_id(link):
    return hashlib.sha1(link.encode()).hexdigest()[:16]


def attach_articles(results):
    """Baixa (ou reaproveita) o texto completo e as fotos das matérias do g1."""
    art_dir = OUT_DIR / "articles"
    art_dir.mkdir(parents=True, exist_ok=True)
    prev_dir = PREV_DIR / "articles" if PREV_DIR else None

    links = {n["link"] for news in results.values() for n in news if "g1.globo.com" in n["link"]}
    articles, to_fetch = {}, []
    for link in links:
        aid = article_id(link)
        prev = prev_dir / f"{aid}.json" if prev_dir else None
        cached = json.loads(prev.read_text(encoding="utf-8")) if prev and prev.exists() else None
        if cached and cached.get("v") == ARTICLE_VERSION:
            articles[link] = cached
        else:
            to_fetch.append(link)

    def get(link):
        try:
            return link, fetch_article(link)
        except Exception as err:
            print(f"FAIL artigo {link}: {err}")
            return link, None

    with ThreadPoolExecutor(max_workers=12) as pool:
        for link, art in pool.map(get, to_fetch[:MAX_ARTICLE_FETCHES]):
            if art:
                articles[link] = art

    for link, art in articles.items():
        (art_dir / f"{article_id(link)}.json").write_text(json.dumps(art, ensure_ascii=False), encoding="utf-8")

    for news in results.values():
        for n in news:
            art = articles.get(n["link"])
            if not art:
                continue
            if art["paragraphs"]:
                n["article"] = article_id(n["link"])
            imgs = ([n["image"]] if n["image"] else []) + art["images"]
            seen, uniq = set(), []
            for img in imgs:
                if image_key(img) not in seen:
                    seen.add(image_key(img))
                    uniq.append(img)
            n["images"] = uniq[:MAX_IMAGES]
            if art.get("videos"):
                n["videos"] = art["videos"]
            if not n["image"] and uniq:
                n["image"] = uniq[0]

    with_text = sum(1 for a in articles.values() if a["paragraphs"])
    print(f"Matérias: {len(articles)} prontas ({with_text} com texto), "
          f"{min(len(to_fetch), MAX_ARTICLE_FETCHES)} baixadas agora, "
          f"{max(0, len(to_fetch) - MAX_ARTICLE_FETCHES)} ficam para a próxima")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    codes = ["BR", *REGIONS, *(f"cat:{c}" for c in CATEGORIES)]
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(codes, pool.map(build, codes)))
    attach_articles(results)
    updated = int(time.time() * 1000)
    (OUT_DIR / "cat").mkdir(exist_ok=True)
    for code, news in results.items():
        name = f"cat/{code[4:]}" if code.startswith("cat:") else code
        (OUT_DIR / f"{name}.json").write_text(
            json.dumps({"updated": updated, "items": news}, ensure_ascii=False), encoding="utf-8")
    total = sum(len(v) for v in results.values())
    print(f"\n{total} notícias salvas em {OUT_DIR}/")
    if results["BR"] == []:
        sys.exit("Nenhuma notícia nacional carregada")


if __name__ == "__main__":
    main()
