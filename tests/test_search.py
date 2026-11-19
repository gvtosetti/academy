from services.search import Filters, LocalSearch, search_concepts, search_notes


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


def test_area_filter_is_multidimensional(cat):
    res = set(ids(LocalSearch(cat).search("", Filters(areas=("creative-tech",)))))
    assert res == {"motion", "manim", "lottie-web"}
    ds = set(ids(LocalSearch(cat).search("", Filters(areas=("data-science",)))))
    assert "manim" in ds  # o mesmo recurso aparece em mais de um contexto


def test_filters_combine(cat):
    f = Filters(areas=("dev-backend",), languages=("multi",))
    res = ids(LocalSearch(cat).search("", f))
    assert res == ["sdd-emersonmendes"]
    assert LocalSearch(cat).search("", Filters(types=("tool",), difficulties=("beginner",)))


def test_tag_filter(cat):
    res = LocalSearch(cat).search("", Filters(tags=("portugues",)))
    assert "llms-por-dentro" in ids(res)


def test_diverse_default_mixes_areas(cat):
    first = [r.areas[0] for r, _ in LocalSearch(cat).search("", sort="diverse")[:5]]
    assert len(set(first)) >= 4


def test_notes_search_accent_insensitive(cat):
    a = [n.id for n in search_notes(cat.notes.values(), "linhagem")]
    assert "data-lineage" in a
    b = [n.id for n in search_notes(cat.notes.values(), "idempotencia")]
    assert b and b[0] == "api-idempotencia"
    assert [n.id for n in search_notes(cat.notes.values(), "idempotência")] == b


def test_nonsense_returns_nothing(cat):
    assert LocalSearch(cat).search("xyzzyqwerty") == []


def test_concept_search(cat):
    found = [c.id for c in search_concepts(cat.concepts.values(), "embeddings")]
    assert found and found[0] == "embeddings"
