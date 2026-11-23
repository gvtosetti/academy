"""Persistencia do Release Watch: candidatos (com historico), execucoes e cache de fontes.

Backends (mesma politica do repository.py):
- Delta em Unity Catalog via SQL warehouse: `RELEASE_WATCH_TABLE_PREFIX` (ex. `main.academy.release_watch`)
  + `DATABRICKS_WAREHOUSE_ID`. Cria `<prefix>_candidates`, `<prefix>_runs`, `<prefix>_cache`.
  Todas as gravacoes usam parametros nomeados (sem interpolar texto externo no SQL).
- SQLite em `RELEASE_WATCH_SQLITE_PATH` (ou /tmp em ACADEMY_ENV=dev): testes e desenvolvimento.
- Desabilitado: o app continua funcionando; o Release Watch mostra o motivo.

Cada candidato e um dict JSON com colunas indexadas (key, url, period, review_status).
Upserts sao idempotentes pela chave da funcionalidade.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from services.config import is_dev, setting

log = logging.getLogger("academy.release_watch.store")
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
_IDENT = re.compile(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+$")


class StoreError(Exception):
    pass


class BaseStore:
    durable = False
    enabled = True
    warning: Optional[str] = None

    # candidatos
    def get(self, key: str) -> Optional[dict]: ...
    def find_by_url(self, url: str) -> Optional[dict]: ...
    def upsert(self, cand: dict) -> None: ...
    def list(self, *, period: Optional[str] = None, review_status: Optional[str] = None) -> list[dict]: ...
    # execucoes
    def save_run(self, run: dict) -> None: ...
    def runs(self, limit: int = 20) -> list[dict]: ...
    # cache
    def cache_get(self, url: str) -> Optional[dict]: ...
    def cache_put(self, url: str, body: str, sha: str, status: int) -> None: ...

    def last_run(self, *, mode: Optional[str] = None, ok_only: bool = False) -> Optional[dict]:
        for r in self.runs(200):
            if (mode is None or r.get("mode") == mode or mode in (r.get("effective_modes") or [])) and \
                    (not ok_only or r.get("status") in ("ok", "partial")):
                return r
        return None


class DisabledStore(BaseStore):
    enabled = False

    def __init__(self, warning: str):
        self.warning = warning

    def _err(self, *a, **k):
        raise StoreError(self.warning)

    get = find_by_url = upsert = save_run = cache_put = _err

    def list(self, **k):
        return []

    def runs(self, limit: int = 20):
        return []

    def cache_get(self, url: str):
        return None


class SQLiteStore(BaseStore):
    durable = False
    warning = "Release Watch em SQLite local (desenvolvimento/testes): nao e duravel em producao."

    def __init__(self, path: Path | str):
        self.path = str(path)
        db = self._db()
        db.executescript("""
        create table if not exists rw_candidates (key text primary key, url text, period text, review_status text,
            updated_at text, data_json text not null);
        create index if not exists rw_cand_url on rw_candidates(url);
        create table if not exists rw_runs (run_id text primary key, started_at text, data_json text not null);
        create table if not exists rw_cache (url text primary key, fetched_at text, sha text, status integer, body text);
        """)
        db.commit(); db.close()

    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def get(self, key):
        db = self._db(); r = db.execute("select data_json from rw_candidates where key=?", [key]).fetchone(); db.close()
        return json.loads(r[0]) if r else None

    def find_by_url(self, url):
        db = self._db(); r = db.execute("select data_json from rw_candidates where url=?", [url]).fetchone(); db.close()
        return json.loads(r[0]) if r else None

    def upsert(self, cand):
        db = self._db()
        db.execute("insert into rw_candidates values (?,?,?,?,?,?) on conflict(key) do update set url=excluded.url, "
                   "period=excluded.period, review_status=excluded.review_status, updated_at=excluded.updated_at, "
                   "data_json=excluded.data_json",
                   [cand["key"], cand["url"], cand["period"], cand["review_status"], NOW(), json.dumps(cand, ensure_ascii=False)])
        db.commit(); db.close()

    def list(self, *, period=None, review_status=None):
        db = self._db()
        rows = db.execute("select data_json from rw_candidates where (? is null or period=?) and (? is null or review_status=?) "
                          "order by period desc, updated_at desc", [period, period, review_status, review_status]).fetchall()
        db.close()
        return [json.loads(r[0]) for r in rows]

    def save_run(self, run):
        db = self._db()
        db.execute("insert or replace into rw_runs values (?,?,?)", [run["run_id"], run["started_at"], json.dumps(run, ensure_ascii=False)])
        db.commit(); db.close()

    def runs(self, limit=20):
        db = self._db(); rows = db.execute("select data_json from rw_runs order by started_at desc limit ?", [limit]).fetchall(); db.close()
        return [json.loads(r[0]) for r in rows]

    def cache_get(self, url):
        db = self._db(); r = db.execute("select * from rw_cache where url=?", [url]).fetchone(); db.close()
        return dict(r) if r else None

    def cache_put(self, url, body, sha, status):
        db = self._db()
        db.execute("insert or replace into rw_cache values (?,?,?,?,?)", [url, NOW(), sha, status, body])
        db.commit(); db.close()


class DeltaStore(BaseStore):
    """Tabelas Delta via SQL warehouse (Statement Execution API) com parametros nomeados."""

    durable = True

    def __init__(self, prefix: str, warehouse_id: str, client=None):
        if not _IDENT.match(prefix or ""):
            raise StoreError("RELEASE_WATCH_TABLE_PREFIX deve ter o formato catalogo.schema.prefixo.")
        self.prefix, self.warehouse_id = prefix, warehouse_id
        if client is None:
            try:
                from databricks.sdk import WorkspaceClient
                client = WorkspaceClient()
            except Exception as exc:
                raise StoreError(f"Credenciais Databricks indisponiveis ({type(exc).__name__}).") from None
        self.w = client
        self.t_cand, self.t_runs, self.t_cache = f"{prefix}_candidates", f"{prefix}_runs", f"{prefix}_cache"
        self._sql(f"create table if not exists {self.t_cand} (key string, url string, period string, review_status string, "
                  f"updated_at timestamp, data_json string) using delta")
        self._sql(f"create table if not exists {self.t_runs} (run_id string, started_at string, data_json string) using delta")
        self._sql(f"create table if not exists {self.t_cache} (url string, fetched_at timestamp, sha string, status int, body string) using delta")

    def _sql(self, statement: str, params: Optional[dict] = None):
        from databricks.sdk.service.sql import StatementParameterListItem, StatementState

        plist = [StatementParameterListItem(name=k, value=None if v is None else str(v)) for k, v in (params or {}).items()]
        try:
            res = self.w.statement_execution.execute_statement(statement=statement, warehouse_id=self.warehouse_id,
                                                               parameters=plist or None, wait_timeout="50s")
        except Exception as exc:
            raise StoreError(f"Falha no SQL warehouse ({type(exc).__name__}).") from None
        state = res.status.state if res.status else None
        if state not in (StatementState.SUCCEEDED,):
            msg = res.status.error.message if res.status and res.status.error else str(state)
            raise StoreError(f"SQL nao concluido: {msg[:300]}")
        return [list(r) for r in (res.result.data_array or [])] if res.result else []

    def get(self, key):
        rows = self._sql(f"select data_json from {self.t_cand} where key = :k limit 1", {"k": key})
        return json.loads(rows[0][0]) if rows else None

    def find_by_url(self, url):
        rows = self._sql(f"select data_json from {self.t_cand} where url = :u limit 1", {"u": url})
        return json.loads(rows[0][0]) if rows else None

    def upsert(self, cand):
        self._sql(
            f"merge into {self.t_cand} t using (select :k as key, :u as url, :p as period, :r as review_status, "
            f"current_timestamp() as updated_at, :d as data_json) s on t.key = s.key "
            f"when matched then update set * when not matched then insert *",
            {"k": cand["key"], "u": cand["url"], "p": cand["period"], "r": cand["review_status"],
             "d": json.dumps(cand, ensure_ascii=False)})

    def list(self, *, period=None, review_status=None):
        rows = self._sql(
            f"select data_json from {self.t_cand} where (:p is null or period = :p) and (:r is null or review_status = :r) "
            f"order by period desc, updated_at desc limit 2000", {"p": period, "r": review_status})
        return [json.loads(r[0]) for r in rows]

    def save_run(self, run):
        self._sql(f"merge into {self.t_runs} t using (select :i as run_id, :s as started_at, :d as data_json) s "
                  f"on t.run_id = s.run_id when matched then update set * when not matched then insert *",
                  {"i": run["run_id"], "s": run["started_at"], "d": json.dumps(run, ensure_ascii=False)})

    def runs(self, limit=20):
        rows = self._sql(f"select data_json from {self.t_runs} order by started_at desc limit {int(limit)}")
        return [json.loads(r[0]) for r in rows]

    def cache_get(self, url):
        rows = self._sql(f"select url, cast(fetched_at as string), sha, status, body from {self.t_cache} where url = :u limit 1", {"u": url})
        if not rows:
            return None
        u, fa, sha, st, body = rows[0]
        return {"url": u, "fetched_at": fa, "sha": sha, "status": int(st or 0), "body": body}

    def cache_put(self, url, body, sha, status):
        self._sql(f"merge into {self.t_cache} t using (select :u as url, current_timestamp() as fetched_at, :s as sha, "
                  f"cast(:c as int) as status, :b as body) s on t.url = s.url "
                  f"when matched then update set * when not matched then insert *",
                  {"u": url, "s": sha, "c": status, "b": body})


_STORE: Optional[BaseStore] = None


def get_store(refresh: bool = False) -> BaseStore:
    global _STORE
    if _STORE is not None and not refresh:
        return _STORE
    prefix, wh = setting("RELEASE_WATCH_TABLE_PREFIX"), setting("DATABRICKS_WAREHOUSE_ID")
    store: BaseStore
    if prefix and wh:
        try:
            store = DeltaStore(prefix, wh)
        except StoreError as exc:
            store = DisabledStore(str(exc))
    elif setting("RELEASE_WATCH_SQLITE_PATH") or is_dev():
        store = SQLiteStore(setting("RELEASE_WATCH_SQLITE_PATH") or "/tmp/academy_release_watch.db")
    else:
        store = DisabledStore("Release Watch sem persistencia: defina RELEASE_WATCH_TABLE_PREFIX e DATABRICKS_WAREHOUSE_ID.")
    _STORE = store
    return store


def set_store(store: Optional[BaseStore]) -> None:
    """Injecao para testes e para o job."""
    global _STORE
    _STORE = store
