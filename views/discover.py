"""Discover: vitrine editorial compacta (não é o catálogo completo — isso é a Library).

Ordem: hero com busca -> chips de área -> novidades Databricks (máx. 3, só aprovadas) ->
1. Make Your Work Easier: subcategorias como cards-resumo (clique abre a Library filtrada)
2. Tools & Resources: até 2 itens por grupo
3. Deep Dives & Courses: até 2 itens por grupo
4. Quick Knowledge: 6 coleções em destaque (4 Databricks fixas + as 2 seguintes na ordem do arquivo)

Com um chip ativo, cada seção mostra só itens da área e some se ficar vazia.
"""
from __future__ import annotations

import streamlit as st

from components.cards import resource_card, topic_card
from components.layout import go, param, section_title
from services.catalog import Catalog
from services.models import Resource
from utils.safe import esc

HERO_TITLE = "Resource Library"
ALL = "all"
ITEMS_PER_GROUP = 2   # recursos por subcategoria na Home
SECTION_MAX = 6       # teto de recursos por seção na Home
QK_FEATURED = 6       # coleções em destaque no Quick Knowledge
RELEASES_MAX = 3      # novidades Databricks aprovadas na Home
QK_PRIORITY = (
    "databricks-fundamentals", "databricks-jobs-workflows", "unity-catalog-governance",
    "mlflow-experiment-tracking",
)
STATUS_LABEL = {"ga": "GA", "public_preview": "Public Preview", "private_preview": "Private Preview",
                "beta": "Beta", "retired": "Retired", "deprecated": "Deprecated"}


def _hero() -> None:
    with st.container(key="hero"):
        st.title(HERO_TITLE, anchor=False)
        with st.form("global-search", border=False, clear_on_submit=False):
            c1, c2 = st.columns([6, 1], vertical_alignment="bottom", gap="small")
            q = c1.text_input(
                "Buscar",
                placeholder="Buscar ferramentas, cursos, conceitos...",
                label_visibility="collapsed",
            )
            sent = c2.form_submit_button("Buscar", icon=":material/search:", type="primary", width="stretch")
        if sent and q.strip():
            go("library", q=q.strip()[:120])


def _chips(cat: Catalog, area: str | None) -> None:
    counts = cat.area_counts()
    options = [ALL] + [a.id for a in cat.areas.values() if a.chip and counts.get(a.id, 0) > 0]
    names = {ALL: "Todos", **{a.id: a.name for a in cat.areas.values()}}
    choice = st.pills(
        "Temas", options, default=area or ALL, format_func=names.get,
        label_visibility="collapsed", key=f"chips-{area or ALL}",
    )
    if choice and choice != (area or ALL):
        go("discover", area=None if choice == ALL else choice)


def _area_filter(resources: list[Resource], area: str | None) -> list[Resource]:
    if not area:
        return resources
    return [r for r in resources if area in r.areas]


def _see_all(label: str, key: str, **target: str | None) -> None:
    if st.button(label, key=key, icon=":material/arrow_forward:", type="tertiary"):
        go("library", **target)


def _release_updates(cat: Catalog) -> None:
    """No máximo 3 novidades Databricks APROVADAS, em uma faixa discreta (sem nova seção grande)."""
    items = sorted((r for r in cat.resources.values() if r.announced_on and r.release_status),
                   key=lambda r: r.announced_on, reverse=True)[:RELEASES_MAX]
    if not items:
        return
    with st.container(key="releases"):
        st.markdown('<div class="ac-rel-label">Novidades Databricks</div>', unsafe_allow_html=True)
        cols = st.columns(RELEASES_MAX, gap="small")
        for i, r in enumerate(items):
            with cols[i]:
                status = STATUS_LABEL.get(r.release_status or "", r.release_status or "")
                st.markdown(
                    f'<div class="ac-rel"><span class="ac-rel-meta">{r.announced_on:%d %b %Y} · {esc(status)}</span>'
                    f'<a href="{esc(r.url)}" target="_blank" rel="noopener noreferrer">{esc(r.title)}</a></div>',
                    unsafe_allow_html=True)


