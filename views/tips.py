"""Tips & Insights: colecao de notas curtas e independentes (nao e um curso)."""
from __future__ import annotations

from collections import defaultdict

import streamlit as st

from components.cards import note_grid
from components.layout import go, param
from services.catalog import NOTE_KINDS, Catalog, Note
from services.search import search_notes

ALL = "all"
KIND_PLURAL = {
    ALL: "Todas",
    "explainer": "Quick Explainers",
    "dev-tip": "Dev Tips",
    "tool": "Tools Worth Knowing",
    "practice": "Good Practices",
    "in-practice": "Concepts in Practice",
}
# Ordem da vitrine padrao: notas praticas primeiro, explainers intercalados.
MIX_ORDER = ["practice", "dev-tip", "explainer", "in-practice", "tool", "explainer"]


def _mixed(notes: list[Note]) -> list[Note]:
    by_kind: dict[str, list[Note]] = defaultdict(list)
    for n in notes:
        by_kind[n.kind].append(n)
    out: list[Note] = []
    while any(by_kind.values()):
        for k in MIX_ORDER:
            if by_kind[k]:
                out.append(by_kind[k].pop(0))
    return out


def render(cat: Catalog) -> None:
    kind = param("kind") if param("kind") in NOTE_KINDS else None
    area = param("area") if param("area") in cat.areas else None
    q0 = param("q") or ""

    st.title("Tips & Insights", anchor=False)
    st.caption("Notas curtas sobre conceitos, ferramentas, workflows e boas práticas. Cada uma se lê sozinha, em poucos minutos.")

    choice = st.pills(
        "Tipo de nota", list(KIND_PLURAL), default=kind or ALL, format_func=KIND_PLURAL.get,
        label_visibility="collapsed", key=f"kinds-{kind or ALL}-{area}",
    )
    if choice and choice != (kind or ALL):
        go("tips", kind=None if choice == ALL else choice, area=area, q=q0 or None)

    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    q = c1.text_input(
        "Buscar notas", value=q0, placeholder="Buscar nas notas — ex.: API, lineage, testes",
        label_visibility="collapsed", key=f"tips-q-{q0}",
    ).strip()[:120]
    if q != q0:
        st.query_params["q"] = q
    area_opts = [ALL] + [a for a in cat.areas if cat.notes_in_area(a)]
    sel = c2.selectbox(
        "Área", area_opts, index=area_opts.index(area) if area in area_opts else 0,
        format_func=lambda a: "Todas as áreas" if a == ALL else cat.areas[a].name,
        label_visibility="collapsed", key=f"tips-area-{area}",
    )
    if sel != (area or ALL):
        go("tips", kind=kind, area=None if sel == ALL else sel, q=q or None)

    notes = search_notes(cat.notes.values(), q, kinds=(kind,) if kind else (), areas=(area,) if area else ())
    if not q and not kind:
        notes = _mixed(notes)
    st.caption(f"{len(notes)} nota(s)")
    if notes:
        note_grid(notes, cat, "tips")
    else:
        st.info("Nenhuma nota com esses critérios.", icon=":material/search_off:")
