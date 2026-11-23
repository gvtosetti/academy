"""Carrega e valida o catalogo curado (fonte de verdade da Resource Library).

APIs externas (GitHub, YouTube) apenas ENRIQUECEM o catalogo; a experiencia
funciona integralmente com estes arquivos locais.
"""
from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import yaml

from services.curator import CuratedDraft
from services.ingest.base import Extraction
from services.models import (
    TAGLINE_MAX, Area, Category, Collection, CollectionItem, Concept, PracticalPlaybook, Resource, Tip, TopicCollection,
)
from services.publishing import draft_to_resource, parse_created_at
from services.repository import get_repository
from services.taxonomy import Taxonomy, load_taxonomy

log = logging.getLogger("academy.catalog")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DYN_RESOURCE_ID = "imported-resources"


class CatalogError(ValueError):
    """Erro de consistencia no catalogo."""


WORDS_PER_MINUTE = 200

NOTE_KINDS = {
    "explainer": "Quick Explainer",
    "dev-tip": "Dev Tip",
    "tool": "Tool",
    "practice": "Good Practice",
    "in-practice": "Concept in Practice",
}


def reading_minutes(*texts: str) -> int:
    """Tempo de leitura calculado a partir do texto exibido (200 palavras/min)."""
    words = sum(len((t or "").split()) for t in texts)
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


@dataclass
class Note:
    """Item de Tips & Insights (vem de glossary.yaml ou de tips.yaml)."""

    id: str
    kind: str
    title: str
    summary: str
    body: str
    areas: list[str]
    tags: list[str] = field(default_factory=list)
    technical: Optional[str] = None
    level: Optional[str] = None
    related_resources: list[str] = field(default_factory=list)
    related_notes: list[str] = field(default_factory=list)
    minutes: int = 1

    @property
    def kind_label(self) -> str:
        return NOTE_KINDS[self.kind]


def _note_from_concept(c: Concept, resources: dict[str, Resource]) -> Note:
    body = f"**Exemplo.** {c.example}\n\n**Por que importa.** {c.why}"
    # Evita parenteses duplos, ex.: "Machine Learning (ML)" nao vira "Machine Learning (ML) (Aprendizado...)"
    title = c.name if not c.name_pt or c.name_pt == c.name or "(" in c.name else f"{c.name} ({c.name_pt})"
    rel = [r.id for r in sorted(resources.values(), key=lambda r: (r.sequence, r.title)) if c.id in r.key_concepts]
    return Note(
        id=c.id, kind="explainer", title=title, summary=c.simple, body=body, areas=list(c.areas),
        tags=list(c.tags), technical=c.technical, related_resources=rel, related_notes=list(c.related),
        minutes=reading_minutes(c.simple, body),
    )


def _note_from_tip(t: Tip) -> Note:
    return Note(
        id=t.id, kind=t.kind, title=t.title, summary=t.summary, body=t.body, areas=list(t.areas),
        tags=list(t.tags), level=t.level, related_resources=list(t.related_resources),
        related_notes=list(t.related_concepts), minutes=reading_minutes(t.summary, t.body),
    )


