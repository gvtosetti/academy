"""Identidade visual da Academy: portal editorial minimalista.

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
.block-container {max-width: 1160px; padding-top: 1rem; padding-bottom: 3.5rem;}
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

/* ---------- cabecalhos de secao ---------- */
.ac-eyebrow {font-size: .72rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase;
  color: var(--ac-accent); margin: 1.6rem 0 -.6rem;}
.ac-subhead {display: flex; align-items: baseline; gap: .75rem; flex-wrap: wrap; margin: .9rem 0 .1rem;}
.ac-subhead b {font-size: 1.08rem; font-weight: 650; color: var(--ac-ink);}
.ac-subhead span {font-size: .9rem; color: var(--ac-mute);}
.st-key-sec-deep-dives, .st-key-sec-quick-knowledge {margin-top: .4rem;}

/* ---------- cards: tratamento unico ---------- */
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] {height: 100%;}
[data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {height: 100%;}
[class*="st-key-card-"] {
  background: var(--ac-paper); border-radius: var(--ac-radius) !important; border-color: var(--ac-line) !important;
  height: 100%; gap: .45rem; padding: 1rem 1.05rem .55rem !important;
  transition: box-shadow .15s ease, border-color .15s ease, transform .15s ease;
}
[class*="st-key-card-"]:hover {border-color: #D6D3D1 !important; box-shadow: 0 6px 22px rgba(28,25,23,.07); transform: translateY(-1px);}
[class*="st-key-card-"] [data-testid="stMarkdownContainer"] {line-height: 1.45;}

.ac-head {display: flex; align-items: center; gap: .6rem; margin-bottom: .55rem; min-width: 0;}
.ac-logo {flex: 0 0 34px; width: 34px; height: 34px; border-radius: 9px; overflow: hidden;
  background: var(--bg); color: var(--fg); display: inline-flex; align-items: center; justify-content: center;
  border: 1px solid rgba(0,0,0,.05);}
.ac-logo img {width: 100%; height: 100%; object-fit: cover; display: block;}
.ac-mono {font-size: .78rem; font-weight: 750; letter-spacing: .02em;}
.ac-kicker {font-size: .74rem; color: var(--ac-mute); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;}
.ac-kicker b {font-weight: 650;}
.ac-kicker i {font-style: normal; margin: 0 .35rem; color: #D6D3D1;}

.ac-title {font-size: 1.04rem; font-weight: 650; line-height: 1.3; color: var(--ac-ink);
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: .3rem;}
.ac-desc {font-size: .9rem; color: var(--ac-ink-2); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;}
.ac-quote {margin-top: .6rem; padding-left: .7rem; border-left: 2px solid #C7D2FE; font-size: .86rem;
  color: var(--ac-ink-2); font-style: italic; line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;}

/* acoes: sempre no rodape do card, como links, sem truncar */
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-act-"]) {margin-top: auto;}
[class*="st-key-act-"] {margin-top: auto; padding-top: .35rem; border-top: 1px solid #F1F0EE; flex-wrap: wrap; row-gap: 0;}
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
