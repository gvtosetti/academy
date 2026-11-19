"""Blocos de UI reutilizaveis (cards, rotulos, metadados).

Nenhuma funcao aqui usa unsafe_allow_html: o texto curado e renderizado como
Markdown/texto padrao do Streamlit.
"""
from __future__ import annotations

import streamlit as st

from components.nav import go
from services.catalog import Catalog
from services.models import Resource
from utils.safe import is_safe_url

DIFFICULTY_LABEL = {"beginner": "Iniciante", "intermediate": "Intermediário", "advanced": "Avançado"}
TYPE_LABEL = {
    "github": "Repositório GitHub", "course": "Curso", "video": "Vídeo", "playlist": "Playlist",
    "documentation": "Documentação", "tool": "Ferramenta", "collection": "Coleção",
}
LANGUAGE_LABEL = {"pt": "Português", "en": "Inglês", "multi": "Multilíngue"}
STATUS_LABEL = {"not_started": "Não iniciado", "started": "Em andamento", "completed": "Concluído"}
METADATA_LABEL = {
    "verified": "Metadados verificados na fonte",
    "partial": "Metadados parcialmente verificados",
    "pending": "Metadados em validação",
}


def meta_line(r: Resource, cat: Catalog) -> str:
    cat_name = cat.categories[r.category].name if r.category in cat.categories else r.category
    parts = [TYPE_LABEL.get(r.type, r.type), DIFFICULTY_LABEL[r.difficulty], LANGUAGE_LABEL[r.language], r.provider, cat_name]
    return " · ".join(parts)


def source_button(r: Resource, key: str, label: str = "Abrir fonte") -> None:
    if is_safe_url(r.url):
        st.link_button(label, r.url, icon=":material/open_in_new:")


def resource_card(r: Resource, cat: Catalog, key: str, status: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{r.title}**")
        st.caption(meta_line(r, cat))
        st.write(r.short_description)
        notes = []
        if r.metadata_status != "verified":
            notes.append(METADATA_LABEL[r.metadata_status])
        if status and status != "not_started":
            notes.append(STATUS_LABEL[status])
        if notes:
            st.caption(" · ".join(notes))
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Ver detalhes", key=f"{key}-open-{r.id}", icon=":material/arrow_forward:"):
                go("resource", resource=r.id)
        with c2:
            source_button(r, key)


def card_grid(resources: list[Resource], cat: Catalog, key: str, cols: int = 3, statuses: dict | None = None) -> None:
    if not resources:
        st.info("Nenhum recurso encontrado.")
        return
    columns = st.columns(cols)
    for i, r in enumerate(resources):
        with columns[i % cols]:
            resource_card(r, cat, key=f"{key}-{i}", status=(statuses or {}).get(r.id))


def bullet_list(items: list[str]) -> None:
    if items:
        st.markdown("\n".join(f"- {x}" for x in items))


def concept_chips(concept_ids: list[str], cat: Catalog, key: str) -> None:
    """Botoes pequenos que levam ao conceito na Base de Conhecimento."""
    ids = [c for c in concept_ids if c in cat.concepts]
    if not ids:
        return
    cols = st.columns(min(len(ids), 4))
    for i, cid in enumerate(ids):
        with cols[i % len(cols)]:
            if st.button(cat.concepts[cid].name, key=f"{key}-c-{cid}", icon=":material/menu_book:"):
                go("knowledge", concept=cid)
