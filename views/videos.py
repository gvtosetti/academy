"""Videos, playlists e cursos."""
from __future__ import annotations

import streamlit as st

from components.nav import go
from components.ui import DIFFICULTY_LABEL, source_button
from services.catalog import Catalog

VIDEO_TYPES = ("playlist", "video", "course")


def render(cat: Catalog, repo) -> None:
    st.title("Vídeos e cursos")
    st.write("Playlists e cursos do catálogo, com a lista de aulas conferida na fonte quando disponível.")
    items = sorted((r for r in cat.resources.values() if r.type in VIDEO_TYPES),
                   key=lambda r: (r.sequence, r.title))
    for r in items:
        v = r.verified
        with st.container(border=True):
            st.markdown(f"### {r.title}")
            info = [r.provider, DIFFICULTY_LABEL[r.difficulty]]
            if v.video_count:
                info.append(f"{v.video_count} vídeos")
            st.caption(" · ".join(info))
            if v.video_count_note:
                st.caption(f"Observação: {v.video_count_note}")
            st.write(r.short_description)
            if r.metadata_status != "verified":
                st.caption(r.metadata_notes or "Metadados em validação.")
            if v.episodes:
                with st.expander(f"Aulas ({len(v.episodes)})"):
                    st.markdown("\n".join(f"{i}. {e}" for i, e in enumerate(v.episodes, 1)))
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Ver detalhes", key=f"vid-{r.id}", icon=":material/arrow_forward:"):
                    go("resource", resource=r.id)
            with c2:
                source_button(r, key=f"vid-{r.id}", label="Assistir na fonte")
