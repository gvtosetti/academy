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
/* secoes: respiro claro ENTRE secoes, titulo proximo do proprio conteudo */
[data-testid="stHeading"] h3 {padding: 1.35rem 0 .2rem;}
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
.ac-kicker {font-size: .74rem; color: var(--ac-mute); min-width: 0; line-height: 1.35;}
.ac-kicker b {font-weight: 650;}
.ac-kicker i {font-style: normal; margin: 0 .35rem; color: #D6D3D1;}

.ac-title {font-size: 1.02rem; font-weight: 650; line-height: 1.3; color: var(--ac-ink);
  overflow-wrap: anywhere; margin-bottom: .2rem;}  /* titulo nunca e cortado (identifica o curso/recurso) */
.ac-desc {font-size: .89rem; color: var(--ac-ink-2); line-height: 1.45;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;}
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
.ac-rowtext .ac-title {margin: 0;}
.ac-rowtext .ac-desc {-webkit-line-clamp: 2;}
[class*="st-key-card-row-"] {padding: .85rem 1rem .45rem !important;}

/* variante destaque (Interesting discoveries): mais respiro, faixa de cor */
[class*="st-key-card-feature-"] {background: linear-gradient(180deg, #FBFAFF 0%, #FFFFFF 60%); padding: 1.2rem 1.25rem .6rem !important;}
[class*="st-key-card-feature-"] .ac-title {font-size: 1.15rem;}

/* variante prateleira (Deep dives): discreta, secundaria */
[class*="st-key-card-shelf-"] {background: #FCFCFB; box-shadow: none;}
[class*="st-key-card-shelf-"] .ac-title {font-size: .95rem;}
[class*="st-key-card-shelf-"] .ac-desc {font-size: .84rem; -webkit-line-clamp: 2;}
[class*="st-key-card-shelf-"] .ac-logo {flex-basis: 28px; width: 28px; height: 28px; border-radius: 7px;}

/* variante bloco de leitura (Quick knowledge) */
[class*="st-key-card-tile-"] {background: #FFFDF7; border-color: #F1E9D8 !important;}
[class*="st-key-card-tile-"] .ac-head {margin-bottom: .35rem;}
[class*="st-key-card-tile-"] .ac-title {font-size: .98rem;}
[class*="st-key-card-tile-"] .ac-desc {font-size: .86rem;}

/* CAUSA RAIZ da sobreposicao: o stMarkdownContainer do Streamlit tem margin-bottom:-1rem para
   anular a margem do ultimo <p>. Nossos blocos HTML terminam em <div>, entao o -1rem puxava o
   widget seguinte (linha de acoes, "Ver todos") 16px para cima do texto. Zera so nesses blocos. */
[data-testid="stMarkdownContainer"]:has(.ac-grid, .ac-group, .ac-head, .ac-rowwrap, .ac-title, .ac-desc, .ac-rel) {margin-bottom: 0 !important;}

/* ---------- componentes compactos da Home (um bloco HTML, CSS grid, altura pelo conteudo) ---------- */
.ac-ms {font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; line-height: 1;
  letter-spacing: normal; text-transform: none; white-space: nowrap; direction: ltr; font-feature-settings: 'liga';
  -webkit-font-smoothing: antialiased; display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto;}
.ac-grid {display: grid; gap: .75rem; margin: .3rem 0 .4rem;}
/* colunas pela largura REAL do bloco (container query): 3 -> 2 -> 1 e 4 -> 2 -> 1, sem linha orfa */
.ac-cq {container-type: inline-size;}
.ac-grid-3 {grid-template-columns: repeat(3, minmax(0, 1fr));}
.ac-grid-4 {grid-template-columns: repeat(4, minmax(0, 1fr));}
@container (max-width: 900px) {.ac-grid-4 {grid-template-columns: repeat(2, minmax(0, 1fr));}}
@container (max-width: 760px) {.ac-grid-3 {grid-template-columns: repeat(2, minmax(0, 1fr));}}
@container (max-width: 520px) {.ac-grid-3, .ac-grid-4 {grid-template-columns: minmax(0, 1fr);}}
.ac-grid a, .ac-group a {text-decoration: none !important; color: var(--ac-ink) !important; min-width: 0;}
.ac-grid a:focus-visible, .ac-group a:focus-visible {outline: 2px solid var(--ac-accent); outline-offset: 2px;}
.ac-ext {flex: 0 0 auto; color: var(--ac-accent); font-size: .9rem; font-weight: 700; line-height: 1.3;}

/* Make Your Work Easier: card de categoria inteiramente clicavel */
.ac-cat {display: flex; align-items: flex-start; gap: .8rem; padding: .95rem 1.05rem; background: var(--ac-paper);
  border: 1px solid var(--ac-line); border-radius: 12px; transition: border-color .15s ease, box-shadow .15s ease;}
.ac-cat:hover {border-color: #C7D2FE; box-shadow: 0 4px 16px rgba(67,56,202,.08);}
.ac-cat-icon {font-size: 22px; width: 38px; height: 38px; border-radius: 10px; background: #EEF0FF; color: var(--ac-accent);}
.ac-cat-text {display: flex; flex-direction: column; gap: .2rem; min-width: 0;}
.ac-cat-title {font-size: 1rem; font-weight: 650; line-height: 1.3;}
.ac-cat-desc {font-size: .88rem; line-height: 1.42; color: var(--ac-ink-2);}

/* grupos (Tools & Resources, Deep Dives) */
.ac-group {display: flex; flex-direction: column; gap: .3rem; min-width: 0; background: var(--ac-paper);
  border: 1px solid var(--ac-line); border-radius: 12px; padding: .75rem .8rem .45rem;}
.ac-group-wide {margin: .3rem 0 .7rem;}
.ac-ghead {display: flex; align-items: center; gap: .45rem; font-size: .78rem; font-weight: 700; letter-spacing: .05em;
  text-transform: uppercase; color: var(--ac-ink-2); padding: 0 .3rem .15rem;}
.ac-ghead-icon {font-size: 18px; color: var(--ac-accent);}
.ac-list {display: flex; flex-direction: column; min-width: 0;}
.ac-list-2 {display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 340px), 1fr)); column-gap: 1.25rem;}

/* linha de ferramenta: logo, nome, descricao de uma linha, indicador externo */
.ac-trow, .ac-course, .ac-guide {display: flex; gap: .65rem; padding: .55rem .35rem; border-radius: 8px;
  border-top: 1px solid #F1F0EE; transition: background .12s ease;}
.ac-list > a:first-child, .ac-list-2 > a:nth-child(-n+2) {border-top-color: transparent;}
.ac-trow {align-items: center;}
.ac-course, .ac-guide {align-items: flex-start;}
.ac-trow:hover, .ac-course:hover, .ac-guide:hover, .ac-plat:hover {background: #F6F6FB;}
.ac-trow .ac-logo {flex-basis: 30px; width: 30px; height: 30px; border-radius: 8px;}
.ac-trow-text, .ac-course-text, .ac-guide-text {display: flex; flex-direction: column; gap: .08rem; flex: 1; min-width: 0;}
.ac-trow-name, .ac-guide-title, .ac-course-title {font-size: .93rem; font-weight: 650; line-height: 1.35; overflow-wrap: anywhere;}
.ac-trow-desc, .ac-guide-desc {font-size: .84rem; line-height: 1.4; color: var(--ac-ink-2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
.ac-course-meta {font-size: .82rem; line-height: 1.4; color: var(--ac-ink-2);}

/* Learning Platforms: grade compacta de logos e nomes */
.ac-plats {display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 175px), 1fr)); gap: .5rem; padding: .15rem 0 .35rem;}
.ac-plat {display: flex; align-items: center; gap: .55rem; padding: .5rem .6rem; border: 1px solid var(--ac-line);
  border-radius: 10px; transition: background .12s ease;}
.ac-plat .ac-logo {flex-basis: 28px; width: 28px; height: 28px; border-radius: 7px;}
.ac-plat-name {flex: 1; min-width: 0; font-size: .9rem; font-weight: 600; line-height: 1.3; overflow-wrap: anywhere;}

/* Quick Knowledge: colecao compacta (icone, titulo, topicos, numero real de notas) */
.ac-coll {display: flex; flex-direction: column; gap: .3rem; padding: .85rem 1rem; background: #FFFDF7;
  border: 1px solid #F1E9D8; border-radius: 12px; transition: border-color .15s ease, box-shadow .15s ease;}
.ac-coll:hover {border-color: #E5D6B5; box-shadow: 0 4px 16px rgba(28,25,23,.06);}
.ac-coll-head {display: flex; align-items: center; gap: .5rem; min-width: 0;}
.ac-coll-icon {font-size: 20px; color: var(--ac-accent);}
.ac-coll-title {font-size: 1rem; font-weight: 650; line-height: 1.3; min-width: 0;}
.ac-coll-topics {font-size: .86rem; line-height: 1.42; color: var(--ac-ink-2);}
.ac-coll-count {font-size: .8rem; font-weight: 650; color: var(--ac-accent);}

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
