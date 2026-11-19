from services.catalog import validate_references
from utils.safe import is_safe_url


def test_catalog_is_consistent(cat):
    assert validate_references(cat) == []


def test_catalog_has_content(cat):
    assert len(cat.resources) >= 20
    assert len(cat.tracks) == 6
    assert len(cat.concepts) >= 30
    assert cat.quizzes


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


def test_every_category_has_resources(cat):
    for c in cat.categories:
        assert cat.resources_in_category(c), c


def test_collections_have_children(cat):
    for rid in ["stanford-online-playlists", "dair-ai", "mattpocock-skills"]:
        assert cat.children_of(rid), rid


def test_quiz_answers_in_range(cat):
    for q in cat.quizzes:
        assert 0 <= q.answer < len(q.options)