@dataclass
class Catalog:
    resources: dict[str, Resource]
    concepts: dict[str, Concept]
    categories: dict[str, Category]
    areas: dict[str, Area] = field(default_factory=dict)
    tips: dict[str, Tip] = field(default_factory=dict)
    collections: dict[str, Collection] = field(default_factory=dict)
    notes: dict[str, Note] = field(default_factory=dict)
    playbooks: dict[str, PracticalPlaybook] = field(default_factory=dict)
    topics: dict[str, TopicCollection] = field(default_factory=dict)
    taxonomy: Optional[Taxonomy] = None

    def __post_init__(self) -> None:
        if not self.notes:
            self.notes = {c.id: _note_from_concept(c, self.resources) for c in self.concepts.values()}
            for t in self.tips.values():
                if t.id not in self.notes:  # colisao e reportada em validate_references
                    self.notes[t.id] = _note_from_tip(t)
        if self.taxonomy is None:
            self.taxonomy = load_taxonomy()
        self.derive_sections()

    def derive_sections(self) -> None:
        """editorial_section vem sempre da subcategoria (fonte unica)."""
        for r in self.resources.values():
            if r.editorial_subcategory:
                r.editorial_section = self.taxonomy.section_of(r.editorial_subcategory)

    # ---- arquitetura editorial -----------------------------------------
    def resources_in_subcategory(self, sub_id: str) -> list[Resource]:
        return sorted((r for r in self.resources.values() if r.editorial_subcategory == sub_id),
                      key=lambda r: (r.parent is not None, r.sequence, r.title))

    def resources_in_section(self, section_id: str) -> list[Resource]:
        return [r for r in self.resources.values() if r.editorial_section == section_id]

    def items_for_use_case(self, uid: str) -> tuple[list[Resource], list[Note], list[PracticalPlaybook]]:
        res = sorted((r for r in self.resources.values() if uid in r.use_cases), key=lambda r: (r.sequence, r.title))
        pbs = [p for p in self.playbooks.values() if uid in p.use_cases]
        note_ids = {i for t in self.topics.values() if uid in t.use_cases for i in t.items}
        notes = [self.notes[i] for i in note_ids if i in self.notes]
        return res, sorted(notes, key=lambda n: n.title), pbs

    def topic_items(self, tid: str) -> list[Union[Note, PracticalPlaybook]]:
        t = self.topics.get(tid)
        if not t:
            return []
        return [x for x in (self.notes.get(i) or self.playbooks.get(i) for i in t.items) if x is not None]

    def topics_of(self, item_id: str) -> list[TopicCollection]:
        return [t for t in self.topics.values() if item_id in t.items]

    def resources_for_topic(self, tid: str) -> list[Resource]:
        """Recursos ligados ao compilado (related_collections ou citados pelas notas/playbooks)."""
        ids = [r.id for r in self.resources.values() if tid in r.related_collections]
        for x in self.topic_items(tid):
            ids += [i for i in x.related_resources if i not in ids]
        return [self.resources[i] for i in dict.fromkeys(ids) if i in self.resources]

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

    def resources_in_area(self, area_id: str) -> list[Resource]:
        return [r for r in self.resources.values() if area_id in r.areas]

    def notes_in_area(self, area_id: str) -> list[Note]:
        return [n for n in self.notes.values() if area_id in n.areas]

    def area_counts(self) -> dict[str, int]:
        """Quantidade de itens (recursos + notas) por area."""
        c: Counter = Counter()
        for r in self.resources.values():
            c.update(set(r.areas))
        for n in self.notes.values():
            c.update(set(n.areas))
        return {a: c.get(a, 0) for a in self.areas}

    def tag_counts(self) -> list[tuple[str, int]]:
        c = Counter(t for r in self.resources.values() for t in set(r.tags))
        return sorted(c.items(), key=lambda x: (-x[1], x[0]))

    def item(self, item_id: str) -> Optional[Union[Resource, Note]]:
        """Resolve um id de colecao (recurso ou nota)."""
        return self.resources.get(item_id) or self.notes.get(item_id)

    def collection_items(self, cid: str) -> list[tuple[Union[Resource, Note], Optional[str]]]:
        col = self.collections.get(cid)
        if not col:
            return []
        return [(self.item(i.id), i.note) for i in col.items if self.item(i.id) is not None]

    def collections_of(self, item_id: str) -> list[Collection]:
        return [c for c in self.collections.values() if any(i.id == item_id for i in c.items)]

    def recent(self, n: int = 6) -> list[Resource]:
        return sorted(self.resources.values(), key=lambda r: (r.added_on, -r.sequence), reverse=True)[:n]


def diverse(resources: list[Resource]) -> list[Resource]:
    """Ordena intercalando areas principais, para a vitrine padrao nao ficar monotematica.

    Itens de topo (sem parent) vem antes dos filhos dentro de cada area.
    """
    buckets: dict[str, list[Resource]] = defaultdict(list)
    for r in sorted(resources, key=lambda r: (r.parent is not None, r.sequence, r.title)):
        buckets[r.areas[0]].append(r)
    order = sorted(buckets, key=lambda a: -len(buckets[a]))
    out: list[Resource] = []
    while any(buckets.values()):
        for a in order:
            if buckets[a]:
                out.append(buckets[a].pop(0))
    return out


