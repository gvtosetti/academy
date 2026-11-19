"""Explorador dos repositorios GitHub do catalogo."""
from __future__ import annotations

import streamlit as st

from components.nav import go, param
from components.ui import bullet_list, meta_line
from services import github_api
from services.catalog import Catalog
from utils.safe import sanitize_markdown


def _repos(cat: Catalog):
    """Um item por repositorio: filhos que apontam ao mesmo repo do pai ficam sob o pai."""
    out = []
    for r in sorted(cat.resources.values(), key=lambda x: (x.sequence, x.title)):
        if not r.github_repo:
            continue
        parent = cat.resources.get(r.parent) if r.parent else None
        if parent and parent.github_repo == r.github_repo:
            continue
        out.append(r)
    return out


def render(cat: Catalog, repo) -> None:
    st.title("GitHub Explorer")
    st.write("Repositórios do catálogo com metadados ao vivo, estrutura de pastas e README. "
             "A curadoria funciona mesmo se a API do GitHub estiver indisponível.")
    items = _repos(cat)
    ids = [r.id for r in items]
    pre = param("resource")
    sel = st.selectbox("Repositório", ids, index=ids.index(pre) if pre in ids else 0,
                       format_func=lambda x: f"{cat.resources[x].title} ({cat.resources[x].github_repo})")
    r = cat.resources[sel]
    full = r.github_repo or ""

    with st.container(border=True):
        st.markdown(f"### {r.title}")
        st.caption(meta_line(r, cat))
        st.write(r.short_description)
        if st.button("Ver página completa do recurso", key="gh-detail", icon=":material/arrow_forward:"):
            go("resource", resource=r.id)

    if r.github_highlights:
        st.markdown("#### Onde olhar (curadoria)")
        bullet_list([f"`{h.path}` — {h.why}" for h in r.github_highlights])
    kids = [k for k in cat.children_of(r.id) if k.github_repo == full]
    if kids:
        st.markdown("#### Itens curados neste repositório")
        for k in kids:
            if st.button(k.title, key=f"gh-kid-{k.id}"):
                go("resource", resource=k.id)

    if "/" not in full:  # organizacao
        res = github_api.org(full)
        st.markdown("#### Organização (ao vivo)")
        if res.ok:
            st.metric("Repositórios públicos", res.data.get("public_repos") or "-")
            if res.data.get("description"):
                st.write(res.data["description"])
        else:
            st.caption("Não foi possível consultar o GitHub agora.")
        return

    meta = github_api.repo(full)
    st.markdown("#### Metadados (ao vivo)")
    if not meta.ok:
        st.caption("Limite da API atingido; tente mais tarde." if meta.rate_limited else "Não foi possível consultar o GitHub agora.")
        return
    d = meta.data
    c1, c2, c3 = st.columns(3)
    c1.metric("Linguagem", d.get("language") or "-")
    c2.metric("Licença", d.get("license") or "-")
    c3.metric("Último push", (d.get("pushed_at") or "-")[:10])
    if d.get("topics"):
        st.caption("Tópicos: " + ", ".join(d["topics"][:12]))

    st.markdown("#### Estrutura da raiz")
    cont = github_api.contents(full)
    if cont.ok and isinstance(cont.data, list):
        bullet_list([(":material/folder: " if x["type"] == "dir" else ":material/description: ") + f"`{x['name']}`"
                     for x in cont.data[:40]])
    else:
        st.caption("Estrutura indisponível no momento.")

    st.markdown("#### README")
    if st.toggle("Carregar prévia do README", key=f"gh-readme-{r.id}"):
        rd = github_api.readme(full, d.get("default_branch") or "main")
        if rd.ok and isinstance(rd.data, str):
            with st.container(border=True, height=500):
                st.markdown(sanitize_markdown(rd.data))
            st.caption("Prévia truncada e sem HTML/imagens. Veja o original no GitHub.")
        else:
            st.caption("README indisponível no momento.")
