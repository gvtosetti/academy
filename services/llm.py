"""Cliente de LLM via Databricks Model Serving (endpoint de chat aprovado no workspace).

Autenticacao pela cadeia padrao do Databricks SDK (`databricks.sdk.core.Config`):
service principal do Databricks Apps (DATABRICKS_CLIENT_ID/SECRET injetados pelo runtime),
OAuth M2M ou token configurado como segredo. Nada e presumido: sem
`ACADEMY_LLM_ENDPOINT`, a curadoria cai para o modo sem IA (rascunho para revisao).

O modelo NAO recebe ferramentas: so devolve texto. A saida e validada (Pydantic) antes
de qualquer uso.
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol

from services.config import setting

log = logging.getLogger("academy.llm")


class LLMError(Exception):
    pass


class LLM(Protocol):
    name: str

    def chat(self, messages: list[dict], max_tokens: int = 2000, temperature: float = 0.2) -> str: ...


class DatabricksServingLLM:
    def __init__(self, endpoint: str, timeout: tuple[float, float] = (5, 120)):
        self.endpoint, self.timeout = endpoint, timeout
        self.name = f"databricks:{endpoint}"

    def _auth(self) -> tuple[str, dict]:
        try:
            from databricks.sdk.core import Config
        except ImportError as exc:
            raise LLMError("Pacote databricks-sdk ausente.") from exc
        try:
            cfg = Config()
            return cfg.host.rstrip("/"), cfg.authenticate()
        except Exception as exc:
            raise LLMError(f"Credenciais do Databricks indisponiveis ({type(exc).__name__}).") from None

    def chat(self, messages: list[dict], max_tokens: int = 2000, temperature: float = 0.2) -> str:
        import requests

        host, headers = self._auth()
        try:
            r = requests.post(f"{host}/serving-endpoints/{self.endpoint}/invocations",
                              json={"messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                              headers={**headers, "Content-Type": "application/json"}, timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"Falha de rede ao chamar o endpoint de IA ({type(exc).__name__}).") from None
        if r.status_code in (401, 403):
            raise LLMError("Sem permissao para consultar o endpoint de IA (verifique CAN_QUERY para a identidade do app).")
        if r.status_code == 404:
            raise LLMError(f"Endpoint de IA '{self.endpoint}' nao encontrado.")
        if r.status_code == 429:
            raise LLMError("Endpoint de IA com limite de taxa atingido; tente novamente em instantes.")
        if not r.ok:
            raise LLMError(f"Endpoint de IA respondeu com status {r.status_code}.")
        try:
            msg = r.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise LLMError("Resposta do endpoint de IA em formato inesperado.") from None
        if isinstance(msg, list):  # blocos de conteudo
            msg = "".join(b.get("text", "") for b in msg if isinstance(b, dict))
        return str(msg)


def get_llm() -> Optional[LLM]:
    endpoint = setting("ACADEMY_LLM_ENDPOINT")
    return DatabricksServingLLM(endpoint) if endpoint else None
