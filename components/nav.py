"""Navegacao por query params (?page=...&resource=...) para URLs compartilhaveis."""
from __future__ import annotations

import streamlit as st

# (id, rotulo, icone) — ordem do menu lateral
PAGES: list[tuple[str, str, str]] = [
    ("home", "Início", ":material/home:"),
    ("paths", "Trilhas", ":material/route:"),
    ("explore", "Explorar", ":material/search:"),
    ("github", "GitHub Explorer", ":material/folder_code:"),
    ("videos", "Vídeos e cursos", ":material/smart_display:"),
    ("knowledge", "Base de Conhecimento", ":material/menu_book:"),
    ("my_learning", "Meu aprendizado", ":material/bookmark:"),
    ("about", "Sobre", ":material/info:"),
]
PAGE_IDS = {p[0] for p in PAGES} | {"resource"}


def param(name: str, default: str | None = None) -> str | None:
    v = st.query_params.get(name)
    return v if v else default


def current_page() -> str:
    p = param("page", "home")
    return p if p in PAGE_IDS else "home"


def go(page: str, **params: str) -> None:
    """Troca de pagina mantendo a URL compartilhavel."""
    st.query_params.clear()
    st.query_params["page"] = page
    for k, v in params.items():
        if v:
            st.query_params[k] = str(v)
    st.rerun()


def sidebar() -> None:
    active = current_page()
    with st.sidebar:
        st.markdown("## :material/school: Academy")
        st.caption("Aprenda IA, LLMs e agentes com uma curadoria explicada em português.")
        for pid, label, icon in PAGES:
            if st.button(label, icon=icon, key=f"nav-{pid}",
                         type="primary" if pid == active else "secondary"):
                go(pid)
        st.divider()
        st.caption("Progresso salvo apenas nesta sessão do navegador.")
