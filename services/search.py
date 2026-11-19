"""Busca local deterministica sobre o catalogo (sem LLM, sem servico externo).

Estrategia: indice invertido simples com pesos por campo. Cada token da consulta
precisa casar (igualdade ou prefixo com >=3 letras) em algum campo do recurso
(semantica AND). A pontuacao soma os pesos dos campos em que houve casamento.

Ponto de extensao: `SearchBackend` permite plugar busca semantica no futuro
(ex.: Vector Search) sem mudar a UI.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol

from services.catalog import Catalog
from services.models import DIFFICULTY_ORDER, Concept, Resource
from utils.text import normalize, tokenize

FIELD_WEIGHTS = {
    "title": 6.0,
    "tags": 4.0,
    "concepts": 4.0,
    "provider": 2.0,
    "short": 2.0,
    "body": 1.0,
}


@dataclass
class Filters:
    categories: tuple[str, ...] = ()
    difficulties: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    tracks: tuple[str, ...] = ()


class SearchBackend(Protocol):
    def search(self, query: str, filters: Optional[Filters] = None, sort: str = "relevance") -> list[tuple[Resource, float]]:
        ...


def _resource_fields(r: Resource, concepts: dict[str, Concept]) -> dict[str, str]:
    cnames = []
    for cid in r.key_concepts:
        c = concepts.get(cid)
        if c:
            cnames += [c.name, c.name_pt or "", cid.replace("-", " ")]
    return {
        "title": r.title,
        "tags": " ".join(r.tags),
        "concepts": " ".join(cnames),
        "provider": r.provider,
        "short": r.short_description,
        "body": " ".join(
            [r.plain_language_explanation, r.why_it_matters, r.technical_explanation]
            + r.learning_outcomes + r.practical_applications
        ),
    }


class LocalSearch:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog
        self._index: dict[str, dict[str, set[str]]] = {}
        for r in catalog.resources.values():
            self._index[r.id] = {f: set(tokenize(txt)) for f, txt in _resource_fields(r, catalog.concepts).items()}

    @staticmethod
    def _match(qtok: str, tokens: set[str]) -> bool:
        if qtok in tokens:
            return True
        if len(qtok) >= 3:
            return any(t.startswith(qtok) for t in tokens)
        return False

    def score(self, resource_id: str, query: str) -> float:
        qtoks = tokenize(query)
        if not qtoks:
            return 1.0
        fields = self._index[resource_id]
        total = 0.0
        for qt in qtoks:
            hit = [w for f, w in FIELD_WEIGHTS.items() if self._match(qt, fields[f])]
            if not hit:
                return 0.0  # semantica AND
            total += sum(hit)
        # bonus para frase exata no titulo
        if normalize(query) in normalize(self.catalog.resources[resource_id].title):
            total += 5.0
        return total

    def _passes(self, r: Resource, f: Filters) -> bool:
        if f.categories and r.category not in f.categories:
            return False
        if f.difficulties and r.difficulty not in f.difficulties:
            return False
        if f.types and r.type not in f.types:
            return False
        if f.languages and r.language not in f.languages:
            return False
        if f.providers and r.provider not in f.providers:
            return False
        if f.tracks and not set(f.tracks) & set(r.learning_paths):
            return False
        return True

    def search(self, query: str = "", filters: Optional[Filters] = None, sort: str = "relevance") -> list[tuple[Resource, float]]:
        f = filters or Filters()
        out: list[tuple[Resource, float]] = []
        for r in self.catalog.resources.values():
            if not self._passes(r, f):
                continue
            s = self.score(r.id, query)
            if s > 0:
                out.append((r, s))
        if sort == "title":
            out.sort(key=lambda x: normalize(x[0].title))
        elif sort == "sequence":
            out.sort(key=lambda x: (x[0].sequence, DIFFICULTY_ORDER[x[0].difficulty], normalize(x[0].title)))
        else:  # relevance; empate -> sequencia curada
            out.sort(key=lambda x: (-x[1], x[0].sequence, normalize(x[0].title)))
        return out


def search_concepts(concepts: Iterable[Concept], query: str) -> list[Concept]:
    """Busca simples no glossario (nome, nome em pt, definicao)."""
    qtoks = tokenize(query)
    res = []
    for c in concepts:
        if not qtoks:
            res.append((c, 0))
            continue
        name_toks = set(tokenize(f"{c.name} {c.name_pt or ''} {c.id.replace('-', ' ')}"))
        body_toks = set(tokenize(f"{c.simple} {c.technical}"))
        score = 0
        ok = True
        for qt in qtoks:
            if LocalSearch._match(qt, name_toks):
                score += 3
            elif LocalSearch._match(qt, body_toks):
                score += 1
            else:
                ok = False
                break
        if ok:
            res.append((c, score))
    res.sort(key=lambda x: (-x[1], normalize(x[0].name)))
    return [c for c, _ in res]
