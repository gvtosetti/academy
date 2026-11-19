"""Cards reutilizaveis: recurso (acesso direto a fonte) e nota (Tips & Insights).

Um card mostra apenas: identidade visual discreta (icone da area), area, tipo,
titulo, 1-2 frases e acoes. O link externo abre direto do card.
"""
from __future__ import annotations

from typing import Callable, Iterable, Optional, Sequence

import streamlit as st

from components.layout import go
from services.catalog import Catalog, Note
from services.models import Resource

TYPE_LABEL = {
    "github": ("Repositório GitHub", ":material/code:"),
    "course": ("Curso", ":material/school:"),
    "video": ("Vídeo", ":material/play_circle:"),
    "playlist": ("Playlist de vídeos", ":material/smart_display:"),
    "documentation": ("Documentação", ":material/description:"),
    "tool": ("Ferramenta", ":material/build:"),
    "collection": ("Coleção", ":material/folder_special:"),
}
LEVEL_LABEL = {"beginner": "Iniciante", "intermediate": "Intermediário", "advanced": "Avançado"}
LANG_LABEL = {"pt": "Português", "en": "Inglês", "multi": "Vários idiomas"}
KIND_ICON = {
    "explainer": ":material/menu_book:",
    "dev-tip": ":material/terminal:",
    "tool": ":material/handyman:",
    "practice": ":material/task_alt:",
    "in-practice": ":material/work:",
}
# Cor discreta por area (paleta nativa do Streamlit markdown).
AREA_COLOR = {
    "data-science": "blue",
    "dev-backend": "gray",
    "product": "orange",
    "data-governance": "green",
    "market-research": "red",
    "ai-llms": "violet",
    "creative-tech": "orange",
    "data-engineering": "blue",
    "analytics": "green",
}


def area_label(cat: Catalog, area_id: str, bold: bool = True) -> str:
    a = cat.areas.get(area_id)
    if not a:
        return ""
    name = f"**{a.name}**" if bold else a.name
    return f":{AREA_COLOR.get(area_id, 'gray')}[{a.icon} {name}]"


def type_label(r: Resource) -> str:
    label, icon = TYPE_LABEL[r.type]
    return f"{icon} {label}"


def resource_card(r: Resource, cat: Catalog, key: str, note: Optional[str] = None) -> None:
    with st.container(border=True, key=f"card-{key}-{r.id}"):
        st.caption(f"{area_label(cat, r.areas[0])}  ·  {type_label(r)}")
        st.subheader(r.title, anchor=False)
        st.markdown(r.blurb)
        if note:
            st.caption(f":material/format_quote: {note}")
        c1, c2 = st.columns(2)
        c1.link_button("Explorar", r.url, icon=":material/open_in_new:", type="primary")
        if c2.button("Saiba mais", key=f"more-{key}-{r.id}", type="tertiary"):
            go("resource", resource=r.id)


def note_card(n: Note, cat: Catalog, key: str) -> None:
    with st.container(border=True, key=f"card-{key}-{n.id}"):
        st.caption(f"{KIND_ICON[n.kind]} {n.kind_label}  ·  {n.minutes} min")
        st.subheader(n.title, anchor=False)
        st.markdown(n.summary)
        st.caption("  ·  ".join(area_label(cat, a, bold=False) for a in n.areas[:2]))
        if st.button("Ler nota", key=f"read-{key}-{n.id}", icon=":material/arrow_forward:", type="tertiary"):
            go("note", note=n.id)


def grid(items: Sequence, render: Callable[[object, int], None], cols: int = 3) -> None:
    """Grid responsivo: colunas lado a lado no desktop, empilhadas no mobile."""
    for start in range(0, len(items), cols):
        row = st.columns(cols, gap="medium")
        for i, item in enumerate(items[start:start + cols]):
            with row[i]:
                render(item, start + i)


def resource_grid(resources: Iterable[Resource], cat: Catalog, key: str, cols: int = 3) -> None:
    items = list(resources)
    grid(items, lambda r, i: resource_card(r, cat, key), cols)


def note_grid(notes: Iterable[Note], cat: Catalog, key: str, cols: int = 3) -> None:
    items = list(notes)
    grid(items, lambda n, i: note_card(n, cat, key), cols)
