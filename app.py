"""Resource Library — vitrine editorial de ferramentas, cursos e conhecimento (Streamlit).

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
    page_title="Resource Library",
    page_icon=":material/auto_awesome:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from components import layout  # noqa: E402
from components.styles import inject_css  # noqa: E402
from services.catalog import CatalogError, load_catalog  # noqa: E402
from views import admin, discover, library, note, playbook, release_watch, resource, tips, topic  # noqa: E402

VIEWS = {
    "discover": discover, "library": library, "tips": tips,
    "resource": resource, "note": note, "admin": admin,
    "playbook": playbook, "topic": topic, "release-watch": release_watch,
}


def _content_version() -> str:
    """Assinatura do codigo + dados do catalogo.

    `st.cache_resource` so invalida quando o corpo da funcao muda; sem esta chave, um
    redeploy reaproveita o objeto Catalog criado pela versao anterior do codigo
    (ex.: sem o atributo `collections`) e quebra a pagina.
    """
    import hashlib

    h = hashlib.sha1()
    for p in sorted([*ROOT.glob("services/**/*.py"), *ROOT.glob("data/*.yaml")]):
        try:
            h.update(p.as_posix().encode())
            h.update(p.read_bytes())
        except OSError:
            continue
    return h.hexdigest()[:16]


# ttl: recursos publicados por outra instancia/replica aparecem sem reiniciar o app
@st.cache_resource(show_spinner=False, ttl=300, max_entries=2)
def get_catalog(version: str):
    return load_catalog()


def main() -> None:
    inject_css()
    try:
        cat = get_catalog(_content_version())
    except (CatalogError, ValueError) as exc:
        st.error("Não foi possível carregar o catálogo. Verifique os arquivos em data/.")
        st.code(str(exc)[:2000])
        st.stop()
    page = layout.current_page()
    layout.header(page)
    VIEWS[page].render(cat)
    layout.footer()


main()