def _read_yaml(path: Path, kind: type = list):
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or kind()
    if not isinstance(data, kind):
        raise CatalogError(f"{path.name}: esperado {'uma lista' if kind is list else 'um mapa'} no topo do arquivo")
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
    R, C, K, A, N = cat.resources, cat.concepts, cat.categories, cat.areas, cat.notes

    for tid in cat.tips:
        if tid in C:
            errs.append(f"tip '{tid}' usa o mesmo id de um conceito do glossario")

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
        for x in r.areas:
            if x not in A:
                errs.append(f"{r.id}: area inexistente '{x}'")
        if len(r.blurb) > 260:
            errs.append(f"{r.id}: blurb longo demais ({len(r.blurb)} > 260)")
        if len(r.tagline) > TAGLINE_MAX:
            errs.append(f"{r.id}: tagline do card longa demais ({len(r.tagline)} > {TAGLINE_MAX})")
        if r.type == "github" and not r.github_repo:
            errs.append(f"{r.id}: tipo github sem github_repo")
        if r.metadata_status != "verified" and not r.metadata_notes:
            errs.append(f"{r.id}: status '{r.metadata_status}' exige metadata_notes")

    for n in N.values():
        for x in n.areas:
            if x not in A:
                errs.append(f"nota {n.id}: area inexistente '{x}'")
        for x in n.related_resources:
            if x not in R:
                errs.append(f"nota {n.id}: recurso inexistente '{x}'")
        for x in n.related_notes:
            if x not in N:
                errs.append(f"nota {n.id}: nota relacionada inexistente '{x}'")

    # nenhuma area vazia (evita categorias sem conteudo)
    for a, cnt in cat.area_counts().items():
        if cnt < 2:
            errs.append(f"area '{a}' tem {cnt} item(ns); minimo 2")

    for x in set(R) & set(N):
        errs.append(f"id '{x}' existe como recurso e como nota (ambiguo nas colecoes)")

    # ---- arquitetura editorial (taxonomy.yaml) ----------------------------
    T, P, TC = cat.taxonomy, cat.playbooks, cat.topics
    ucs, subs = set(T.use_case_ids), set(T.subcategory_ids)
    for r in R.values():
        if r.curation_status == "published" and not r.editorial_subcategory:
            errs.append(f"{r.id}: sem editorial_subcategory (todo recurso publicado precisa de secao na Home)")
        if r.editorial_subcategory and r.editorial_subcategory not in subs:
            errs.append(f"{r.id}: subcategoria inexistente '{r.editorial_subcategory}'")
        for u in r.use_cases:
            if u not in ucs:
                errs.append(f"{r.id}: use_case inexistente '{u}'")
        if r.supported_technologies and not r.source_evidence:
            errs.append(f"{r.id}: supported_technologies exige source_evidence")
        for t in r.supported_technologies:
            if T.technology(t) is None:
                errs.append(f"{r.id}: tecnologia desconhecida '{t}'")
        for t in r.related_collections:
            if t not in TC:
                errs.append(f"{r.id}: topic collection inexistente '{t}'")
    for x in set(P) & (set(R) | set(N)):
        errs.append(f"id '{x}' usado por playbook e por recurso/nota")
    for p in P.values():
        for u in p.use_cases:
            if u not in ucs:
                errs.append(f"playbook {p.id}: use_case inexistente '{u}'")
        for x in p.areas:
            if x not in A:
                errs.append(f"playbook {p.id}: area inexistente '{x}'")
        for x in p.related_notes:
            if x not in N:
                errs.append(f"playbook {p.id}: nota inexistente '{x}'")
        for x in p.related_resources:
            if x not in R:
                errs.append(f"playbook {p.id}: recurso inexistente '{x}'")
        if not any(s.human_checkpoint for s in p.steps):
            errs.append(f"playbook {p.id}: precisa de ao menos uma etapa com revisao humana")
    for t in TC.values():
        for i in t.items:
            if i not in N and i not in P:
                errs.append(f"topic {t.id}: item inexistente '{i}'")
        if len(set(t.items)) != len(t.items):
            errs.append(f"topic {t.id}: item repetido")
        for u in t.use_cases:
            if u not in ucs:
                errs.append(f"topic {t.id}: use_case inexistente '{u}'")
    for s in T.sections:
        for sub in s.subcategories:
            if not cat.resources_in_subcategory(sub.id):
                errs.append(f"subcategoria '{sub.id}' sem recursos (secao vazia na Home)")
    for col in cat.collections.values():
        seen: set[str] = set()
        for it in col.items:
            if it.id not in R and it.id not in N:
                errs.append(f"colecao {col.id}: item inexistente '{it.id}'")
            if it.id in seen:
                errs.append(f"colecao {col.id}: item repetido '{it.id}'")
            seen.add(it.id)
    return errs


