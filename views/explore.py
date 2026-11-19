"""Busca e filtros do catalogo."""
from __future__ import annotations

import streamlit as st

from components.nav import param
from components.ui import DIFFICULTY_LABEL, LANGUAGE_LABEL, TYPE_LABEL, card_grid
from services.catalog import Catalog
from services.search import Filters, LocalSearch

SORTS = {"relevance": "Relevância", "sequence": "Ordem sugerida de estudo", "title": "Título (A-Z)"}


@st.cache_resource(show_spinner=False)
def _engine(_cat: Catalog, version: int) -> LocalSearch:
    return LocalSearch(_cat)


def render(cat: Catalog, repo) -> None:
    st.title("Explorar")
    q = st.text_input("Buscar por tema, conceito, ferramenta ou autor", value=param("q", "") or "",
                      placeholder="Ex.: busca híbrida, LangGraph, Stanford, animação")
    pre_cat = param("category")
    with st.expander("Filtros", expanded=bool(pre_cat)):
        c1, c2, c3 = st.columns(3)
        cats = c1.multiselect("Categoria", list(cat.categories), default=[pre_cat] if pre_cat in cat.categories else [],
                              format_func=lambda x: cat.categories[x].name)
        diffs = c2.multiselect("Nível", list(DIFFICULTY_LABEL), format_func=DIFFICULTY_LABEL.get)
        types = c3.multiselect("Tipo", list(TYPE_LABEL), format_func=TYPE_LABEL.get)
        c4, c5, c6 = st.columns(3)
        langs = c4.multiselect("Idioma", list(LANGUAGE_LABEL), format_func=LANGUAGE_LABEL.get)
        tracks = c5.multiselect("Trilha", list(cat.tracks), format_func=lambda x: cat.tracks[x].title)
        providers = c6.multiselect("Fonte", sorted({r.provider for r in cat.resources.values()}))
    sort = st.radio("Ordenar por", list(SORTS), format_func=SORTS.get, horizontal=True)

    f = Filters(categories=tuple(cats), difficulties=tuple(diffs), types=tuple(types),
                languages=tuple(langs), providers=tuple(providers), tracks=tuple(tracks))
    results = _engine(cat, id(cat)).search(q, f, sort=sort)
    st.caption(f"{len(results)} resultado(s)")
    if not results and q:
        st.info("Nada encontrado. Tente termos mais gerais ou remova filtros. A Base de Conhecimento também pode ajudar.")
        return
    statuses = {r.id: repo.get_status(r.id) for r, _ in results}
    card_grid([r for r, _ in results], cat, key="explore", statuses=statuses)
