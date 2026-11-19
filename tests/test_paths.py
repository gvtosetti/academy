from services.progress import SessionProgressRepository
from services.recommend import recommend


def test_tracks_and_resources_are_bidirectional(cat):
    for t in cat.tracks.values():
        for m in t.modules:
            for rid in m.resources:
                assert t.id in cat.resources[rid].learning_paths
    for r in cat.resources.values():
        for tid in r.learning_paths:
            assert any(r.id in m.resources for m in cat.tracks[tid].modules)


def test_recommendations_exclude_self(cat):
    for rid in cat.resources:
        recs = recommend(cat, rid, k=4)
        assert all(x.resource.id != rid for x in recs)
        assert len(recs) <= 4


def test_progress_repository_roundtrip():
    repo = SessionProgressRepository({})
    assert repo.get_status("manim") == "not_started"
    repo.set_status("manim", "completed")
    assert repo.get_status("manim") == "completed"
    assert repo.toggle_saved("manim") is True and repo.is_saved("manim")
    repo.set_module_done("t6-visualizacao-creative", "m1-explicacoes-visuais", True)
    assert repo.is_module_done("t6-visualizacao-creative", "m1-explicacoes-visuais")
    repo.record_visit("manim")
    assert repo.recent_visits(1) == ["manim"]
