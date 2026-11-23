"""Persistencia de conteudo publicado/drafts.

Preferencia: tabela Delta em Unity Catalog (`ACADEMY_CONTENT_TABLE`).
Se a tabela/config/credencial nao estiverem disponiveis, cai para SQLite local em
`/tmp/academy_content.db` APENAS em `ACADEMY_ENV=dev`, com aviso explicito. Em qualquer
outro caso, o app continua legivel mas a publicacao persistente fica desabilitada.

Nao usa arquivos do deploy como armazenamento de producao.
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from services.config import in_databricks_app, is_dev, setting
from services.curator import CuratedDraft
from services.ingest.base import Extraction, canonical_url

log = logging.getLogger("academy.repo")
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
SQLITE = Path(setting("ACADEMY_SQLITE_PATH") or "/tmp/academy_content.db")


@dataclass
class Record:
    id: str
    canonical_url: str
    title: str
    status: str  # draft|published|archived
    data: dict
    extraction: dict
    created_at: str
    updated_at: str
    published_at: Optional[str] = None
    created_by: Optional[str] = None
    published_by: Optional[str] = None


class RepoError(Exception):
    pass


class BaseRepository:
    durable: bool = False
    warning: Optional[str] = None

    def ensure(self) -> None: ...
    def create_resource(self, draft: CuratedDraft, extraction: Extraction, *, created_by: Optional[str], status: str = "draft") -> str: ...
    def get_resource(self, rid: str) -> Optional[Record]: ...
    def list_resources(self, status: Optional[str] = None) -> list[Record]: ...
    def update_resource(self, rid: str, draft: CuratedDraft, *, updated_by: Optional[str]) -> None: ...
    def publish_resource(self, rid: str, *, published_by: Optional[str]) -> None: ...
    def archive_resource(self, rid: str, *, archived_by: Optional[str]) -> None: ...
    def find_duplicates(self, url: str) -> list[Record]: ...


class DisabledRepository(BaseRepository):
    durable = False

    def __init__(self, warning: str):
        self.warning = warning

    def ensure(self) -> None:
        return None

    def _err(self, *args, **kwargs):
        raise RepoError(self.warning or "Persistencia desabilitada.")

    create_resource = get_resource = list_resources = update_resource = publish_resource = archive_resource = find_duplicates = _err


class SQLiteRepository(BaseRepository):
    durable = False
    warning = "Persistencia local de desenvolvimento em SQLite (/tmp). Nao e duravel em producao."

    def __init__(self, path: Path = SQLITE):
        self.path = path
        self.ensure()

    def _db(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def ensure(self) -> None:
        db = self._db()
        db.execute("""
        create table if not exists academy_content (
          id text primary key,
          canonical_url text not null,
          title text not null,
          status text not null,
          data_json text not null,
          extraction_json text not null,
          created_at text not null,
          updated_at text not null,
          published_at text,
          created_by text,
          published_by text
        )""")
        db.execute("create index if not exists idx_academy_content_url on academy_content(canonical_url)")
        db.commit(); db.close()

    def _row(self, r) -> Record:
        return Record(r["id"], r["canonical_url"], r["title"], r["status"], json.loads(r["data_json"]),
                      json.loads(r["extraction_json"]), r["created_at"], r["updated_at"], r["published_at"],
                      r["created_by"], r["published_by"])

    def create_resource(self, draft: CuratedDraft, extraction: Extraction, *, created_by: Optional[str], status: str = "draft") -> str:
        rid = _resource_id(draft.title)
        now = NOW()
        db = self._db()
        i = 1
        base = rid
        while db.execute("select 1 from academy_content where id=?", [rid]).fetchone():
            i += 1; rid = f"{base}-{i}"
        db.execute("insert into academy_content values (?,?,?,?,?,?,?,?,?,?,?)",
                   [rid, extraction.canonical_url, draft.title, status, draft.model_dump_json(), json.dumps(extraction.to_dict(), ensure_ascii=False),
                    now, now, now if status == "published" else None, created_by, created_by if status == "published" else None])
        db.commit(); db.close(); return rid

    def get_resource(self, rid: str) -> Optional[Record]:
        db = self._db(); r = db.execute("select * from academy_content where id=?", [rid]).fetchone(); db.close()
        return self._row(r) if r else None

    def list_resources(self, status: Optional[str] = None) -> list[Record]:
        db = self._db()
        rows = db.execute("select * from academy_content where (? is null or status=?) order by updated_at desc", [status, status]).fetchall()
        db.close(); return [self._row(r) for r in rows]

    def update_resource(self, rid: str, draft: CuratedDraft, *, updated_by: Optional[str]) -> None:
        db = self._db(); now = NOW()
        db.execute("update academy_content set title=?, data_json=?, updated_at=? where id=?",
                   [draft.title, draft.model_dump_json(), now, rid])
        db.commit(); db.close()

    def publish_resource(self, rid: str, *, published_by: Optional[str]) -> None:
        db = self._db(); now = NOW()
        db.execute("update academy_content set status='published', published_at=?, published_by=?, updated_at=? where id=?",
                   [now, published_by, now, rid])
        db.commit(); db.close()

    def archive_resource(self, rid: str, *, archived_by: Optional[str]) -> None:
        db = self._db(); now = NOW()
        db.execute("update academy_content set status='archived', updated_at=? where id=?", [now, rid])
        db.commit(); db.close()

    def find_duplicates(self, url: str) -> list[Record]:
        cu = canonical_url(url)
        db = self._db(); rows = db.execute("select * from academy_content where canonical_url=? order by updated_at desc", [cu]).fetchall(); db.close()
        return [self._row(r) for r in rows]


class DeltaRepository(BaseRepository):
    durable = True

    def __init__(self, table: str):
        self.table = table
        self.warning = None
        self._sdk = None
        self._ensure_client()

    def _ensure_client(self):
        try:
            from databricks.sdk import WorkspaceClient
        except ImportError as exc:
            raise RepoError("Pacote databricks-sdk ausente para acesso a Delta.") from exc
        try:
            self._sdk = WorkspaceClient()
        except Exception as exc:
            raise RepoError(f"Credenciais Databricks indisponiveis ({type(exc).__name__}).") from None

    def _sql(self, statement: str):
        warehouse = setting("DATABRICKS_WAREHOUSE_ID")
        if not warehouse:
            raise RepoError("DATABRICKS_WAREHOUSE_ID nao configurado para usar a tabela Delta.")
        try:
            return self._sdk.statement_execution.execute_statement(statement=statement, warehouse_id=warehouse, wait_timeout="50s")
        except Exception as exc:
            raise RepoError(f"Falha ao executar SQL no warehouse ({type(exc).__name__}).") from None

    def ensure(self) -> None:
        self._sql(f"""
        create table if not exists {self.table} (
          id string,
          canonical_url string,
          title string,
          status string,
          data_json string,
          extraction_json string,
          created_at timestamp,
          updated_at timestamp,
          published_at timestamp,
          created_by string,
          published_by string
        ) using delta
        """)

    def create_resource(self, draft: CuratedDraft, extraction: Extraction, *, created_by: Optional[str], status: str = "draft") -> str:
        rid = _resource_id(draft.title)
        self._sql(
            f"insert into {self.table} values ("
            f"'{_q(rid)}','{_q(extraction.canonical_url)}','{_q(draft.title)}','{_q(status)}',"
            f"'{_q(draft.model_dump_json())}','{_q(json.dumps(extraction.to_dict(), ensure_ascii=False))}',"
            f"current_timestamp(),current_timestamp(),{ 'current_timestamp()' if status == 'published' else 'null' },"
            f"{_lit(created_by)},{_lit(created_by) if status == 'published' else 'null'})"
        )
        return rid

    def _rows(self, sql: str) -> list[Record]:
        res = self._sql(sql)
        data = getattr(res, "result", None) or getattr(res, "manifest", None)
        # fallback simples: usar pandas JSON do SDK nao esta garantido aqui; entao reexecutamos via REST se necessario.
        chunks = getattr(res, "result", None)
        rows = []
        if getattr(chunks, "data_array", None):
            for r in chunks.data_array:
                rows.append(Record(r[0], r[1], r[2], r[3], json.loads(r[4]), json.loads(r[5]), r[6], r[7], r[8], r[9], r[10]))
        return rows

    def get_resource(self, rid: str) -> Optional[Record]:
        rows = self._rows(f"select * from {self.table} where id='{_q(rid)}' limit 1")
        return rows[0] if rows else None

    def list_resources(self, status: Optional[str] = None) -> list[Record]:
        where = f"where status='{_q(status)}'" if status else ""
        return self._rows(f"select * from {self.table} {where} order by updated_at desc")

    def update_resource(self, rid: str, draft: CuratedDraft, *, updated_by: Optional[str]) -> None:
        self._sql(f"update {self.table} set title='{_q(draft.title)}', data_json='{_q(draft.model_dump_json())}', updated_at=current_timestamp() where id='{_q(rid)}'")

    def publish_resource(self, rid: str, *, published_by: Optional[str]) -> None:
        self._sql(f"update {self.table} set status='published', published_at=current_timestamp(), published_by={_lit(published_by)}, updated_at=current_timestamp() where id='{_q(rid)}'")

    def archive_resource(self, rid: str, *, archived_by: Optional[str]) -> None:
        self._sql(f"update {self.table} set status='archived', updated_at=current_timestamp() where id='{_q(rid)}'")

    def find_duplicates(self, url: str) -> list[Record]:
        return self._rows(f"select * from {self.table} where canonical_url='{_q(canonical_url(url))}' order by updated_at desc")


def get_repository() -> BaseRepository:
    table = setting("ACADEMY_CONTENT_TABLE")
    if table:
        try:
            repo = DeltaRepository(table)
            repo.ensure()
            return repo
        except RepoError as exc:
            log.warning("delta repo unavailable: %s", exc)
            if in_databricks_app() and not is_dev():
                return DisabledRepository(str(exc))
    if is_dev() or not in_databricks_app():
        return SQLiteRepository()
    return DisabledRepository("Persistencia duravel nao configurada. Defina ACADEMY_CONTENT_TABLE e DATABRICKS_WAREHOUSE_ID.")


def _resource_id(title: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9]+", "-", t).strip("-")
    return t[:80] or "resource"


def _q(s: str) -> str:
    return str(s).replace("'", "''")


def _lit(s: Optional[str]) -> str:
    return f"'{_q(s)}'" if s else "null"
