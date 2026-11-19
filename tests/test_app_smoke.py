"""Smoke test: cada pagina renderiza sem excecao (Streamlit AppTest)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")

CASES = [
    {},
    {"page": "discover", "area": "data-governance"},
    {"page": "discover", "area": "market-research"},
    {"page": "discover", "area": "creative-tech"},
    {"page": "library"},
    {"page": "library", "q": "rag"},
    {"page": "library", "q": "xyzzyqwerty"},
    {"page": "library", "area": "data-science"},
    {"page": "tips"},
    {"page": "tips", "kind": "dev-tip"},
    {"page": "tips", "area": "product", "q": "teste"},
    {"page": "resource", "resource": "stanford-cs336-2026"},
    {"page": "resource", "resource": "mattpocock-skills"},
    {"page": "resource", "resource": "dlai-evaluating-debugging-genai"},
    {"page": "resource", "resource": "nao-existe"},
    {"page": "note", "note": "data-contract"},
    {"page": "note", "note": "api-idempotencia"},
    {"page": "note", "note": "nao-existe"},
    # rotas antigas continuam funcionando
    {"page": "paths"},
    {"page": "explore", "q": "rag"},
    {"page": "knowledge", "concept": "embeddings"},
    {"page": "my_learning"},
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


def _run(**params):
    at = AppTest.from_file(APP, default_timeout=60)
    for k, v in params.items():
        at.query_params[k] = v
    return at.run()


def _offline(monkeypatch):
    import requests

    def offline(*a, **k):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(requests, "get", offline)
    monkeypatch.setattr(requests.Session, "get", offline, raising=False)


def test_discover_has_hero_chips_and_sections(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    assert at.title[0].value == "Um lugar para descobrir algo novo."
    chips = at.get("button_group")
    labels = [o for g in chips for o in g.proto.options]
    text = " ".join(str(x) for x in labels)
    for name in ["Todos", "Data Science", "Dev & Backend", "Produto", "Data Governance", "Market Research", "AI & LLMs", "Creative Tech"]:
        assert name in text, name
    subs = [s.value for s in at.subheader]
    for sec in ["Explore & Discover", "Worth Checking Out", "Quick Knowledge", "Tools & Resources"]:
        assert sec in subs, sec
    # nada de LMS na home
    md = " ".join(m.value for m in at.markdown).lower()
    assert "progresso" not in md and "quiz" not in md and "trilha" not in md


def test_every_card_links_directly_to_source(monkeypatch):
    _offline(monkeypatch)
    at = _run(page="library")
    from services.catalog import load_catalog

    cat = load_catalog()
    urls = {b.proto.url for b in at.get("link_button")}
    assert urls == {r.url for r in cat.resources.values()}


def test_saiba_mais_opens_detail(monkeypatch):
    _offline(monkeypatch)
    at = _run(page="library", q="manim")
    btn = next(b for b in at.button if b.key == "more-lib-manim")
    at = btn.click().run()
    assert dict(at.query_params) == {"page": "resource", "resource": "manim"}
    assert at.title[0].value.startswith("Manim")
    assert any(b.proto.url == "https://github.com/ManimCommunity/manim" for b in at.get("link_button"))
    heads = " ".join(m.value for m in at.markdown)
    for q in ["O que é?", "Por que é útil?", "Para quem faz sentido?", "O que vou encontrar?"]:
        assert q in heads


def test_global_search_goes_to_library(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    at.text_input[0].input("Animação")
    at = next(b for b in at.button if b.label == "Buscar").click().run()
    assert dict(at.query_params) == {"page": "library", "q": "Animação"}
    assert at.title[0].value == "Library"
    urls = {b.proto.url for b in at.get("link_button")}
    assert "https://github.com/ManimCommunity/manim" in urls


def test_chip_click_filters_home(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    chips = next(g for g in at.get("button_group") if g.key == "chips-all")
    at = chips.set_value("creative-tech").run()
    assert dict(at.query_params) == {"page": "discover", "area": "creative-tech"}
    urls = {b.proto.url for b in at.get("link_button")}
    assert urls and urls <= {"https://github.com/ManimCommunity/manim", "https://github.com/motiondivision/motion",
                             "https://github.com/airbnb/lottie-web"}


def test_area_without_resources_still_has_content(monkeypatch):
    _offline(monkeypatch)
    at = _run(page="discover", area="market-research")
    subs = [s.value for s in at.subheader]
    assert "Quick Knowledge" in subs
    assert not at.exception


def test_nav_switches_sections(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    nav = next(g for g in at.get("button_group") if g.key == "nav-discover")
    at = nav.set_value("tips").run()
    assert at.title[0].value == "Tips & Insights"
    at = next(b for b in at.button if b.key.startswith("read-tips-")).click().run()
    assert at.query_params["page"] == "note"
