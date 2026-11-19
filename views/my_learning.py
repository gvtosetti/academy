"""Progresso do usuario (temporario, por sessao)."""
from __future__ import annotations

import json

import streamlit as st

from components.ui import card_grid
from services.catalog import Catalog


def render(cat: Catalog, repo) -> None:
    st.title("Meu aprendizado")
    if not getattr(repo, "is_persistent", False):
        st.info("Seu progresso fica salvo apenas nesta sessão do navegador e some ao recarregar a página. "
                "Use o botão de exportação abaixo para guardar uma cópia.")
    statuses = {rid: repo.get_status(rid) for rid in cat.resources}
    started = [cat.resources[r] for r, s in statuses.items() if s == "started"]
    completed = [cat.resources[r] for r, s in statuses.items() if s == "completed"]
    saved = [r for r in cat.resources.values() if repo.is_saved(r.id)]
    c1, c2, c3 = st.columns(3)
    c1.metric("Em andamento", len(started))
    c2.metric("Concluídos", len(completed))
    c3.metric("Salvos", len(saved))

    st.header("Trilhas")
    for t in cat.tracks.values():
        done = sum(1 for m in t.modules if repo.is_module_done(t.id, m.id))
        st.progress(done / len(t.modules), text=f"{t.title}: {done}/{len(t.modules)} módulos")

    for title, items, key in [("Em andamento", started, "ml-started"), ("Salvos", saved, "ml-saved"),
                              ("Concluídos", completed, "ml-done")]:
        st.header(title)
        card_grid(items, cat, key=key, statuses=statuses)

    recent = [cat.resources[r] for r in repo.recent_visits(6) if r in cat.resources]
    if recent:
        st.header("Vistos recentemente")
        card_grid(recent, cat, key="ml-recent", statuses=statuses)

    st.download_button("Exportar meu progresso (JSON)", json.dumps(repo.snapshot(), ensure_ascii=False, indent=2, default=str),
                       file_name="academy-progresso.json", mime="application/json", icon=":material/download:")
