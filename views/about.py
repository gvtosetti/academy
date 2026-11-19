"""Sobre a Academy."""
from __future__ import annotations

import streamlit as st

from services.catalog import Catalog


def render(cat: Catalog, repo) -> None:
    st.title("Sobre a Academy")
    st.write(
        "A Academy é uma plataforma de aprendizado que organiza materiais públicos de qualidade sobre IA, "
        "LLMs, agentes, LLMOps, engenharia de software assistida por IA e visualização — com explicações "
        "em português e trilhas de estudo."
    )
    st.header("Princípios da curadoria")
    st.markdown(
        "- **Fonte original primeiro:** a Academy explica e organiza; o conteúdo pertence aos autores.\n"
        "- **Transparência:** separamos o que foi verificado na fonte (título, licença, aulas) do texto autoral da curadoria.\n"
        "- **Sem invenção:** quando um dado não pôde ser conferido, o recurso aparece como *em validação*.\n"
        "- **Nível sugerido:** o nível (iniciante, intermediário, avançado) é uma sugestão da curadoria."
    )
    st.header("Status dos metadados")
    counts = {s: sum(1 for r in cat.resources.values() if r.metadata_status == s) for s in ("verified", "partial", "pending")}
    c1, c2, c3 = st.columns(3)
    c1.metric("Verificados", counts["verified"])
    c2.metric("Parciais", counts["partial"])
    c3.metric("Em validação", counts["pending"])
    st.header("Limitações")
    st.markdown(
        "- O progresso é temporário (por sessão do navegador).\n"
        "- Dados ao vivo do GitHub dependem da API pública e podem estar indisponíveis por limite de uso.\n"
        "- A busca é local, por palavras-chave, sobre o catálogo curado."
    )
    st.caption("Catálogo mantido em data/*.yaml e validado automaticamente pelos testes.")
