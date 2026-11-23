"""Área administrativa: detectar URL, extrair metadados, curar, revisar e publicar."""
from __future__ import annotations

import json
from typing import Optional

import streamlit as st

from components.layout import go, section_title
from services.auth import current_identity, require_admin
from services.catalog import Catalog
from services.curator import CuratedDraft, curate
from services.ingest import analyze_url, detect
from services.ingest.base import Extraction
from services.repository import RepoError, get_repository

STATE_EX = "admin_extraction"
STATE_DRAFT = "admin_draft"
STATE_RESULT = "admin_curation"
STATE_RID = "admin_record_id"


def _lines(text: str) -> list[str]:
    return [x.strip() for x in (text or "").splitlines() if x.strip()]


def _csv(text: str) -> list[str]:
    return [x.strip().lower() for x in (text or "").replace(";", ",").split(",") if x.strip()]


def _default_draft(cat: Catalog, extraction: Extraction) -> CuratedDraft:
    c = curate(extraction)
    st.session_state[STATE_RESULT] = {"status": c.status, "source": c.source, "warnings": c.warnings, "raw_text": c.raw_text}
    return c.draft


def _save_form(cat: Catalog, extraction: Extraction) -> tuple[CuratedDraft, list[str]]:
    draft = CuratedDraft(
        title=st.session_state["f_title"],
        provider=st.session_state["f_provider"],
        resource_type=st.session_state["f_type"],
        short_description_pt=st.session_state["f_short"],
        detailed_description_pt=st.session_state["f_detailed"],
        why_it_matters=st.session_state["f_why"],
        target_audience=_lines(st.session_state["f_audience"]),
        difficulty=st.session_state["f_difficulty"],
        categories=st.session_state["f_categories"],
        areas=st.session_state["f_areas"],
        editorial_collections=st.session_state["f_collections"],
        tags=_csv(st.session_state["f_tags"]),
        practical_use_cases=_lines(st.session_state["f_use_cases"]),
        language=st.session_state["f_lang"],
        source_url=extraction.canonical_url,
        metadata_confidence=float(st.session_state["f_confidence"]),
        missing_information=_lines(st.session_state["f_missing"]),
        plain_language_summary_pt=st.session_state["f_plain"],
        technical_summary_pt=st.session_state["f_technical"],
        learning_outcomes=_lines(st.session_state["f_outcomes"]),
        study_guide=_lines(st.session_state["f_study_guide"]),
        related_search_terms=_csv(st.session_state["f_related_terms"]),
        featured=bool(st.session_state["f_featured"]),
    )
    warnings = st.session_state.get(STATE_RESULT, {}).get("warnings", [])
    return draft, warnings


def _status_badge(repo_warning: Optional[str], ident) -> None:
    cols = st.columns([2, 2, 4])
    cols[0].metric("Identidade", ident.email or "anônima")
    cols[1].metric("Perfil", "admin" if ident.is_admin else "visitante")
    if repo_warning:
        cols[2].warning(repo_warning)


