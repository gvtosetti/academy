"""Extracao segura de HTML (stdlib `html.parser`): nada e executado nem renderizado.

Coleta titulo, meta tags (description, Open Graph, Twitter, author), canonical, idioma,
headings, texto principal (ignorando script/style/nav/footer/forms/svg) e links.
Scripts sao descartados sem leitura; JSON-LD e lido apenas como dado (json.loads).
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Optional
from urllib.parse import urljoin

SKIP = {"script", "style", "noscript", "template", "svg", "canvas", "iframe", "object", "embed",
        "nav", "footer", "form", "button", "select", "head"}
BLOCK = {"p", "div", "section", "article", "li", "br", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
         "pre", "blockquote", "dd", "dt", "td", "th", "main", "header", "summary", "details"}
VOID = {"br", "img", "meta", "link", "input", "hr", "source", "area", "base", "col", "wbr", "track", "param"}


@dataclass
class Page:
    title: Optional[str] = None
    meta: dict = field(default_factory=dict)
    canonical: Optional[str] = None
    lang: Optional[str] = None
    headings: list[str] = field(default_factory=list)
    text: str = ""
    links: list[dict] = field(default_factory=list)
    jsonld: list[dict] = field(default_factory=list)
    script_count: int = 0

    @property
    def description(self) -> Optional[str]:
        for k in ("og:description", "description", "twitter:description"):
            if self.meta.get(k):
                return self.meta[k]
        return None

    @property
    def best_title(self) -> Optional[str]:
        return self.meta.get("og:title") or self.meta.get("twitter:title") or self.title

    @property
    def author(self) -> Optional[str]:
        if self.meta.get("author") or self.meta.get("article:author"):
            return self.meta.get("author") or self.meta.get("article:author")
        for d in self.jsonld:
            a = d.get("author")
            if isinstance(a, dict) and isinstance(a.get("name"), str):
                return a["name"]
            if isinstance(a, list) and a and isinstance(a[0], dict) and isinstance(a[0].get("name"), str):
                return a[0]["name"]
            if isinstance(a, str):
                return a
        return None

    @property
    def likely_js_rendered(self) -> bool:
        return len(self.text) < 400 and self.script_count >= 3


class _Parser(HTMLParser):
    def __init__(self, base_url: str, max_text: int):
        super().__init__(convert_charrefs=True)
        self.base, self.max_text = base_url, max_text
        self.page = Page()
        self._skip = 0
        self._stack: list[str] = []
        self._in_title = False
        self._heading: Optional[list[str]] = None
        self._link: Optional[dict] = None
        self._jsonld: Optional[list[str]] = None
        self._buf: list[str] = []
        self._size = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.page.lang = a["lang"][:10]
        if tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and a.get("content") and len(self.page.meta) < 80:
                self.page.meta.setdefault(key, html.unescape(a["content"]).strip()[:1000])
            return
        if tag == "link" and "canonical" in a.get("rel", "").lower() and a.get("href"):
            self.page.canonical = urljoin(self.base, a["href"])
            return
        if tag == "script":
            self.page.script_count += 1
            if a.get("type", "").lower() == "application/ld+json":
                self._jsonld = []
        if tag == "title":
            self._in_title = True
        if tag in VOID:
            if tag == "br":
                self._emit("\n")
            return
        self._stack.append(tag)
        if tag in SKIP:
            self._skip += 1
            return
        if tag in {"h1", "h2", "h3"} and not self._skip:
            self._heading = []
        if tag == "a" and a.get("href") and not self._skip:
            self._link = {"href": urljoin(self.base, a["href"]), "text": []}
        if tag in BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._jsonld is not None:
            raw = "".join(self._jsonld)[:50_000]
            self._jsonld = None
            try:
                data = json.loads(raw)
                items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
                self.page.jsonld.extend(d for d in items[:10] if isinstance(d, dict))
            except (ValueError, AttributeError):
                pass
        if tag in VOID or tag not in self._stack:
            return
        while self._stack:
            t = self._stack.pop()
            if t in SKIP:
                self._skip = max(0, self._skip - 1)
            if t == tag:
                break
        if tag in {"h1", "h2", "h3"} and self._heading is not None:
            h = " ".join("".join(self._heading).split())
            if h and len(self.page.headings) < 80:
                self.page.headings.append(h[:200])
            self._heading = None
        if tag == "a" and self._link is not None:
            t = " ".join("".join(self._link["text"]).split())
            if t and self._link["href"].startswith("https://") and len(self.page.links) < 200:
                self.page.links.append({"url": self._link["href"], "text": t[:120]})
            self._link = None
        if tag in BLOCK:
            self._emit("\n")

    def handle_data(self, data):
        if self._jsonld is not None:
            self._jsonld.append(data)
            return
        if self._in_title:
            self.page.title = ((self.page.title or "") + data).strip()[:300]
            return
        if self._skip:
            return
        if self._heading is not None:
            self._heading.append(data)
        if self._link is not None:
            self._link["text"].append(data)
        self._emit(data)

    def _emit(self, s: str):
        if self._size < self.max_text:
            self._buf.append(s)
            self._size += len(s)


def parse_html(doc: str, base_url: str, max_text: int = 30_000) -> Page:
    p = _Parser(base_url, max_text)
    try:
        p.feed(doc[:3_000_000])
        p.close()
    except Exception:  # HTML malformado: fica com o que foi lido
        pass
    text = "".join(p._buf)
    lines = [" ".join(l.split()) for l in text.splitlines()]
    p.page.text = "\n".join(l for l in lines if len(l) > 1)
    p.page.text = re.sub(r"\n{3,}", "\n\n", p.page.text).strip()
    return p.page