def _make_work_easier(cat: Catalog, area: str | None) -> None:
    """Subcategorias como cards-resumo; o clique abre a Library filtrada pela subcategoria."""
    sec = cat.taxonomy.section("make-your-work-easier")
    if not sec:
        return
    all_res = _area_filter(cat.resources_in_section(sec.id), area)
    subs = [(s, sum(1 for r in all_res if r.editorial_subcategory == s.id)) for s in sec.subcategories]
    subs = [(s, n) for s, n in subs if n]
    if not subs:
        return
    section_title(sec.title)
    cols = st.columns(len(subs), gap="small")
    for i, (sub, n) in enumerate(subs):
        with cols[i]:
            with st.container(border=True, key=f"sub-{sub.id}"):
                st.markdown(f"{sub.icon} **{sub.title}**")
                st.caption(f"{sub.scope} · {n} {'recurso' if n == 1 else 'recursos'}")
                if st.button("Explorar", key=f"go-{sub.id}", icon=":material/arrow_forward:", type="tertiary"):
                    go("library", subcategory=sub.id, area=area)
    _see_all(f"Ver todos ({len(all_res)})", f"more-{sec.id}", section=sec.id, area=area)


def _compact_section(cat: Catalog, section_id: str, area: str | None) -> None:
    """Até 2 recursos por subcategoria (máx. 6 por seção); o resto fica na Library."""
    sec = cat.taxonomy.section(section_id)
    if not sec:
        return
    all_res = _area_filter(cat.resources_in_section(section_id), area)
    if not all_res:
        return
    section_title(sec.title)
    groups: list[tuple] = []  # (subcategoria, ate 2 recursos); no maximo SECTION_MAX recursos no total
    shown = 0
    for sub in sec.subcategories:
        room = min(ITEMS_PER_GROUP, SECTION_MAX - shown)
        sub_res = [r for r in all_res if r.editorial_subcategory == sub.id][:room]
        if sub_res:
            groups.append((sub, sub_res))
            shown += len(sub_res)
    # cada coluna e um grupo: legenda da subcategoria + seus cards empilhados
    for row in range(0, len(groups), 3):
        cols = st.columns(3, gap="medium")
        for col, (sub, items) in zip(cols, groups[row:row + 3]):
            with col:
                st.caption(f"{sub.icon} {sub.title}")
                for r in items:
                    resource_card(r, cat, f"home-{section_id}", variant="grid")
    if len(all_res) > shown:
        _see_all(f"Ver todos ({len(all_res)})", f"more-{section_id}", section=section_id, area=area)


def _quick_knowledge(cat: Catalog) -> None:
    """Só 6 coleções em destaque: as 4 Databricks de QK_PRIORITY e depois as seguintes na ordem do arquivo."""
    if not cat.topics:
        return
    section_title("Quick Knowledge")
    first = [cat.topics[t] for t in QK_PRIORITY if t in cat.topics]
    rest = [t for t in cat.topics.values() if t.id not in QK_PRIORITY]
    featured = (first + rest)[:QK_FEATURED]
    cols = st.columns(3, gap="medium")
    for i, t in enumerate(featured):
        with cols[i % 3]:
            topic_card(t, cat, "qk")
    if len(cat.topics) > len(featured):
        if st.button(f"Ver todas ({len(cat.topics)} coleções)", key="more-qk",
                     icon=":material/arrow_forward:", type="tertiary"):
            go("tips")


def render(cat: Catalog) -> None:
    area = param("area")
    if area not in cat.areas:
        area = None
    _hero()
    _chips(cat, area)
    _release_updates(cat)

    _make_work_easier(cat, area)
    _compact_section(cat, "tools-resources", area)
    _compact_section(cat, "deep-dives-courses", area)
    _quick_knowledge(cat)

    st.write("")
    with st.container(horizontal=True, gap="medium", key="home-more"):
        if st.button("Ver a Library completa", icon=":material/grid_view:", key="to-library"):
            go("library", area=area)
        if st.button("Ver todas as notas", icon=":material/lightbulb:", key="to-tips"):
            go("tips", area=area)
