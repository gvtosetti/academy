from __future__ import annotations

from datetime import date

from services.curator import CuratedDraft
from services.ingest.base import Child, Extraction
from services.publishing import draft_to_resource
from services.repository import SQLiteRepository


def sample_extraction() -> Extraction:
    return Extraction(
        url="https://www.youtube.com/@CibeleRussoUSP/playlists",
        canonical_url="https://youtube.com/@cibelerussousp/playlists",
        adapter="youtube",
        provider="YouTube",
        kind="channel",
        status="partial",
        title="Cibele Russo",
        description="Canal com playlists públicas de estatística e ciência de dados.",
        language="pt",
        children=[Child(title="Inferência Estatística", kind="playlist", url="https://youtube.com/playlist?list=abc"),
                  {"title": "Regressão", "kind": "playlist", "url": "https://youtube.com/playlist?list=def"}],
        missing=["lista completa de playlists"],
        warnings=["API não configurada"],
        facts={"channel_id": "abc"},
    )


def sample_draft() -> CuratedDraft:
    return CuratedDraft(
        title="Cibele Russo — Playlists públicas",
        provider="YouTube",
        resource_type="collection",
        short_description_pt="Catálogo de playlists públicas de estatística e ciência de dados em português.",
        detailed_description_pt="Reúne séries organizadas de aulas da Cibele Russo sobre estatística, inferência e regressão.",
        why_it_matters="Oferece um ponto de entrada curado para conteúdo acadêmico em português, sem depender de edição manual em YAML.",
        target_audience=["Quem quer estudar estatística em português."],
        difficulty="intermediate",
        categories=["ai-foundations"],
        areas=["data-science", "analytics"],
        editorial_collections=["deep-dives"],
        tags=["estatistica", "playlist"],
        practical_use_cases=["Escolher uma playlist por assunto."],
        language="pt",
        source_url="https://youtube.com/@cibelerussousp/playlists",
        metadata_confidence=0.8,
        missing_information=["lista completa de playlists"],
        plain_language_summary_pt="Funciona como uma estante de playlists para escolher rapidamente o tema certo.",
        technical_summary_pt="Canal público com várias playlists visíveis e cobertura de estatística e ciência de dados.",
        learning_outcomes=["Identificar rapidamente as playlists mais úteis."],
        study_guide=["Comece pelo tema mais próximo do seu nível atual."],
        related_search_terms=["estatistica", "regressao"],
        featured=False,
    )


def test_draft_to_resource_accepts_mixed_children():
    res = draft_to_resource("cibele-russo", sample_draft(), sample_extraction(), added_on=date(2026, 11, 23),
                            valid_categories={"ai-foundations", "llm-engineering"})
    assert res.id == "cibele-russo"
    assert res.category == "ai-foundations"
    assert res.metadata_status == "partial"
    assert res.verified.episodes == ["Inferência Estatística", "Regressão"]


def test_sqlite_repository_deduplicates_by_canonical_url(tmp_path):
    repo = SQLiteRepository(tmp_path / "academy.db")
    draft = sample_draft()
    extraction = sample_extraction()
    rid = repo.create_resource(draft, extraction, created_by="tester", status="draft")
    assert rid == "cibele-russo-playlists-publicas"
    # mesma URL em outra grafia (www, maiusculas) e reconhecida como duplicata
    dups = repo.find_duplicates("https://www.youtube.com/@CibeleRussoUSP/playlists")
    assert len(dups) == 1
    assert dups[0].canonical_url == "https://youtube.com/@cibelerussousp/playlists"


# ---- seguranca de rede (sem rede real: tudo e barrado antes de conectar) ----------
import pytest  # noqa: E402

from services.ingest import analyze_url, detect  # noqa: E402


@pytest.mark.parametrize("url", [
    "http://example.com", "https://localhost/x", "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.5/", "https://[::1]/", "file:///etc/passwd", "ftp://example.com/a",
    "https://user:pw@example.com/", "javascript:alert(1)", "",
])
def test_blocked_urls_never_fetch(url):
    ex = analyze_url(url)
    assert ex.status == "failed" and ex.error_code == "invalid_url"


@pytest.mark.parametrize("url,adapter,kind", [
    ("https://www.youtube.com/@CibeleRussoUSP/playlists", "youtube", "channel"),
    ("https://www.youtube.com/playlist?list=PLt7qVSwRVn5aDu6DW-98cgk7ahkjku1B8", "youtube", "playlist"),
    ("https://youtu.be/BLIosfH2yM0", "youtube", "video"),
    ("https://github.com/databricks", "github", "organization"),
    ("https://github.com/anthropics/anthropic-cookbook/tree/main/skills", "github", "directory"),
    ("https://ai-engineer-roadmap-2026.vercel.app/", "web", "webpage"),
])
def test_detect_offline(url, adapter, kind):
    d = detect(url)
    assert d.ok and d.adapter == adapter and d.kind == kind


def test_curator_without_llm_requires_review(monkeypatch):
    from services import curator

    monkeypatch.setattr(curator, "get_llm", lambda: None)
    res = curator.curate(sample_extraction())
    assert res.status == "needs_review" and res.source == "heuristic"
    assert res.draft.source_url == "https://youtube.com/@cibelerussousp/playlists"


def test_curator_ignores_url_injected_by_model(monkeypatch):
    """Mesmo que o modelo devolva outra URL, a fonte publicada continua a canonica extraida."""
    from services import curator

    payload = sample_draft().model_dump()
    payload["source_url"] = "https://evil.example/phish"

    class Fake:
        name = "fake"

        def chat(self, *a, **k):
            import json
            return "```json\n" + json.dumps(payload) + "\n```"

    monkeypatch.setattr(curator, "get_llm", lambda: Fake())
    res = curator.curate(sample_extraction())
    assert res.source == "llm"
    assert res.draft.source_url == "https://youtube.com/@cibelerussousp/playlists"


def test_overlay_publishes_into_catalog(tmp_path, monkeypatch):
    from services import catalog as catmod

    repo = SQLiteRepository(tmp_path / "overlay.db")
    rid = repo.create_resource(sample_draft(), sample_extraction(), created_by="t", status="draft")
    monkeypatch.setattr(catmod, "get_repository", lambda: repo)
    assert rid not in catmod.load_catalog().resources  # draft nao aparece
    repo.publish_resource(rid, published_by="t")
    cat = catmod.load_catalog()
    # Se a URL canonica ja existe no YAML, o overlay pula (dedup correta).
    # Testamos que o mecanismo funciona: ou o recurso aparece, ou foi dedup.
    from services.ingest.base import canonical_url
    yaml_urls = {canonical_url(r.url) for r in cat.resources.values() if r.id != rid}
    if canonical_url("https://youtube.com/@cibelerussousp/playlists") in yaml_urls:
        assert rid not in cat.resources  # dedup correta
    else:
        assert rid in cat.resources


def test_admin_writes_require_identity(monkeypatch):
    from services import auth

    for k in ("ACADEMY_ENV", "ACADEMY_DEV_ADMIN", "ACADEMY_ADMINS"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(PermissionError):
        auth.require_admin()
