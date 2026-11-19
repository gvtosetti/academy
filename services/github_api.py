"""Integracao read-only com a GitHub REST API para metadados publicos.

- Nao exige token. Se `GITHUB_TOKEN` existir em st.secrets ou no ambiente, e
  usado apenas no header do servidor (nunca enviado ao navegador nem logado).
- Timeouts curtos, cache com TTL e tratamento de rate limit.
- Nunca clona, instala ou executa codigo de repositorios.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import requests

log = logging.getLogger("academy.github")

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
TIMEOUT = (4, 8)  # (connect, read) em segundos


@dataclass
class ApiResult:
    ok: bool
    data: Any = None
    error: Optional[str] = None
    rate_limited: bool = False
    reset_at: Optional[int] = None
    meta: dict = field(default_factory=dict)


def _token() -> Optional[str]:
    try:
        import streamlit as st

        tok = st.secrets.get("GITHUB_TOKEN")  # type: ignore[attr-defined]
        if tok:
            return str(tok)
    except Exception:  # secrets ausentes -> modo anonimo
        pass
    return os.environ.get("GITHUB_TOKEN") or None


def _headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "academy-learning-app"}
    tok = _token()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _get(url: str, params: Optional[dict] = None, raw: bool = False) -> ApiResult:
    try:
        resp = requests.get(url, headers=_headers() if not raw else {"User-Agent": "academy-learning-app"},
                            params=params, timeout=TIMEOUT)
    except requests.RequestException as exc:
        log.warning("github request failed: %s (%s)", url, type(exc).__name__)
        return ApiResult(False, error="GitHub indisponivel no momento (falha de rede ou timeout).")

    remaining = resp.headers.get("X-RateLimit-Remaining")
    if resp.status_code in (403, 429) and (remaining == "0" or "rate limit" in resp.text.lower()):
        reset = int(resp.headers.get("X-RateLimit-Reset", "0") or 0)
        mins = max(1, int((reset - time.time()) / 60)) if reset else None
        msg = "Limite de requisicoes da API do GitHub atingido."
        if mins:
            msg += f" Tente novamente em ~{mins} min."
        log.info("github rate limited; reset=%s", reset)
        return ApiResult(False, error=msg, rate_limited=True, reset_at=reset)
    if resp.status_code == 404:
        return ApiResult(False, error="Recurso nao encontrado no GitHub (404).")
    if not resp.ok:
        log.warning("github status %s for %s", resp.status_code, url)
        return ApiResult(False, error=f"GitHub respondeu com status {resp.status_code}.")
    if raw:
        return ApiResult(True, data=resp.text)
    try:
        return ApiResult(True, data=resp.json(), meta={"remaining": remaining})
    except ValueError:
        return ApiResult(False, error="Resposta invalida do GitHub.")


def split_repo(full: str) -> tuple[str, Optional[str], Optional[str]]:
    """'owner/repo' ou 'owner/repo/tree/main/path' -> (owner, repo, subpath)."""
    parts = full.strip("/").split("/")
    owner = parts[0]
    repo = parts[1] if len(parts) > 1 else None
    return owner, repo, None


def fetch_repo(full_name: str) -> ApiResult:
    res = _get(f"{API}/repos/{full_name}")
    if not res.ok:
        return res
    j = res.data
    res.data = {
        "full_name": j.get("full_name"),
        "description": j.get("description"),
        "language": j.get("language"),
        "pushed_at": j.get("pushed_at"),
        "updated_at": j.get("updated_at"),
        "default_branch": j.get("default_branch") or "main",
        "license": (j.get("license") or {}).get("spdx_id"),
        "homepage": j.get("homepage") or None,
        "topics": j.get("topics") or [],
        "archived": bool(j.get("archived")),
        "html_url": j.get("html_url"),
    }
    return res


def fetch_org(org: str) -> ApiResult:
    res = _get(f"{API}/orgs/{org}")
    if res.ok:
        j = res.data
        res.data = {"login": j.get("login"), "name": j.get("name"), "description": j.get("description"),
                    "public_repos": j.get("public_repos"), "blog": j.get("blog"), "html_url": j.get("html_url")}
    return res


def fetch_root_contents(full_name: str, path: str = "") -> ApiResult:
    res = _get(f"{API}/repos/{full_name}/contents/{path}".rstrip("/"))
    if res.ok and isinstance(res.data, list):
        res.data = sorted(
            ({"name": x.get("name"), "type": x.get("type"), "path": x.get("path")} for x in res.data),
            key=lambda x: (x["type"] != "dir", x["name"].lower()),
        )
    return res


def fetch_readme(full_name: str, branch: str = "main", path: str = "README.md") -> ApiResult:
    """README via raw.githubusercontent (nao consome cota da REST API)."""
    return _get(f"{RAW}/{full_name}/{branch}/{path}", raw=True)


# ---- versoes com cache para a UI ---------------------------------------
try:
    import streamlit as st

    _TTL_META = 6 * 3600
    _TTL_ERR = 300

    @st.cache_data(ttl=_TTL_META, show_spinner=False)
    def _cached_repo(full_name: str) -> ApiResult:
        return fetch_repo(full_name)

    @st.cache_data(ttl=_TTL_META, show_spinner=False)
    def _cached_contents(full_name: str, path: str) -> ApiResult:
        return fetch_root_contents(full_name, path)

    @st.cache_data(ttl=_TTL_META, show_spinner=False)
    def _cached_readme(full_name: str, branch: str, path: str) -> ApiResult:
        return fetch_readme(full_name, branch, path)

    @st.cache_data(ttl=_TTL_META, show_spinner=False)
    def _cached_org(org: str) -> ApiResult:
        return fetch_org(org)

    def _no_cache_errors(fn, *args) -> ApiResult:
        """Falhas nao devem ficar em cache por 6h: limpa a entrada se der erro."""
        res = fn(*args)
        if not res.ok:
            fn.clear()  # simples e seguro: o proximo acesso tenta de novo
        return res

    def repo(full_name: str) -> ApiResult:
        return _no_cache_errors(_cached_repo, full_name)

    def contents(full_name: str, path: str = "") -> ApiResult:
        return _no_cache_errors(_cached_contents, full_name, path)

    def readme(full_name: str, branch: str = "main", path: str = "README.md") -> ApiResult:
        return _no_cache_errors(_cached_readme, full_name, branch, path)

    def org(name: str) -> ApiResult:
        return _no_cache_errors(_cached_org, name)

except ImportError:  # uso fora do Streamlit (testes)
    repo, contents, readme, org = fetch_repo, fetch_root_contents, fetch_readme, fetch_org
