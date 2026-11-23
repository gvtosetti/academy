"""Configuracao centralizada (variaveis de ambiente ou `.streamlit/secrets.toml`).

Nenhum segredo e versionado. Em Databricks Apps, use `env` com `valueFrom` (secret
scope) no app.yaml; no Streamlit Community Cloud, use Secrets do app.

| Chave                      | Uso                                                              |
|----------------------------|------------------------------------------------------------------|
| ACADEMY_ADMINS             | e-mails de administradores, separados por virgula               |
| ACADEMY_CONTENT_TABLE      | tabela Delta `catalogo.schema.tabela` (camada persistente)       |
| DATABRICKS_WAREHOUSE_ID    | SQL warehouse usado para ler/gravar a tabela                     |
| DATABRICKS_HOST            | workspace (fora do Databricks Apps)                              |
| DATABRICKS_CLIENT_ID/SECRET| service principal (OAuth M2M) fora do Databricks Apps            |
| ACADEMY_LLM_ENDPOINT       | endpoint de inferencia (ex.: databricks-claude-sonnet-4-5)       |
| GITHUB_TOKEN               | opcional: aumenta o limite da API do GitHub                      |
| YOUTUBE_API_KEY            | opcional: YouTube Data API v3                                    |
| ACADEMY_ENV                | `dev` habilita backend local (nao duravel) e admin de dev        |
| ACADEMY_DEV_ADMIN          | e-mail do admin local (so com ACADEMY_ENV=dev)                   |
"""
from __future__ import annotations

import os
from typing import Optional


def setting(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    if val not in (None, ""):
        return val
    try:
        import streamlit as st

        v = st.secrets.get(name)  # type: ignore[attr-defined]
        if v not in (None, ""):
            return str(v)
    except Exception:  # secrets ausentes
        pass
    return default


def setting_list(name: str) -> list[str]:
    raw = setting(name) or ""
    return [x.strip().lower() for x in raw.replace(";", ",").split(",") if x.strip()]


def is_dev() -> bool:
    return (setting("ACADEMY_ENV") or "").lower() == "dev"


def in_databricks_app() -> bool:
    """Databricks Apps define DATABRICKS_APP_NAME no runtime do app."""
    return bool(os.environ.get("DATABRICKS_APP_NAME"))