def _overlay_published(cat: Catalog) -> Catalog:
    """Soma recursos publicados persistidos ao catalogo YAML sem quebrar o modo read-only.

    Recursos importados entram/atualizam `cat.resources`. Se trouxerem colecoes novas,
    elas sao acrescentadas ao fim; se trouxerem colecoes existentes, o item e anexado
    se ainda nao estiver la. Nenhuma falha aqui derruba o app.
    """
    try:
        repo = get_repository()
        rows = repo.list_resources("published") if hasattr(repo, "list_resources") else []
    except Exception as exc:
        log.info("published overlay unavailable: %s", type(exc).__name__)
        return cat
    from services.ingest.base import canonical_url

    yaml_urls = {canonical_url(r.url): r.id for r in cat.resources.values()}
    for row in rows:
        try:
            r = draft_to_resource(row.id, CuratedDraft(**row.data), Extraction(**row.extraction),
                                  added_on=parse_created_at(row.created_at), valid_categories=set(cat.categories))
        except Exception as exc:
            log.warning("invalid persisted resource %s: %s", row.id, type(exc).__name__)
            continue
        owner = yaml_urls.get(canonical_url(r.url))
        if owner and owner != r.id:  # duplicata de recurso legado: nao quebra o catalogo
            log.warning("persisted resource %s duplicates %s; skipped", r.id, owner)
            continue
        r.areas = [a for a in r.areas if a in cat.areas] or [next(iter(cat.areas))]
        tax = cat.taxonomy
        if r.editorial_subcategory not in tax.subcategory_ids:
            r.editorial_subcategory = "tools-libraries"
        r.use_cases = [u for u in r.use_cases if u in tax.use_case_ids]
        r.related_collections = [t for t in r.related_collections if t in cat.topics]
        if not r.source_evidence:
            r.supported_technologies = []
        cat.resources[r.id] = r
        # "featured" = primeiro lugar nas colecoes editoriais escolhidas (sem campo LMS no Resource)
        featured = bool(row.data.get("featured"))
        for cid in row.data.get("editorial_collections", []) or []:
            col = cat.collections.get(cid)
            if not col or any(i.id == r.id for i in col.items):
                continue
            item = CollectionItem(id=r.id, note=row.data.get("editorial_note"))
            col.items.insert(0, item) if featured else col.items.append(item)
    return cat


def load_catalog(data_dir: Path | str = DATA_DIR, strict: bool = True) -> Catalog:
    d = Path(data_dir)
    cat = Catalog(
        resources=_index([Resource(**x) for x in _read_yaml(d / "resources.yaml")], "resources"),
        concepts=_index([Concept(**x) for x in _read_yaml(d / "glossary.yaml")], "glossary"),
        categories=_index([Category(**x) for x in _read_yaml(d / "categories.yaml")], "categories"),
        areas=_index([Area(**x) for x in _read_yaml(d / "areas.yaml")], "areas"),
        tips=_index([Tip(**x) for x in _read_yaml(d / "tips.yaml")], "tips"),
        collections=_index([Collection(**x) for x in _read_yaml(d / "collections.yaml")], "collections"),
    )
    if (d / "playbooks.yaml").exists():
        cat.playbooks = _index([PracticalPlaybook(**x) for x in _read_yaml(d / "playbooks.yaml")], "playbooks")
    if (d / "topic_collections.yaml").exists():
        cat.topics = _index([TopicCollection(**x) for x in _read_yaml(d / "topic_collections.yaml")], "topics")
    if (d / "taxonomy.yaml").exists():
        cat.taxonomy = load_taxonomy(d / "taxonomy.yaml")
    cat = _overlay_published(cat)
    try:  # novidades Databricks APROVADAS no Release Watch (nunca derruba o catalogo)
        from services.release_watch.publish import overlay as _overlay_releases
        cat = _overlay_releases(cat)
    except Exception as exc:  # pragma: no cover - defensivo
        log.info("release watch overlay skipped: %s", type(exc).__name__)
    cat.derive_sections()
    errs = validate_references(cat)
    if errs:
        for e in errs:
            log.error("catalog: %s", e)
        if strict:
            raise CatalogError("Catalogo inconsistente:\n- " + "\n- ".join(errs))
    return cat
