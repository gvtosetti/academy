"""Extracao deterministica das release notes mensais do Azure Databricks.

Nenhum LLM participa: o HTML externo e tratado como DADO NAO CONFIAVEL. O texto e
normalizado, frases com padrao de prompt injection sao neutralizadas e sinalizadas, e
somente links https para dominios oficiais sao mantidos. A UI sempre escapa o texto.

Estrutura esperada (learn.microsoft.com): cada novidade e um <h2 id=...>, seguido de
<p><strong>Month D, YYYY</strong></p> e paragrafos/listas ate o proximo <h2>.
"""
from __future__ import annotations

import hashlib
import html as _html
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Optional
from urllib.parse import urljoin, urlsplit, urlunsplit

OFFICIAL_HOSTS = ("learn.microsoft.com", "docs.databricks.com", "www.databricks.com", "databricks.com",
                  "mlflow.org", "www.mlflow.org")
SKIP_ANCHORS = {"ms--in-this-article", "in-this-article", "feedback", "additional-resources"}
SKIP_TITLES = {"feedback", "additional resources", "in this article", "next steps", "related content"}
MAX_DESC = 1500

# ---- status oficial e tipo de lancamento ----------------------------------
_STATUS_RULES = (
    ("retired", r"\b(is|are|will be|has been|have been)\s+retired\b|\bretirement\b|\bend[- ]of[- ]life\b|\bis retired\b|\bretires\b"),
    ("deprecated", r"\bdeprecat(ed|ion|es)\b"),
    ("ga", r"\bgenerally available\b|\bgeneral availability\b|\(ga\)|\bis now ga\b|\bnow ga\b"),
    ("public_preview", r"\bpublic preview\b"),
    ("private_preview", r"\bprivate preview\b"),
    ("beta", r"\(beta\)|\bin beta\b|\bbeta\b"),
)
STATUS_LABEL = {"ga": "GA", "public_preview": "Public Preview", "private_preview": "Private Preview",
                "beta": "Beta", "retired": "Retired", "deprecated": "Deprecated", "other": "Outro"}
FINAL_STATUSES = {"ga", "retired", "deprecated"}

CHANGE_LABEL = {"new_feature": "Novidade de produto", "status_change": "Mudança de status",
                "behavior_change": "Mudança de comportamento", "improvement": "Melhoria incremental",
                "fix": "Correção", "retirement": "Descontinuação"}

# frases de status removidas do titulo para formar a identidade da funcionalidade
_KEY_NOISE = (
    r"\((?:beta|public preview|private preview|ga|generally available|preview)\)",
    r"\b(?:is|are)\s+now\s+(?:generally available|available|in public preview|in private preview|in beta|ga|supported)\b.*$",
    r"\b(?:is|are)\s+(?:generally available|available|in public preview|in private preview|in beta|retired|deprecated)\b.*$",
    r"\bnow\s+(?:generally available|available|in public preview|in beta|ga)\b.*$",
    r"\bwill\s+be\s+(?:retired|deprecated|removed)\b.*$",
    r"\bgenerally available\b", r"\bpublic preview\b", r"\bprivate preview\b",
    r"^(?:new|introducing|announcing)\s+",
)

# ---- prompt injection ------------------------------------------------------
_INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\s+(instructions|prompts?|rules)"
    r"|\b(system|developer)\s+prompt\b|\byou\s+are\s+now\b|\bact\s+as\s+(an?\s+)?(ai|assistant|admin)"
    r"|\bnew\s+instructions\s*:|\b(assistant|system)\s*:\s|<\s*/?\s*(script|iframe|object)\b|javascript:",
    re.I)
_ZERO_WIDTH = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")


def sanitize(text: str, limit: int = MAX_DESC) -> tuple[str, bool]:
    """Texto plano, sem controles/zero-width; frases de injection viram [removido]."""
    t = _ZERO_WIDTH.sub("", text or "")
    t = "".join(ch for ch in t if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    flagged = bool(_INJECTION.search(t))
    if flagged:
        t = _INJECTION.sub("[removido]", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t, flagged


def strip_tags(fragment: str) -> str:
    f = re.sub(r"(?is)<(script|style|noscript|template)[^>]*>.*?</\1>", " ", fragment)
    f = re.sub(r"(?i)<\s*li[^>]*>", "\n- ", f)
    f = re.sub(r"(?i)</\s*(p|li|ul|ol|div|h\d|tr)\s*>|<br\s*/?>", "\n", f)
    f = re.sub(r"<[^>]+>", "", f)
    return _html.unescape(f)


def detect_status(title: str, body: str = "") -> str:
    for text in (title.lower(), body.lower()):
        for status, rx in _STATUS_RULES:
            if re.search(rx, text):
                return status
    return "other"


def detect_change_type(title: str, body: str, status: str) -> str:
    t, b = title.lower(), body.lower()
    if status in ("retired", "deprecated") or re.search(r"\bwill be removed\b|\bend of support\b", t):
        return "retirement"
    if re.search(r"\b(fix|fixed|fixes|resolved|bug)\b", t):
        return "fix"
    if status == "ga" and re.search(r"generally available|general availability|\bga\b", t):
        return "status_change"
    if re.search(r"\b(behavior change|breaking change|no longer|by default|default (is|will)|changes? to|will change|now require)", t + " " + b[:400]):
        return "behavior_change"
    if status in ("public_preview", "private_preview", "beta") or re.search(r"^(new|introducing|announcing)\b", t):
        return "new_feature"
    if re.search(r"\b(improved|improvement|faster|now supports?|support for|enhanced|increased|expanded)\b", t):
        return "improvement"
    return "new_feature" if re.search(r"\bnew\b", t) else "improvement"


def feature_key(title: str) -> str:
    """Identidade estavel da funcionalidade: o mesmo recurso em preview e em GA gera a mesma chave."""
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    for rx in _KEY_NOISE:
        t = re.sub(rx, " ", t)
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:90] or "feature"


def canonical(url: str, keep_fragment: bool = True) -> str:
    p = urlsplit(url)
    path = re.sub(r"/+$", "", p.path) or "/"
    return urlunsplit(("https", (p.hostname or "").lower(), path, "", p.fragment if keep_fragment else ""))


def official(url: str) -> bool:
    p = urlsplit(url)
    return p.scheme == "https" and (p.hostname or "").lower() in OFFICIAL_HOSTS


def _parse_date(text: str) -> Optional[date]:
    m = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})", text)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
    except ValueError:
        return None


