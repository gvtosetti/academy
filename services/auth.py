"""Autenticacao/autorizacao para a area administrativa.

Leitura do catalogo continua publica; escrita exige identidade autorizada. A regra NAO
fica so na UI: `require_admin()` barra a acao no servidor antes de qualquer gravacao.

Ordem de deteccao da identidade:
1. Databricks Apps / proxies com cabeçalhos de usuario (`X-Forwarded-Email`, etc.);
2. email explicitado em `ACADEMY_DEV_ADMIN` quando `ACADEMY_ENV=dev` (para testes locais);
3. ausente => visitante anonimo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.config import is_dev, setting, setting_list


@dataclass
class Identity:
    email: Optional[str]
    display_name: Optional[str]
    is_admin: bool
    source: str


def current_identity() -> Identity:
    try:
        import streamlit as st

        headers = {k.lower(): str(v) for k, v in st.context.headers.items()}  # type: ignore[attr-defined]
    except Exception:
        headers = {}
    email = next((headers.get(k) for k in (
        "x-forwarded-email", "x-auth-request-email", "x-webauth-user", "x-user-email", "remote-user"
    ) if headers.get(k)), None)
    name = next((headers.get(k) for k in ("x-forwarded-user", "x-user-name", "x-auth-request-user") if headers.get(k)), None)
    if email:
        return Identity(email=email.lower(), display_name=name or email.split("@")[0],
                        is_admin=email.lower() in set(setting_list("ACADEMY_ADMINS")), source="header")
    if is_dev() and setting("ACADEMY_DEV_ADMIN"):
        email = setting("ACADEMY_DEV_ADMIN").lower()
        return Identity(email=email, display_name=email.split("@")[0], is_admin=True, source="dev")
    return Identity(email=None, display_name=None, is_admin=False, source="anonymous")


def require_admin() -> Identity:
    ident = current_identity()
    if not ident.is_admin:
        raise PermissionError("A area administrativa exige uma identidade autorizada.")
    return ident
