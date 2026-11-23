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
    assert len(cat.resources) >= 26  # 26 originais + novos recursos verificados


def test_no_lms_structures_left(cat):
    for r in cat.resources.values():
        assert not hasattr(r, "learning_paths") and not hasattr(r, "featured")
    assert not hasattr(cat, "tracks") and not hasattr(cat, "quizzes")


def test_cards_have_short_descriptions(cat):
    for r in cat.resources.values():
        assert 30 <= len(r.tagline) <= 125, (r.id, len(r.tagline))
        assert 40 <= len(r.blurb) <= 260, r.id  # texto de abertura do Saiba mais


def test_editorial_sections(cat):
    """Todos os recursos publicados pertencem a uma secao editorial via taxonomy."""
    for r in cat.resources.values():
        assert r.editorial_section, f"{r.id} sem editorial_section"
        assert r.editorial_subcategory, f"{r.id} sem editorial_subcategory"
    sec_ids = {s.id for s in cat.taxonomy.sections}
    for r in cat.resources.values():
        if r.editorial_section not in sec_ids | {"quick-knowledge"}:  # QK nao tem subcats de recurso
            assert r.editorial_section in sec_ids, f"{r.id}: secao {r.editorial_section} desconhecida"


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


def test_playbooks_have_human_checkpoints(cat):
    """Todo playbook deve ter ao menos uma etapa com revisao humana."""
    for p in cat.playbooks.values():
        assert any(s.human_checkpoint for s in p.steps), f"playbook {p.id} sem human_checkpoint"


def test_documentation_runbooks_subcategory(cat):
    sec = cat.taxonomy.section("make-your-work-easier")
    assert [s.id for s in sec.subcategories] == [
        "automation-workflows", "ai-assisted-work", "templates-standards", "validation-quality", "documentation-runbooks"]
    ids = {r.id for r in cat.resources_in_subcategory("documentation-runbooks")}
    assert {"sdd-emersonmendes", "openapi-specification"} <= ids


def test_databricks_notes_are_explainers(cat):
    core = ["databricks-workspace", "databricks-compute", "databricks-jobs", "databricks-unity-catalog",
            "databricks-mlflow", "databricks-sql-warehouse"]
    for n in core:
        assert cat.notes[n].kind == "explainer", n


def test_databricks_topic_collections_lead_quick_knowledge(cat):
    assert list(cat.topics)[:4] == ["databricks-fundamentals", "databricks-jobs-workflows",
                                    "unity-catalog-governance", "mlflow-experiment-tracking"]


def test_topic_collections_non_empty(cat):
    for t in cat.topics.values():
        items = cat.topic_items(t.id)
        assert len(items) >= 2, f"topic {t.id} com {len(items)} itens"


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


def test_every_subcategory_has_resources(cat):
    """Nenhuma subcategoria da Home fica vazia."""
    for sec in cat.taxonomy.sections:
        for sub in sec.subcategories:
            res = cat.resources_in_subcategory(sub.id)
            assert res, f"subcategoria {sub.id} sem recursos"


def test_collections_have_children(cat):
    for rid in ["stanford-online-playlists", "dair-ai", "mattpocock-skills"]:
        assert cat.children_of(rid), rid

