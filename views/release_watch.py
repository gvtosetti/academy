"""Admin · Databricks Release Watch: fila editorial das novidades oficiais do Azure Databricks.

Nada e publicado automaticamente: cada candidato precisa de Approve. Acoes: Approve, Edit,
Dismiss, Mark as duplicate, Open official source. Todo texto externo e escapado.
"""
from __future__ import annotations

import streamlit as st

from components.layout import go, section_title
from services.auth import current_identity, require_admin
from services.catalog import Catalog
from services.release_watch import publish
from services.release_watch.classify import AREA_BY_ID, AREAS
from services.release_watch.parser import CHANGE_LABEL, STATUS_LABEL
from services.release_watch.store import StoreError, get_store

REVIEW_LABEL = {"pending": "Pendente", "approved": "Aprovado", "dismissed": "Descartado", "duplicate": "Duplicata"}
REL_LABEL = {"high": "Alta", "medium": "Média", "low": "Baixa"}
PAGE_SIZE = 25


def _refresh() -> None:
    st.cache_resource.clear()
    st.rerun()


def _run_panel(store) -> None:
    runs = store.runs(20)
    last = runs[0] if runs else None
    c1, c2, c3 = st.columns([3, 2, 2], vertical_alignment="bottom")
    if last:
        icon = {"ok": "✅", "partial": "⚠️", "failed": "❌"}.get(last.get("status"), "•")
        c1.markdown(f"**Última verificação:** {icon} {last.get('finished_at') or last.get('started_at')} UTC · "
                    f"modo `{last.get('mode')}` → {', '.join(last.get('effective_modes') or [])} · "
                    f"{len(last.get('sources') or [])} fontes")
    else:
        c1.info("Nenhuma execução registrada ainda.")
    mode = c2.selectbox("Modo", ["auto", "weekly", "monthly", "revalidate"], key="rw-mode",
                        help="auto: mês corrente; na 1ª execução do mês também consolida e revalida o mês anterior.")
    if c3.button("Executar agora", icon=":material/play_arrow:", type="primary", key="rw-run"):
        ident = require_admin()
        from services.config import setting
        job_id = setting("RELEASE_WATCH_JOB_ID")
        if job_id:  # dispara o Lakeflow Job (não depende desta sessão continuar aberta)
            try:
                from databricks.sdk import WorkspaceClient
                run = WorkspaceClient().jobs.run_now(job_id=int(job_id), job_parameters={"mode": mode, "triggered_by": ident.email or "admin"})
                st.success(f"Job disparado (run {run.run_id}). Os candidatos aparecem quando a execução terminar.")
            except Exception as exc:
                st.error(f"Falha ao disparar o job: {type(exc).__name__}")
        else:
            from services.release_watch.runner import run as rw_run
            with st.spinner("Consultando fontes oficiais…"):
                rep = rw_run(mode, store=store, triggered_by=ident.email or "admin")
            st.success(f"Execução {rep['status']}: {rep['stats']}")
            _refresh()
    if runs:
        with st.expander("Execuções e fontes consultadas", expanded=False):
            st.dataframe([{"início (UTC)": r.get("started_at"), "modo": r.get("mode"), "efetivo": ", ".join(r.get("effective_modes") or []),
                           "status": r.get("status"), "por": r.get("triggered_by"), "stats": str(r.get("stats")),
                           "erros": len(r.get("errors") or [])} for r in runs], hide_index=True, width="stretch")
            if last:
                st.caption("Fontes da última execução")
                st.dataframe(last.get("sources") or [], hide_index=True, width="stretch")
                for e in last.get("errors") or []:
                    st.caption(f"⚠️ {e}")
                if last.get("monthly_summary"):
                    st.caption("Revisão consolidada mensal")
                    st.json(last["monthly_summary"], expanded=False)


