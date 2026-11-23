"""Pagina de detalhe de um Practical Playbook."""
from __future__ import annotations

import streamlit as st

from components.cards import area_label, resource_grid
from components.layout import go, param
from services.catalog import Catalog


def render(cat: Catalog) -> None:
    pid = param("playbook") or ""
    p = cat.playbooks.get(pid)
    if not p:
        st.title("Playbook n\u00e3o encontrado", anchor=False)
        st.write("O link pode estar desatualizado.")
        if st.button("Voltar", icon=":material/arrow_back:"):
            go("discover")
        return

    if st.button("Voltar", icon=":material/arrow_back:", type="tertiary", key="back"):
        go("discover")
    areas = " \u00b7 ".join(area_label(cat, a, bold=False) for a in p.areas)
    st.caption(f":material/assignment: Playbook \u00b7 {len(p.steps)} etapas \u00b7 {areas}")
    st.title(p.title, anchor=False)
    with st.container(key="lead"):
        st.markdown(p.summary)
    st.caption(f"**Quando usar:** {p.when_to_use}")

    st.subheader("Etapas", anchor=False)
    for i, step in enumerate(p.steps, 1):
        icon = ":material/person:" if step.human_checkpoint else ":material/check_circle:"
        with st.expander(f"{icon} {i}. {step.title}", expanded=i <= 2):
            st.write(step.detail)
            if step.human_checkpoint:
                st.info("Esta etapa depende de julgamento ou aprova\u00e7\u00e3o humana.", icon=":material/person:")

    if p.considerations:
        st.subheader("Considera\u00e7\u00f5es", anchor=False)
        st.markdown("\n".join(f"- {c}" for c in p.considerations))

    # notas relacionadas
    rel_notes = [cat.notes[x] for x in p.related_notes if x in cat.notes]
    if rel_notes:
        st.markdown("##### Notas relacionadas")
        cols = st.columns(min(4, len(rel_notes)))
        for i, n in enumerate(rel_notes):
            if cols[i % len(cols)].button(n.title, key=f"rn-{n.id}", type="tertiary"):
                go("note", note=n.id)

    # recursos relacionados
    res = [cat.resources[x] for x in p.related_resources if x in cat.resources][:4]
    if res:
        st.subheader("Recursos relacionados", anchor=False)
        resource_grid(res, cat, "pb-res")

    # topic collections que incluem este playbook
    topics = cat.topics_of(pid)
    if topics:
        st.caption("Parte de: " + ", ".join(f"[{t.title}](?page=topic&topic={t.id})" for t in topics))
