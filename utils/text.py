"""Normalizacao de texto para busca local (insensivel a acentos e caixa)."""
from __future__ import annotations

import re
import unicodedata

# Palavras muito comuns em pt-BR/en que nao ajudam na busca.
STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
    "nos", "nas", "um", "uma", "para", "por", "com", "como", "que", "se", "ao",
    "the", "of", "and", "to", "in", "for", "on", "with", "is", "an",
    # formulacoes de problema ("como automatizar uma tarefa?", "how do I validate data")
    "eu", "meu", "minha", "meus", "minhas", "quero", "preciso", "posso", "fazer", "qual", "quais",
    "onde", "sobre", "mais", "how", "i", "my", "can", "what", "which",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    """Remove acentos: 'Generacao' == 'Geração'."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize(text: str | None) -> str:
    """Minusculas, sem acentos e com espacos colapsados."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", strip_accents(str(text)).lower()).strip()


def tokenize(text: str | None, drop_stopwords: bool = True) -> list[str]:
    tokens = _TOKEN_RE.findall(normalize(text))
    if drop_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]
    return tokens
