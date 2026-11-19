"""Apresentacao curta de um recurso ("Saiba mais").

Conteudo principal limitado a: O que e? Por que e util? Para quem faz sentido?
O que vou encontrar? Acessar material. Detalhes tecnicos ficam em expansores opcionais.
"""
from __future__ import annotations

import streamlit as st

from components.cards import LANG_LABEL, LEVEL_LABEL, area_label, resource_grid, type_label
from components.layout import go, param
from services import github_api
from services.catalog import Catalog
from services.models import Resource
from services.recommend import recommend
from utils.safe import is_safe_url

STATUS_NOTE = {
    "partial": "Parte das informações ainda está em verificação na fonte original.",
    "pending": "Informações em validação: confira os detalhes na fonte original.",
}


def _bullets(items: list[str], limit: int | None = None) -> None:
    items = items[:limit] if limit else items
    if items:
        st.markdown("\n".join(f"- {x}" for x in items))


def _for_whom(r: Resource) -> None:
    _bullets(r.audience, 4)
    req, helpful = r.prerequisites.required, r.prerequisites.helpful
    if r.difficulty == "advanced" or req:
        if req:
            st.caption("Para aproveitar bem: " + "; ".join(req))
        if helpful:
            st.caption("Ajuda ter: " + "; ".join(helpful))
    elif helpful:
        st.caption("Ajuda ter (não obrigatório): " + "; ".join(helpful))


def _what_you_find(r: Resource, cat: Catalog) -> None:
    v = r.verified
    if v.video_count:
        st.caption(f":material/smart_display: {v.video_count} vídeos" + (f" ({v.video_count_note})" if v.video_count_note else ""))
    kids = cat.children_of(r.id)
    if kids:
        st.caption(f":material/folder_special: {len(kids)} recursos nesta coleção (listados abaixo)")
    _bullets(r.learning_outcomes, 4)


def _live_github(full: str) -> None:
    res = github_api.repo(full)
    if not res.ok:
        msg = "Limite da API do GitHub atingido." if res.rate_limited else "Não foi possível consultar o GitHub agora."
        st.caption(f"{msg} As informações curadas continuam válidas.")
        return
    d = res.data
    c1, c2, c3 = st.columns(3)
    c1.caption(f"Linguagem: **{d.get('language') or '-'}**")
    c2.caption(f"Licença: **{d.get('license') or '-'}**")
    c3.caption(f"Último push: **{(d.get('pushed_at') or '-')[:10]}**")
    if d.get("archived"):
        st.warning("Este repositório está arquivado (somente leitura).")
    st.caption("Dados ao vivo da API pública do GitHub (cache de 6h).")


def render(cat: Catalog) -> None:
    r = cat.resources.get(param("resource") or "")
    if not r:
        st.title("Recurso não encontrado", anchor=False)
        st.write("O link pode estar desatualizado. O conteúdo continua disponível na Library.")
        if st.button("Ir para a Library", icon=":material/grid_view:"):
            go("library")
        return

    if st.button("Library", icon=":material/arrow_back:", type="tertiary", key="back"):
        go("library")
    meta = [area_label(cat, a) for a in r.areas[:3]]
    st.caption("  ·  ".join(meta + [type_label(r), LEVEL_LABEL[r.difficulty], LANG_LABEL[r.language], r.provider]))
    st.title(r.title, anchor=False)
    with st.container(key="lead"):
        st.markdown(r.blurb)
    st.link_button("Acessar material", r.url, icon=":material/open_in_new:", type="primary")
    if r.metadata_status in STATUS_NOTE:
        st.caption(f":material/info: {STATUS_NOTE[r.metadata_status]}")
    if r.parent and r.parent in cat.resources:
        p = cat.resources[r.parent]
        if st.button(f"Faz parte de: {p.title}", icon=":material/folder_special:", type="tertiary", key="parent"):
            go("resource", resource=p.id)

    st.write("")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("##### O que é?")
        st.write(r.short_description)
        st.markdown("##### Para quem faz sentido?")
        _for_whom(r)
    with right:
        st.markdown("##### Por que é útil?")
        st.write(r.why_it_matters)
        st.markdown("##### O que vou encontrar?")
        _what_you_find(r, cat)

    with st.expander("Explicação detalhada e dicas de uso", icon=":material/menu_book:"):
        st.markdown("**Em linguagem simples**")
        st.write(r.plain_language_explanation)
        st.markdown("**Visão técnica**")
        st.write(r.technical_explanation)
        if r.practical_applications:
            st.markdown("**Aplicações práticas**")
            _bullets(r.practical_applications)
        if r.study_guide:
            st.markdown("**Como aproveitar**")
            _bullets(r.study_guide)
        if r.verified.episodes:
            st.markdown("**Aulas**")
            st.markdown("\n".join(f"{i}. {e}" for i, e in enumerate(r.verified.episodes, 1)))
        if r.github_highlights:
            st.markdown("**Onde olhar no repositório**")
            _bullets([f"`{h.path}` — {h.why}" for h in r.github_highlights])
        links = [ln for ln in r.links if is_safe_url(ln.url)]
        if links:
            st.markdown("**Links da fonte**")
            _bullets([f"[{ln.label}]({ln.url})" for ln in links])
        concepts = [c for c in r.key_concepts if c in cat.notes]
        if concepts:
            st.markdown("**Conceitos explicados em Tips & Insights**")
            cols = st.columns(min(4, len(concepts)))
            for i, cid in enumerate(concepts):
                if cols[i % len(cols)].button(cat.concepts[cid].name, key=f"c-{cid}", type="tertiary"):
                    go("note", note=cid)

    with st.expander("Fonte e verificação", icon=":material/verified:"):
        v = r.verified
        if v.verified_on:
            st.caption(f"Conferido na fonte original em {v.verified_on:%d/%m/%Y}.")
        if v.source_title:
            st.caption(f"Título na fonte: {v.source_title}")
        if v.source_description:
            st.caption(v.source_description)
        if r.metadata_notes:
            st.caption(r.metadata_notes)
        if r.github_repo:
            _live_github(r.github_repo)
        st.caption("Explicações e níveis são texto autoral da curadoria da Academy; o material pertence aos seus autores.")

    kids = cat.children_of(r.id)
    if kids:
        st.subheader("Nesta coleção", anchor=False)
        resource_grid(kids, cat, "kids")
    recs = [x.resource for x in recommend(cat, r.id, k=3) if x.resource not in kids]
    if recs:
        st.subheader("Relacionados", anchor=False)
        resource_grid(recs, cat, "rel")