_AVAIL = re.compile(r"\b(region|regions|available (in|on|for)|requires?|only|not (yet )?supported|limitation|limited|"
                    r"workspace admin|account admin|enable|opt[- ]in|preview|premium|pricing|quota)\b", re.I)


def availability_notes(text: str, status: str) -> list[str]:
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n", text) if s.strip()]
    out = [s for s in sents if _AVAIL.search(s)][:4]
    if status in ("public_preview", "private_preview", "beta"):
        out.append("Recurso em prévia: pode exigir habilitação, não estar disponível em todas as regiões/planos e mudar "
                   "antes do GA. Não presuma que esteja ativo no seu workspace.")
    return out


@dataclass
class ReleaseItem:
    key: str
    title: str
    url: str               # URL canonica com ancora da novidade
    period: str            # YYYY-MM da pagina consultada
    announced_on: Optional[str]
    date_uncertain: bool
    status: str
    change_type: str
    description: str
    links: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    injection_flag: bool = False
    source: str = "release-notes"
    content_hash: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_release_notes(html: str, page_url: str, period_key: str) -> list[ReleaseItem]:
    main_at = html.find("<main")
    body = html[main_at:] if main_at >= 0 else html
    heads = list(re.finditer(r'<h2[^>]*\bid="([^"]+)"[^>]*>(.*?)</h2>', body, re.S | re.I))
    items: list[ReleaseItem] = []
    seen: set[str] = set()
    for i, h in enumerate(heads):
        anchor = h.group(1)
        if anchor in SKIP_ANCHORS:
            continue
        end = heads[i + 1].start() if i + 1 < len(heads) else len(body)
        chunk = body[h.end():end]
        stop = re.search(r'(?is)<(footer|aside)\b|<div[^>]+class="[^"]*(feedback|page-metadata)', chunk)
        if stop:
            chunk = chunk[:stop.start()]
        title, t_flag = sanitize(strip_tags(h.group(2)).strip(), 300)
        if not title or title.lower().strip(" :") in SKIP_TITLES or anchor.lower().endswith(("feedback", "additional-resources")):
            continue
        text = strip_tags(chunk)
        announced = _parse_date(text[:200])
        if announced:  # remove a linha de data do corpo
            text = re.sub(r"^\s*(January|February|March|April|May|June|July|August|September|October|November|"
                          r"December)\s+\d{1,2},\s+\d{4}\s*", "", text.strip(), count=1)
        desc, d_flag = sanitize(text)
        links = []
        for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', chunk, re.S | re.I):
            href = urljoin(page_url, _html.unescape(m.group(1)))
            if official(href):
                label, _ = sanitize(strip_tags(m.group(2)), 120)
                u = canonical(href)
                if u not in {l["url"] for l in links}:
                    links.append({"label": label or "Documentação oficial", "url": u})
        status = detect_status(title, desc)
        url = canonical(f"{page_url}#{anchor}")
        if url in seen:
            continue
        seen.add(url)
        items.append(ReleaseItem(
            key=feature_key(title), title=title, url=url, period=period_key,
            announced_on=announced.isoformat() if announced else None, date_uncertain=announced is None,
            status=status, change_type=detect_change_type(title, desc, status), description=desc,
            links=links[:6], limitations=availability_notes(desc, status), injection_flag=t_flag or d_flag,
            content_hash=hashlib.sha1(f"{title}\n{desc}".encode()).hexdigest()[:16],
        ))
    return items


def parse_rss_titles(xml: str) -> list[dict]:
    """Itens de um feed RSS (blog oficial): titulo, link e data. Usado so como evidencia complementar."""
    out = []
    for m in re.finditer(r"(?is)<item\b.*?</item>", xml):
        it = m.group(0)
        t = re.search(r"(?is)<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it)
        l = re.search(r"(?is)<link>(.*?)</link>", it)
        d = re.search(r"(?is)<pubDate>(.*?)</pubDate>", it)
        if t and l:
            title, _ = sanitize(strip_tags(t.group(1)), 300)
            link = _html.unescape(l.group(1).strip())
            if official(link):
                out.append({"title": title, "url": canonical(link, keep_fragment=False),
                            "date": (d.group(1).strip() if d else None)})
    return out[:200]
