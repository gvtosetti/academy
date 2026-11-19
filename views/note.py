"""Leitura de uma nota de Tips & Insights (1-3 minutos, independente)."""
from __future__ import annotations

import streamlit as st

from components.cards import KIND_ICON, area_label, resource_grid
from components.layout import go, param
from services.catalog import Catalog


def render(cat: Catalog) -> None:
    nid = param("note") or param("concept") or ""
    n = cat.notes.get(nid)
    if not n:
        st.title("Nota não encontrada", anchor=False)
        st.write("O link pode estar desatualizado.")
        if st.button("Ver Tips & Insights", icon=":material/lightbulb:"):
            go("tips")
        return

    if st.button("Tips & Insights", icon=":material/arrow_back:", type="tertiary", key="back"):
        go("tips")
    meta = [f"{KIND_ICON[n.kind]} {n.kind_label}", f"{n.minutes} min de leitura"]
    st.caption("  ·  ".join(meta + [area_label(cat, a, bold=False) for a in n.areas]))
    st.title(n.title, anchor=False)
    with st.container(key="lead"):
        st.markdown(n.summary)
    st.markdown(n.body)
    if n.technical:
        with st.expander("Em mais detalhe", icon=":material/science:"):
            st.write(n.technical)

    related = [cat.notes[x] for x in n.related_notes if x in cat.notes]
    if related:
        st.markdown("##### Veja também")
        cols = st.columns(min(4, len(related)))
        for i, rn in enumerate(related):
            if cols[i % len(cols)].button(rn.title, key=f"rn-{rn.id}", icon=KIND_ICON[rn.kind], type="tertiary"):
                go("note", note=rn.id)

    res = [cat.resources[x] for x in n.related_resources if x in cat.resources][:3]
    if res:
        st.subheader("Para ir além", anchor=False)
        resource_grid(res, cat, "noteres")
