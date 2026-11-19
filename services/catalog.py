"""Carrega e valida o catalogo curado (fonte de verdade da Academy).

APIs externas (GitHub, YouTube) apenas ENRIQUECEM o catalogo; a experiencia
funciona integralmente com estes arquivos locais.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from services.models import Category, Concept, QuizQuestion, Resource, Track

log = logging.getLogger("academy.catalog")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class CatalogError(ValueError):
    """Erro de consistencia no catalogo."""


@dataclass
class Catalog:
    resources: dict[str, Resource]
    concepts: dict[str, Concept]
    tracks: dict[str, Track]
    categories: dict[str, Category]
    quizzes: list[QuizQuestion] = field(default_factory=list)

    # ---- consultas auxiliares -------------------------------------------
    def children_of(self, resource_id: str) -> list[Resource]:
        kids = [r for r in self.resources.values() if r.parent == resource_id]
        return sorted(kids, key=lambda r: (r.sequence, r.title))

    def resources_for_concept(self, concept_id: str) -> list[Resource]:
        return sorted(
            (r for r in self.resources.values() if concept_id in r.key_concepts),
            key=lambda r: (r.sequence, r.title),
        )

    def resources_in_category(self, category_id: str) -> list[Resource]:
        return sorted(
            (r for r in self.resources.values() if r.category == category_id),
            key=lambda r: (r.sequence, r.title),
        )

    def tracks_for_resource(self, resource_id: str) -> list[Track]:
        return [
            t for t in self.tracks.values()
            if any(resource_id in m.resources for m in t.modules)
        ]

    def quizzes_for_concept(self, concept_id: str) -> list[QuizQuestion]:
        return [q for q in self.quizzes if q.concept == concept_id]

    def featured(self, section: str) -> list[Resource]:
        return sorted(
            (r for r in self.resources.values() if section in r.featured),
            key=lambda r: (r.sequence, r.title),
        )

    def recent(self, n: int = 6) -> list[Resource]:
        return sorted(self.resources.values(), key=lambda r: (r.added_on, -r.sequence), reverse=True)[:n]


def _read_yaml(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or []
    if not isinstance(data, list):
        raise CatalogError(f"{path.name}: esperado uma lista no topo do arquivo")
    return data


def _index(items, kind: str) -> dict:
    counts = Counter(i.id for i in items)
    dups = [k for k, c in counts.items() if c > 1]
    if dups:
        raise CatalogError(f"IDs duplicados em {kind}: {dups}")
    return {i.id: i for i in items}


def validate_references(cat: Catalog) -> list[str]:
    """Retorna a lista de problemas de integridade (vazia = catalogo consistente)."""
    errs: list[str] = []
    R, C, T, K = cat.resources, cat.concepts, cat.tracks, cat.categories

    urls = Counter(r.url.rstrip("/").lower() for r in R.values())
    for u, n in urls.items():
        if n > 1:
            errs.append(f"URL canonica registrada {n}x: {u}")

    for r in R.values():
        if r.category not in K:
            errs.append(f"{r.id}: categoria inexistente '{r.category}'")
        if r.parent and r.parent not in R:
            errs.append(f"{r.id}: parent inexistente '{r.parent}'")
        if r.parent == r.id:
            errs.append(f"{r.id}: parent aponta para si mesmo")
        for x in r.related_resources:
            if x not in R:
                errs.append(f"{r.id}: related_resources inexistente '{x}'")
            if x == r.id:
                errs.append(f"{r.id}: relacionado a si mesmo")
        for x in r.key_concepts:
            if x not in C:
                errs.append(f"{r.id}: conceito inexistente '{x}'")
        for x in r.learning_paths:
            if x not in T:
                errs.append(f"{r.id}: trilha inexistente '{x}'")
            elif not any(r.id in m.resources for m in T[x].modules):
                errs.append(f"{r.id}: declara trilha '{x}', mas nenhum modulo dela o referencia")
        if r.type == "github" and not r.github_repo:
            errs.append(f"{r.id}: tipo github sem github_repo")
        if r.metadata_status != "verified" and not r.metadata_notes:
            errs.append(f"{r.id}: status '{r.metadata_status}' exige metadata_notes")

    for c in C.values():
        for x in c.related:
            if x not in C:
                errs.append(f"conceito {c.id}: related inexistente '{x}'")

    for t in T.values():
        mids = Counter(m.id for m in t.modules)
        errs += [f"trilha {t.id}: modulo duplicado '{k}'" for k, n in mids.items() if n > 1]
        for m in t.modules:
            for x in m.resources:
                if x not in R:
                    errs.append(f"trilha {t.id}/{m.id}: recurso inexistente '{x}'")
                elif t.id not in R[x].learning_paths:
                    errs.append(f"trilha {t.id}/{m.id}: recurso '{x}' nao lista a trilha em learning_paths")
            for x in m.concepts:
                if x not in C:
                    errs.append(f"trilha {t.id}/{m.id}: conceito inexistente '{x}'")
            if not m.resources and not m.recommended_topics:
                errs.append(f"trilha {t.id}/{m.id}: modulo sem recursos nem topicos recomendados")

    qids = Counter(q.id for q in cat.quizzes)
    errs += [f"quiz duplicado '{k}'" for k, n in qids.items() if n > 1]
    for q in cat.quizzes:
        if q.concept not in C:
            errs.append(f"quiz {q.id}: conceito inexistente '{q.concept}'")
        if not 0 <= q.answer < len(q.options):
            errs.append(f"quiz {q.id}: indice de resposta fora do intervalo")
    return errs


def load_catalog(data_dir: Path | str = DATA_DIR, strict: bool = True) -> Catalog:
    d = Path(data_dir)
    cat = Catalog(
        resources=_index([Resource(**x) for x in _read_yaml(d / "resources.yaml")], "resources"),
        concepts=_index([Concept(**x) for x in _read_yaml(d / "glossary.yaml")], "glossary"),
        tracks=_index([Track(**x) for x in _read_yaml(d / "tracks.yaml")], "tracks"),
        categories=_index([Category(**x) for x in _read_yaml(d / "categories.yaml")], "categories"),
        quizzes=[QuizQuestion(**x) for x in _read_yaml(d / "quizzes.yaml")],
    )
    errs = validate_references(cat)
    if errs:
        for e in errs:
            log.error("catalog: %s", e)
        if strict:
            raise CatalogError("Catalogo inconsistente:\n- " + "\n- ".join(errs))
    return cat
