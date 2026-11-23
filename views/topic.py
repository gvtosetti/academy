"""Pagina de detalhe de um Topic Collection do Quick Knowledge."""
from __future__ import annotations

import streamlit as st

from components.cards import note_card, playbook_card, resource_grid
from components.layout import go, param
from services.catalog import Catalog

KIND_LABEL = {"technology": "Technology Collection", "practical": "Practical Collection"}


def render(cat: Catalog) -> None:
    tid = param("topic") or ""
    t = cat.topics.get(tid)
    if not t:
        st.title("Compilado n\u00e3o encontrado", anchor=False)
        st.write("O link pode estar desatualizado.")
        if st.button("Voltar", icon=":material/arrow_back:"):
            go("discover")
        return

    if st.button("Voltar", icon=":material/arrow_back:", type="tertiary", key="back"):
        go("discover")
    items = cat.topic_items(tid)
    st.caption(f"{t.icon} {KIND_LABEL.get(t.kind, t.kind)} \u00b7 {len(items)} itens")
    st.title(t.title, anchor=False)
    st.markdown(t.scope)

    # Renderizar itens: notas e playbooks
    from services.catalog import Note
    from services.models import PracticalPlaybook

    cols = st.columns(2, gap="medium")
    for i, item in enumerate(items):
        with cols[i % 2]:
            if isinstance(item, Note):
                note_card(item, cat, f"topic-{tid}", variant="grid")
            elif isinstance(item, PracticalPlaybook):
                playbook_card(item, cat, f"topic-{tid}")

    # Recursos relacionados ao topic
    res = cat.resources_for_topic(tid)[:6]
    if res:
        st.subheader("Recursos relacionados", anchor=False)
        resource_grid(res, cat, f"topic-res-{tid}")
