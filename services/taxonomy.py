"""Taxonomia editorial (data/taxonomy.yaml): casos de uso, secoes da Home e tecnologias.

Tudo aqui e deterministico e local. As funcoes `suggest_*` apenas SUGEREM classificacoes
a partir do texto real da fonte; a decisao final e sempre editorial (admin).
"""
from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field

from utils.text import normalize

TAXONOMY_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.yaml"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UseCase(_M):
    id: str
    label: str
    keywords: list[str] = Field(default_factory=list)


class Subcategory(_M):
    id: str
    title: str
    icon: str
    scope: str = ""


class Section(_M):
    id: str
    title: str
    icon: str
    subcategories: list[Subcategory] = Field(default_factory=list)


class Technology(_M):
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)


class Taxonomy(_M):
    use_cases: list[UseCase]
    sections: list[Section]
    technologies: list[Technology] = Field(default_factory=list)

    # ---- consultas ----------------------------------------------------------
    @property
    def use_case_ids(self) -> list[str]:
        return [u.id for u in self.use_cases]

    def use_case(self, uid: str) -> Optional[UseCase]:
        return next((u for u in self.use_cases if u.id == uid), None)

    def label(self, uid: str) -> str:
        u = self.use_case(uid)
        return u.label if u else uid

    def section(self, sid: str) -> Optional[Section]:
        return next((s for s in self.sections if s.id == sid), None)

    def subcategory(self, sub_id: str) -> Optional[Subcategory]:
        for s in self.sections:
            for c in s.subcategories:
                if c.id == sub_id:
                    return c
        return None

    def section_of(self, sub_id: Optional[str]) -> Optional[str]:
        for s in self.sections:
            if any(c.id == sub_id for c in s.subcategories):
                return s.id
        return None

    @property
    def subcategory_ids(self) -> list[str]:
        return [c.id for s in self.sections for c in s.subcategories]

    def technology(self, tid: str) -> Optional[Technology]:
        return next((t for t in self.technologies if t.id == tid), None)

    # ---- deteccao (sugestoes) -----------------------------------------------
    def match_use_cases(self, text: str, min_hits: int = 1, limit: int = 3) -> list[str]:
        """Casos de uso cujos termos aparecem no texto, do mais ao menos citado."""
        norm = f" {normalize(text)} "
        toks = set(re.findall(r"[a-z0-9]+", norm))
        hits: Counter = Counter()
        for u in self.use_cases:
            for kw in u.keywords:
                k = normalize(kw)
                if " " in k:
                    if f" {k} " in norm:
                        hits[u.id] += 2
                elif k in toks or (len(k) >= 6 and any(t.startswith(k) for t in toks)):
                    hits[u.id] += 1
        ranked = [uid for uid, n in hits.most_common() if n >= min_hits]
        return ranked[:limit]

    def detect_technologies(self, text: str) -> list[str]:
        """Tecnologias MENCIONADAS no texto (mencao nao e prova de integracao)."""
        norm = f" {normalize(text)} "
        out = []
        for t in self.technologies:
            if any(re.search(rf"(?<![a-z0-9]){re.escape(normalize(a))}(?![a-z0-9])", norm) for a in t.aliases):
                out.append(t.id)
        if "claude-code" in out and "claude" in out:
            out.remove("claude")
        return out

    def suggest_subcategory(self, *, url: str, kind: str, resource_type: str, text: str) -> tuple[str, str]:
        """(subcategoria, motivo). Regras simples e explicaveis; o admin pode corrigir."""
        host = (urlsplit(url).hostname or "").lower()
        t = normalize(text)
        def has(*ws: str) -> bool:  # palavras curtas exigem fronteira dos dois lados ('ide' != 'ideia')
            return any(re.search(rf"(?<![a-z0-9]){re.escape(w)}" + (r"(?![a-z0-9])" if len(w) <= 4 else ""), t)
                       for w in ws)

        if resource_type == "platform" or has("learning platform", "plataforma de cursos", "course catalog"):
            return "learning-platforms", "plataforma com catalogo de cursos"
        if host.endswith(("arxiv.org", "scholar.google.com", "semanticscholar.org", "paperswithcode.com")):
            return "research-resources", "repositorio de literatura cientifica"
        if resource_type == "roadmap" or kind == "roadmap":
            return "guides-roadmaps", "roteiro de estudo"
        if kind in {"playlist", "channel", "video"} or resource_type in {"course", "playlist", "video"}:
            return "courses-lectures", "aulas em video ou curso"
        if has("template", "especificacao", "specification", "spec driven", "spec-driven", "convention", "padrao"):
            return "templates-standards", "template, especificacao ou convencao"
        if has("skill", "agent skills", "claude", "assistente de codigo", "coding assistant", "prompt"):
            return "ai-assisted-work", "trabalho assistido por IA"
        if has("tests", "testing", "pytest", "teste", "validation", "validacao", "schema", "data quality", "qualidade de dados"):
            return "validation-quality", "testes ou validacao"
        if has("schedul", "agendamento", "orchestrat", "orquestr", "workflow", "automat"):
            return "automation-workflows", "automacao ou orquestracao"
        if has("paper", "papers", "artigo cientifico", "research"):
            return "research-resources", "material de pesquisa"
        if has("course", "curso", "tutorial", "from scratch", "do zero", "guide", "guia", "roadmap"):
            return "guides-roadmaps", "guia ou material didatico"
        if host.startswith("docs.") and has("databricks", "mlflow", "unity catalog", "model serving"):
            return "ai-data-tools", "documentacao de plataforma de dados/IA"
        if has("editor", "ide", "git", "hook", "cli"):
            return "developer-tools", "ferramenta de desenvolvimento"
        return "tools-libraries", "ferramenta ou biblioteca"


@lru_cache(maxsize=4)
def _load(path: str, mtime: float) -> Taxonomy:
    with open(path, encoding="utf-8") as fh:
        return Taxonomy(**(yaml.safe_load(fh) or {}))


def load_taxonomy(path: Path | str = TAXONOMY_PATH) -> Taxonomy:
    p = Path(path)
    return _load(str(p), p.stat().st_mtime)
