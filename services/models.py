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

# Tipos distinguem a natureza do recurso: ferramenta, plataforma, biblioteca, servico,
# framework, repositorio (github) e documentacao sao categorias diferentes.
ResourceType = Literal["github", "course", "video", "playlist", "documentation", "tool", "collection",
                       "roadmap", "article", "platform", "library", "service", "framework", "book"]
CurationStatus = Literal["published", "needs_review", "draft"]
Difficulty = Literal["beginner", "intermediate", "advanced"]
MetadataStatus = Literal["verified", "partial", "pending"]
TipKind = Literal["dev-tip", "tool", "practice", "in-practice", "explainer"]
CollectionLayout = Literal["grid", "list", "feature", "notes", "shelf"]
TAGLINE_MAX = 160  # descricao do card: 100-160 caracteres, ate 3 linhas

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


class ReleaseEvent(_Strict):
    """Uma mudanca de status anunciada oficialmente (ex.: Public Preview -> GA)."""

    status: str
    announced_on: date
    url: str
    title: str = ""


class Resource(_Strict):
    id: str
    title: str
    url: str
    provider: str
    type: ResourceType
    category: str
    difficulty: Optional[Difficulty] = Field(default=None, description="Nivel sugerido; None para plataformas e documentacao")
    language: Literal["pt", "en", "multi"]
    areas: list[str] = Field(min_length=1, description="Dominio principal (primeiro) e dominios secundarios")
    tagline: str = Field(description="Descricao objetiva do card (100-160 caracteres): o que e / o que faz")
    blurb: str = Field(description="1-2 frases de abertura da pagina Saiba mais")
    short_description: str
    # Secoes explicativas: opcionais. Vazias nao sao exibidas (sem texto de preenchimento).
    plain_language_explanation: str = ""
    technical_explanation: str = ""
    why_it_matters: str = ""
    learning_outcomes: list[str] = Field(default_factory=list)
    audience: list[str] = Field(default_factory=list)
    # ---- classificacao editorial orientada a uso (taxonomy.yaml) -------------
    editorial_subcategory: Optional[str] = Field(default=None, description="Subcategoria da Home; define a secao")
    editorial_section: Optional[str] = Field(default=None, description="Derivada da subcategoria se omitida")
    use_cases: list[str] = Field(default_factory=list, description="Problemas que o recurso ajuda a resolver")
    supported_technologies: list[str] = Field(default_factory=list,
                                              description="Integracoes documentadas na fonte (exige source_evidence)")
    source_evidence: list[Link] = Field(default_factory=list, description="Paginas da fonte que sustentam a classificacao")
    considerations: list[str] = Field(default_factory=list, description="Pre-requisitos ou restricoes relevantes")
    related_collections: list[str] = Field(default_factory=list, description="Topic collections do Quick Knowledge")
    icon_org: Optional[str] = Field(default=None, description="Organizacao oficial no GitHub usada como icone")
    curation_status: CurationStatus = "published"
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
    # ---- Databricks Release Watch (preenchidos so por novidades APROVADAS) -----
    release_status: Optional[str] = Field(default=None, description="ga|public_preview|private_preview|beta|retired|deprecated|other")
    announced_on: Optional[date] = Field(default=None, description="Data do anuncio oficial mais recente")
    release_history: list[ReleaseEvent] = Field(default_factory=list, description="Historico de status (mais antigo primeiro)")

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

    @field_validator("icon_org")
    @classmethod
    def v_org(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[A-Za-z0-9-]{1,39}$", v):
            raise ValueError(f"icon_org invalido: {v!r}")
        return v

    @property
    def canonical_url(self) -> str:
        from services.ingest.base import canonical_url

        return canonical_url(self.url)

    @property
    def primary_domain(self) -> str:
        return self.areas[0]

    @property
    def secondary_domains(self) -> list[str]:
        return self.areas[1:]


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


class PlaybookStep(_Strict):
    title: str
    detail: str
    human_checkpoint: bool = Field(default=False, description="Etapa que exige julgamento, autorizacao ou revisao humana")


class PracticalPlaybook(_Strict):
    """Abordagem pratica e generica para um tipo de problema (nao e trilha de aprendizagem)."""

    id: str
    title: str
    summary: str
    when_to_use: str
    steps: list[PlaybookStep] = Field(min_length=3)
    considerations: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(min_length=1)
    areas: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    related_notes: list[str] = Field(default_factory=list)
    related_resources: list[str] = Field(default_factory=list)
    references: list[Link] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def v_id(cls, v: str) -> str:
        return _check_id(v)


class TopicCollection(_Strict):
    """Compilado do Quick Knowledge: por tecnologia/assunto ou por finalidade pratica."""

    id: str
    title: str
    kind: Literal["technology", "practical"]
    scope: str = Field(description="Assuntos cobertos, em poucas palavras (sem slogan)")
    icon: str = ":material/folder:"
    items: list[str] = Field(min_length=2, description="IDs de notas tecnicas ou playbooks")
    use_cases: list[str] = Field(default_factory=list)

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
    tagline: Optional[str] = None
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
