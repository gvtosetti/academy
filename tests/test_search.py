from services.search import Filters, LocalSearch, search_concepts


def ids(results):
    return [r.id for r, _ in results]


def test_empty_query_returns_everything(cat):
    assert len(LocalSearch(cat).search("")) == len(cat.resources)


def test_rag_finds_rag_course(cat):
    assert "production-agentic-rag-course" in ids(LocalSearch(cat).search("rag"))[:5]


def test_accent_insensitive(cat):
    a = ids(LocalSearch(cat).search("animacao"))
    b = ids(LocalSearch(cat).search("animação"))
    assert a == b and "manim" in a


def test_filters_restrict_results(cat):
    res = LocalSearch(cat).search("", Filters(categories=("creative-coding",)))
    assert set(ids(res)) == {"motion", "manim", "lottie-web"}


def test_nonsense_returns_nothing(cat):
    assert LocalSearch(cat).search("xyzzyqwerty") == []


def test_concept_search(cat):
    found = [c.id for c in search_concepts(cat.concepts.values(), "embeddings")]
    assert found and found[0] == "embeddings"
