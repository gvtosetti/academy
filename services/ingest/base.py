"""Tipos comuns da ingestao: resultado da extracao, URL canonica e contrato dos adaptadores."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

MAX_TEXT = 12_000  # caracteres de texto da fonte enviados para analise
MAX_CHILDREN = 30
MAX_LINKS = 20

ExtractionStatus = Literal["ok", "partial", "failed"]

_TRACKING = re.compile(r"^(utm_.*|fbclid|gclid|mc_[a-z]+|ref|ref_src|si|feature|igshid|spm|_hs.*)$", re.I)


def canonical_url(url: str) -> str:
    """Chave de deduplicacao: mesma URL logica => mesma string.

    https, host minusculo sem `www.`/`m.`, sem fragmento, sem parametros de rastreamento,
    query ordenada, sem barra final. Regras especificas para YouTube e GitHub.
    """
    p = urlsplit(url.strip())
    host = (p.hostname or "").lower().rstrip(".")
    for pre in ("www.", "m.", "mobile."):
        if host.startswith(pre):
            host = host[len(pre):]
    path = re.sub(r"/{2,}", "/", p.path or "/")
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False) if not _TRACKING.match(k)]
    if host == "youtu.be":
        vid = path.strip("/").split("/")[0]
        host, path, query = "youtube.com", "/watch", [("v", vid)]
    if host == "youtube.com":
        if path.startswith(("/shorts/", "/embed/", "/live/")):
            vid = path.strip("/").split("/")[1] if path.count("/") >= 2 else ""
            path, query = "/watch", [("v", vid)]
        keep = {"/watch": {"v"}, "/playlist": {"list"}}.get(path)
        if keep is not None:
            query = [(k, v) for k, v in query if k in keep]
        elif path.startswith("/@") or path.startswith(("/channel/", "/c/", "/user/")):
            query = []
            path = path.lower() if path.startswith("/@") else path
    if host == "github.com":
        parts = [x for x in path.split("/") if x]
        if len(parts) >= 2:
            parts[1] = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
            parts[0], parts[1] = parts[0].lower(), parts[1].lower()
        elif parts:
            parts[0] = parts[0].lower()
        path = "/" + "/".join(parts)
        query = []
    path = path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


@dataclass
class Child:
    """Sub-item encontrado na fonte (playlist de um canal, repo de uma organizacao...)."""

    title: str
    url: str
    kind: str
    meta: dict = field(default_factory=dict)


@dataclass
class Extraction:
    """O que foi EFETIVAMENTE obtido da fonte. Nada aqui e inferido."""

    url: str
    canonical_url: str
    adapter: str
    provider: str
    kind: str  # repository, directory, file, organization, video, playlist, channel, article, docs, roadmap, webpage, document, unknown
    status: ExtractionStatus = "ok"
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    language: Optional[str] = None
    text: str = ""
    headings: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    updated_at: Optional[str] = None
    links: list[dict] = field(default_factory=list)
    children: list[Child] = field(default_factory=list)
    facts: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    error: Optional[str] = None
    error_code: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def __post_init__(self) -> None:
        # registros persistidos voltam como dict; normaliza para Child
        self.children = [c if isinstance(c, Child) else Child(title=str(c.get("title") or ""), url=str(c.get("url") or ""),
                                                             kind=str(c.get("kind") or ""), meta=dict(c.get("meta") or {}))
                         for c in (self.children or []) if isinstance(c, (Child, dict))]

    def clamp(self) -> "Extraction":
        self.text = (self.text or "")[:MAX_TEXT]
        self.headings = [h[:200] for h in self.headings[:60]]
        self.children = self.children[:MAX_CHILDREN]
        self.links = self.links[:MAX_LINKS]
        self.topics = self.topics[:20]
        if self.description:
            self.description = self.description[:2000]
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Extraction":
        d = dict(d)
        d["children"] = [Child(**c) for c in d.get("children", [])]
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @property
    def usable(self) -> bool:
        return self.status != "failed" and bool(self.title or self.description or self.text)


def failed(url: str, adapter: str, provider: str, kind: str, code: str, message: str) -> Extraction:
    try:
        canon = canonical_url(url)
    except ValueError:
        canon = url
    return Extraction(url=url, canonical_url=canon, adapter=adapter, provider=provider, kind=kind,
                      status="failed", error=message, error_code=code)


class Adapter(Protocol):
    name: str

    def matches(self, url: str) -> bool: ...

    def extract(self, url: str) -> Extraction: ...
