"""Smoke test: cada pagina renderiza sem excecao (Streamlit AppTest)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

CASES = [
    {},
    {"page": "paths"},
    {"page": "paths", "track": "t1-fundamentos-ia-llms"},
    {"page": "explore", "q": "rag"},
    {"page": "resource", "resource": "stanford-cs336-2026"},
    {"page": "resource", "resource": "dlai-evaluating-debugging-genai"},
    {"page": "resource", "resource": "nao-existe"},
    {"page": "videos"},
    {"page": "knowledge", "concept": "embeddings"},
    {"page": "my_learning"},
    {"page": "about"},
    {"page": "pagina-invalida"},
]


@pytest.mark.parametrize("params", CASES, ids=lambda p: "-".join(p.values()) or "home")
def test_page_renders(params, monkeypatch):
    # isola o smoke test da rede: GitHub indisponivel deve degradar com elegancia
    import requests

    def offline(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", offline)
    monkeypatch.setattr(requests.Session, "get", offline, raising=False)
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_github_page_offline(monkeypatch):
    import requests

    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError("x")))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["page"] = "github"
    at.run()
    assert not at.exception
