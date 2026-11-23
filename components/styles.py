"""Identidade visual da Resource Library: portal editorial minimalista e compacto.

So CSS estatico (nenhum dado do catalogo e interpolado aqui). Seletores usam as
classes `st-key-*` geradas pelos `key=` dos containers, que sao estaveis.
"""
from __future__ import annotations

import streamlit as st

_CSS = """
<style>
:root {
  --ac-ink: #1C1917; --ac-ink-2: #44403C; --ac-mute: #78716C; --ac-line: #E7E5E4;
  --ac-paper: #FFFFFF; --ac-accent: #4338CA; --ac-radius: 14px;
}

/* ---------- moldura ---------- */
.block-container {max-width: 1160px; padding-bottom: 3.5rem;}
/* padding-top herdado do Streamlit (6rem) garante que o conteudo nao sobreponha o header absoluto */
#MainMenu, footer, [data-testid="stDecoration"] {visibility: hidden;}
h1, h2, h3 {letter-spacing: -0.02em; color: var(--ac-ink);}
h3 {font-size: 1.55rem; font-weight: 600;}
[data-testid="stCaptionContainer"] {color: var(--ac-mute);}

/* ---------- barra superior ---------- */
.st-key-topbar {border-bottom: 1px solid var(--ac-line); padding-bottom: .4rem; margin-bottom: .6rem;}
.st-key-brand button p {font-weight: 700; font-size: 1.05rem; letter-spacing: -0.01em; color: var(--ac-ink);}

/* ---------- hero compacto ---------- */
.st-key-hero {
  padding: 1.6rem 1.75rem 1.25rem; border-radius: 18px; border: 1px solid #ECEBF5; gap: .5rem;
  background: radial-gradient(900px 220px at 0% 0%, #EEF0FF 0%, rgba(238,240,255,0) 60%),
              radial-gradient(700px 200px at 100% 0%, #FFF3E6 0%, rgba(255,243,230,0) 55%), #FFFFFF;
}
.st-key-hero h1 {font-size: 1.95rem; line-height: 1.15; font-weight: 700; padding: 0;}
.st-key-hero [data-testid="stMarkdownContainer"] p {font-size: 1rem; color: var(--ac-ink-2); margin: 0;}
.st-key-hero [data-testid="stForm"] {padding: 0; margin-top: .2rem;}
/* botao de busca: texto branco sobre fundo violeta (nao herda cor do hero) */
.st-key-hero [data-testid="stFormSubmitButton"] button p {color: #FFFFFF !important;}

/* ---------- cabecalhos de secao ---------- */
.ac-eyebrow {font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ac-accent); margin: 1.1rem 0 -.6rem;}
/* secoes da Home: titulo mais proximo do conteudo, menos respiro entre secoes */
[data-testid="stHeading"] h3 {padding: .9rem 0 .15rem;}
.ac-subhead {display: flex; align-items: baseline; gap: .75rem; flex-wrap: wrap; margin: .9rem 0 .1rem;}
.ac-subhead b {font-size: 1.08rem; font-weight: 650; color: var(--ac-ink);}
.ac-subhead span {font-size: .9rem; color: var(--ac-mute);}
.st-key-sec-deep-dives, .st-key-sec-quick-knowledge {margin-top: .4rem;}

/* ---------- cards: tratamento unico ---------- */
/* cards com altura do proprio conteudo: nada de esticar ate o maior card da linha */
[data-testid="stHorizontalBlock"]:has([class*="st-key-card-"]) {align-items: flex-start;}
[class*="st-key-card-"] {
  background: var(--ac-paper); border-radius: var(--ac-radius) !important; border-color: var(--ac-line) !important;
  gap: .35rem; padding: .8rem .95rem .4rem !important;
  transition: box-shadow .15s ease, border-color .15s ease, transform .15s ease;
}
[class*="st-key-card-"]:hover {border-color: #D6D3D1 !important; box-shadow: 0 6px 22px rgba(28,25,23,.07); transform: translateY(-1px);}
[class*="st-key-card-"] [data-testid="stMarkdownContainer"] {line-height: 1.45;}

.ac-head {display: flex; align-items: center; gap: .6rem; margin-bottom: .35rem; min-width: 0;}
.ac-logo {flex: 0 0 34px; width: 34px; height: 34px; border-radius: 9px; overflow: hidden;
  background: var(--bg); color: var(--fg); display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid rgba(0,0,0,.05);}
.ac-logo img {width: 100%; height: 100%; object-fit: cover; display: block;}
.ac-mono {font-size: .78rem; font-weight: 750; letter-spacing: .02em;}
.ac-kicker {font-size: .74rem; color: var(--ac-mute); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;}
.ac-kicker b {font-weight: 650;}
.ac-kicker i {font-style: normal; margin: 0 .35rem; color: #D6D3D1;}

.ac-title {font-size: 1.02rem; font-weight: 650; line-height: 1.3; color: var(--ac-ink);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: .2rem;}
.ac-desc {font-size: .89rem; color: var(--ac-ink-2); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;}
/* Home: descricoes em 2 linhas (o texto completo fica no Saiba mais) */
[class*="st-key-card-grid-home-"] .ac-desc, [class*="st-key-card-topic-qk-"] .ac-desc {-webkit-line-clamp: 2;}
.ac-quote {margin-top: .6rem; padding-left: .7rem; border-left: 2px solid #C7D2FE; font-size: .86rem;
  color: var(--ac-ink-2); font-style: italic; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;}

/* acoes: sempre no rodape do card, como links, sem truncar */
[class*="st-key-act-"] {margin-top: .15rem; padding-top: .25rem; border-top: 1px solid #F1F0EE; flex-wrap: wrap; row-gap: 0;
  column-gap: 1rem; align-items: center;}
[class*="st-key-act-"] button, [class*="st-key-act-"] a {padding: .2rem 0 !important; min-height: 0 !important;}
[class*="st-key-act-"] p {font-size: .86rem !important; font-weight: 600; white-space: nowrap; overflow: visible !important;}
[class*="st-key-act-"] a p {color: var(--ac-accent);}
[class*="st-key-act-"] button p {color: var(--ac-ink-2);}
[class*="st-key-act-"] a:hover p, [class*="st-key-act-"] button:hover p {text-decoration: underline; text-underline-offset: 3px;}

/* variante linha (Make your work easier) */
.ac-rowwrap {display: flex; gap: .85rem; align-items: flex-start;}
.ac-rowwrap .ac-logo {flex-basis: 44px; width: 44px; height: 44px; border-radius: 11px;}
.ac-rowtext {min-width: 0; display: flex; flex-direction: column; gap: .15rem;}
.ac-rowtext .ac-title {-webkit-line-clamp: 2; margin: 0;}
.ac-rowtext .ac-desc {-webkit-line-clamp: 2;}
[class*="st-key-card-row-"] {padding: .85rem 1rem .45rem !important;}

/* variante destaque (Interesting discoveries): mais respiro, faixa de cor */
[class*="st-key-card-feature-"] {background: linear-gradient(180deg, #FBFAFF 0%, #FFFFFF 60%); padding: 1.2rem 1.25rem .6rem !important;}
[class*="st-key-card-feature-"] .ac-title {font-size: 1.15rem;}

/* variante prateleira (Deep dives): discreta, secundaria */
[class*="st-key-card-shelf-"] {background: #FCFCFB; box-shadow: none;}
[class*="st-key-card-shelf-"] .ac-title {font-size: .95rem; -webkit-line-clamp: 3;}
[class*="st-key-card-shelf-"] .ac-desc {font-size: .84rem; -webkit-line-clamp: 2;}
[class*="st-key-card-shelf-"] .ac-logo {flex-basis: 28px; width: 28px; height: 28px; border-radius: 7px;}

/* variante bloco de leitura (Quick knowledge) */
[class*="st-key-card-tile-"] {background: #FFFDF7; border-color: #F1E9D8 !important;}
[class*="st-key-card-tile-"] .ac-head {margin-bottom: .35rem;}
[class*="st-key-card-tile-"] .ac-title {font-size: .98rem;}
[class*="st-key-card-tile-"] .ac-desc {font-size: .86rem;}

/* Make Your Work Easier: subcategorias como cards-resumo compactos */
[class*="st-key-sub-"] {background: var(--ac-paper); border-radius: 12px !important; border-color: var(--ac-line) !important;
  padding: .7rem .85rem .3rem !important; gap: .1rem;
  transition: border-color .15s ease, box-shadow .15s ease;}
[class*="st-key-sub-"]:hover {border-color: #C7D2FE !important; box-shadow: 0 4px 16px rgba(67,56,202,.07);}
[class*="st-key-sub-"] [data-testid="stMarkdownContainer"] p {font-size: .95rem; line-height: 1.3; margin: 0;}
[class*="st-key-sub-"] [data-testid="stCaptionContainer"] p {font-size: .8rem; line-height: 1.35; margin: 0;}
[class*="st-key-sub-"] button {padding: .1rem 0 !important; min-height: 0 !important;}
[class*="st-key-sub-"] button p {font-size: .85rem; font-weight: 600; color: var(--ac-accent);}

/* Novidades Databricks: faixa discreta, no maximo 3 itens */
.st-key-releases {margin-top: .35rem; gap: .25rem;}
.ac-rel-label {font-size: .72rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; color: var(--ac-mute);}
.ac-rel {display: flex; flex-direction: column; gap: .1rem; padding: .45rem .7rem; border: 1px solid var(--ac-line);
  border-radius: 10px; background: #FBFAFF;}
.ac-rel-meta {font-size: .72rem; color: var(--ac-mute);}
.ac-rel a {font-size: .88rem; font-weight: 600; color: var(--ac-ink); text-decoration: none; line-height: 1.3;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;}
.ac-rel a:hover {color: var(--ac-accent); text-decoration: underline; text-underline-offset: 3px;}

/* paginas de detalhe */
.st-key-lead p {font-size: 1.12rem; color: var(--ac-ink-2); line-height: 1.6;}

/* ---------- larguras menores ---------- */
@media (max-width: 1100px) {
  .ac-kicker {font-size: .7rem;}
}
@media (max-width: 640px) {
  .block-container {padding-left: .9rem; padding-right: .9rem;}
  .st-key-hero {padding: .9rem 1rem .75rem;}
  .st-key-hero h1 {font-size: 1.5rem;}
  .st-key-hero [data-testid="stMarkdownContainer"] p {font-size: .92rem;}
  h3 {font-size: 1.3rem;}
  .ac-eyebrow {margin-top: 1.1rem;}
}
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)
