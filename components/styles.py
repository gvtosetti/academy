"""Estilo visual complementar ao tema definido em .streamlit/config.toml.

O CSS abaixo e uma CONSTANTE estatica: nenhum dado do catalogo ou de APIs
externas e interpolado aqui, entao o uso de unsafe_allow_html e restrito a ele.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
/* Moldura editorial: coluna central, respiro generoso */
.block-container {max-width: 1120px; padding-top: 1.25rem; padding-bottom: 4rem;}
h1, h2, h3 {letter-spacing: -0.015em;}
h3 {font-weight: 600;}
[data-testid="stCaptionContainer"] {color: #78716C;}

/* Barra superior */
.st-key-topbar {border-bottom: 1px solid #E7E5E4; padding-bottom: .5rem; margin-bottom: .75rem;}
.st-key-brand button p {font-weight: 700; font-size: 1.05rem; letter-spacing: -0.01em;}

/* Hero com elemento grafico discreto (gradiente suave) */
.st-key-hero {
  padding: 2.5rem 2rem 1.75rem; border-radius: 20px; border: 1px solid #EEF0F6;
  background: radial-gradient(1200px 300px at 0% 0%, #EEF0FF 0%, rgba(238,240,255,0) 60%),
              radial-gradient(800px 260px at 100% 0%, #FFF4E8 0%, rgba(255,244,232,0) 55%), #FFFFFF;
  margin-bottom: .5rem;
}
.st-key-hero h1 {font-size: 2.6rem; line-height: 1.12; font-weight: 700; padding-bottom: .25rem;}
.st-key-hero p {font-size: 1.1rem; color: #57534E;}

/* Texto de abertura nas paginas de detalhe */
.st-key-lead p {font-size: 1.12rem; color: #44403C; line-height: 1.6;}

/* Cards brancos, bordas sutis, hover leve */
[class*="st-key-card-"] {background: #FFFFFF; border-radius: 14px; transition: box-shadow .15s ease, border-color .15s ease;}
[class*="st-key-card-"]:hover {border-color: #D6D3D1; box-shadow: 0 2px 14px rgba(28, 25, 23, .06);}
[class*="st-key-card-"] h3 {font-size: 1.05rem; line-height: 1.35; padding: .1rem 0 .15rem;}
[class*="st-key-card-"] [data-testid="stMarkdownContainer"] p {font-size: .93rem; color: #44403C; line-height: 1.5;}

/* Mobile */
@media (max-width: 640px) {
  .block-container {padding-left: 1rem; padding-right: 1rem;}
  .st-key-hero {padding: 1.5rem 1.1rem 1.1rem;}
  .st-key-hero h1 {font-size: 1.85rem;}
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