def _filters(cands: list[dict]) -> list[dict]:
    periods = sorted({c["period"] for c in cands}, reverse=True)
    f1, f2, f3, f4, f5 = st.columns(5)
    per = f1.selectbox("Mês", ["Todos"] + periods, key="rw-f-period")
    area = f2.selectbox("Área", ["Todas"] + [a.id for a in AREAS], key="rw-f-area",
                        format_func=lambda a: AREA_BY_ID[a].label if a in AREA_BY_ID else a)
    rel = f3.selectbox("Relevância", ["Todas", "high", "medium", "low"], key="rw-f-rel", format_func=lambda x: REL_LABEL.get(x, x))
    rev = f4.selectbox("Revisão", ["pending", "approved", "dismissed", "duplicate", "Todas"], key="rw-f-rev",
                       format_func=lambda x: REVIEW_LABEL.get(x, x))
    stt = f5.selectbox("Status", ["Todos"] + list(STATUS_LABEL), key="rw-f-status", format_func=lambda x: STATUS_LABEL.get(x, x))
    out = [c for c in cands
           if (per == "Todos" or c["period"] == per) and (area == "Todas" or area in (c.get("areas") or []))
           and (rel == "Todas" or c.get("relevance_label") == rel) and (rev == "Todas" or c["review_status"] == rev)
           and (stt == "Todos" or c["status"] == stt)]
    out.sort(key=lambda c: (c.get("changed_since_review") or c.get("update_of_approved"), c.get("relevance") or 0,
                            c.get("announced_on") or ""), reverse=True)
    return out


def _candidate(c: dict, cat: Catalog, store, all_keys: list[str], ident) -> None:
    k = c["key"]
    v = publish.effective(c)
    with st.container(border=True, key=f"rw-{k}"):
        flags = []
        if c.get("update_of_approved"):
            flags.append("🔄 mudou após aprovação")
        elif c.get("changed_since_review"):
            flags.append("🔄 alterado desde a revisão")
        if len(c.get("history") or []) > 1:
            flags.append(f"{len(c['history'])} anúncios")
        if c.get("injection_flag"):
            flags.append("🛡️ texto suspeito neutralizado")
        st.markdown(f"**{v['title']}**")
        st.caption(" · ".join(x for x in [
            c.get("announced_on") or "data não informada", STATUS_LABEL.get(c["status"], c["status"]),
            CHANGE_LABEL.get(c.get("change_type"), c.get("change_type") or ""),
            f"relevância {REL_LABEL.get(c.get('relevance_label'), '?')}",
            ", ".join(AREA_BY_ID[a].label for a in c.get("areas") or [] if a in AREA_BY_ID),
            REVIEW_LABEL.get(c["review_status"], c["review_status"]), *flags] if x))
        st.text(v["description"][:600] + ("…" if len(v["description"]) > 600 else ""))
        with st.expander("Detalhes, histórico e evidências"):
            if c.get("limitations"):
                st.markdown("**Disponibilidade e limitações**")
                for x in c["limitations"]:
                    st.text(f"• {x}")
            st.markdown("**Histórico de status**")
            st.dataframe([{"data": h.get("announced_on"), "status": STATUS_LABEL.get(h["status"], h["status"]),
                           "tipo": CHANGE_LABEL.get(h.get("change_type"), ""), "fonte": h["url"]} for h in c.get("history") or []],
                         hide_index=True, width="stretch")
            if c.get("changes"):
                st.markdown("**Alterações desde consultas anteriores**")
                for ch in c["changes"][-5:]:
                    st.text(f"{ch['at']}: {ch['summary']}")
            st.markdown("**Evidências oficiais**")
            for e in c.get("evidence") or []:
                st.text(f"[{e['source']}] {e.get('title', '')} — {e['url']}")
            rel = [r for r in c.get("related_resources") or [] if r in cat.resources]
            if rel:
                st.markdown("**Recursos existentes relacionados:** " + ", ".join(cat.resources[r].title for r in rel))
            if c.get("use_cases"):
                st.caption("Casos de uso: " + ", ".join(cat.taxonomy.use_case(u).label if cat.taxonomy.use_case(u) else u
                                                       for u in c["use_cases"]))
        a1, a2, a3, a4, a5 = st.columns(5)
        a1.link_button("Open official source", c["url"], icon=":material/open_in_new:")
        editing = a2.toggle("Edit / Approve", key=f"rw-edit-{k}")
        if a3.button("Dismiss", key=f"rw-dis-{k}", icon=":material/block:"):
            publish.dismiss(store, k, by=require_admin().email)
            _refresh()
        if a4.button("Smart Import", key=f"rw-imp-{k}", icon=":material/input:",
                     help="Abre a URL oficial no Smart Content Import para curadoria completa."):
            go("admin", url=(c.get("links") or [{"url": c["url"]}])[0]["url"])
        if c["review_status"] in ("dismissed", "duplicate") and a5.button("Reabrir", key=f"rw-reo-{k}"):
            publish.reopen(store, k, by=require_admin().email)
            _refresh()
        if c["review_status"] not in ("duplicate",):
            with a5.popover("Mark as duplicate"):
                opts = [x for x in all_keys if x != k] + [f"resource:{r}" for r in cat.resources]
                of = st.selectbox("Duplicata de", opts, key=f"rw-dupsel-{k}", index=None, placeholder="Candidato ou recurso")
                if st.button("Confirmar", key=f"rw-dup-{k}", disabled=not of):
                    publish.mark_duplicate(store, k, of, by=require_admin().email)
                    _refresh()
        if editing:
            _editor(c, v, cat, store)


