from services.catalog import validate_references
from utils.safe import is_safe_url


def test_catalog_is_consistent(cat):
    assert validate_references(cat) == []


PRESERVED = [
    "mattpocock-skills", "grill-with-docs", "grill-me", "stanford-online-playlists", "stanford-cs221-2025",
    "stanford-cs229-2026", "stanford-cs230-2025", "stanford-cme295-2025", "stanford-cs336-2026",
    "stanford-cs329a", "stanford-ee292r", "dair-ai", "dair-prompt-engineering-guide", "dair-ml-youtube-courses",
    "dair-ml-papers-explained", "dair-transformers-recipe", "dlai-evaluating-debugging-genai",
    "fsdl-llm-bootcamp-2023", "train-llm-from-scratch", "llms-por-dentro", "all-agentic-architectures",
    "sdd-emersonmendes", "production-agentic-rag-course", "motion", "manim", "lottie-web",
]


def test_all_previous_resources_preserved(cat):
    assert set(PRESERVED) <= set(cat.resources)
    assert len(cat.resources) == 26


def test_no_lms_structures_left(cat):
    for r in cat.resources.values():
        assert not hasattr(r, "learning_paths") and not hasattr(r, "featured")
    assert not hasattr(cat, "tracks") and not hasattr(cat, "quizzes")


def test_cards_have_short_descriptions(cat):
    for r in cat.resources.values():
        assert 30 <= len(r.tagline) <= 125, (r.id, len(r.tagline))
        assert 40 <= len(r.blurb) <= 260, r.id  # texto de abertura do Saiba mais


EDITORIAL = ["Tools worth knowing", "Make your work easier", "Interesting discoveries", "Quick knowledge", "Deep dives"]


def test_editorial_collections(cat):
    assert [c.title for c in cat.collections.values()] == EDITORIAL
    # transversais: o mesmo item pode estar em mais de uma colecao
    from collections import Counter

    counts = Counter(i.id for c in cat.collections.values() for i in c.items)
    assert any(n > 1 for n in counts.values())
    # nenhum recurso fica de fora da curadoria
    assert set(cat.resources) <= set(counts)


def test_main_collections_are_tools_not_courses(cat):
    for c in cat.collections.values():
        if c.home == "main":
            for obj, _ in cat.collection_items(c.id):
                assert getattr(obj, "type", "note") not in {"course", "playlist", "video"}, (c.id, obj.id)


def test_areas_are_multidimensional_and_populated(cat):
    counts = cat.area_counts()
    assert all(c >= 2 for c in counts.values()), counts
    multi = sum(len(r.areas) > 1 for r in cat.resources.values())
    assert multi >= len(cat.resources) // 2
    for a in ["data-science", "dev-backend", "product", "data-governance", "market-research", "ai-llms", "creative-tech"]:
        assert cat.areas[a].chip


def test_collection_notes_preserved(cat):
    notes = {i.id: i.note for i in cat.collections["interesting-discoveries"].items}
    assert notes["grill-me"].startswith("Uma ideia simples")
    assert notes["dair-ml-papers-explained"] == "Um atalho para entender os papers que todo mundo cita."


def test_all_urls_are_https(cat):
    for r in cat.resources.values():
        assert is_safe_url(r.url), r.id
        for ln in r.links:
            assert is_safe_url(ln.url), r.id


def test_unverified_resources_explain_why(cat):
    for r in cat.resources.values():
        if r.metadata_status != "verified":
            assert r.metadata_notes, r.id


def test_pending_course_is_flagged(cat):
    assert cat.resources["dlai-evaluating-debugging-genai"].metadata_status == "pending"


def test_every_theme_has_resources(cat):
    for c in cat.categories:
        assert cat.resources_in_category(c), c


def test_collections_have_children(cat):
    for rid in ["stanford-online-playlists", "dair-ai", "mattpocock-skills"]:
        assert cat.children_of(rid), rid

