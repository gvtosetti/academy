"""Execucao do Release Watch: planeja periodos (UTC), busca fontes com cache, extrai,
classifica, deduplica e registra a execucao. Nunca publica nada: so gera candidatos.

Idempotente: reexecutar o mesmo periodo nao cria registros novos nem reescreve os
inalterados; so ha gravacao quando surge algo novo ou a fonte muda.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from collections import Counter
from datetime import datetime
from typing import Optional

from services.release_watch.classify import classify
from services.release_watch.parser import FINAL_STATUSES, ReleaseItem, parse_release_notes, parse_rss_titles
from services.release_watch.periods import Target, current_period, plan, to_utc
from services.release_watch.store import BaseStore, StoreError, get_store

log = logging.getLogger("academy.release_watch")
BLOG_FEED = "https://www.databricks.com/feed"
RETRY_STATUS = {429, 500, 502, 503, 504}
PERMANENT_CODES = {"invalid_url", "blocked_url", "blocked_scheme", "robots_disallowed", "robots", "dns_failed",
                   "content_type", "too_large"}
CACHE_MAX_AGE_DAYS = 45


# ---- busca com retry e cache ------------------------------------------------
def fetch_with_cache(fetcher, store: BaseStore, url: str, *, retries: int = 2, sleep=time.sleep) -> dict:
    """Retorna {outcome, body, http_status, from_cache, error}. outcome: ok|cached|not_published|failed."""
    from services.ingest.net import FetchError

    last_err: Optional[str] = None
    status: Optional[int] = None
    for attempt in range(retries + 1):
        try:
            res = fetcher.get(url, accept_status=(200,))
            body = res.text or ""
            sha = hashlib.sha1(body.encode()).hexdigest()
            try:
                store.cache_put(url, body, sha, res.status)
            except StoreError as exc:
                log.warning("cache_put failed: %s", exc)
            return {"outcome": "ok", "body": body, "http_status": res.status, "from_cache": False, "error": None, "sha": sha}
        except FetchError as exc:
            status, last_err = exc.status, f"{exc.code}: {exc.message}"
            if status == 404:
                return {"outcome": "not_published", "body": "", "http_status": 404, "from_cache": False,
                        "error": None, "sha": None}
            transient = (status in RETRY_STATUS) or (status is None and exc.code not in PERMANENT_CODES)
            if not transient or attempt == retries:
                break
            sleep(min(2 ** attempt, 8))
        except Exception as exc:  # falha inesperada de rede: registra e segue com o cache
            last_err = f"{type(exc).__name__}"
            if attempt == retries:
                break
            sleep(min(2 ** attempt, 8))
    cached = None
    try:
        cached = store.cache_get(url)
    except StoreError:
        cached = None
    if cached and cached.get("body") and _cache_fresh(cached.get("fetched_at")):
        return {"outcome": "cached", "body": cached["body"], "http_status": status, "from_cache": True,
                "error": last_err, "sha": cached.get("sha")}
    return {"outcome": "failed", "body": "", "http_status": status, "from_cache": False, "error": last_err, "sha": None}


def _cache_fresh(ts: Optional[str]) -> bool:
    if not ts:
        return False
    try:
        dt = to_utc(datetime.fromisoformat(str(ts).replace("Z", "+00:00").replace(" ", "T")))
    except ValueError:
        return False
    return (to_utc() - dt).days <= CACHE_MAX_AGE_DAYS


# ---- candidato e merge ------------------------------------------------------
def _classified_fields(item: ReleaseItem, catalog) -> dict:
    res = list(catalog.resources.values()) if catalog is not None else []
    c = classify(item.title, item.description, item.status, item.change_type,
                 taxonomy=getattr(catalog, "taxonomy", None), resource_ids={r.id for r in res}, resources=res,
                 links=item.links)
    return {"areas": c.areas, "library_areas": c.library_areas, "relevance": c.relevance,
            "relevance_label": c.relevance_label, "suggested_subcategory": c.suggested_subcategory,
            "use_cases": c.use_cases, "related_resources": c.related_resources, "note_suggested": c.note_suggested}


def _hist_entry(item: ReleaseItem, now: str) -> dict:
    return {"status": item.status, "announced_on": item.announced_on, "url": item.url, "title": item.title,
            "period": item.period, "change_type": item.change_type, "seen_at": now}


def _evidence(item: ReleaseItem) -> list[dict]:
    ev = [{"source": "release-notes", "url": item.url, "title": f"Azure Databricks release notes ({item.period})"}]
    for l in item.links:
        ev.append({"source": "docs", "url": l["url"], "title": l.get("label") or "Documentação oficial"})
    return ev


def new_candidate(item: ReleaseItem, catalog, now: str) -> dict:
    d = item.to_dict()
    d.update(_classified_fields(item, catalog))
    d.update({"history": [_hist_entry(item, now)], "evidence": _evidence(item), "review_status": "pending",
              "duplicate_of": None, "edits": {}, "published": None, "changes": [], "changed_since_review": False,
              "update_of_approved": False, "first_seen": now, "last_seen": now, "reviewed_by": None, "reviewed_at": None})
    return d


def _merge_evidence(c: dict, extra: list[dict]) -> int:
    have = {e["url"] for e in c.get("evidence", [])}
    added = 0
    for e in extra:
        if e["url"] not in have:
            c.setdefault("evidence", []).append(e); have.add(e["url"]); added += 1
    return added


def merge(existing: Optional[dict], item: ReleaseItem, catalog, now: str) -> tuple[dict, str]:
    """Associa o anuncio ao registro existente da mesma funcionalidade, preservando historico.

    change: new | status_changed | updated | unchanged
    """
    if existing is None:
        return new_candidate(item, catalog, now), "new"
    c = dict(existing)
    hist = list(c.get("history") or [])
    known_urls = {h["url"] for h in hist}
    newer = (item.announced_on or "") >= (c.get("announced_on") or "")
    change, summary = "unchanged", ""
    if item.url not in known_urls:  # outro anuncio da mesma funcionalidade (ex.: preview -> GA)
        hist.append(_hist_entry(item, now))
        hist.sort(key=lambda h: (h.get("announced_on") or "", h.get("seen_at") or ""))
        old = c.get("status")
        if newer:
            for k in ("title", "url", "period", "announced_on", "date_uncertain", "change_type",
                      "description", "links", "limitations", "content_hash"):
                c[k] = getattr(item, k)
            c["injection_flag"] = bool(c.get("injection_flag")) or item.injection_flag
            c.update(_classified_fields(item, catalog))
        # status vigente = ultimo status EXPLICITO do historico (anuncio sem status nao rebaixa GA);
        # o historico registra cada anuncio exatamente como publicado
        explicit = [h["status"] for h in hist if h["status"] != "other"]
        c["status"] = explicit[-1] if explicit else "other"
        if old != c["status"]:
            change, summary = "status_changed", f"status: {old} -> {c['status']} ({item.announced_on})"
        elif newer:
            change, summary = "updated", f"novo anúncio em {item.announced_on}"
        else:
            change, summary = "updated", f"anúncio anterior associado ({item.announced_on})"
    elif item.url == c.get("url") and item.content_hash != c.get("content_hash"):
        for k in ("title", "description", "links", "limitations", "content_hash", "announced_on", "date_uncertain"):
            c[k] = getattr(item, k)
        if item.status != c.get("status"):
            change, summary = "status_changed", f"status revisado na fonte: {c.get('status')} -> {item.status}"
            c["status"] = item.status
        else:
            change, summary = "updated", "texto ou links alterados na fonte"
        c["injection_flag"] = bool(c.get("injection_flag")) or item.injection_flag
        c.update(_classified_fields(item, catalog))
    c["history"] = hist
    added = _merge_evidence(c, _evidence(item))
    if change == "unchanged" and added:
        change = "updated"; summary = "nova evidência oficial"
    if change != "unchanged":
        c["last_seen"] = now
        c["changes"] = (c.get("changes") or []) + [{"at": now, "summary": summary}]
        c["changed_since_review"] = c.get("review_status") != "pending"
        if c.get("review_status") == "approved":
            c["review_status"], c["update_of_approved"] = "pending", True  # publicado segue no ar ate nova aprovacao
        elif c.get("review_status") == "dismissed" and change == "status_changed":
            c["review_status"] = "pending"
    return c, change


# ---- fontes complementares -----------------------------------------------------
_STOP = {"the", "and", "for", "with", "now", "new", "in", "on", "of", "to", "a", "an", "is", "are", "databricks", "azure"}


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in _STOP and len(t) > 2}


def attach_blog_evidence(cands: dict[str, dict], posts: list[dict]) -> list[str]:
    """Liga posts do blog oficial a candidatos existentes (nunca cria candidato so com o blog)."""
    touched = []
    for c in cands.values():
        ft = _tokens(c["key"].replace("-", " "))
        if len(ft) < 2:
            continue
        for p in posts:
            pt = _tokens(p["title"])
            inter = ft & pt
            if len(inter) >= 2 and len(inter) / len(ft | pt) >= 0.4:
                if _merge_evidence(c, [{"source": "blog", "url": p["url"], "title": p["title"]}]):
                    touched.append(c["key"])
    return touched


# ---- execucao -------------------------------------------------------------
def _monthly_due(store: BaseStore, cur_key: str) -> bool:
    for r in store.runs(200):
        if r.get("current_period") == cur_key and "monthly" in (r.get("effective_modes") or []) \
                and r.get("status") in ("ok", "partial"):
            return False
    return True


def _summary(cands: list[dict], period: str) -> dict:
    rows = [c for c in cands if c.get("period") == period]
    return {"total": len(rows), "by_status": dict(Counter(c["status"] for c in rows)),
            "by_area": dict(Counter((c.get("areas") or ["?"])[0] for c in rows)),
            "by_review": dict(Counter(c["review_status"] for c in rows)),
            "high_relevance_pending": sum(1 for c in rows if c.get("relevance_label") == "high" and c["review_status"] == "pending")}


def run(mode: str = "auto", *, now: Optional[datetime] = None, store: Optional[BaseStore] = None, fetcher=None,
        catalog=None, triggered_by: str = "schedule", include_blog: bool = True) -> dict:
    store = store or get_store()
    if not store.enabled:
        raise StoreError(store.warning or "Release Watch sem persistencia.")
    if fetcher is None:
        from services.ingest.net import SafeFetcher
        fetcher = SafeFetcher(max_bytes=3_000_000)
    if catalog is None:
        try:
            from services.catalog import load_catalog
            catalog = load_catalog(strict=False)
        except Exception:
            catalog = None
    now_dt = to_utc(now)
    now_s = now_dt.isoformat(timespec="seconds")
    cur = current_period(now_dt)
    all_cands = {c["key"]: c for c in store.list()}
    by_url = {c["url"]: c["key"] for c in all_cands.values()}
    for c in all_cands.values():
        for h in c.get("history") or []:
            by_url.setdefault(h["url"], c["key"])
    monthly_due = mode == "monthly" or (mode == "auto" and _monthly_due(store, cur.key))
    history = [c["period"] for c in all_cands.values()
               if c.get("status") not in FINAL_STATUSES and c.get("review_status") in ("pending", "approved")]
    targets: list[Target] = plan(mode, now_dt, monthly_due=monthly_due, history=history)
    effective = ["weekly"] if mode in ("auto", "weekly") else [mode]
    if monthly_due and "monthly" not in effective:
        effective.append("monthly")
    if any(t.role == "history" for t in targets) and "revalidate" not in effective:
        effective.append("revalidate")
    report = {"run_id": f"{now_s}-{mode}-{uuid.uuid4().hex[:6]}", "mode": mode, "effective_modes": effective,
              "current_period": cur.key, "triggered_by": triggered_by, "started_at": now_s, "finished_at": None,
              "status": "running", "sources": [], "stats": Counter(), "errors": []}
    dirty: dict[str, dict] = {}
    ok_sources = 0
    for t in targets:
        url = t.period.url
        res = fetch_with_cache(fetcher, store, url)
        src = {"url": url, "role": t.role, "period": t.period.key, "outcome": res["outcome"],
               "http_status": res["http_status"], "from_cache": res["from_cache"], "items": 0, "error": res["error"]}
        if res["outcome"] in ("ok", "cached"):
            try:
                items = parse_release_notes(res["body"], url, t.period.key)
            except Exception as exc:
                items = []
                src["outcome"], src["error"] = "failed", f"parse: {type(exc).__name__}"
            src["items"] = len(items)
            if items:
                ok_sources += 1
            elif src["outcome"] != "failed":
                src["error"] = "Nenhuma novidade reconhecida na página (estrutura pode ter mudado)."
            for item in items:
                key = by_url.get(item.url) or (item.key if item.key in all_cands else None)
                existing = all_cands.get(key) if key else None
                cand, change = merge(existing, item, catalog, now_s)
                report["stats"][change] += 1
                if change != "unchanged":
                    all_cands[cand["key"]] = cand
                    dirty[cand["key"]] = cand
                    by_url[cand["url"]] = cand["key"]
                if item.injection_flag:
                    report["stats"]["injection_flagged"] += 1
        elif res["outcome"] == "not_published":
            ok_sources += 1  # mes ainda sem pagina: nao e falha
        if res["error"]:
            report["errors"].append(f"{t.period.key} ({t.role}): {res['error']}")
        report["sources"].append(src)
    if include_blog:
        res = fetch_with_cache(fetcher, store, BLOG_FEED, retries=1)
        src = {"url": BLOG_FEED, "role": "complementary", "period": None, "outcome": res["outcome"],
               "http_status": res["http_status"], "from_cache": res["from_cache"], "items": 0, "error": res["error"]}
        if res["outcome"] in ("ok", "cached"):
            posts = parse_rss_titles(res["body"])
            src["items"] = len(posts)
            recent = {k: c for k, c in all_cands.items() if c.get("period") in {t.period.key for t in targets}}
            for k in attach_blog_evidence(recent, posts):
                dirty[k] = all_cands[k]
                report["stats"]["evidence_added"] += 1
        elif res["error"]:
            report["errors"].append(f"blog: {res['error']}")
        report["sources"].append(src)
    for cand in dirty.values():
        try:
            store.upsert(cand)
        except StoreError as exc:
            report["errors"].append(f"upsert {cand['key']}: {exc}")
    if "monthly" in effective:
        cands = list(all_cands.values())
        report["monthly_summary"] = {t.period.key: _summary(cands, t.period.key) for t in targets if t.role in ("current", "previous")}
    primary = [s for s in report["sources"] if s["role"] != "complementary"]
    failed = [s for s in primary if s["outcome"] == "failed"]
    report["status"] = "failed" if primary and len(failed) == len(primary) else "partial" if (failed or report["errors"]) else "ok"
    report["stats"] = dict(report["stats"])
    report["finished_at"] = to_utc().isoformat(timespec="seconds")
    try:
        store.save_run(report)
    except StoreError as exc:
        report["errors"].append(f"save_run: {exc}")
    log.info("release watch %s: %s %s", report["run_id"], report["status"], report["stats"])
    return report
