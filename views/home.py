"""Pagina inicial."""
from __future__ import annotations

import streamlit as st

from components.nav import go
from components.ui import DIFFICULTY_LABEL, card_grid
from services.catalog import Catalog

SECTIONS = [
    ("start_here", "Comece por aqui", "Pontos de partida recomendados pela curadoria."),
    ("beginners", "Para iniciantes", "Sem pré-requisitos técnicos pesados."),
    ("hands_on", "Mão na massa", "Projetos e código para praticar."),
    ("deep_dives", "Aprofundamento", "Cursos completos para ir fundo."),
]


def render(cat: Catalog, repo) -> None:
    st.title("Academy")
    st.subheader("Aprenda IA, LLMs e agentes com uma curadoria explicada em português")
    st.write(
        "Cursos, playlists e repositórios selecionados, cada um com explicação simples, visão técnica, "
        "guia de estudo e indicação do que foi verificado na fonte original."
    )
    with st.form("home-search", border=False):
        c1, c2 = st.columns([5, 1])
        q = c1.text_input("Buscar", placeholder="Ex.: RAG, tokens, agentes, Transformer...", label_visibility="collapsed")
        if c2.form_submit_button("Buscar", icon=":material/search:") and q.strip():
            go("explore", q=q.strip())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Recursos", len(cat.resources))
    m2.metric("Trilhas", len(cat.tracks))
    m3.metric("Conceitos", len(cat.concepts))
    m4.metric("Categorias", len(cat.categories))

    st.header("Trilhas de aprendizado")
    cols = st.columns(3)
    for i, t in enumerate(cat.tracks.values()):
        with cols[i % 3], st.container(border=True):
            st.markdown(f"**{t.title}**")
            st.caption(f"{DIFFICULTY_LABEL.get(t.difficulty, t.difficulty)} · {len(t.modules)} módulos")
            st.write(t.objective)
            if st.button("Abrir trilha", key=f"home-track-{t.id}", icon=t.icon):
                go("paths", track=t.id)

    for sec, title, desc in SECTIONS:
        items = cat.featured(sec)
        if items:
            st.header(title)
            st.caption(desc)
            card_grid(items[:6], cat, key=f"home-{sec}")

    st.header("Categorias")
    cols = st.columns(3)
    for i, c in enumerate(cat.categories.values()):
        n = len(cat.resources_in_category(c.id))
        with cols[i % 3], st.container(border=True):
            st.markdown(f"{c.icon} **{c.name}**")
            st.caption(f"{n} recurso(s)")
            st.write(c.description)
            if st.button("Ver recursos", key=f"home-cat-{c.id}"):
                go("explore", category=c.id)

    st.header("Adicionados recentemente")
    card_grid(cat.recent(6), cat, key="home-recent")
