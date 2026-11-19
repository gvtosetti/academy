"""Trilhas de aprendizado."""
from __future__ import annotations

import streamlit as st

from components.nav import go, param
from components.ui import DIFFICULTY_LABEL, bullet_list, card_grid, concept_chips
from services.catalog import Catalog


def track_progress(track, repo) -> tuple[int, int]:
    done = sum(1 for m in track.modules if repo.is_module_done(track.id, m.id))
    return done, len(track.modules)


def render(cat: Catalog, repo) -> None:
    st.title("Trilhas de aprendizado")
    ids = list(cat.tracks)
    sel = param("track")
    if sel not in cat.tracks:
        sel = None
    labels = {t.id: t.title for t in cat.tracks.values()}
    choice = st.selectbox("Escolha uma trilha", [""] + ids, index=(ids.index(sel) + 1) if sel else 0,
                          format_func=lambda x: labels.get(x, "Todas as trilhas"))
    if choice != (sel or ""):
        go("paths", track=choice)

    if not sel:
        for t in cat.tracks.values():
            done, total = track_progress(t, repo)
            with st.container(border=True):
                st.markdown(f"### {t.title}")
                st.caption(f"{DIFFICULTY_LABEL.get(t.difficulty, t.difficulty)} · {total} módulos · {done}/{total} concluídos")
                st.write(t.objective)
                if st.button("Abrir trilha", key=f"paths-open-{t.id}", icon=t.icon):
                    go("paths", track=t.id)
        return

    t = cat.tracks[sel]
    st.header(t.title)
    st.write(t.objective)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Para quem**")
        bullet_list(t.audience)
    with c2:
        st.markdown("**Pré-requisitos**")
        bullet_list(t.prerequisites or ["Nenhum"])
    done, total = track_progress(t, repo)
    st.progress(done / total if total else 0.0, text=f"{done} de {total} módulos concluídos (nesta sessão)")

    for i, m in enumerate(t.modules, 1):
        is_done = repo.is_module_done(t.id, m.id)
        with st.expander(f"Módulo {i} — {m.title}" + (" (concluído)" if is_done else ""), expanded=(i == 1)):
            st.write(m.summary)
            st.markdown("**Você vai aprender**")
            bullet_list(m.outcomes)
            if m.resources:
                st.markdown("**Recursos**")
                card_grid([cat.resources[x] for x in m.resources], cat, key=f"paths-{t.id}-{m.id}", cols=2)
            if m.concepts:
                st.markdown("**Conceitos do módulo**")
                concept_chips(m.concepts, cat, key=f"paths-{t.id}-{m.id}")
            if m.practice:
                st.markdown("**Prática sugerida**")
                bullet_list(m.practice)
            if m.recommended_topics:
                st.info("Tópicos recomendados ainda sem fonte curada na Academy:")
                bullet_list(m.recommended_topics)
            new = st.checkbox("Marcar módulo como concluído", value=is_done, key=f"done-{t.id}-{m.id}")
            if new != is_done:
                repo.set_module_done(t.id, m.id, new)
                st.rerun()
