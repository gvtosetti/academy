"""Salvaguardas de renderizacao: URLs e HTML.

Regra: todo texto vindo do catalogo ou de APIs externas que entra em HTML
customizado passa por `esc()`. Markdown externo (ex.: README do GitHub) e
renderizado SEM unsafe_allow_html e sem tags HTML cruas.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"https"}


def esc(text: object) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def is_safe_url(url: str | None) -> bool:
    """Aceita apenas URLs https absolutas com host."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    return parsed.scheme in ALLOWED_SCHEMES and bool(parsed.netloc) and " " not in url


_HTML_TAG = re.compile(r"<[^>]+>")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def sanitize_markdown(md: str, max_chars: int = 6000) -> str:
    """Remove HTML cru e imagens de um markdown externo e limita o tamanho.

    Exibimos apenas um trecho (excerpt) com atribuicao, nunca o conteudo integral.
    """
    if not md:
        return ""
    text = _HTML_COMMENT.sub("", md)
    text = _HTML_TAG.sub("", text)
    text = _MD_IMAGE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        # evita cortar no meio de um bloco de codigo
        if cut.count("```") % 2 == 1:
            cut = cut[: cut.rfind("```")]
        text = cut.rstrip() + "\n\n*[… trecho truncado — leia o README completo no GitHub]*"
    return text
