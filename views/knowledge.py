"""Base de Conhecimento: glossario em camadas + quizzes."""
from __future__ import annotations

import streamlit as st

from components.nav import go, param
from services.catalog import Catalog
from services.search import search_concepts


def _quiz(cat: Catalog, cid: str) -> None:
    for q in cat.quizzes_for_concept(cid):
        st.markdown(f"**Quiz:** {q.question}")
        choice = st.radio("Resposta", list(range(len(q.options))), format_func=lambda i: q.options[i],
                          index=None, key=f"quiz-{q.id}", label_visibility="collapsed")
        if st.button("Verificar", key=f"quiz-btn-{q.id}"):
            if choice is None:
                st.warning("Escolha uma opção.")
            elif choice == q.answer:
                st.success(f"Correto! {q.explanation}")
            else:
                st.error(f"Não é essa. Resposta: {q.options[q.answer]}. {q.explanation}")


def render(cat: Catalog, repo) -> None:
    st.title("Base de Conhecimento")
    st.write("Conceitos explicados em camadas: primeiro em linguagem simples, depois a visão técnica.")
    focus = param("concept")
    q = st.text_input("Buscar conceito", placeholder="Ex.: embeddings, atenção, agentes")
    concepts = search_concepts(cat.concepts.values(), q)
    if focus in cat.concepts and not q:
        concepts = [cat.concepts[focus]] + [c for c in concepts if c.id != focus]
    st.caption(f"{len(concepts)} conceito(s)")
    for c in concepts:
        title = c.name + (f" — {c.name_pt}" if c.name_pt and c.name_pt != c.name else "")
        with st.expander(title, expanded=(c.id == focus)):
            st.markdown("**Em linguagem simples**")
            st.write(c.simple)
            st.markdown("**Visão técnica**")
            st.write(c.technical)
            st.markdown("**Exemplo**")
            st.write(c.example)
            st.markdown("**Por que importa**")
            st.write(c.why)
            if c.related:
                st.caption("Relacionados: " + ", ".join(cat.concepts[x].name for x in c.related if x in cat.concepts))
            res = cat.resources_for_concept(c.id)
            if res:
                st.markdown("**Onde estudar**")
                for r in res[:5]:
                    if st.button(r.title, key=f"k-{c.id}-{r.id}", icon=":material/arrow_forward:"):
                        go("resource", resource=r.id)
            _quiz(cat, c.id)
