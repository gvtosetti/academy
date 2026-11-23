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

from services.catalog import Catalog, Note, diverse
from services.models import DIFFICULTY_ORDER, Concept, Resource
from utils.text import normalize, tokenize

FIELD_WEIGHTS = {
    "title": 6.0,
    "tags": 4.0,
    "concepts": 4.0,
    "provider": 2.0,
    "areas": 2.0,
    "short": 2.0,
    "body": 1.0,
}


@dataclass
class Filters:
    """Filtros opcionais e combinaveis (AND entre grupos, OR dentro do grupo)."""

    areas: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    difficulties: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return any((self.areas, self.types, self.difficulties, self.languages, self.tags))


class SearchBackend(Protocol):
    def search(self, query: str, filters: Optional[Filters] = None, sort: str = "relevance") -> list[tuple[Resource, float]]:
        ...


def _resource_fields(r: Resource, cat: Catalog) -> dict[str, str]:
    cnames = []
    for cid in r.key_concepts:
        c = cat.concepts.get(cid)
        if c:
            cnames += [c.name, c.name_pt or "", cid.replace("-", " ")]
    return {
        "title": r.title,
        "tags": " ".join(r.tags),
        "concepts": " ".join(cnames),
        "provider": r.provider,
        "areas": " ".join(cat.areas[a].name for a in r.areas if a in cat.areas),
        "short": f"{r.tagline} {r.blurb} {r.short_description}",
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
            self._index[r.id] = {f: set(tokenize(txt)) for f, txt in _resource_fields(r, catalog).items()}

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

    @staticmethod
    def _passes(r: Resource, f: Filters) -> bool:
        if f.areas and not set(f.areas) & set(r.areas):
            return False
        if f.difficulties and r.difficulty not in f.difficulties:
            return False
        if f.types and r.type not in f.types:
            return False
        if f.languages and r.language not in f.languages:
            return False
        if f.tags and not set(f.tags) & set(r.tags):
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
        if sort == "diverse":
            pos = {r.id: i for i, r in enumerate(diverse([r for r, _ in out]))}
            out.sort(key=lambda x: pos[x[0].id])
        elif sort == "title":
            out.sort(key=lambda x: normalize(x[0].title))
        elif sort == "sequence":
            out.sort(key=lambda x: (x[0].sequence, DIFFICULTY_ORDER[x[0].difficulty], normalize(x[0].title)))
        else:  # relevance; empate -> sequencia curada
            out.sort(key=lambda x: (-x[1], x[0].sequence, normalize(x[0].title)))
        return out


def search_notes(notes: Iterable[Note], query: str = "", kinds: tuple[str, ...] = (), areas: tuple[str, ...] = ()) -> list[Note]:
    """Busca em Tips & Insights (titulo/tags pesam mais que o corpo). Sem consulta: ordem curada."""
    qtoks = tokenize(query)
    scored = []
    for i, n in enumerate(notes):
        if kinds and n.kind not in kinds:
            continue
        if areas and not set(areas) & set(n.areas):
            continue
        head = set(tokenize(f"{n.title} {n.id.replace('-', ' ')} {' '.join(n.tags)}"))
        body = set(tokenize(f"{n.summary} {n.body} {n.technical or ''}"))
        score, ok = 0, True
        for qt in qtoks:
            if LocalSearch._match(qt, head):
                score += 3
            elif LocalSearch._match(qt, body):
                score += 1
            else:
                ok = False
                break
        if ok:
            scored.append((n, score, i))
    scored.sort(key=lambda x: (-x[1], x[2]))
    return [n for n, _, _ in scored]


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
