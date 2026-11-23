"""Academy — Knowledge & Discovery Hub (Streamlit).

Descobrir -> entender em 30 segundos -> acessar o conteudo original.
Execute com:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Academy · Knowledge & Discovery Hub",
    page_icon=":material/auto_awesome:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from components import layout  # noqa: E402
from components.styles import inject_css  # noqa: E402
from services.catalog import CatalogError, load_catalog  # noqa: E402
from views import admin, discover, library, note, resource, tips  # noqa: E402

VIEWS = {"discover": discover, "library": library, "tips": tips, "resource": resource, "note": note, "admin": admin}


@st.cache_resource(show_spinner=False)
def get_catalog():
    return load_catalog()


def main() -> None:
    inject_css()
    try:
        cat = get_catalog()
    except (CatalogError, ValueError) as exc:
        st.error("Não foi possível carregar o catálogo. Verifique os arquivos em data/.")
        st.code(str(exc)[:2000])
        st.stop()
    page = layout.current_page()
    layout.header(page)
    VIEWS[page].render(cat)
    layout.footer()


main()
