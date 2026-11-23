"""Classificacao editorial das novidades: areas priorizadas, relevancia, destino sugerido.

Regras deterministicas por palavra-chave (sem LLM). A relevancia combina a prioridade da
area, o tipo de lancamento e o status: nem toda novidade tem o mesmo peso.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AreaRule:
    id: str
    label: str
    priority: int            # 1 = mais importante
    library_areas: tuple     # areas do catalogo (areas.yaml)
    subcategory: str         # destino sugerido (taxonomy.yaml)
    keywords: tuple


AREAS = (
    AreaRule("ai-agents", "AI Engineering & Agents", 1, ("ai-llms",), "ai-data-tools",
             ("agent", "agents", "agent bricks", "genie", "llm", "llms", "model serving", "serving endpoint",
              "foundation model", "ai functions", "ai_", "vector search", "rag", "mcp", "ai gateway", "unity gateway",
              "gpt", "claude", "gemini", "llama", "prompt", "embedding", "genai", "generative")),
    AreaRule("data-science-mlflow", "Data Science & MLflow", 2, ("data-science",), "ai-data-tools",
             ("mlflow", "experiment", "model registry", "feature store", "feature engineering", "training",
              "automl", "evaluation", "tracing", "machine learning", "ml ", "gpu", "forecast")),
    AreaRule("automation-workflows", "Automation & Workflows", 3, ("data-engineering",), "automation-workflows",
             ("job", "jobs", "lakeflow jobs", "workflow", "schedule", "trigger", "task", "orchestration",
              "notification", "webhook", "alert", "retry", "retries")),
    AreaRule("governance-uc", "Data Governance & Unity Catalog", 4, ("data-governance",), "ai-data-tools",
             ("unity catalog", "lineage", "permission", "permissions", "grant", "abac", "governed tag", "tags",
              "audit", "system table", "system tables", "delta sharing", "governance", "row filter", "column mask",
              "data classification", "privilege", "metastore", "retention")),
    AreaRule("developer-experience", "Developer Experience", 5, ("dev-backend",), "developer-tools",
             ("cli", "sdk", "api", "terraform", "bundle", "bundles", "git", "ide", "vs code", "notebook",
              "notebooks", "repos", "extension", "oauth", "genie code", "assistant", "debugger")),
    AreaRule("data-eng-analytics", "Data Engineering & Analytics", 6, ("data-engineering", "analytics"), "ai-data-tools",
             ("sql", "warehouse", "delta", "spark", "dashboard", "query", "variant", "function", "ingestion",
              "lakeflow connect", "pipeline", "pipelines", "streaming", "photon", "compute", "serverless",
              "table", "tables", "iceberg", "lakebase", "postgres", "connector", "metric view")),
    AreaRule("product-business", "Product & Business Applications", 7, ("product",), "tools-libraries",
             ("genie one", "databricks one", "ai/bi", "apps", "databricks apps", "sharepoint", "business",
              "marketplace", "clean room", "clean rooms", "excel", "power bi", "tableau")),
)
AREA_BY_ID = {a.id: a for a in AREAS}
CHANGE_WEIGHT = {"new_feature": 3.0, "status_change": 2.5, "behavior_change": 2.5, "retirement": 2.0,
                 "improvement": 1.0, "fix": 0.5}
STATUS_WEIGHT = {"ga": 2.0, "public_preview": 1.5, "beta": 1.0, "private_preview": 0.5, "retired": 1.5,
                 "deprecated": 1.5, "other": 0.5}

# recursos existentes do catalogo relacionados por assunto (ids de resources.yaml)
RELATED_BY_TERM = (
    ("unity catalog", "unity-catalog-docs"), ("lineage", "unity-catalog-docs"), ("mlflow", "mlflow-docs"),
    ("lakeflow jobs", "databricks-lakeflow-jobs"), ("jobs", "databricks-lakeflow-jobs"),
    ("claude", "claude-platform-docs"),
)


def _hits(text: str, keywords: tuple) -> int:
    n = 0
    for kw in keywords:
        if kw.endswith("_") or kw.endswith(" "):
            n += text.count(kw)
        else:
            n += len(re.findall(rf"\b{re.escape(kw)}\b", text))
    return n


@dataclass
class Classification:
    areas: list[str]              # ids AREAS, da maior para a menor prioridade
    library_areas: list[str]
    relevance: float
    relevance_label: str          # high | medium | low
    suggested_subcategory: str
    use_cases: list[str]
    related_resources: list[str]
    note_suggested: bool


def classify(title: str, description: str, status: str, change_type: str, *, taxonomy=None,
             resource_ids: Optional[set] = None, resources=None, links: Optional[list] = None) -> Classification:
    text = f" {title.lower()} {title.lower()} {description.lower()} "  # titulo pesa em dobro
    scored = []
    for a in AREAS:
        h = _hits(text, a.keywords)
        if h:
            scored.append((a, h))
    # ordem: prioridade editorial primeiro; empate pelo numero de evidencias
    scored.sort(key=lambda x: (x[0].priority, -x[1]))
    strong = [a for a, h in scored if h >= 2] or [a for a, _ in scored[:1]]
    areas = [a.id for a in strong][:3] or ["data-eng-analytics"]
    top = AREA_BY_ID[areas[0]]
    lib_areas: list[str] = []
    for aid in areas:
        for la in AREA_BY_ID[aid].library_areas:
            if la not in lib_areas:
                lib_areas.append(la)
    relevance = round((8 - top.priority) * 1.0 + CHANGE_WEIGHT.get(change_type, 1.0)
                      + STATUS_WEIGHT.get(status, 0.5) + min(len(description), 900) / 450, 2)
    label = "high" if relevance >= 10 else "medium" if relevance >= 7 else "low"
    use_cases = taxonomy.match_use_cases(f"{title} {description}") if taxonomy is not None else []
    related: list[str] = []
    ids = resource_ids or set()
    for term, rid in RELATED_BY_TERM:
        if rid in ids and rid not in related and re.search(rf"\b{re.escape(term)}\b", text):
            related.append(rid)
    # mesmo link de documentacao de um recurso existente => provavel atualizacao desse recurso
    if resources and links:
        from services.release_watch.parser import canonical
        link_urls = {canonical(l["url"], keep_fragment=False) for l in links if l.get("url")}
        for r in resources:
            try:
                if canonical(r.url, keep_fragment=False) in link_urls and r.id not in related:
                    related.insert(0, r.id)
            except Exception:
                continue
    return Classification(
        areas=areas, library_areas=lib_areas or ["data-engineering"], relevance=relevance, relevance_label=label,
        suggested_subcategory=top.subcategory, use_cases=use_cases, related_resources=related[:5],
        note_suggested=len(description) >= 300 and change_type in ("new_feature", "behavior_change", "status_change"),
    )
