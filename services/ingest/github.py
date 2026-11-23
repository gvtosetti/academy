"""Adaptador GitHub (REST API v3, somente leitura).

Reconhece repositorio, organizacao/usuario, diretorio (`/tree/<ref>/<path>`), arquivo
Markdown/README (`/blob/<ref>/<path>.md`). Para diretorios, analisa o proprio diretorio
(README local + listagem), nao apenas a raiz. Para organizacoes, lista candidatos
relevantes (nao-fork, nao-arquivados, por estrelas e atividade) sem importar nada.

Limites: 1 nivel de listagem, ate 60 entradas, README ate 10k caracteres. Nada e
clonado, instalado ou executado. `GITHUB_TOKEN` (opcional) so vai para api.github.com.
"""
from __future__ import annotations

import os
import re
from typing import Optional
from urllib.parse import quote, urlsplit

from services.ingest.base import Child, Extraction, canonical_url, failed
from services.ingest.net import FetchError, SafeFetcher
from utils.safe import sanitize_markdown

API = "https://api.github.com"
RESERVED = {"orgs", "topics", "collections", "trending", "marketplace", "features", "settings", "login",
            "about", "pricing", "sponsors", "explore", "notifications", "search", "enterprise", "apps"}
NAME = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
MAX_ENTRIES = 60
MAX_README = 10_000
ORG_CANDIDATES = 8
DOC_DIRS = {"docs", "doc", "documentation", "guides", "wiki"}
EXAMPLE_DIRS = {"examples", "example", "samples", "notebooks", "tutorials", "demos", "cookbook"}


def parse_github_url(url: str) -> Optional[dict]:
    p = urlsplit(url)
    if (p.hostname or "").lower() not in ("github.com", "www.github.com"):
        return None
    parts = [x for x in p.path.split("/") if x]
    if not parts or parts[0].lower() in RESERVED or not NAME.match(parts[0]):
        return None
    if len(parts) == 1:
        return {"kind": "organization", "owner": parts[0]}
    repo = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
    if not NAME.match(repo):
        return None
    info = {"kind": "repository", "owner": parts[0], "repo": repo, "ref": None, "path": ""}
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        info["ref"], info["path"] = parts[3], "/".join(parts[4:])
        if parts[2] == "tree":
            info["kind"] = "directory" if info["path"] else "repository"
        else:
            info["kind"] = "file"
    return info


