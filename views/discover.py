"""Discover: vitrine editorial compacta (não é o catálogo completo — isso é a Library).

Ordem: hero com busca -> chips de área -> novidades Databricks (máx. 3, só aprovadas) ->
1. Make Your Work Easier: cards de categoria inteiramente clicáveis (abrem a Library filtrada)
2. Tools & Resources: 4 grupos em lista compacta, até 3 linhas cada (abrem o recurso)
3. Deep Dives & Courses: grade de plataformas, lista de cursos e lista de guias
4. Quick Knowledge: 6 coleções em destaque (4 Databricks fixas + as 2 seguintes na ordem do arquivo)

Cada seção é um único bloco HTML em CSS grid (components/cards.py + styles.py): o link é o
próprio card/linha, então texto e navegação nunca ficam em containers diferentes.

Com um chip ativo, cada seção mostra só itens da área e some se ficar vazia.
"""
from __future__ import annotations

import streamlit as st

from components.cards import (category_card_html, collection_card_html, course_row_html, guide_row_html,
                              html_block, ms_icon, platform_tile_html, tool_row_html)
from components.layout import go, param, section_title
from services.catalog import Catalog
from services.models import Resource
from utils.safe import esc

HERO_TITLE = "Resource Library"
ALL = "all"
TOOLS_PER_GROUP = 3   # linhas por grupo em Tools & Resources
DEEP_LIMITS = {"learning-platforms": 9, "courses-lectures": 4, "guides-roadmaps": 4}
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
    """Cards de categoria: icone, titulo e descricao curta; o card inteiro abre a Library filtrada."""
    sec = cat.taxonomy.section("make-your-work-easier")
    if not sec:
        return
    all_res = _area_filter(cat.resources_in_section(sec.id), area)
    subs = [s for s in sec.subcategories if any(r.editorial_subcategory == s.id for r in all_res)]
    if not subs:
        return
    section_title(sec.title)
    html_block("ac-grid ac-grid-3", (category_card_html(s, area) for s in subs), "mwe")
    _see_all(f"Ver todos ({len(all_res)})", f"more-{sec.id}", section=sec.id, area=area)


def _group_head(sub) -> str:
    return f'<div class="ac-ghead">{ms_icon(sub.icon, "ac-ms ac-ghead-icon")}<span>{esc(sub.title)}</span></div>'


def _by_sub(cat: Catalog, section_id: str, area: str | None):
    sec = cat.taxonomy.section(section_id)
    if not sec:
        return None, [], []
    all_res = _area_filter(cat.resources_in_section(section_id), area)
    groups = [(s, [r for r in all_res if r.editorial_subcategory == s.id]) for s in sec.subcategories]
    return sec, all_res, [(s, rs) for s, rs in groups if rs]


def _tools_resources(cat: Catalog, area: str | None) -> None:
    """Grupos em lista compacta (ate 3 linhas); cada linha abre o recurso direto."""
    sec, all_res, groups = _by_sub(cat, "tools-resources", area)
    if not groups:
        return
    section_title(sec.title)
    blocks = (f'<div class="ac-group">{_group_head(s)}<div class="ac-list">'
              f'{"".join(tool_row_html(r) for r in rs[:TOOLS_PER_GROUP])}</div></div>' for s, rs in groups)
    html_block("ac-grid ac-grid-4", blocks, "tools")
    if len(all_res) > sum(min(len(rs), TOOLS_PER_GROUP) for _, rs in groups):
        _see_all(f"Ver todos ({len(all_res)})", "more-tools-resources", section="tools-resources", area=area)


def _deep_dives(cat: Catalog, area: str | None) -> None:
    """Tres apresentacoes distintas: grade de plataformas, lista de cursos, lista de guias."""
    sec, all_res, groups = _by_sub(cat, "deep-dives-courses", area)
    if not groups:
        return
    section_title(sec.title)
    shown = 0
    for s, rs in groups:
        items = rs[:DEEP_LIMITS.get(s.id, 4)]
        shown += len(items)
        if s.id == "learning-platforms":
            inner, cls = (platform_tile_html(r) for r in items), "ac-plats"
        elif s.id == "courses-lectures":
            inner, cls = (course_row_html(r, cat) for r in items), "ac-list ac-list-2"
        else:
            inner, cls = (guide_row_html(r) for r in items), "ac-list ac-list-2"
        _html_group(s, cls, inner)
    if len(all_res) > shown:
        _see_all(f"Ver todos ({len(all_res)})", "more-deep-dives-courses", section="deep-dives-courses", area=area)


def _html_group(sub, cls: str, inner) -> None:
    st.markdown(f'<div class="ac-group ac-group-wide">{_group_head(sub)}<div class="{cls}">{"".join(inner)}</div></div>',
                unsafe_allow_html=True)


def _quick_knowledge(cat: Catalog) -> None:
    """Só 6 coleções em destaque: as 4 Databricks de QK_PRIORITY e depois as seguintes na ordem do arquivo."""
    if not cat.topics:
        return
    section_title("Quick Knowledge")
    first = [cat.topics[t] for t in QK_PRIORITY if t in cat.topics]
    rest = [t for t in cat.topics.values() if t.id not in QK_PRIORITY]
    featured = (first + rest)[:QK_FEATURED]
    html_block("ac-grid ac-grid-3", (collection_card_html(t, cat) for t in featured), "qk")
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
    _tools_resources(cat, area)
    _deep_dives(cat, area)
    _quick_knowledge(cat)

    st.write("")
    with st.container(horizontal=True, gap="medium", key="home-more"):
        if st.button("Ver a Library completa", icon=":material/grid_view:", key="to-library"):
            go("library", area=area)
        if st.button("Ver todas as notas", icon=":material/lightbulb:", key="to-tips"):
            go("tips", area=area)
