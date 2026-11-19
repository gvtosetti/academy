"""Discover: home editorial. Hero + busca global + chips de area + secoes curadas.

Os chips filtram a propria pagina (navegacao instantanea entre temas). Secoes
sem conteudo para a area escolhida simplesmente nao aparecem.
"""
from __future__ import annotations

import streamlit as st

from components.cards import grid, note_card, note_grid, resource_card, resource_grid
from components.layout import go, param, section_title
from services.catalog import Catalog, diverse

HERO_TITLE = "Um lugar para descobrir algo novo."
HERO_SUBTITLE = "Referências, ferramentas, ideias e conteúdos para aprender no seu ritmo — do básico ao avançado."
ALL = "all"


def _hero() -> None:
    with st.container(key="hero"):
        st.title(HERO_TITLE, anchor=False)
        st.markdown(HERO_SUBTITLE)
        with st.form("global-search", border=False, clear_on_submit=False):
            c1, c2 = st.columns([5, 1], vertical_alignment="bottom")
            q = c1.text_input(
                "Buscar",
                placeholder="Busque um tema, ferramenta ou conceito — ex.: RAG, forecast, Git, data contract",
                label_visibility="collapsed",
            )
            sent = c2.form_submit_button("Buscar", icon=":material/search:", type="primary")
        if sent and q.strip():
            go("library", q=q.strip()[:120])


def _chips(cat: Catalog, area: str | None) -> str | None:
    counts = cat.area_counts()
    options = [ALL] + [a.id for a in cat.areas.values() if a.chip and counts.get(a.id, 0) > 0]
    names = {ALL: "Todos", **{a.id: a.name for a in cat.areas.values()}}
    choice = st.pills(
        "Temas",
        options,
        default=area or ALL,
        format_func=names.get,
        label_visibility="collapsed",
        key=f"chips-{area or ALL}",
    )
    if choice and choice != (area or ALL):
        go("discover", area=None if choice == ALL else choice)
    return area


def render(cat: Catalog) -> None:
    area = param("area")
    if area not in cat.areas:
        area = None
    _hero()
    _chips(cat, area)
    if area:
        st.caption(cat.areas[area].description)

    def in_area(ids):
        return [cat.resources[i] for i in ids if i in cat.resources and (not area or area in cat.resources[i].areas)]

    shown: set[str] = set()

    # ---- Explore & Discover -------------------------------------------------
    explore = in_area(cat.home.explore)
    if area:  # completa a vitrine com outros recursos da area
        reserved = {w.id for w in cat.home.worth_checking_out} | set(cat.home.tools)
        extra = [r for r in diverse(cat.resources_in_area(area)) if r not in explore and r.id not in reserved]
        explore = (explore + extra)[:6]
    if explore:
        st.write("")
        section_title("Explore & Discover", "Uma seleção variada para começar a explorar.")
        resource_grid(explore, cat, "explore")
        shown |= {r.id for r in explore}

    # ---- Worth Checking Out -------------------------------------------------
    worth = [(cat.resources[w.id], w.note) for w in cat.home.worth_checking_out
             if w.id in cat.resources and w.id not in shown and (not area or area in cat.resources[w.id].areas)]
    if worth:
        section_title("Worth Checking Out", "Escolhas da curadoria, com o motivo de cada uma.")
        grid(worth, lambda item, i: resource_card(item[0], cat, "worth", note=item[1]), cols=2)
        shown |= {r.id for r, _ in worth}

    # ---- Quick Knowledge ----------------------------------------------------
    notes = [cat.notes[i] for i in cat.home.quick_knowledge if i in cat.notes]
    if area:
        notes = [n for n in notes if area in n.areas]
        notes += [n for n in cat.notes_in_area(area) if n not in notes and n.kind == "explainer"]
        notes += [n for n in cat.notes_in_area(area) if n not in notes]
    notes = notes[:6]
    if notes:
        section_title("Quick Knowledge", "Conceitos explicados em poucos minutos.")
        note_grid(notes, cat, "quick")

    # ---- Tools & Resources --------------------------------------------------
    tools = [r for r in in_area(cat.home.tools) if r.id not in shown]
    tool_notes = [n for n in cat.notes.values() if n.kind == "tool" and n not in notes and (not area or area in n.areas)][:3]
    if tools or tool_notes:
        section_title("Tools & Resources", "Coisas para usar direto no trabalho.")
        if tools:
            resource_grid(tools, cat, "tools")
        if tool_notes:
            note_grid(tool_notes, cat, "toolnotes")

    st.write("")
    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("Ver a Library completa", icon=":material/grid_view:", key="to-library"):
        go("library", area=area)
    if c2.button("Ver todas as notas", icon=":material/lightbulb:", key="to-tips"):
        go("tips", area=area)
