"""Estilo visual complementar ao tema definido em .streamlit/config.toml.

O CSS abaixo e uma CONSTANTE estatica: nenhum dado do catalogo ou de APIs
externas e interpolado aqui, entao o uso de unsafe_allow_html e restrito a ele.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
.block-container {max-width: 1180px; padding-top: 2rem;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;}
h1, h2, h3 {letter-spacing: -0.01em;}
[data-testid="stCaptionContainer"] {color: #57534E;}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
