"""Ingestao de URLs: deteccao do provedor, escolha do adaptador e extracao isolada.

`analyze_url()` nunca levanta excecao: qualquer falha vira `Extraction(status="failed")`
com mensagem clara, para a interface seguir funcionando.

Para adicionar um provedor: crie uma classe com `name`, `matches(url)` e
`extract(url) -> Extraction` e inclua em `default_adapters()` antes do WebAdapter.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence
from urllib.parse import urlsplit

from services.ingest.base import Adapter, Child, Extraction, canonical_url, failed
from services.ingest.github import GitHubAdapter, parse_github_url
from services.ingest.net import FetchError, SafeFetcher, validate_url
from services.ingest.web import GenericAdapter, WebAdapter
from services.ingest.youtube import YouTubeAdapter, parse_youtube_url

log = logging.getLogger("academy.ingest")

__all__ = ["Detection", "Extraction", "Child", "analyze_url", "detect", "canonical_url", "default_adapters"]


@dataclass
class Detection:
    ok: bool
    url: str
    canonical_url: str = ""
    adapter: str = ""
    provider: str = ""
    kind: str = "unknown"
    error: Optional[str] = None


PROVIDER_LABEL = {"github": "GitHub", "youtube": "YouTube"}


def detect(url: str) -> Detection:
    """Passos 1 e 2 (sem rede): tipo de URL e provedor."""
    try:
        norm, host = validate_url(url)
    except FetchError as exc:
        return Detection(False, url, error=exc.message)
    if (gh := parse_github_url(norm)):
        return Detection(True, norm, canonical_url(norm), "github", "GitHub", gh["kind"])
    if (yt := parse_youtube_url(norm)):
        return Detection(True, norm, canonical_url(norm), "youtube", "YouTube", yt["kind"])
    return Detection(True, norm, canonical_url(norm), "web", host.removeprefix("www."), "webpage")


def default_adapters(fetcher: SafeFetcher) -> list:
    return [GitHubAdapter(fetcher), YouTubeAdapter(fetcher), WebAdapter(fetcher)]


def analyze_url(url: str, fetcher: Optional[SafeFetcher] = None, adapters: Optional[Sequence] = None) -> Extraction:
    det = detect(url)
    if not det.ok:
        return failed(url, "none", "", "unknown", "invalid_url", det.error or "URL invalida.")
    fetcher = fetcher or SafeFetcher()
    chain = list(adapters) if adapters is not None else default_adapters(fetcher)
    chosen = next((a for a in chain if a.matches(det.url)), None) or GenericAdapter(fetcher)
    try:
        ex = chosen.extract(det.url)
    except Exception as exc:  # isolamento: um adaptador com bug nao derruba a interface
        log.exception("adapter %s failed", getattr(chosen, "name", "?"))
        ex = failed(det.url, getattr(chosen, "name", "?"), det.provider, det.kind, "adapter_error",
                    f"Erro inesperado ao processar a fonte ({type(exc).__name__}).")
    if ex.status == "failed" and chosen.name == "web" and ex.error_code not in ("blocked_url", "robots_disallowed", "dns_failed"):
        log.info("web adapter failed (%s); generic fallback not retried to avoid duplicate requests", ex.error_code)
    ex.url = url.strip()
    return ex
