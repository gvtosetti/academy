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
from services.models import DIFFICULTY_ORDER, Concept, PracticalPlaybook, Resource
from utils.text import normalize, tokenize

FIELD_WEIGHTS = {
    "title": 6.0,
    "tags": 4.0,
    "concepts": 4.0,
    "usecases": 3.0,
    "provider": 2.0,
    "areas": 2.0,
    "short": 2.0,
    "body": 1.0,
}
USE_CASE_WEIGHT = 4.0  # pontuacao de um recurso que entra so pelo caso de uso detectado na consulta


@dataclass
class Filters:
    """Filtros opcionais e combinaveis (AND entre grupos, OR dentro do grupo)."""

    areas: tuple[str, ...] = ()
    types: tuple[str, ...] = ()
    difficulties: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    use_cases: tuple[str, ...] = ()
    subcategories: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()

    @property
    def active(self) -> bool:
        return any((self.areas, self.types, self.difficulties, self.languages, self.tags,
                    self.use_cases, self.subcategories, self.sections))


class SearchBackend(Protocol):
    def search(self, query: str, filters: Optional[Filters] = None, sort: str = "relevance") -> list[tuple[Resource, float]]:
        ...


def _resource_fields(r: Resource, cat: Catalog) -> dict[str, str]:
    cnames = []
    for cid in r.key_concepts:
        c = cat.concepts.get(cid)
        if c:
            cnames += [c.name, c.name_pt or "", cid.replace("-", " ")]
    tax = cat.taxonomy
    uc_text = []
    for u in r.use_cases:
        uc = tax.use_case(u)
        if uc:
            uc_text += [uc.label, *uc.keywords]
    sub = tax.subcategory(r.editorial_subcategory or "")
    if sub:
        uc_text.append(sub.title)
    uc_text += [t.name for t in (tax.technology(x) for x in r.supported_technologies) if t]
    return {
        "usecases": " ".join(uc_text),
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
        if f.use_cases and not set(f.use_cases) & set(r.use_cases):
            return False
        if f.subcategories and r.editorial_subcategory not in f.subcategories:
            return False
        if f.sections and r.editorial_section not in f.sections:
            return False
        return True

    def intent(self, query: str) -> list[str]:
        """Casos de uso implicitos na consulta ("como automatizar uma tarefa repetitiva")."""
        return self.catalog.taxonomy.match_use_cases(query) if query else []

    def search(self, query: str = "", filters: Optional[Filters] = None, sort: str = "relevance") -> list[tuple[Resource, float]]:
        f = filters or Filters()
        out: list[tuple[Resource, float]] = []
        for r in self.catalog.resources.values():
            if not self._passes(r, f):
                continue
            s = self.score(r.id, query)
            if s > 0:
                out.append((r, s))
        # Busca por problema: se a consulta descreve um caso de uso, inclui os recursos
        # classificados nele mesmo sem casamento literal de todas as palavras.
        intent = self.intent(query)
        if intent:
            seen = {r.id for r, _ in out}
            for r in self.catalog.resources.values():
                if r.id in seen or not self._passes(r, f):
                    continue
                hits = [u for u in intent if u in r.use_cases]
                if hits:
                    out.append((r, USE_CASE_WEIGHT * (len(intent) - intent.index(hits[0])) / len(intent)))
        if sort == "diverse":
            pos = {r.id: i for i, r in enumerate(diverse([r for r, _ in out]))}
            out.sort(key=lambda x: pos[x[0].id])
        elif sort == "title":
            out.sort(key=lambda x: normalize(x[0].title))
        elif sort == "sequence":
            out.sort(key=lambda x: (x[0].sequence, DIFFICULTY_ORDER.get(x[0].difficulty or "", -1), normalize(x[0].title)))
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


def search_playbooks(playbooks: Iterable[PracticalPlaybook], query: str = "", use_cases: Iterable[str] = ()) -> list[PracticalPlaybook]:
    """Busca em playbooks (titulo/tags/resumo). `use_cases` inclui os do caso de uso detectado."""
    qtoks, ucs = tokenize(query), set(use_cases)
    scored = []
    for i, p in enumerate(playbooks):
        head = set(tokenize(f"{p.title} {' '.join(p.tags)}"))
        body = set(tokenize(f"{p.summary} {p.when_to_use} " + " ".join(s.title + ' ' + s.detail for s in p.steps)))
        score, ok = 0, True
        for qt in qtoks:
            if LocalSearch._match(qt, head):
                score += 3
            elif LocalSearch._match(qt, body):
                score += 1
            else:
                ok = False
                break
        if ucs & set(p.use_cases):  # o caso de uso detectado pesa mais que casamento no corpo
            ok, score = True, score + 4
        if ok:
            scored.append((p, score, i))
    scored.sort(key=lambda x: (-x[1], x[2]))
    return [p for p, _, _ in scored]


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
