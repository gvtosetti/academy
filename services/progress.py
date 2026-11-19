"""Acompanhamento de progresso.

MVP: `SessionProgressRepository` guarda o estado em st.session_state, ou seja,
o progresso e TEMPORARIO (some ao fechar/recarregar a aba). A interface
`ProgressRepository` permite trocar por um armazenamento duravel no futuro
(ex.: tabela Delta no Unity Catalog ou banco gerenciado) -- habilitar somente
apos haver identidade de usuario estavel, permissao e destino autorizados.
Os dados ficam isolados por usuario (cada sessao tem o seu dicionario).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal, MutableMapping, Protocol

Status = Literal["not_started", "started", "completed"]
STATUS_LABEL = {"not_started": "Nao iniciado", "started": "Em andamento", "completed": "Concluido"}


class ProgressRepository(Protocol):
    is_persistent: bool

    def get_status(self, resource_id: str) -> Status: ...
    def set_status(self, resource_id: str, status: Status) -> None: ...
    def is_saved(self, resource_id: str) -> bool: ...
    def toggle_saved(self, resource_id: str) -> bool: ...
    def record_visit(self, resource_id: str) -> None: ...
    def recent_visits(self, n: int = 5) -> list[str]: ...
    def is_module_done(self, track_id: str, module_id: str) -> bool: ...
    def set_module_done(self, track_id: str, module_id: str, done: bool) -> None: ...
    def snapshot(self) -> dict: ...


class SessionProgressRepository:
    """Implementacao baseada em um dicionario mutavel (st.session_state em producao)."""

    is_persistent = False
    KEY = "_academy_progress"

    def __init__(self, store: MutableMapping):
        if self.KEY not in store:
            store[self.KEY] = {"status": {}, "saved": [], "visits": [], "modules": {}}
        self._s = store[self.KEY]

    def get_status(self, resource_id: str) -> Status:
        return self._s["status"].get(resource_id, "not_started")

    def set_status(self, resource_id: str, status: Status) -> None:
        if status not in STATUS_LABEL:
            raise ValueError(status)
        if status == "not_started":
            self._s["status"].pop(resource_id, None)
        else:
            self._s["status"][resource_id] = status

    def is_saved(self, resource_id: str) -> bool:
        return resource_id in self._s["saved"]

    def toggle_saved(self, resource_id: str) -> bool:
        if resource_id in self._s["saved"]:
            self._s["saved"].remove(resource_id)
            return False
        self._s["saved"].append(resource_id)
        return True

    def record_visit(self, resource_id: str) -> None:
        v = [x for x in self._s["visits"] if x[0] != resource_id]
        v.insert(0, (resource_id, datetime.now().isoformat(timespec="seconds")))
        self._s["visits"] = v[:20]

    def recent_visits(self, n: int = 5) -> list[str]:
        return [x[0] for x in self._s["visits"][:n]]

    def is_module_done(self, track_id: str, module_id: str) -> bool:
        return module_id in self._s["modules"].get(track_id, [])

    def set_module_done(self, track_id: str, module_id: str, done: bool) -> None:
        mods = self._s["modules"].setdefault(track_id, [])
        if done and module_id not in mods:
            mods.append(module_id)
        elif not done and module_id in mods:
            mods.remove(module_id)

    def snapshot(self) -> dict:
        return {
            "status": dict(self._s["status"]),
            "saved": list(self._s["saved"]),
            "visits": list(self._s["visits"]),
            "modules": {k: list(v) for k, v in self._s["modules"].items()},
        }


def get_repository() -> ProgressRepository:
    import streamlit as st

    return SessionProgressRepository(st.session_state)
