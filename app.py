"""Academy — plataforma de aprendizado em IA (Streamlit).

Execute com:  streamlit run app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(page_title="Academy", page_icon=":material/school:", layout="wide")

from components import nav  # noqa: E402
from components.styles import inject_css  # noqa: E402
from services.catalog import CatalogError, load_catalog  # noqa: E402
from services.progress import get_repository  # noqa: E402
from views import (  # noqa: E402
    about, explore, github_explorer, home, knowledge, my_learning, paths, resource_detail, videos,
)

VIEWS = {
    "home": home, "paths": paths, "explore": explore, "resource": resource_detail,
    "github": github_explorer, "videos": videos, "knowledge": knowledge,
    "my_learning": my_learning, "about": about,
}


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
    repo = get_repository()
    nav.sidebar()
    VIEWS[nav.current_page()].render(cat, repo)


main()
