"""Revisao editorial do Release Watch: aprovar, editar, descartar, marcar duplicata e
sobrepor ao catalogo SOMENTE o que foi aprovado.

Aprovar grava um snapshot (`published`) no candidato. Uma novidade pode:
- criar um recurso novo na secao/subcategoria escolhida; ou
- atualizar um recurso existente (status, data, historico e link oficial), sem duplicar;
- opcionalmente gerar uma nota tecnica (Quick Knowledge) relacionada.
Se a fonte muda depois da aprovacao, o snapshot continua no ar ate nova aprovacao.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Optional

from services.release_watch.parser import STATUS_LABEL
from services.release_watch.store import BaseStore, StoreError, get_store

log = logging.getLogger("academy.release_watch.publish")
TAGLINE_MAX, BLURB_MAX = 125, 260
EDITABLE = ("title", "tagline", "description", "subcategory", "library_areas", "target_resource", "create_note")


def _cut(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= n:
        return text
    return text[: n - 1].rsplit(" ", 1)[0].rstrip(",.;:") + "…"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:70] or "release"


def effective(c: dict) -> dict:
    """Valores do candidato com as edicoes editoriais aplicadas por cima."""
    e = c.get("edits") or {}
    first_sentence = re.split(r"(?<=[.!?])\s", c.get("description") or "", maxsplit=1)[0]
    return {
        "title": e.get("title") or c["title"],
        "tagline": e.get("tagline") or _cut(first_sentence or c["title"], TAGLINE_MAX),
        "description": e.get("description") or c.get("description") or "",
        "subcategory": e.get("subcategory") or c.get("suggested_subcategory") or "ai-data-tools",
        "library_areas": e.get("library_areas") or c.get("library_areas") or ["data-engineering"],
        "target_resource": e.get("target_resource", (c.get("related_resources") or [None])[0] if c.get("update_target_suggested") else None),
        "create_note": e.get("create_note", bool(c.get("note_suggested"))),
    }


def release_events(c: dict) -> list[dict]:
    return [{"status": h["status"], "announced_on": h["announced_on"], "url": h["url"], "title": h.get("title", "")}
            for h in (c.get("history") or []) if h.get("announced_on")]


def build_payload(c: dict, catalog=None) -> dict:
    v = effective(c)
    today = date.today().isoformat()
    note = None
    target = v["target_resource"] if v["target_resource"] and (catalog is None or v["target_resource"] in catalog.resources) else None
    rid = target or f"dbx-{_slug(c['key'])}"
    if v["create_note"] and len(v["description"]) >= 120:
        lim = "\n".join(f"- {x}" for x in c.get("limitations") or [])
        body = v["description"] + (f"\n\n**Disponibilidade e limitações**\n{lim}" if lim else "") + \
            f"\n\nStatus anunciado: {STATUS_LABEL.get(c['status'], c['status'])} em {c.get('announced_on') or 'data não informada'}."
        note = {"id": f"dbx-note-{_slug(c['key'])}"[:80], "kind": "explainer", "title": _cut(v["title"], 110),
                "summary": v["tagline"], "body": body, "areas": v["library_areas"],
                "tags": ["databricks", "release notes", STATUS_LABEL.get(c["status"], c["status"]).lower()],
                "related_resources": [rid]}
    release = {"release_status": c["status"], "announced_on": c.get("announced_on"), "release_history": release_events(c),
               "official_url": c["url"]}
    if target:
        return {"mode": "update", "target": target, "release": release, "note": note, "approved_on": today}
    resource = {
        "id": rid, "title": v["title"], "url": c["url"], "provider": "Databricks", "type": "documentation",
        "category": "data-platforms", "difficulty": None, "language": "en", "areas": v["library_areas"],
        "tagline": v["tagline"], "blurb": _cut(v["description"], BLURB_MAX), "short_description": v["tagline"],
        "technical_explanation": v["description"], "considerations": list(c.get("limitations") or []),
        "editorial_subcategory": v["subcategory"], "use_cases": list(c.get("use_cases") or []),
        "related_resources": [r for r in c.get("related_resources") or [] if r != rid],
        "tags": ["databricks", "azure databricks", "release notes", STATUS_LABEL.get(c["status"], c["status"]).lower()],
        "added_on": (c.get("announced_on") or today), "icon_org": "databricks",
        "links": [{"label": e.get("title") or "Fonte oficial", "url": e["url"]} for e in (c.get("evidence") or [])
                  if e["url"] != c["url"]][:6],
        "source_evidence": [{"label": "Azure Databricks release notes", "url": c["url"]}],
        "verified": {"verified_on": (c.get("last_seen") or today)[:10], "source_title": "Azure Databricks release notes"},
        "metadata_status": "verified" if not c.get("date_uncertain") else "partial",
        "metadata_notes": "Novidade oficial aprovada no Databricks Release Watch. Disponibilidade varia por região, "
                          "plano e configuração do workspace.",
        "release_status": c["status"], "announced_on": c.get("announced_on"), "release_history": release_events(c),
    }
    return {"mode": "new", "resource": resource, "note": note, "approved_on": today}


def _save(store: BaseStore, c: dict) -> None:
    store.upsert(c)


def save_edits(store: BaseStore, key: str, edits: dict, *, by: Optional[str]) -> dict:
    c = store.get(key)
    if not c:
        raise StoreError(f"candidato {key} não encontrado")
    clean = {k: v for k, v in (edits or {}).items() if k in EDITABLE}
    if "tagline" in clean and clean["tagline"]:
        clean["tagline"] = _cut(clean["tagline"], TAGLINE_MAX)
    c["edits"] = {**(c.get("edits") or {}), **clean}
    c["edited_by"] = by
    _save(store, c)
    return c


def approve(store: BaseStore, key: str, *, by: Optional[str], catalog=None, edits: Optional[dict] = None) -> dict:
    from services.config import setting  # noqa: F401  (mantem import leve)
    c = save_edits(store, key, edits or {}, by=by) if edits else store.get(key)
    if not c:
        raise StoreError(f"candidato {key} não encontrado")
    if c.get("review_status") == "duplicate":
        raise StoreError("Candidato marcado como duplicata: desfaça a marcação antes de aprovar.")
    payload = build_payload(c, catalog)
    if catalog is not None:  # valida antes de publicar: nada invalido entra no catalogo
        _validate_payload(payload, catalog)
    from datetime import datetime, timezone
    c.update({"review_status": "approved", "published": payload, "reviewed_by": by,
              "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "changed_since_review": False, "update_of_approved": False})
    _save(store, c)
    return c


def dismiss(store: BaseStore, key: str, *, by: Optional[str], reason: str = "") -> dict:
    c = store.get(key)
    if not c:
        raise StoreError(f"candidato {key} não encontrado")
    from datetime import datetime, timezone
    c.update({"review_status": "dismissed", "dismiss_reason": reason[:300], "reviewed_by": by,
              "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "changed_since_review": False})
    _save(store, c)
    return c


def mark_duplicate(store: BaseStore, key: str, of: str, *, by: Optional[str]) -> dict:
    """`of` e outro candidato (key) ou um recurso do catalogo (resource:<id>). Historicos sao unidos."""
    c = store.get(key)
    if not c:
        raise StoreError(f"candidato {key} não encontrado")
    if of == key:
        raise StoreError("Um candidato não pode ser duplicata de si mesmo.")
    from datetime import datetime, timezone
    if not of.startswith("resource:"):
        main = store.get(of)
        if not main:
            raise StoreError(f"candidato principal {of} não encontrado")
        urls = {h["url"] for h in main.get("history") or []}
        main["history"] = sorted((main.get("history") or []) + [h for h in c.get("history") or [] if h["url"] not in urls],
                                 key=lambda h: (h.get("announced_on") or "", h.get("seen_at") or ""))
        ev = {e["url"] for e in main.get("evidence") or []}
        main["evidence"] = (main.get("evidence") or []) + [e for e in c.get("evidence") or [] if e["url"] not in ev]
        _save(store, main)
    c.update({"review_status": "duplicate", "duplicate_of": of, "published": None, "reviewed_by": by,
              "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    _save(store, c)
    return c


def reopen(store: BaseStore, key: str, *, by: Optional[str]) -> dict:
    c = store.get(key)
    if not c:
        raise StoreError(f"candidato {key} não encontrado")
    c.update({"review_status": "pending", "duplicate_of": None, "reviewed_by": by})
    _save(store, c)
    return c


# ---- sobreposicao ao catalogo ---------------------------------------------------
def _apply_release(r, release: dict):
    from services.models import Link, ReleaseEvent

    r.release_status = release.get("release_status")
    r.announced_on = date.fromisoformat(release["announced_on"]) if release.get("announced_on") else None
    r.release_history = [ReleaseEvent(**e) for e in release.get("release_history") or []]
    url = release.get("official_url")
    if url and all(l.url != url for l in r.links):
        r.links = [*r.links, Link(label="Release notes (Azure Databricks)", url=url)]
    return r


def _validate_payload(payload: dict, catalog) -> None:
    from services.models import Resource, Tip

    if payload["mode"] == "new":
        r = Resource(**payload["resource"])
        if r.editorial_subcategory not in catalog.taxonomy.subcategory_ids:
            raise StoreError(f"subcategoria inválida: {r.editorial_subcategory}")
        bad = [a for a in r.areas if a not in catalog.areas]
        if bad:
            raise StoreError(f"áreas inválidas: {bad}")
        if r.id in catalog.resources and not str(r.id).startswith("dbx-"):
            raise StoreError(f"id {r.id} já existe no catálogo")
    elif payload["target"] not in catalog.resources:
        raise StoreError(f"recurso alvo {payload['target']} não existe")
    if payload.get("note"):
        Tip(**payload["note"])


def overlay(cat, store: Optional[BaseStore] = None):
    """Soma ao catalogo apenas os snapshots aprovados. Falhas nunca derrubam o app."""
    try:
        store = store or get_store()
        if not store.enabled:
            return cat
        cands = [c for c in store.list() if c.get("published") and c.get("review_status") not in ("dismissed", "duplicate")]
    except Exception as exc:
        log.info("release watch overlay unavailable: %s", type(exc).__name__)
        return cat
    from services.catalog import _note_from_tip
    from services.models import Resource, Tip

    for c in cands:
        p = c["published"]
        try:
            if p["mode"] == "update":
                r = cat.resources.get(p["target"])
                if r is None:
                    continue
                cat.resources[r.id] = _apply_release(r.model_copy(deep=True), p["release"])
                rid = r.id
            else:
                r = Resource(**p["resource"])
                if r.id in cat.resources and not r.id.startswith("dbx-"):
                    continue  # nunca sobrescreve recurso curado do YAML
                r.areas = [a for a in r.areas if a in cat.areas] or ["data-engineering"]
                if r.editorial_subcategory not in cat.taxonomy.subcategory_ids:
                    r.editorial_subcategory = "ai-data-tools"
                r.use_cases = [u for u in r.use_cases if u in cat.taxonomy.use_case_ids]
                r.related_resources = [x for x in r.related_resources if x in cat.resources]
                cat.resources[r.id] = r
                rid = r.id
            if p.get("note"):
                t = Tip(**{**p["note"], "related_resources": [rid]})
                t.areas = [a for a in t.areas if a in cat.areas] or ["data-engineering"]
                if t.id not in cat.notes:
                    cat.tips[t.id] = t
                    cat.notes[t.id] = _note_from_tip(t)
        except Exception as exc:
            log.warning("release watch item %s skipped: %s", c.get("key"), type(exc).__name__)
    return cat
