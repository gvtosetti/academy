"""Library: catalogo completo com busca (sem acento) e filtros opcionais combinaveis.

Sem consulta, mostra primeiro ferramentas e repositorios (areas intercaladas) e depois
cursos e playlists. Colecoes editoriais funcionam como mais um filtro transversal
(`?collection=<id>`).
"""
from __future__ import annotations

import streamlit as st

from components.cards import COURSE_TYPES, LANG_LABEL, LEVEL_LABEL, TYPE_LABEL, note_grid, resource_grid
from components.layout import go, param, section_title
from services.catalog import Catalog
from services.search import Filters, LocalSearch, search_notes

MAX_TAGS = 40
MONTHS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
RELEASE_LABEL = {"ga": "GA", "public_preview": "Public Preview", "private_preview": "Private Preview",
                 "beta": "Beta", "retired": "Retired", "deprecated": "Deprecated", "other": "Outro"}


@st.cache_resource(show_spinner=False)
def _engine(_cat: Catalog, version: int) -> LocalSearch:
    return LocalSearch(_cat)


def _multi(label: str, options: list[str], fmt, key: str, default: list[str] | None = None) -> tuple[str, ...]:
    return tuple(st.multiselect(label, options, default=default or [], format_func=fmt, key=key, placeholder="Todos"))


def render(cat: Catalog) -> None:
    q0 = param("q") or ""
    area0 = param("area") if param("area") in cat.areas else None
    section0 = param("section")
    sub0 = param("subcategory") if param("subcategory") in cat.taxonomy.subcategory_ids else None
    col0 = param("collection") if param("collection") in cat.collections else None
    res_cols = [c for c in cat.collections.values() if any(i.id in cat.resources for i in c.items)]

    st.title("Library", anchor=False)
    st.caption("Ferramentas, repositórios, referências e cursos em um só catálogo.")

    # Hint de busca por problema
    if not q0 and not section0 and not sub0:
        st.info("Dica: busque pelo que precisa fazer, como \"automatizar relatório\" ou \"validar dados de entrada\".",
                icon=":material/tips_and_updates:")

    c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
    q = c1.text_input(
        "Buscar na Library",
        value=q0,
        placeholder="Palavra-chave, conceito ou descrição — ex.: avaliação, animação, agentes",
        label_visibility="collapsed",
        key=f"lib-q-{q0}",
    ).strip()[:120]
    if q != q0:
        st.query_params["q"] = q  # URL compartilhavel

    sfx = f"{area0 or 'all'}-{col0 or 'all'}-{section0 or 'all'}-{sub0 or 'all'}"
    with c2.popover("Filtros", icon=":material/tune:"):
        sec_opts = [(s.id, s.title) for s in cat.taxonomy.sections]
        sections = _multi("Seção", [s[0] for s in sec_opts], lambda s: dict(sec_opts).get(s, s), f"f-sec-{sfx}",
                          [section0] if section0 else None)
        sub_opts = [(s.id, s.title) for sec in cat.taxonomy.sections for s in sec.subcategories]
        subcats = _multi("Subcategoria", [s[0] for s in sub_opts], lambda s: dict(sub_opts).get(s, s), f"f-sub-{sfx}",
                         [sub0] if sub0 else None)
        cols_sel = _multi("Coleção", [c.id for c in res_cols], lambda c: cat.collections[c].title, f"f-col-{sfx}",
                          [col0] if col0 else None)
        areas = _multi("Área", list(cat.areas), lambda a: cat.areas[a].name, f"f-area-{sfx}", [area0] if area0 else None)
        types = _multi("Tipo de recurso", sorted({r.type for r in cat.resources.values()}, key=list(TYPE_LABEL).index),
                       lambda t: TYPE_LABEL[t][0], f"f-type-{sfx}")
        levels = _multi("Nível", list(LEVEL_LABEL), LEVEL_LABEL.get, f"f-level-{sfx}")
        langs = _multi("Idioma", sorted({r.language for r in cat.resources.values()}), LANG_LABEL.get, f"f-lang-{sfx}")
        tags = _multi("Tags", [t for t, _ in cat.tag_counts()[:MAX_TAGS]], str, f"f-tags-{sfx}")
        # Novidades Databricks aprovadas (Release Watch): ano, mês e status de lançamento
        released = [r for r in cat.resources.values() if r.announced_on]
        if released:
            years = _multi("Ano do anúncio", sorted({r.announced_on.year for r in released}, reverse=True), str, f"f-year-{sfx}")
            months = _multi("Mês do anúncio", list(range(1, 13)), lambda m: MONTHS[m - 1], f"f-month-{sfx}")
            rstatus = _multi("Status de lançamento", sorted({r.release_status for r in released if r.release_status}),
                             lambda s: RELEASE_LABEL.get(s, s), f"f-rstatus-{sfx}")
        else:
            years, months, rstatus = (), (), ()

    f = Filters(areas=areas, types=types, difficulties=levels, languages=langs, tags=tags,
                sections=sections, subcategories=subcats)
    engine = _engine(cat, id(cat))
    results = [r for r, _ in engine.search(q, f, sort="relevance" if q else "diverse")]
    if cols_sel:
        keep = [i.id for c in cols_sel for i in cat.collections[c].items]
        results = [r for r in results if r.id in keep]
        if not q and len(cols_sel) == 1:  # ordem editorial da colecao
            results.sort(key=lambda r: keep.index(r.id))
    elif not q:  # Tools & Resources primeiro; cursos longos depois
        results.sort(key=lambda r: r.type in COURSE_TYPES)
    if years or months or rstatus:
        results = [r for r in results if r.announced_on
                   and (not years or r.announced_on.year in years)
                   and (not months or r.announced_on.month in months)
                   and (not rstatus or r.release_status in rstatus)]
        results.sort(key=lambda r: r.announced_on, reverse=True)

    active = [cat.collections[c].title for c in cols_sel] + [cat.areas[a].name for a in areas] + [TYPE_LABEL[t][0] for t in types] + \
        [LEVEL_LABEL[x] for x in levels] + [LANG_LABEL[x] for x in langs] + list(tags) + \
        [str(y) for y in years] + [MONTHS[m - 1] for m in months] + [RELEASE_LABEL.get(s, s) for s in rstatus]
    info = f"{len(results)} recurso(s)"
    if q:
        info += f" para “{q}”"
    if active:
        info += " · filtros: " + ", ".join(active)
    cc1, cc2 = st.columns([4, 1], vertical_alignment="center")
    cc1.caption(info)
    if (q or f.active or cols_sel or years or months or rstatus) and cc2.button("Limpar", icon=":material/close:", type="tertiary", key="clear"):
        go("library")

    if results:
        resource_grid(results, cat, "lib")
    else:
        st.info("Nada encontrado com essa combinação. Tente menos filtros ou outra palavra.", icon=":material/search_off:")

    if q:
        notes = search_notes(cat.notes.values(), q, areas=areas)[:3]
        if notes:
            st.write("")
            section_title("Em Tips & Insights", "Notas curtas relacionadas à sua busca.")
            note_grid(notes, cat, "libnotes")
