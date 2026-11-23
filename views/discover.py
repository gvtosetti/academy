"""Discover: home editorial centrada em Tools & Resources.

Ordem: hero compacto com busca -> chips de area (filtros transversais) -> bloco central
"Tools & Resources" (colecoes `home: main`) -> demais colecoes editoriais, cada uma com
um layout proprio. Cursos longos ficam em "Deep dives", secundario, no fim da pagina.

Com um chip ativo, cada colecao mostra so itens da area e some se ficar vazia. Um item
aparece no maximo uma vez na home, mesmo que pertenca a varias colecoes.
"""
from __future__ import annotations

import streamlit as st

from components.cards import COURSE_TYPES, item_grid
from components.layout import go, param, section_title, subhead
from services.catalog import Catalog, diverse
from services.models import Collection, Resource

HERO_TITLE = "Um lugar para descobrir algo novo."
HERO_SUBTITLE = "Ferramentas, repositórios e conhecimento prático, com curadoria."
ALL = "all"

# layout da colecao -> (colunas, variante do card)
LAYOUTS = {
    "grid": (3, "grid"),
    "list": (2, "row"),
    "feature": (2, "feature"),
    "notes": (4, "tile"),
    "shelf": (4, "shelf"),
}
EYEBROW = {
    "interesting-discoveries": "Curadoria",
    "quick-knowledge": "Para ler em 1 minuto",
    "deep-dives": "Para estudar com calma",
}


def _hero() -> None:
    with st.container(key="hero"):
        st.title(HERO_TITLE, anchor=False)
        st.markdown(HERO_SUBTITLE)
        with st.form("global-search", border=False, clear_on_submit=False):
            c1, c2 = st.columns([6, 1], vertical_alignment="bottom", gap="small")
            q = c1.text_input(
                "Buscar",
                placeholder="Busque uma ferramenta, tema ou conceito — ex.: forecast, RAG, Git, data contract",
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


def _pick(cat: Catalog, col: Collection, area: str | None, shown: set[str]) -> list:
    out = []
    for obj, note in cat.collection_items(col.id):
        if obj.id in shown or (area and area not in obj.areas):
            continue
        out.append((obj, note))
        if len(out) >= col.home_limit:
            break
    return out


def _render(cat: Catalog, col: Collection, items: list, total: int) -> None:
    cols, variant = LAYOUTS[col.layout]
    item_grid(items, cat, col.id, cols=cols, variant=variant)
    if total > len(items):
        target = ("tips", {}) if col.layout == "notes" else ("library", {"collection": col.id})
        if st.button(f"Ver tudo em {col.title} →", key=f"all-{col.id}", type="tertiary"):
            go(target[0], **target[1])


def _in_area(obj, area: str | None) -> bool:
    return not area or area in obj.areas


def render(cat: Catalog) -> None:
    area = param("area")
    if area not in cat.areas:
        area = None
    _hero()
    _chips(cat, area)

    shown: set[str] = set()
    main = [c for c in cat.collections.values() if c.home == "main"]
    rest = [c for c in cat.collections.values() if c.home == "section"]

    # ---- Tools & Resources (bloco central) ---------------------------------
    blocks = []
    for col in main:
        items = _pick(cat, col, area, shown)
        shown |= {o.id for o, _ in items}
        blocks.append((col, items))
    if area and blocks and len(blocks[0][1]) < 3:
        # completa com outras ferramentas/repositorios da area (nunca cursos longos)
        extra = [r for r in diverse(cat.resources_in_area(area))
                 if r.id not in shown and r.type not in COURSE_TYPES and r.parent is None]
        need = blocks[0][0].home_limit - len(blocks[0][1])
        blocks[0][1].extend((r, None) for r in extra[:need])
        shown |= {r.id for r in extra[:need]}
    if any(items for _, items in blocks):
        section_title("Tools & Resources", "Ferramentas, repositórios e referências para usar no trabalho.",
                      eyebrow="Em destaque")
        for col, items in blocks:
            if items:
                subhead(col.title, col.tagline)
                total = sum(1 for o, _ in cat.collection_items(col.id) if _in_area(o, area))
                _render(cat, col, items, total)

    # ---- colecoes editoriais ------------------------------------------------
    for col in rest:
        items = _pick(cat, col, area, shown)
        if not items:
            continue
        shown |= {o.id for o, _ in items if isinstance(o, Resource)}
        with st.container(key=f"sec-{col.id}"):
            section_title(col.title, col.tagline, eyebrow=EYEBROW.get(col.id))
            total = sum(1 for o, _ in cat.collection_items(col.id) if _in_area(o, area))
            _render(cat, col, items, total)

    st.write("")
    with st.container(horizontal=True, gap="medium", key="home-more"):
        if st.button("Ver a Library completa", icon=":material/grid_view:", key="to-library"):
            go("library", area=area)
        if st.button("Ver todas as notas", icon=":material/lightbulb:", key="to-tips"):
            go("tips", area=area)
