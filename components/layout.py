"""Navegacao por query params (URLs estaveis e compartilhaveis) e moldura da pagina.

Tres secoes principais: Discover, Library e Tips & Insights. As paginas de detalhe
(`resource`, `note`) nao aparecem no menu. Rotas antigas sao redirecionadas.
"""
from __future__ import annotations

from typing import Optional

import streamlit as st

PAGES = {
    "discover": ("Discover", ":material/explore:"),
    "library": ("Library", ":material/grid_view:"),
    "tips": ("Tips & Insights", ":material/lightbulb:"),
}
DETAIL_PAGES = {"resource", "note"}

# Rotas da versao anterior (LMS) -> novas secoes. Mantem links antigos funcionando.
LEGACY = {
    "home": "discover",
    "explore": "library",
    "paths": "library",
    "videos": "library",
    "github": "library",
    "my_learning": "discover",
    "about": "discover",
    "knowledge": "tips",
}


def param(name: str) -> Optional[str]:
    v = st.query_params.get(name)
    return v.strip() if isinstance(v, str) and v.strip() else None


def current_page() -> str:
    p = param("page") or "discover"
    if p == "knowledge" and param("concept"):
        return "note"  # link antigo de conceito do glossario
    p = LEGACY.get(p, p)
    return p if p in PAGES or p in DETAIL_PAGES else "discover"


def go(page: str, **params: Optional[str]) -> None:
    st.query_params.clear()
    st.query_params["page"] = page
    for k, v in params.items():
        if v:
            st.query_params[k] = v
    st.rerun()


def header(active: str) -> None:
    section = active if active in PAGES else {"resource": "library", "note": "tips"}.get(active)
    with st.container(key="topbar"):
        left, right = st.columns([1, 2], vertical_alignment="center")
        with left:
            if st.button("Academy", icon=":material/auto_awesome:", type="tertiary", key="brand"):
                go("discover")
        with right:
            choice = st.segmented_control(
                "Navegação",
                list(PAGES),
                default=section,
                format_func=lambda k: PAGES[k][0],
                label_visibility="collapsed",
                key=f"nav-{active}",
            )
    if choice and choice != section:
        go(choice)


def section_title(title: str, subtitle: str | None = None) -> None:
    st.subheader(title, anchor=False)
    if subtitle:
        st.caption(subtitle)


def footer() -> None:
    st.divider()
    st.caption(
        "Academy é um espaço de curadoria: os materiais pertencem aos seus autores e cada card leva "
        "direto à fonte original. Explicações e notas são texto autoral da curadoria. Nada aqui exige "
        "inscrição, ordem de estudo ou acompanhamento de progresso."
    )