class GitHubAdapter:
    name = "github"

    def __init__(self, fetcher: SafeFetcher, token: Optional[str] = None):
        self.fetcher = fetcher
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")

    def matches(self, url: str) -> bool:
        return parse_github_url(url) is not None

    # -- http --------------------------------------------------------------
    def _api(self, path: str, raw: bool = False, params: Optional[dict] = None):
        h = {"Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        try:
            res = self.fetcher.get(API + path, params=params, headers=h, robots=False,
                                   auth_hosts=("api.github.com",), max_bytes=1_500_000)
        except FetchError as exc:
            if exc.status == 403 or exc.status == 429:
                raise FetchError("rate_limited", "Limite da API do GitHub atingido (configure GITHUB_TOKEN ou tente mais tarde).",
                                 exc.status) from None
            if exc.status == 404:
                raise FetchError("not_found", "Repositorio, organizacao ou caminho nao encontrado no GitHub (ou e privado).",
                                 404) from None
            raise
        return res.text if raw else res.json()

    def _readme(self, owner: str, repo: str, directory: str = "", ref: Optional[str] = None) -> Optional[str]:
        path = f"/repos/{owner}/{repo}/readme" + (f"/{quote(directory)}" if directory else "")
        try:
            return self._api(path, raw=True, params={"ref": ref} if ref else None)
        except FetchError as exc:
            if exc.code == "not_found":
                return None
            raise

    # -- extract -----------------------------------------------------------
    def extract(self, url: str) -> Extraction:
        info = parse_github_url(url)
        if not info:
            return failed(url, self.name, "GitHub", "unknown", "invalid_url", "URL do GitHub nao reconhecida.")
        try:
            if info["kind"] == "organization":
                return self._org(url, info["owner"]).clamp()
            return self._repo(url, info).clamp()
        except FetchError as exc:
            return failed(url, self.name, "GitHub", info["kind"], exc.code, exc.message)
        except (ValueError, KeyError, TypeError):
            return failed(url, self.name, "GitHub", info["kind"], "bad_response", "Resposta inesperada da API do GitHub.")

    def _repo(self, url: str, info: dict) -> Extraction:
        owner, repo = info["owner"], info["repo"]
        meta = self._api(f"/repos/{owner}/{repo}")
        full = meta.get("full_name") or f"{owner}/{repo}"
        ref = info["ref"] or meta.get("default_branch") or "main"
        path = info["path"].strip("/")
        # canonica pelo nome atual (repos renomeados redirecionam: evita duplicatas)
        mode = "blob" if info["kind"] == "file" else "tree"
        canon = f"https://github.com/{full}" + (f"/{mode}/{ref}/{path}" if path else "")
        ex = Extraction(url=url, canonical_url=canonical_url(canon), adapter=self.name, provider="GitHub",
                        kind=info["kind"], title=full + (f"/{path}" if path else ""),
                        description=meta.get("description"), author=(meta.get("owner") or {}).get("login"),
                        topics=list(meta.get("topics") or []), updated_at=meta.get("pushed_at"))
        ex.facts = {"full_name": full, "stars": meta.get("stargazers_count"), "forks": meta.get("forks_count"),
                    "license": (meta.get("license") or {}).get("spdx_id"), "homepage": meta.get("homepage") or None,
                    "archived": bool(meta.get("archived")), "default_branch": meta.get("default_branch"),
                    "ref": ref, "path": path or None, "github_repo": full}
        if meta.get("archived"):
            ex.warnings.append("Repositorio arquivado (sem manutencao ativa).")
        try:
            langs = self._api(f"/repos/{owner}/{repo}/languages")
            ex.languages = sorted(langs, key=lambda k: -langs[k])[:6] if isinstance(langs, dict) else []
        except FetchError:
            ex.missing.append("linguagens")

        if info["kind"] == "file":
            if not re.search(r"\.(md|markdown|mdx|rst|txt)$", path, re.I):
                ex.status = "partial"
                ex.warnings.append("Arquivo nao textual/Markdown: apenas metadados do repositorio foram usados.")
            else:
                txt = self._api(f"/repos/{owner}/{repo}/contents/{quote(path)}", raw=True, params={"ref": ref})
                ex.text = sanitize_markdown(txt, MAX_README)
                ex.title = f"{full} — {path.rsplit('/', 1)[-1]}"
            ex.headings = re.findall(r"^#{1,3}\s+(.+)$", ex.text, re.M)[:40]
            return ex

        # diretorio ou raiz: listagem de 1 nivel
        try:
            entries = self._api(f"/repos/{owner}/{repo}/contents/{quote(path)}".rstrip("/"), params={"ref": ref})
        except FetchError as exc:
            if info["kind"] == "directory":
                raise FetchError(exc.code, "Diretorio nao encontrado nesse branch/ref (branches com '/' nao sao suportados).",
                                 exc.status) from None
            entries = []
        if isinstance(entries, dict):  # caminho e um arquivo
            entries = [entries]
        entries = entries[:MAX_ENTRIES] if isinstance(entries, list) else []
        names = [(e.get("name"), e.get("type")) for e in entries]
        ex.facts["structure"] = [f"{n}/" if t == "dir" else n for n, t in names][:40]
        dirs = {n.lower() for n, t in names if t == "dir"}
        ex.facts["docs_dirs"] = sorted(dirs & DOC_DIRS)
        ex.facts["example_dirs"] = sorted(dirs & EXAMPLE_DIRS)
        readme = self._readme(owner, repo, path, ref) if path else self._readme(owner, repo, "", info["ref"])
        if readme:
            ex.text = sanitize_markdown(readme, MAX_README)
            ex.headings = re.findall(r"^#{1,3}\s+(.+)$", ex.text, re.M)[:40]
            for label, link in re.findall(r"\[([^\]]{2,80})\]\((https://[^)\s]+)\)", readme)[:200]:
                if re.search(r"doc|guide|tutorial|reference|api|example|demo", label + link, re.I):
                    ex.links.append({"url": link, "text": label})
        else:
            ex.status = "partial"
            ex.missing.append("README" + (" do diretorio" if path else ""))
        if (meta.get("homepage") or "").startswith("https://"):
            ex.links.insert(0, {"url": meta["homepage"], "text": "Site / documentacao oficial"})
        for n, t in names:
            if t == "dir" and n.lower() in DOC_DIRS | EXAMPLE_DIRS:
                ex.children.append(Child(title=n, url=f"https://github.com/{full}/tree/{ref}/{(path + '/' if path else '')}{n}",
                                         kind="directory"))
        if not ex.description and not readme:
            ex.missing.append("descricao")
        return ex

    def _org(self, url: str, owner: str) -> Extraction:
        try:
            meta = self._api(f"/orgs/{owner}")
            kind = "organization"
        except FetchError as exc:
            if exc.code != "not_found":
                raise
            meta = self._api(f"/users/{owner}")
            kind = "organization" if meta.get("type") == "Organization" else "user"
        login = meta.get("login") or owner
        ex = Extraction(url=url, canonical_url=canonical_url(url), adapter=self.name, provider="GitHub",
                        kind="organization", title=meta.get("name") or login, description=meta.get("description") or meta.get("bio"),
                        author=login, updated_at=meta.get("updated_at"))
        ex.facts = {"login": login, "public_repos": meta.get("public_repos"), "blog": meta.get("blog") or None,
                    "account_type": kind}
        repos = self._api(f"/users/{login}/repos", params={"sort": "pushed", "per_page": 100, "type": "owner"})
        repos = [r for r in repos if isinstance(r, dict) and not r.get("fork") and not r.get("archived")]
        repos.sort(key=lambda r: (-(r.get("stargazers_count") or 0), r.get("name", "")))
        for r in repos[:ORG_CANDIDATES]:
            ex.children.append(Child(title=r.get("full_name") or r.get("name"), url=r.get("html_url"), kind="repository",
                                     meta={"description": (r.get("description") or "")[:200],
                                           "stars": r.get("stargazers_count"), "language": r.get("language"),
                                           "pushed_at": r.get("pushed_at")}))
        ex.text = "\n".join(f"- {c.title}: {c.meta.get('description', '')}" for c in ex.children)
        ex.languages = sorted({c.meta.get("language") for c in ex.children if c.meta.get("language")})
        ex.warnings.append(f"Organizacao: {len(ex.children)} projeto(s) relevante(s) listado(s) como candidatos; nada e importado automaticamente.")
        try:
            profile = self._readme(login, ".github", "profile")
            if profile:
                ex.text = sanitize_markdown(profile, 4000) + "\n\n" + ex.text
        except FetchError:
            pass
        return ex
