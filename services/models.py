"""Schema tipado do conteudo da Academy (Pydantic v2).

Separacao editorial:
- `verified`: metadados conferidos na fonte original (titulo, licenca, contagem de videos...).
- campos explicativos (plain_language_explanation, why_it_matters...): texto autoral da curadoria.
- `difficulty`: nivel SUGERIDO pela curadoria.
- `metadata_status` + `metadata_notes`: o que ainda nao foi verificado.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils.safe import is_safe_url

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

ResourceType = Literal["github", "course", "video", "playlist", "documentation", "tool", "collection",
                       "roadmap", "article"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
MetadataStatus = Literal["verified", "partial", "pending"]
TipKind = Literal["dev-tip", "tool", "practice", "in-practice"]
CollectionLayout = Literal["grid", "list", "feature", "notes", "shelf"]
TAGLINE_MAX = 125

DIFFICULTY_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)


def _check_id(v: str) -> str:
    if not ID_RE.match(v):
        raise ValueError(f"id invalido: {v!r} (use minusculas, numeros, '-' ou '_')")
    return v


def _check_url(v: str) -> str:
    if not is_safe_url(v):
        raise ValueError(f"URL invalida ou nao-https: {v!r}")
    return v.strip()


class Link(_Strict):
    label: str
    url: str

    @field_validator("url")
    @classmethod
    def v_url(cls, v: str) -> str:
        return _check_url(v)


class Prerequisites(_Strict):
    required: list[str] = Field(default_factory=list, description="Pre-requisitos obrigatorios")
    helpful: list[str] = Field(default_factory=list, description="Base util, mas nao obrigatoria")


class Highlight(_Strict):
    path: str
    why: str


class VerifiedMetadata(_Strict):
    """Somente dados conferidos na fonte. Nada aqui pode ser estimado."""

    verified_on: Optional[date] = None
    source_title: Optional[str] = None
    license: Optional[str] = None
    primary_language: Optional[str] = None
    video_count: Optional[int] = None
    video_count_note: Optional[str] = None
    episodes: list[str] = Field(default_factory=list)
    source_description: Optional[str] = None
    duration: Optional[str] = None


class Resource(_Strict):
    id: str
    title: str
    url: str
    provider: str
    type: ResourceType
    category: str
    difficulty: Difficulty
    language: Literal["pt", "en", "multi"]
    areas: list[str] = Field(min_length=1, description="Areas/disciplinas (multidimensional); a primeira e a principal")
    tagline: str = Field(description="Frase curta do card (ate ~120 caracteres): para que serve")
    blurb: str = Field(description="1-2 frases de abertura da pagina Saiba mais")
    short_description: str
    plain_language_explanation: str
    technical_explanation: str
    why_it_matters: str
    learning_outcomes: list[str] = Field(min_length=1)
    audience: list[str] = Field(min_length=1)
    prerequisites: Prerequisites = Field(default_factory=Prerequisites)
    key_concepts: list[str] = Field(default_factory=list)
    practical_applications: list[str] = Field(default_factory=list)
    study_guide: list[str] = Field(default_factory=list)
    related_resources: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    parent: Optional[str] = None
    sequence: int = 100
    added_on: date
    github_repo: Optional[str] = None
    github_highlights: list[Highlight] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    verified: VerifiedMetadata = Field(default_factory=VerifiedMetadata)
    metadata_status: MetadataStatus
    metadata_notes: Optional[str] = None

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)
    @field_validator("url")
    @classmethod
    def v_url(cls, v: str) -> str:
        return _check_url(v)

    @field_validator("github_repo")
    @classmethod
    def v_repo(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)?$", v):
            raise ValueError(f"github_repo invalido: {v!r}")
        return v


class Concept(_Strict):
    id: str
    name: str
    name_pt: Optional[str] = None
    simple: str
    technical: str
    example: str
    why: str
    areas: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)


class Tip(_Strict):
    """Nota curta e independente (Tips & Insights). Texto autoral da curadoria."""

    id: str
    kind: TipKind
    title: str
    summary: str
    body: str
    areas: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    level: Optional[Difficulty] = None
    related_resources: list[str] = Field(default_factory=list)
    related_concepts: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)


class Area(_Strict):
    id: str
    name: str
    icon: str
    description: str
    chip: bool = True

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)


class CollectionItem(_Strict):
    """Um recurso ou uma nota, com comentario editorial opcional."""

    id: str
    note: Optional[str] = None


class Collection(_Strict):
    """Agrupamento editorial independente (nao e trilha nem curso).

    Um mesmo item pode estar em varias colecoes. A ordem dos itens e a ordem de exibicao.
    """

    id: str
    title: str
    tagline: str
    layout: CollectionLayout = "grid"
    home: Literal["main", "section", "hidden"] = "section"
    home_limit: int = Field(default=6, ge=1, le=12)
    items: list[CollectionItem] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)

    @field_validator("items", mode="before")
    @classmethod
    def v_items(cls, v):
        return [{"id": x} if isinstance(x, str) else x for x in (v or [])]


class Category(_Strict):
    id: str
    name: str
    icon: str
    description: str

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)
