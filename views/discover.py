"""Discover: home editorial com 4 seções derivadas da taxonomia.

Ordem: hero compacto com busca -> chips de area -> 4 seções:
1. Make Your Work Easier (subcategorias: automacao, IA, templates, validacao)
2. Tools & Resources (subcategorias: ferramentas, dev, ai/data, pesquisa)
3. Deep Dives & Courses (subcategorias: plataformas, cursos, guias)
4. Quick Knowledge (topic collections: technology + practical)

Com um chip ativo, cada seção mostra só itens da área e some se ficar vazia.
"""
from __future__ import annotations

import streamlit as st

from components.cards import (
    item_card, note_card, playbook_card, resource_card, topic_card,
)
from components.layout import go, param, section_title
from services.catalog import Catalog, diverse
from services.models import Resource

HERO_TITLE = "Resource Library"
ALL = "all"
SECTION_LIMIT = 6  # itens por seção na home
QK_LIMIT = 8       # topic collections no Quick Knowledge


def _hero() -> None:
    with st.container(key="hero"):
        st.title(HERO_TITLE, anchor=False)
        with st.form("global-search", border=False, clear_on_submit=False):
            c1, c2 = st.columns([6, 1], vertical_alignment="bottom", gap="small")
            q = c1.text_input(
                "Buscar",
                placeholder="Buscar ferramentas, cursos, conceitos...",
                label_visibility="collapsed",
            )
            sent = c2.form_submit_button("Buscar", icon=":material/search:", type="primary", width="stretch")
        if sent and q.strip():
            go("library", q=q.strip()[:120])


def _chips(cat: Catalog, area: str | None) -> None:
    counts = cat.area_counts()
    options = [ALL] + [a.id for a in cat.areas.values() if a.chip and counts.get(a.id, 0) > 0]
    names = {ALL: "Todos", **{a.id: a.name for a in cat.areas.values()}}
    choice = st.pills(
        "Temas", options, default=area or ALL, format_func=names.get,
        label_visibility="collapsed", key=f"chips-{area or ALL}",
    )
    if choice and choice != (area or ALL):
        go("discover", area=None if choice == ALL else choice)


def _area_filter(resources: list[Resource], area: str | None) -> list[Resource]:
    if not area:
        return resources
    return [r for r in resources if area in r.areas]


def _section_resources(cat: Catalog, section_id: str, area: str | None) -> None:
    """Renderiza uma seção editorial com subcategorias agrupadas."""
    sec = cat.taxonomy.section(section_id)
    if not sec:
        return
    all_res = _area_filter(cat.resources_in_section(section_id), area)
    if not all_res:
        return
    section_title(sec.title)
    # Mostrar por subcategoria
    shown = 0
    for sub in sec.subcategories:
        sub_res = [r for r in all_res if r.editorial_subcategory == sub.id]
        if not sub_res:
            continue
        display = sub_res[:SECTION_LIMIT - shown] if shown < SECTION_LIMIT else []
        if not display:
            continue
        st.caption(f"{sub.icon} **{sub.title}**")
        cols = st.columns(3, gap="medium")
        for i, r in enumerate(display):
            with cols[i % 3]:
                resource_card(r, cat, f"home-{section_id}", variant="grid")
        shown += len(display)
    # Link para a Library filtrada
    total = len(all_res)
    if total > shown:
        if st.button(f"Ver todos ({total})", key=f"more-{section_id}", icon=":material/grid_view:", type="tertiary"):
            go("library", section=section_id, area=area)


def _quick_knowledge(cat: Catalog, area: str | None) -> None:
    """Seção Quick Knowledge: topic collections (technology + practical)."""
    tech = [t for t in cat.topics.values() if t.kind == "technology"]
    prac = [t for t in cat.topics.values() if t.kind == "practical"]
    if not tech and not prac:
        return
    section_title("Quick Knowledge")
    if tech:
        st.caption(":material/school: **Technology Collections**")
        cols = st.columns(4, gap="medium")
        for i, t in enumerate(tech[:QK_LIMIT]):
            with cols[i % 4]:
                topic_card(t, cat, "qk-tech")
    if prac:
        st.caption(":material/build: **Practical Collections**")
        cols = st.columns(4, gap="medium")
        for i, t in enumerate(prac[:QK_LIMIT]):
            with cols[i % 4]:
                topic_card(t, cat, "qk-prac")


def render(cat: Catalog) -> None:
    area = param("area")
    if area not in cat.areas:
        area = None
    _hero()
    _chips(cat, area)

    # 1. Make Your Work Easier
    _section_resources(cat, "make-your-work-easier", area)
    # 2. Tools & Resources
    _section_resources(cat, "tools-resources", area)
    # 3. Deep Dives & Courses
    _section_resources(cat, "deep-dives-courses", area)
    # 4. Quick Knowledge
    _quick_knowledge(cat, area)

    st.write("")
    with st.container(horizontal=True, gap="medium", key="home-more"):
        if st.button("Ver a Library completa", icon=":material/grid_view:", key="to-library"):
            go("library", area=area)
        if st.button("Ver todas as notas", icon=":material/lightbulb:", key="to-tips"):
            go("tips", area=area)
