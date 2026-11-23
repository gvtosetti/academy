"""Entrada do Lakeflow Job "Resource Library · Databricks Release Watch".

Roda fora do Streamlit (nao depende de sessao aberta). Agenda recomendada: semanal
(segunda 06:00 UTC) com --mode auto: verifica o mes corrente e, na primeira execucao de
cada mes (calendario UTC), consolida o mes e revalida o anterior + historico em preview.

Parametros (job parameters ou argumentos):
  --mode auto|weekly|monthly|revalidate   --triggered_by <texto>
  --table_prefix catalogo.schema.prefixo  --warehouse_id <id>
  --sqlite_path /caminho/arquivo.db       (alternativa de dev/teste)
Saida != 0 quando todas as fontes principais falham.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path


def _repo_root() -> Path:
    try:
        return Path(__file__).resolve().parent.parent
    except NameError:  # notebook/REPL
        return Path.cwd()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Databricks Release Watch")
    ap.add_argument("--mode", default="auto", choices=["auto", "weekly", "monthly", "revalidate"])
    ap.add_argument("--triggered_by", default="schedule")
    ap.add_argument("--table_prefix", default=None)
    ap.add_argument("--warehouse_id", default=None)
    ap.add_argument("--sqlite_path", default=None)
    ap.add_argument("--no_blog", action="store_true")
    args, _unknown = ap.parse_known_args(argv)
    for env, val in (("RELEASE_WATCH_TABLE_PREFIX", args.table_prefix), ("DATABRICKS_WAREHOUSE_ID", args.warehouse_id),
                     ("RELEASE_WATCH_SQLITE_PATH", args.sqlite_path)):
        if val:
            os.environ[env] = val
    root = _repo_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from services.release_watch.runner import run
    from services.release_watch.store import StoreError, get_store

    store = get_store(refresh=True)
    if not store.enabled:
        print(f"Release Watch desabilitado: {store.warning}", file=sys.stderr)
        return 2
    try:
        report = run(args.mode, store=store, triggered_by=args.triggered_by, include_blog=not args.no_blog)
    except StoreError as exc:
        print(f"Falha de persistencia: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({k: report[k] for k in ("run_id", "mode", "effective_modes", "current_period", "status",
                                             "stats", "errors")}, ensure_ascii=False, indent=2))
    for s in report["sources"]:
        print(f"  {s['role']:<13} {s['outcome']:<13} items={s['items']:<4} {s['url']}")
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
