import math

from services.catalog import NOTE_KINDS, reading_minutes

REQUIRED_EXPLAINERS = ["api", "rag", "data-lineage", "ci-cd", "data-contract", "product-discovery",
                       "forecast-backtesting", "entity-resolution"]


def test_required_explainers_exist(cat):
    for nid in REQUIRED_EXPLAINERS:
        assert cat.notes[nid].kind == "explainer", nid


def test_every_kind_has_notes(cat):
    kinds = {n.kind for n in cat.notes.values()}
    assert kinds == set(NOTE_KINDS)


def test_reading_time_is_computed_from_text(cat):
    assert reading_minutes("palavra " * 200) == 1
    assert reading_minutes("palavra " * 201) == 2
    for n in cat.notes.values():
        words = len(n.summary.split()) + len(n.body.split())
        assert n.minutes == max(1, math.ceil(words / 200)), n.id
        assert n.minutes <= 3, n.id  # notas curtas, 1-3 min


def test_tips_cover_non_ai_areas(cat):
    for a in ["data-governance", "market-research", "product", "analytics", "data-engineering", "dev-backend"]:
        assert cat.notes_in_area(a), a


def test_notes_not_only_ai(cat):
    non_ai = [n for n in cat.notes.values() if "ai-llms" not in n.areas]
    assert len(non_ai) >= len(cat.notes) // 3
