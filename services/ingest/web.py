"""Adaptadores Web (artigos, documentacao, paginas educacionais, roadmaps) e Generico.

Web: HTTP seguro + parsing HTML sem execucao. Para paginas renderizadas por JavaScript,
usa apenas metadados (Open Graph, description, JSON-LD) e sinaliza a limitacao. Se
`ACADEMY_ENABLE_RENDERER=1` e o Playwright estiver instalado, faz uma renderizacao
controlada (navegador headless isolado, toda requisicao revalidada contra SSRF, sem
downloads, timeout curto). Por padrao fica desligado.

Generico: qualquer URL https que nao seja HTML (PDF, planilha...) ou que nao se encaixe
em outro adaptador. Gera ficha preliminar so com o que a resposta informa.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional
from urllib.parse import urlsplit

from services.ingest.base import Child, Extraction, canonical_url, failed
from services.ingest.html_extract import Page, parse_html
from services.ingest.net import FetchError, SafeFetcher, is_public_ip, validate_url

log = logging.getLogger("academy.ingest.web")

DOC_HOST = re.compile(r"^(docs|doc|developer|developers|learn|wiki|api)\.", re.I)
DOC_PATH = re.compile(r"/(docs?|documentation|guides?|reference|api|manual)(/|$)", re.I)


def _kind(url: str, page: Page) -> str:
    blob = " ".join([url, page.best_title or "", page.meta.get("og:type", "")]).lower()
    if "roadmap" in blob:
        return "roadmap"
    p = urlsplit(url)
    if DOC_HOST.search(p.hostname or "") or DOC_PATH.search(p.path or ""):
        return "docs"
    if page.meta.get("og:type") == "article" or any(d.get("@type") in ("Article", "BlogPosting", "TechArticle")
                                                  for d in page.jsonld):
        return "article"
    if any(d.get("@type") == "Course" for d in page.jsonld) or re.search(r"\b(course|curso)\b", blob):
        return "course"
    return "webpage"


def _provider(url: str, page: Page) -> str:
    site = page.meta.get("og:site_name")
    if site:
        return site[:80]
    title = page.best_title or ""
    m = re.search(r"[|—–-]\s*([^|—–-]{2,40})$", title)
    if m:
        return m.group(1).strip()
    return (urlsplit(url).hostname or "").removeprefix("www.")


def page_to_extraction(url: str, final_url: str, page: Page, adapter: str = "web") -> Extraction:
    canon_src = page.canonical if page.canonical and page.canonical.startswith("https://") and \
        urlsplit(page.canonical).hostname == urlsplit(final_url).hostname else final_url
    ex = Extraction(
        url=url, canonical_url=canonical_url(canon_src), adapter=adapter, provider=_provider(final_url, page),
        kind=_kind(final_url, page), title=page.best_title, description=page.description, author=page.author,
        language=(page.lang or page.meta.get("og:locale") or "")[:5] or None, text=page.text,
        headings=page.headings,
        links=[l for l in page.links if urlsplit(l["url"]).hostname != urlsplit(final_url).hostname][:20],
        facts={k: v for k, v in page.meta.items() if k in ("og:type", "og:site_name", "article:published_time",
                                                            "article:modified_time", "keywords")},
    )
    if page.meta.get("keywords"):
        ex.topics = [t.strip().lower() for t in page.meta["keywords"].split(",") if t.strip()][:15]
    ex.updated_at = page.meta.get("article:modified_time") or page.meta.get("article:published_time")
    if page.likely_js_rendered:
        ex.status = "partial"
        ex.warnings.append("A pagina parece ser renderizada por JavaScript: apenas metadados foram usados.")
    if not ex.title:
        ex.missing.append("titulo")
    if not ex.description:
        ex.missing.append("descricao da fonte")
    if not ex.author:
        ex.missing.append("autor")
    return ex.clamp()


class WebAdapter:
    name = "web"

    def __init__(self, fetcher: SafeFetcher):
        self.fetcher = fetcher

    def matches(self, url: str) -> bool:
        return url.lower().startswith("https://")

    def extract(self, url: str) -> Extraction:
        try:
            res = self.fetcher.get(url)
        except FetchError as exc:
            return failed(url, self.name, urlsplit(url).hostname or "", "webpage", exc.code, exc.message)
        if res.body_skipped or res.content_type not in ("text/html", "application/xhtml+xml", ""):
            return GenericAdapter(self.fetcher).from_response(url, res)
        page = parse_html(res.text, res.url)
        ex = page_to_extraction(url, res.url, page)
        if res.truncated:
            ex.warnings.append("Pagina muito grande: apenas o inicio foi analisado.")
        if page.likely_js_rendered and os.environ.get("ACADEMY_ENABLE_RENDERER") == "1":
            rendered = render_page(res.url, self.fetcher)
            if rendered:
                ex = page_to_extraction(url, res.url, parse_html(rendered, res.url))
                ex.warnings.append("Conteudo obtido por renderizacao controlada (navegador isolado).")
        return ex


class GenericAdapter:
    name = "generic"

    def __init__(self, fetcher: SafeFetcher):
        self.fetcher = fetcher

    def matches(self, url: str) -> bool:
        return url.lower().startswith("https://")

    def from_response(self, url: str, res) -> Extraction:
        path = urlsplit(res.url).path
        name = path.rsplit("/", 1)[-1] or (urlsplit(res.url).hostname or "")
        kind = "document" if res.content_type in ("application/pdf",) or re.search(r"\.(pdf|docx?|pptx?|xlsx?)$", path, re.I) \
            else "unknown"
        ex = Extraction(url=url, canonical_url=canonical_url(res.url), adapter=self.name,
                        provider=(urlsplit(res.url).hostname or "").removeprefix("www."), kind=kind, status="partial",
                        title=None, facts={"content_type": res.content_type, "file_name": name,
                                           "content_length": res.headers.get("Content-Length")})
        if not res.body_skipped and res.text:
            ex.text = res.text[:12000]
        ex.missing += ["titulo", "descricao da fonte", "autor"]
        ex.warnings.append(f"Formato '{res.content_type or 'desconhecido'}' sem extracao de conteudo: ficha preliminar, revise manualmente.")
        return ex.clamp()

    def extract(self, url: str) -> Extraction:
        try:
            res = self.fetcher.get(url)
        except FetchError as exc:
            return failed(url, self.name, urlsplit(url).hostname or "", "unknown", exc.code, exc.message)
        if res.content_type in ("text/html", "application/xhtml+xml"):
            return page_to_extraction(url, res.url, parse_html(res.text, res.url), adapter=self.name)
        return self.from_response(url, res)


def render_page(url: str, fetcher: SafeFetcher, timeout_ms: int = 12000) -> Optional[str]:
    """Renderizacao controlada opcional. Retorna HTML renderizado ou None."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    def guard(route):
        req = route.request
        try:
            _, host = validate_url(req.url)
            fetcher.resolve_public(host)
        except FetchError:
            return route.abort()
        if req.resource_type in ("media", "font", "image", "websocket", "eventsource", "manifest"):
            return route.abort()
        return route.continue_()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--disable-extensions", "--no-first-run"])
            ctx = browser.new_context(accept_downloads=False, java_script_enabled=True, user_agent="AcademyCurator/1.0")
            ctx.route("**/*", guard)
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            content = page.content()[:3_000_000]
            browser.close()
            return content
    except Exception as exc:
        log.info("render failed: %s", type(exc).__name__)
        return None
