"""Converte um draft curado + metadados extraidos em `Resource` publicavel."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from services.curator import CuratedDraft
from services.ingest.base import Extraction
from services.models import Link, Prerequisites, Resource, VerifiedMetadata

KIND_TO_CATEGORY = {
    "video": "ai-foundations",
    "playlist": "ai-foundations",
    "course": "ai-foundations",
    "github": "software-engineering",
    "documentation": "software-engineering",
    "article": "llm-engineering",
    "roadmap": "llm-engineering",
    "collection": "ai-foundations",
    "tool": "software-engineering",
}
AREA_TO_CATEGORY = {
    "data-science": "ai-foundations",
    "analytics": "ai-foundations",
    "ai-llms": "llms",
    "dev-backend": "software-engineering",
    "data-governance": "llmops",
    "creative-tech": "creative-coding",
}


def draft_to_resource(rid: str, draft: CuratedDraft, extraction: Extraction, *, added_on: Optional[date] = None,
                      valid_categories: Optional[set[str]] = None) -> Resource:
    cats = valid_categories or set()
    category = next((c for c in draft.categories if not cats or c in cats), None)
    if not category:
        category = next((AREA_TO_CATEGORY[a] for a in draft.areas if a in AREA_TO_CATEGORY and (not cats or AREA_TO_CATEGORY[a] in cats)), None)
    if not category:
        category = KIND_TO_CATEGORY.get(draft.resource_type, "ai-foundations")
    md_status = "verified" if extraction.status == "ok" and not extraction.missing else "partial" if extraction.status != "failed" else "pending"
    notes = []
    if extraction.missing:
        notes.append("Faltando: " + ", ".join(extraction.missing[:8]))
    if extraction.warnings:
        notes.append("Avisos: " + "; ".join(extraction.warnings[:5]))
    links = [Link(label=l.get("text") or l.get("label") or "Fonte relacionada", url=l["url"])
             for l in extraction.links if isinstance(l, dict) and l.get("url")][:8]
    episodes = []
    for c in extraction.children[:20]:
        if isinstance(c, dict) and c.get("title"):
            episodes.append(c["title"])
        elif getattr(c, "title", None):
            episodes.append(c.title)
    return Resource(
        id=rid,
        title=draft.title,
        url=draft.source_url,
        provider=draft.provider,
        type=draft.resource_type,
        category=category,
        difficulty=draft.difficulty,
        language=draft.language,
        areas=draft.areas,
        tagline=draft.short_description_pt,
        blurb=draft.detailed_description_pt,
        short_description=draft.short_description_pt,
        plain_language_explanation=draft.plain_language_summary_pt,
        technical_explanation=draft.technical_summary_pt,
        why_it_matters=draft.why_it_matters,
        learning_outcomes=draft.learning_outcomes,
        audience=draft.target_audience,
        prerequisites=Prerequisites(),
        key_concepts=[],
        practical_applications=draft.practical_use_cases,
        study_guide=draft.study_guide,
        related_resources=[],
        tags=draft.tags,
        parent=None,
        sequence=100,
        added_on=added_on or date.today(),
        github_repo=(extraction.facts.get("github_repo") or extraction.facts.get("full_name")) if draft.resource_type == "github" else None,
        github_highlights=[],
        links=links,
        verified=VerifiedMetadata(
            verified_on=date.today() if extraction.status == "ok" else None,
            source_title=extraction.title,
            primary_language=extraction.language,
            video_count=extraction.facts.get("video_count") if isinstance(extraction.facts.get("video_count"), int) else None,
            video_count_note=extraction.facts.get("video_count_note"),
            episodes=episodes,
            source_description=extraction.description,
            duration=extraction.facts.get("duration"),
        ),
        metadata_status=md_status,
        metadata_notes=" | ".join(notes) if notes else None,
    )


def parse_created_at(ts: Optional[str]) -> date:
    if not ts:
        return date.today()
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).date()
    except ValueError:
        return date.today()