def _show_extraction(ex: Extraction) -> None:
    with st.expander("Preview da extração", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", ex.status)
        c2.metric("Tipo", ex.kind)
        c3.metric("Filhos", len(ex.children))
        st.write({
            "title": ex.title, "provider": ex.provider, "author": ex.author, "language": ex.language,
            "canonical_url": ex.canonical_url, "facts": ex.facts,
        })
        if ex.description:
            st.caption(ex.description)
        if ex.children:
            st.write([{"title": c.title, "kind": c.kind, "meta": c.meta} for c in ex.children[:12]])
        if ex.missing:
            st.warning("Faltando: " + ", ".join(ex.missing))
        if ex.warnings:
            st.info(" | ".join(ex.warnings))


def _editor(cat: Catalog, extraction: Extraction) -> None:
    seed = st.session_state.get(STATE_DRAFT) or _default_draft(cat, extraction).model_dump()
    cols = st.columns([2, 1, 1, 1])
    cols[0].text_input("Título", value=seed.get("title", ""), key="f_title")
    cols[1].text_input("Provider", value=seed.get("provider", extraction.provider), key="f_provider")
    cols[2].selectbox("Tipo", options=["github", "course", "video", "playlist", "documentation", "tool", "collection", "roadmap", "article"],
                      index=["github", "course", "video", "playlist", "documentation", "tool", "collection", "roadmap", "article"].index(seed.get("resource_type", "tool")), key="f_type")
    cols[3].selectbox("Idioma", options=["pt", "en", "multi"], index=["pt", "en", "multi"].index(seed.get("language", "en")), key="f_lang")
    cols = st.columns([1, 1, 1])
    cols[0].selectbox("Dificuldade", options=["beginner", "intermediate", "advanced"],
                      index=["beginner", "intermediate", "advanced"].index(seed.get("difficulty", "intermediate")), key="f_difficulty")
    cols[1].number_input("Confiança", min_value=0.0, max_value=1.0, value=float(seed.get("metadata_confidence", 0.6)), step=0.05, key="f_confidence")
    cols[2].checkbox("Featured na Home", value=bool(seed.get("featured")), key="f_featured")
    st.multiselect("Áreas", options=list(cat.areas), default=[x for x in seed.get("areas", []) if x in cat.areas], key="f_areas")
    st.multiselect("Categorias", options=list(cat.categories), default=[x for x in seed.get("categories", []) if x in cat.categories], key="f_categories")
    st.multiselect("Coleções editoriais", options=list(cat.collections), default=[x for x in seed.get("editorial_collections", []) if x in cat.collections], key="f_collections")
    st.text_input("Tags (csv)", value=", ".join(seed.get("tags", [])), key="f_tags")
    st.text_area("Card / descrição curta", value=seed.get("short_description_pt", ""), height=80, key="f_short")
    st.text_area("Blurb / descrição detalhada", value=seed.get("detailed_description_pt", ""), height=100, key="f_detailed")
    st.text_area("Por que importa", value=seed.get("why_it_matters", ""), height=100, key="f_why")
    st.text_area("Explicação em linguagem simples", value=seed.get("plain_language_summary_pt", ""), height=130, key="f_plain")
    st.text_area("Explicação técnica", value=seed.get("technical_summary_pt", ""), height=150, key="f_technical")
    st.text_area("Público-alvo (1 por linha)", value="\n".join(seed.get("target_audience", [])), height=90, key="f_audience")
    st.text_area("Aplicações práticas (1 por linha)", value="\n".join(seed.get("practical_use_cases", [])), height=90, key="f_use_cases")
    st.text_area("Learning outcomes (1 por linha)", value="\n".join(seed.get("learning_outcomes", [])), height=90, key="f_outcomes")
    st.text_area("Study guide (1 por linha)", value="\n".join(seed.get("study_guide", [])), height=90, key="f_study_guide")
    st.text_area("Missing information (1 por linha)", value="\n".join(seed.get("missing_information", [])), height=80, key="f_missing")
    st.text_input("Search terms relacionados (csv)", value=", ".join(seed.get("related_search_terms", [])), key="f_related_terms")


def _list_records(repo) -> None:
    with st.expander("Rascunhos e publicados", expanded=False):
        try:
            rows = repo.list_resources()
        except RepoError as exc:
            st.warning(str(exc))
            return
        if not rows:
            st.caption("Nenhum registro persistido ainda.")
            return
        st.dataframe([
            {"id": r.id, "status": r.status, "title": r.title, "canonical_url": r.canonical_url,
             "updated_at": r.updated_at, "published_at": r.published_at}
            for r in rows
        ], use_container_width=True, hide_index=True)


def render(cat: Catalog) -> None:
    ident = current_identity()
    repo = get_repository()
    section_title("Admin · Add Resource", "Detecção, curadoria e publicação sem editar YAML.", eyebrow="Operação")
    _status_badge(getattr(repo, "warning", None), ident)
    if not ident.is_admin:
        st.info("Leitura do catálogo continua aberta. Publicação e edição só aparecem para administradores autorizados.")
        return

    with st.form("admin-add-resource", clear_on_submit=False):
        url = st.text_input("URL da fonte", value=st.query_params.get("url", ""), placeholder="https://...")
        submitted = st.form_submit_button("Analisar URL", type="primary")
    if submitted and url.strip():
        ex = analyze_url(url.strip())
        st.session_state[STATE_EX] = ex.to_dict()
        st.session_state.pop(STATE_DRAFT, None)
        st.session_state.pop(STATE_RID, None)
        if ex.status != "failed":
            st.session_state[STATE_DRAFT] = _default_draft(cat, ex).model_dump()

    ex_data = st.session_state.get(STATE_EX)
    if not ex_data:
        _list_records(repo)
        return
    extraction = Extraction(**ex_data)
    duplicates = []
    try:
        duplicates = repo.find_duplicates(extraction.canonical_url)
    except Exception:
        duplicates = []
    _show_extraction(extraction)
    if extraction.status == "failed":
        st.error(extraction.error or "A extração falhou.")
        _list_records(repo)
        return
    if duplicates:
        st.warning("URL já cadastrada: " + ", ".join(f"{r.id} ({r.status})" for r in duplicates))

    _editor(cat, extraction)
    c1, c2 = st.columns(2)
    if c1.button("Salvar draft", type="secondary"):
        ident = require_admin()
        draft, _ = _save_form(cat, extraction)
        rid = st.session_state.get(STATE_RID)
        if rid:
            repo.update_resource(rid, draft, updated_by=ident.email)
        else:
            rid = repo.create_resource(draft, extraction, created_by=ident.email, status="draft")
            st.session_state[STATE_RID] = rid
        st.session_state[STATE_DRAFT] = draft.model_dump()
        st.cache_resource.clear()
        st.success(f"Draft salvo: {rid}")
    if c2.button("Publicar", type="primary"):
        ident = require_admin()
        draft, warnings = _save_form(cat, extraction)
        rid = st.session_state.get(STATE_RID)
        if rid:
            repo.update_resource(rid, draft, updated_by=ident.email)
        else:
            rid = repo.create_resource(draft, extraction, created_by=ident.email, status="draft")
        repo.publish_resource(rid, published_by=ident.email)
        st.session_state[STATE_RID] = rid
        st.session_state[STATE_DRAFT] = draft.model_dump()
        st.cache_resource.clear()
        if warnings:
            st.warning("Publicado com revisão recomendada: " + " | ".join(warnings))
        st.success(f"Publicado: {rid}")
        if st.button("Abrir recurso publicado"):
            go("resource", resource=rid)

    _list_records(repo)
