"""Pagina de detalhe de um recurso."""
from __future__ import annotations

import streamlit as st

from components.nav import go, param
from components.ui import METADATA_LABEL, STATUS_LABEL, bullet_list, card_grid, concept_chips, meta_line, source_button
from services import github_api
from services.catalog import Catalog
from services.recommend import recommend
from utils.safe import is_safe_url


def _live_github(full: str) -> None:
    """Metadados ao vivo do GitHub; falhas nunca quebram a pagina."""
    if "/" not in full:
        return
    res = github_api.repo(full)
    if not res.ok:
        msg = "Limite da API do GitHub atingido; tente mais tarde." if res.rate_limited else "Não foi possível consultar o GitHub agora."
        st.caption(f"{msg} As informações curadas acima continuam válidas.")
        return
    d = res.data
    c1, c2, c3 = st.columns(3)
    c1.metric("Linguagem", d.get("language") or "-")
    c2.metric("Licença", d.get("license") or "-")
    c3.metric("Último push", (d.get("pushed_at") or "-")[:10])
    if d.get("archived"):
        st.warning("Este repositório está arquivado (somente leitura).")
    st.caption("Dados ao vivo da API pública do GitHub (cache de 6h).")


def render(cat: Catalog, repo) -> None:
    rid = param("resource")
    r = cat.resources.get(rid or "")
    if not r:
        st.title("Recurso não encontrado")
        st.write("O link pode estar desatualizado.")
        if st.button("Explorar o catálogo", icon=":material/search:"):
            go("explore")
        return
    repo.record_visit(r.id)

    if r.parent and r.parent in cat.resources:
        if st.button(f"Parte de: {cat.resources[r.parent].title}", icon=":material/arrow_upward:", key="parent"):
            go("resource", resource=r.parent)
    st.title(r.title)
    st.caption(meta_line(r, cat))
    st.write(r.short_description)
    if r.metadata_status != "verified":
        st.warning(f"{METADATA_LABEL[r.metadata_status]}. {r.metadata_notes or ''}")

    c1, c2, c3 = st.columns([2, 1, 1])
    status = repo.get_status(r.id)
    opts = list(STATUS_LABEL)
    new = c1.selectbox("Meu status", opts, index=opts.index(status), format_func=STATUS_LABEL.get, key=f"status-{r.id}")
    if new != status:
        repo.set_status(r.id, new)
        st.rerun()
    saved = repo.is_saved(r.id)
    with c2:
        if st.button("Remover dos salvos" if saved else "Salvar", icon=":material/bookmark:", key=f"save-{r.id}"):
            repo.toggle_saved(r.id)
            st.rerun()
    with c3:
        source_button(r, key="detail")

    tabs = st.tabs(["Visão geral", "Técnico", "Como estudar", "Conteúdo", "Fonte e verificação"])
    with tabs[0]:
        st.markdown("#### Em linguagem simples")
        st.write(r.plain_language_explanation)
        st.markdown("#### Por que importa")
        st.write(r.why_it_matters)
        st.markdown("#### O que você vai aprender")
        bullet_list(r.learning_outcomes)
        st.markdown("#### Para quem")
        bullet_list(r.audience)
        st.markdown("#### Pré-requisitos")
        st.markdown("**Obrigatórios**")
        bullet_list(r.prerequisites.required or ["Nenhum"])
        if r.prerequisites.helpful:
            st.markdown("**Úteis, mas não obrigatórios**")
            bullet_list(r.prerequisites.helpful)
    with tabs[1]:
        st.write(r.technical_explanation)
        if r.key_concepts:
            st.markdown("#### Conceitos-chave")
            concept_chips(r.key_concepts, cat, key=f"detail-{r.id}")
        if r.practical_applications:
            st.markdown("#### Aplicações práticas")
            bullet_list(r.practical_applications)
    with tabs[2]:
        if r.study_guide:
            st.markdown("\n".join(f"{i}. {s}" for i, s in enumerate(r.study_guide, 1)))
        tracks = cat.tracks_for_resource(r.id)
        if tracks:
            st.markdown("#### Faz parte das trilhas")
            for t in tracks:
                if st.button(t.title, key=f"detail-track-{t.id}", icon=t.icon):
                    go("paths", track=t.id)
    with tabs[3]:
        kids = cat.children_of(r.id)
        if kids:
            st.markdown("#### Itens desta coleção")
            card_grid(kids, cat, key=f"kids-{r.id}", cols=2)
        if r.verified.episodes:
            st.markdown("#### Aulas / episódios (conforme a fonte)")
            bullet_list(r.verified.episodes)
        if r.github_highlights:
            st.markdown("#### Onde olhar no repositório")
            bullet_list([f"`{h.path}` — {h.why}" for h in r.github_highlights])
        for ln in r.links:
            if is_safe_url(ln.url):
                st.link_button(ln.label, ln.url, icon=":material/open_in_new:")
        if r.github_repo:
            st.markdown("#### GitHub ao vivo")
            _live_github(r.github_repo)
        if not (kids or r.verified.episodes or r.github_highlights or r.links or r.github_repo):
            st.caption("Sem detalhamento de conteúdo além do link da fonte.")
    with tabs[4]:
        v = r.verified
        st.write(METADATA_LABEL[r.metadata_status])
        rows = {
            "Verificado em": v.verified_on, "Título na fonte": v.source_title, "Licença": v.license,
            "Linguagem principal": v.primary_language, "Vídeos": v.video_count, "Observação": v.video_count_note,
            "Descrição na fonte": v.source_description, "Duração": v.duration,
        }
        bullet_list([f"**{k}:** {val}" for k, val in rows.items() if val not in (None, "")])
        if r.metadata_notes:
            st.caption(r.metadata_notes)
        st.caption("Explicações, nível e guias de estudo são texto autoral da curadoria da Academy.")

    recs = recommend(cat, r.id, k=4)
    if recs:
        st.header("Próximos passos")
        cols = st.columns(2)
        for i, rec in enumerate(recs):
            with cols[i % 2], st.container(border=True):
                st.markdown(f"**{rec.resource.title}**")
                st.caption(" · ".join(rec.reasons))
                if st.button("Ver detalhes", key=f"rec-{rec.resource.id}", icon=":material/arrow_forward:"):
                    go("resource", resource=rec.resource.id)
