"""Cards editoriais da Resource Library (recurso e nota).

Cada card mostra pouco e sempre no mesmo lugar: identidade visual discreta (avatar do
autor no GitHub ou monograma do provedor), area + formato, titulo (ate 3 linhas),
descricao curta (ate 3 linhas) e duas acoes distintas:
  - "Open resource ↗": abre o material original em um clique;
  - "Saiba mais": explicacao complementar dentro da Resource Library.

Todo texto do catalogo e escapado antes de ir para o HTML (utils.safe.esc).
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional, Sequence, Union

import streamlit as st

from components.layout import go
from services.catalog import Catalog, Note
from services.models import Resource
from utils.safe import esc

TYPE_LABEL = {
    "github": ("Repositório", ":material/code:"),
    "course": ("Curso", ":material/school:"),
    "video": ("Vídeo", ":material/play_circle:"),
    "playlist": ("Playlist", ":material/smart_display:"),
    "documentation": ("Documentação", ":material/description:"),
    "tool": ("Ferramenta", ":material/build:"),
    "collection": ("Coleção", ":material/folder_special:"),
    "roadmap": ("Roadmap", ":material/route:"),
    "article": ("Artigo", ":material/article:"),
    "platform": ("Plataforma", ":material/account_balance:"),
    "library": ("Biblioteca", ":material/widgets:"),
    "service": ("Serviço", ":material/cloud:"),
    "framework": ("Framework", ":material/view_quilt:"),
    "book": ("Livro", ":material/menu_book:"),
}
COURSE_TYPES = {"course", "playlist", "video"}
LEVEL_LABEL = {"beginner": "Iniciante", "intermediate": "Intermediário", "advanced": "Avançado"}
LANG_LABEL = {"pt": "Português", "en": "Inglês", "multi": "Vários idiomas"}
KIND_ICON = {
    "explainer": ":material/menu_book:",
    "dev-tip": ":material/terminal:",
    "tool": ":material/handyman:",
    "practice": ":material/task_alt:",
    "in-practice": ":material/work:",
}
# Paleta discreta por area: (texto, fundo). Usada no kicker e no monograma.
AREA_TINT = {
    "data-science": ("#1D4ED8", "#E8EFFE"),
    "dev-backend": ("#334155", "#EEF1F5"),
    "product": ("#B45309", "#FDF2E3"),
    "data-governance": ("#047857", "#E4F5EE"),
    "market-research": ("#BE123C", "#FCE9EE"),
    "ai-llms": ("#6D28D9", "#F0EAFE"),
    "creative-tech": ("#C2410C", "#FDEDE4"),
    "data-engineering": ("#0E7490", "#E2F4F8"),
    "analytics": ("#4D7C0F", "#EEF6E2"),
}
# Compatibilidade com chamadas que usam a paleta nativa do markdown do Streamlit.
AREA_COLOR = {
    "data-science": "blue", "dev-backend": "gray", "product": "orange", "data-governance": "green",
    "market-research": "red", "ai-llms": "violet", "creative-tech": "orange",
    "data-engineering": "blue", "analytics": "green",
}
DESC_MAX = 160
_OWNER_RE = re.compile(r"^[A-Za-z0-9-]{1,39}$")
_STOP = {"the", "a", "o", "de", "of"}

Item = Union[Resource, Note]


# ---- helpers ---------------------------------------------------------------
def area_label(cat: Catalog, area_id: str, bold: bool = True) -> str:
    """Rotulo de area em markdown do Streamlit (usado nas paginas de detalhe)."""
    a = cat.areas.get(area_id)
    if not a:
        return ""
    name = f"**{a.name}**" if bold else a.name
    return f":{AREA_COLOR.get(area_id, 'gray')}[{a.icon} {name}]"


def type_label(r: Resource) -> str:
    label, icon = TYPE_LABEL[r.type]
    return f"{icon} {label}"


def clip(text: str, limit: int = DESC_MAX) -> str:
    """Corta no limite de palavra mais proximo, sem quebrar o sentido."""
    t = " ".join((text or "").split())
    if len(t) <= limit:
        return t
    cut = t[: limit + 1].rsplit(" ", 1)[0].rstrip(",;:—- ")
    return cut + "…"


def _tint(area_id: str) -> tuple[str, str]:
    return AREA_TINT.get(area_id, ("#44403C", "#F1F0EE"))


def _monogram(provider: str) -> str:
    words = [w for w in re.split(r"[\s()]+", provider) if w and w.lower() not in _STOP]
    if not words:
        return "·"
    if len(words) == 1:
        caps = [c for c in words[0][1:] if c.isupper()]
        return (words[0][0] + (caps[0] if caps else "")).upper()
    return (words[0][0] + words[1][0]).upper()


def _logo(r: Resource) -> str:
    """Avatar real do dono do repositorio no GitHub; senao, monograma do provedor."""
    fg, bg = _tint(r.areas[0])
    owner = r.icon_org or (r.github_repo or "").split("/")[0]
    mono = f'<span class="ac-mono">{esc(_monogram(r.provider))}</span>'
    if owner and _OWNER_RE.match(owner):
        img = f'<img src="https://github.com/{owner}.png?size=96" alt="" loading="lazy" referrerpolicy="no-referrer">'
        return f'<span class="ac-logo" style="--fg:{fg};--bg:{bg}">{img}</span>'
    return f'<span class="ac-logo" style="--fg:{fg};--bg:{bg}">{mono}</span>'


def _kicker(cat: Catalog, area_id: str, fmt: str) -> str:
    fg, _ = _tint(area_id)
    a = cat.areas.get(area_id)
    name = esc(a.name) if a else ""
    return f'<span class="ac-kicker"><b style="color:{fg}">{name}</b><i>·</i>{esc(fmt)}</span>'


def _html(s: str) -> None:
    st.markdown(s, unsafe_allow_html=True)


def _actions(key: str, url: Optional[str], on_more: Callable[[], None], more_label: str = "Saiba mais") -> None:
    """Duas acoes como links discretos; nunca truncam (largura do conteudo, quebra de linha permitida)."""
    with st.container(horizontal=True, gap="medium", vertical_alignment="center", key=f"act-{key}"):
        if url:
            st.link_button("Open resource ↗", url, type="tertiary")
        if st.button(more_label, key=f"more-{key}" if more_label == "Saiba mais" else f"read-{key}", type="tertiary"):
            on_more()


# ---- cards -----------------------------------------------------------------
def resource_card(r: Resource, cat: Catalog, key: str, note: Optional[str] = None, variant: str = "grid") -> None:
    """variant: grid | row | feature | shelf."""
    fmt = TYPE_LABEL[r.type][0]
    if variant == "shelf" and r.difficulty:
        fmt = f"{fmt} · {LEVEL_LABEL[r.difficulty]}"
    head = f'<div class="ac-head">{_logo(r)}{_kicker(cat, r.areas[0], fmt)}</div>'
    title = f'<div class="ac-title">{esc(r.title)}</div>'
    desc = f'<div class="ac-desc">{esc(clip(r.tagline))}</div>'
    quote = f'<div class="ac-quote">{esc(clip(note, 140))}</div>' if note else ""
    with st.container(border=True, key=f"card-{variant}-{key}-{r.id}"):
        if variant == "row":
            _html(f'<div class="ac-rowwrap">{_logo(r)}<div class="ac-rowtext">'
                  f'{_kicker(cat, r.areas[0], fmt)}{title}{desc}</div></div>')
        else:
            _html(head + title + desc + quote)
        _actions(f"{key}-{r.id}", r.url, lambda: go("resource", resource=r.id))


def note_card(n: Note, cat: Catalog, key: str, variant: str = "grid", note: Optional[str] = None) -> None:
    """Nota curta (Tips & Insights). variant: grid | row | tile."""
    fg, bg = _tint(n.areas[0])
    a = cat.areas.get(n.areas[0])
    kick = (f'<span class="ac-kicker"><b style="color:{fg}">{esc(n.kind_label)}</b><i>·</i>'
            f'{n.minutes} min{" · " + esc(a.name) if a else ""}</span>')
    glyph = f'<span class="ac-logo ac-glyph" style="--fg:{fg};--bg:{bg}"><span class="ac-mono">{esc(_note_glyph(n))}</span></span>'
    title = f'<div class="ac-title">{esc(n.title)}</div>'
    desc = f'<div class="ac-desc">{esc(clip(n.summary))}</div>'
    quote = f'<div class="ac-quote">{esc(clip(note, 140))}</div>' if note else ""
    with st.container(border=True, key=f"card-{variant}-{key}-{n.id}"):
        if variant == "row":
            _html(f'<div class="ac-rowwrap">{glyph}<div class="ac-rowtext">{kick}{title}{desc}</div></div>')
        elif variant == "tile":
            _html(f'<div class="ac-head">{kick}</div>{title}{desc}')
        else:
            _html(f'<div class="ac-head">{glyph}{kick}</div>{title}{desc}{quote}')
        _actions(f"{key}-{n.id}", None, lambda: go("note", note=n.id), more_label="Ler nota →")


def _note_glyph(n: Note) -> str:
    return {"explainer": "Aa", "dev-tip": "</>", "tool": "⚒", "practice": "✓", "in-practice": "▸"}[n.kind]


def playbook_card(p, cat: Catalog, key: str) -> None:
    """Practical Playbook: problema + numero de etapas."""
    fg, bg = _tint(p.areas[0])
    glyph = f'<span class="ac-logo ac-glyph" style="--fg:{fg};--bg:{bg}"><span class="ac-mono">▤</span></span>'
    kick = f'<span class="ac-kicker"><b style="color:{fg}">Playbook</b><i>·</i>{len(p.steps)} etapas</span>'
    with st.container(border=True, key=f"card-pb-{key}-{p.id}"):
        _html(f'<div class="ac-head">{glyph}{kick}</div><div class="ac-title">{esc(p.title)}</div>'
              f'<div class="ac-desc">{esc(clip(p.summary))}</div>')
        _actions(f"{key}-{p.id}", None, lambda: go("playbook", playbook=p.id), more_label="Ler playbook →")


def topic_card(t, cat: Catalog, key: str) -> None:
    """Topic Collection do Quick Knowledge: titulo, assuntos e quantidade de itens."""
    n = len(cat.topic_items(t.id))
    with st.container(border=True, key=f"card-topic-{key}-{t.id}"):
        if st.button(t.title, key=f"topic-{key}-{t.id}", icon=t.icon, type="tertiary"):
            go("topic", topic=t.id)
        _html(f'<div class="ac-desc">{esc(t.scope)} · {n} itens</div>')


def item_card(item: Item, cat: Catalog, key: str, note: Optional[str] = None, variant: str = "grid") -> None:
    if isinstance(item, Resource):
        resource_card(item, cat, key, note=note, variant=variant)
    else:
        note_card(item, cat, key, variant={"shelf": "grid", "feature": "grid"}.get(variant, variant), note=note)


# ---- grids -----------------------------------------------------------------
def grid(items: Sequence, render: Callable[[object, int], None], cols: int = 3) -> None:
    """Grade responsiva: colunas no desktop, empilhadas no mobile. Linhas incompletas
    mantem a largura das colunas (cards nao esticam)."""
    for start in range(0, len(items), cols):
        row = st.columns(cols, gap="medium")
        for i, item in enumerate(items[start:start + cols]):
            with row[i]:
                render(item, start + i)


def resource_grid(resources: Iterable[Resource], cat: Catalog, key: str, cols: int = 3, variant: str = "grid") -> None:
    grid(list(resources), lambda r, i: resource_card(r, cat, key, variant=variant), cols)


def note_grid(notes: Iterable[Note], cat: Catalog, key: str, cols: int = 3, variant: str = "grid") -> None:
    grid(list(notes), lambda n, i: note_card(n, cat, key, variant=variant), cols)


def item_grid(items: Iterable[tuple[Item, Optional[str]]], cat: Catalog, key: str, cols: int = 3, variant: str = "grid") -> None:
    grid(list(items), lambda it, i: item_card(it[0], cat, key, note=it[1], variant=variant), cols)


# ---- componentes compactos da Home -----------------------------------------
# Cada componente e UM bloco HTML: o elemento clicavel (<a>) e o proprio card/linha, entao
# titulo, descricao e indicador de link vivem no mesmo container visual e no mesmo fluxo
# (sem position absoluta, sem altura fixa). O layout em colunas e CSS grid (styles.py), que
# decide 3/2/1 colunas pela largura disponivel.
_MS_RE = re.compile(r"^:material/([a-z0-9_]+):$")


def ms_icon(icon: Optional[str], cls: str = "ac-ms") -> str:
    """':material/x:' -> glifo da fonte Material Symbols (a mesma que o Streamlit carrega)."""
    m = _MS_RE.match(icon or "")
    return f'<span class="{cls}" aria-hidden="true">{m.group(1)}</span>' if m else ""


def internal_href(page: str, **params: Optional[str]) -> str:
    """Link interno relativo (mesma aba): a navegacao do app e toda por query params."""
    from urllib.parse import urlencode

    q = {"page": page, **{k: v for k, v in params.items() if v}}
    return esc("?" + urlencode(q))


def _ext(url: str) -> str:
    return f'href="{esc(url)}" target="_blank" rel="noopener noreferrer"'


def _int(page: str, **params: Optional[str]) -> str:
    return f'href="{internal_href(page, **params)}" target="_self"'


def category_card_html(sub, area: Optional[str]) -> str:
    """Make Your Work Easier: icone + titulo + descricao curta; o card inteiro abre a Library filtrada."""
    return (f'<a class="ac-cat" {_int("library", subcategory=sub.id, area=area)}>'
            f'{ms_icon(sub.icon, "ac-ms ac-cat-icon")}'
            f'<span class="ac-cat-text"><span class="ac-cat-title">{esc(sub.title)}</span>'
            f'<span class="ac-cat-desc">{esc(sub.scope)}</span></span></a>')


def tool_row_html(r: Resource) -> str:
    """Tools & Resources: linha com logo, nome, descricao funcional (1 linha) e indicador externo."""
    return (f'<a class="ac-trow" {_ext(r.url)} title="{esc(r.tagline)}">{_logo(r)}'
            f'<span class="ac-trow-text"><span class="ac-trow-name">{esc(r.title)}</span>'
            f'<span class="ac-trow-desc">{esc(r.tagline)}</span></span>'
            f'<span class="ac-ext" aria-label="abre em nova aba">↗</span></a>')


def platform_tile_html(r: Resource) -> str:
    """Learning Platforms: logo + nome em grade compacta."""
    return (f'<a class="ac-plat" {_ext(r.url)} title="{esc(r.tagline)}">{_logo(r)}'
            f'<span class="ac-plat-name">{esc(r.title)}</span><span class="ac-ext">↗</span></a>')


def course_row_html(r: Resource, cat: Catalog) -> str:
    """Courses & Lectures: titulo completo (sem corte), fornecedor e assunto."""
    a = cat.areas.get(r.areas[0]) if r.areas else None
    meta = " · ".join(x for x in (r.provider, a.name if a else "") if x)
    return (f'<a class="ac-course" {_ext(r.url)}><span class="ac-course-text">'
            f'<span class="ac-course-title">{esc(r.title)}</span>'
            f'<span class="ac-course-meta">{esc(meta)}</span></span><span class="ac-ext">↗</span></a>')


def guide_row_html(r: Resource) -> str:
    """Technical Guides & Roadmaps: titulo + descricao de uma linha."""
    return (f'<a class="ac-guide" {_ext(r.url)} title="{esc(r.tagline)}"><span class="ac-guide-text">'
            f'<span class="ac-guide-title">{esc(r.title)}</span>'
            f'<span class="ac-guide-desc">{esc(r.tagline)}</span></span><span class="ac-ext">↗</span></a>')


def collection_card_html(t, cat: Catalog, topics_shown: int = 3) -> str:
    """Quick Knowledge: icone, titulo, topicos (sem corte) e quantidade real de notas."""
    n = sum(1 for i in cat.topic_items(t.id) if isinstance(i, Note))
    topics = " · ".join(x.strip() for x in (t.scope or "").split(",")[:topics_shown] if x.strip())
    return (f'<a class="ac-coll" {_int("topic", topic=t.id)}>'
            f'<span class="ac-coll-head">{ms_icon(t.icon, "ac-ms ac-coll-icon")}'
            f'<span class="ac-coll-title">{esc(t.title)}</span></span>'
            f'<span class="ac-coll-topics">{esc(topics)}</span>'
            f'<span class="ac-coll-count">{n} {"nota" if n == 1 else "notas"}</span></a>')


def html_block(css_class: str, inner: Iterable[str], key: str) -> None:
    """Um unico bloco markdown com a grade inteira (sem widgets Streamlit intercalados)."""
    # .ac-cq e o container de referencia das container queries (colunas pela largura real do bloco)
    _html(f'<div class="ac-cq"><div class="{css_class}" data-block="{esc(key)}">{"".join(inner)}</div></div>')