def _editor(c: dict, v: dict, cat: Catalog, store) -> None:
    k = c["key"]
    subs = [(s.id, f"{sec.title} › {s.title}") for sec in cat.taxonomy.sections for s in sec.subcategories]
    sub_ids = [s for s, _ in subs]
    targets = [""] + sorted(cat.resources, key=lambda r: cat.resources[r].title)
    with st.form(f"rw-form-{k}", border=False):
        title = st.text_input("Título", v["title"], max_chars=160)
        tagline = st.text_input("Tagline (≤125)", v["tagline"], max_chars=125)
        desc = st.text_area("Descrição técnica", v["description"], height=140)
        c1, c2 = st.columns(2)
        sub = c1.selectbox("Seção › subcategoria", sub_ids, index=sub_ids.index(v["subcategory"]) if v["subcategory"] in sub_ids else 0,
                           format_func=dict(subs).get)
        areas = c2.multiselect("Áreas da Library", list(cat.areas), default=[a for a in v["library_areas"] if a in cat.areas],
                               format_func=lambda a: cat.areas[a].name)
        suggested = next((r for r in c.get("related_resources") or [] if r in cat.resources), None)
        tgt = st.selectbox("Atualizar recurso existente (vazio = criar novo recurso)", targets,
                           index=targets.index(v["target_resource"]) if v["target_resource"] in targets else 0,
                           format_func=lambda r: "— criar novo recurso —" if not r else cat.resources[r].title,
                           help=f"Sugestão: {cat.resources[suggested].title}" if suggested else None)
        note = st.checkbox("Gerar nota técnica relacionada (Quick Knowledge)", value=bool(v["create_note"]))
        b1, b2 = st.columns(2)
        save = b1.form_submit_button("Salvar edição")
        ok = b2.form_submit_button("Approve", type="primary")
    edits = {"title": title.strip(), "tagline": tagline.strip(), "description": desc.strip(), "subcategory": sub,
             "library_areas": areas or v["library_areas"], "target_resource": tgt or None, "create_note": note}
    try:
        if save:
            publish.save_edits(store, k, edits, by=require_admin().email)
            st.success("Edição salva (ainda não publicada).")
            _refresh()
        if ok:
            publish.approve(store, k, by=require_admin().email, catalog=cat, edits=edits)
            st.success("Aprovado e publicado.")
            _refresh()
    except (StoreError, ValueError) as exc:
        st.error(str(exc)[:500])


def render(cat: Catalog) -> None:
    ident = current_identity()
    section_title("Databricks Release Watch",
                  "Novidades oficiais do Azure Databricks para curadoria. Nada é publicado sem aprovação editorial.",
                  eyebrow="Operação")
    if not ident.is_admin:
        st.info("Esta área é restrita a administradores.")
        return
    store = get_store()
    if not store.enabled:
        st.warning(store.warning)
        return
    if not store.durable:
        st.caption(f"⚠️ {store.warning}")
    if st.button("Voltar ao Admin", icon=":material/arrow_back:", type="tertiary", key="rw-back"):
        go("admin")
    try:
        _run_panel(store)
        cands = store.list()
    except StoreError as exc:
        st.error(str(exc))
        return
    if not cands:
        st.caption("Sem candidatos. Execute uma verificação.")
        return
    shown = _filters(cands)
    st.caption(f"{len(shown)} de {len(cands)} candidatos")
    page = st.number_input("Página", 1, max(1, (len(shown) - 1) // PAGE_SIZE + 1), 1, key="rw-page") if len(shown) > PAGE_SIZE else 1
    keys = [c["key"] for c in cands]
    for c in shown[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]:
        _candidate(c, cat, store, keys, ident)
