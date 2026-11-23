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
    {"page": "playbook", "playbook": "automating-recurring-reports"},
    {"page": "playbook", "playbook": "nao-existe"},
    {"page": "topic", "topic": "llm-fundamentals"},
    {"page": "topic", "topic": "nao-existe"},
    {"page": "topic", "topic": "databricks-fundamentals"},
    {"page": "note", "note": "databricks-jobs-vs-notebooks"},
    {"page": "library", "subcategory": "documentation-runbooks"},
    {"page": "library", "section": "make-your-work-easier", "subcategory": "documentation-runbooks"},
    {"page": "release-watch"},
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
    assert at.title[0].value == "Resource Library"
    chips = at.get("button_group")
    labels = [o for g in chips for o in g.proto.options]
    text = " ".join(str(x) for x in labels)
    for name in ["Todos", "Data Science"]:
        assert name in text, name
    subs = [s.value for s in at.subheader]
    # 4 secoes da Home na ordem certa
    assert "Make Your Work Easier" in subs
    assert "Tools & Resources" in subs
    assert "Deep Dives & Courses" in subs
    assert "Quick Knowledge" in subs
    # nada de LMS na home
    md = " ".join(m.value for m in at.markdown)
    low = md.lower()
    assert "progresso" not in low and "quiz" not in low and "trilha" not in low


def test_home_is_a_compact_showcase(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    from services.catalog import load_catalog

    cat = load_catalog()
    links = at.get("link_button")
    # vitrine: no maximo 6 recursos por secao de recursos (+3 novidades), nunca o catalogo inteiro
    assert 3 <= len(links) <= 15 < len(cat.resources)
    md = " ".join(m.value for m in at.markdown)
    assert "**Documentation & Runbooks**" in md and "&amp;" not in " ".join(c.value for c in at.caption)
    # Databricks em destaque no Quick Knowledge: as 4 colecoes prioritarias + as 2 seguintes na ordem do arquivo
    labels = [b.label for b in at.button]
    for t in ("Databricks Fundamentals", "Databricks Jobs & Workflows", "Unity Catalog & Governance"):
        assert t in labels, t
    qk = [b.key.removeprefix("topic-qk-") for b in at.button if b.key and b.key.startswith("topic-qk-")]
    prio = ["databricks-fundamentals", "databricks-jobs-workflows", "unity-catalog-governance", "mlflow-experiment-tracking"]
    expected = (prio + [t for t in cat.topics if t not in prio])[:6]
    assert sorted(qk) == sorted(expected), qk
    assert any(b.label == f"Ver todas ({len(cat.topics)} coleções)" for b in at.button)
    assert any(b.label.startswith("Ver todos") for b in at.button)
    assert {"to-library", "to-tips"} <= {b.key for b in at.button}


def test_home_documentation_runbooks_subcategory_card(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    from services.catalog import load_catalog

    cat = load_catalog()
    # 5 subcategorias de Make Your Work Easier como cards-resumo (sem resource cards dessa secao)
    subs = [b for b in at.button if b.key and b.key.startswith("go-")]
    assert [b.key for b in subs] == [f"go-{s.id}" for s in cat.taxonomy.section("make-your-work-easier").subcategories]
    assert all(b.label == "Explorar" for b in subs)
    assert not [b for b in at.button if b.key and b.key.startswith("more-home-make-your-work-easier-")]
    n = len(cat.resources_in_subcategory("documentation-runbooks"))
    caps = " ".join(c.value for c in at.caption)
    assert f"{n} recursos" in caps or f"{n} recurso" in caps
    at = next(b for b in subs if b.key == "go-documentation-runbooks").click().run()
    assert dict(at.query_params) == {"page": "library", "subcategory": "documentation-runbooks"}
    urls = {b.proto.url for b in at.get("link_button")}
    assert urls == {r.url for r in cat.resources_in_subcategory("documentation-runbooks")}


def test_no_academy_branding(monkeypatch):
    _offline(monkeypatch)
    for params in ({}, {"page": "library"}, {"page": "tips"}):
        at = _run(**params)
        assert all(t.value.strip() != "Academy" for t in at.title)
        brand = next(b for b in at.button if b.key == "brand")
        assert brand.label == "Resource Library"
        assert all(b.label.strip() != "Academy" for b in at.button)
        text = " ".join([m.value for m in at.markdown] + [c.value for c in at.caption])
        assert "A Resource Library é um espaço" in text  # rodape (st.caption)
        assert "Academy é um espaço" not in text


def test_release_watch_admin_queue(monkeypatch, tmp_path):
    _offline(monkeypatch)
    db = tmp_path / "rw.db"
    monkeypatch.setenv("ACADEMY_ENV", "dev")
    monkeypatch.setenv("ACADEMY_DEV_ADMIN", "editor@example.com")
    monkeypatch.setenv("RELEASE_WATCH_SQLITE_PATH", str(db))
    from services.release_watch import store as rw_store
    from services.release_watch.runner import run
    from tests.test_release_watch import GA, NOV, NOW, FakeFetcher, page

    rw_store.set_store(None)
    run("weekly", now=NOW, store=rw_store.SQLiteStore(db), fetcher=FakeFetcher({NOV: page(GA)}), include_blog=False)
    at = _run(page="release-watch")
    assert not at.exception, [e.message for e in at.exception]
    md = " ".join(m.value for m in at.markdown)
    assert "Widget API is now generally available" in md
    assert any(b.proto.label == "Open official source" for b in at.get("link_button"))
    rw_store.set_store(None)


def test_cards_have_two_distinct_actions(monkeypatch):
    _offline(monkeypatch)
    at = _run(page="library")
    links = at.get("link_button")
    assert links and all(b.proto.label == "Open resource ↗" for b in links)
    more = [b for b in at.button if b.key and b.key.startswith("more-lib-")]
    assert len(more) == len(links) and all(b.label == "Saiba mais" for b in more)


def test_home_sections_render_cards(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    # deve ter cards (containers com link_button)
    links = at.get("link_button")
    assert len(links) >= 3  # pelo menos 3 recursos aparecem na home


def test_library_section_filter(monkeypatch):
    _offline(monkeypatch)
    at = _run(page="library", section="make-your-work-easier")
    # deve ter algum resultado filtrado
    links = at.get("link_button")
    assert len(links) >= 1


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
    assert not at.exception


def test_nav_switches_sections(monkeypatch):
    _offline(monkeypatch)
    at = _run()
    nav = next(g for g in at.get("button_group") if g.key == "nav-discover")
    at = nav.set_value("tips").run()
    assert at.title[0].value == "Tips & Insights"
    at = next(b for b in at.button if b.key.startswith("read-tips-")).click().run()
    assert at.query_params["page"] == "note"
