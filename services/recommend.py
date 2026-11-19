"""Recomendacoes BASEADAS EM REGRAS (nao sao geradas por IA).

Criterios, em ordem de peso:
1. Relacao explicita definida pela curadoria (related_resources, nos dois sentidos).
2. Conceitos compartilhados.
3. Mesmo tema (category).
4. Areas em comum.
5. Nivel proximo; penaliza saltos grandes.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.catalog import Catalog
from services.models import DIFFICULTY_ORDER, Resource


@dataclass
class Recommendation:
    resource: Resource
    score: float
    reasons: list[str]


def recommend(cat: Catalog, resource_id: str, k: int = 4) -> list[Recommendation]:
    base = cat.resources[resource_id]
    recs: list[Recommendation] = []
    for r in cat.resources.values():
        if r.id == base.id:
            continue
        score, why = 0.0, []
        if r.id in base.related_resources or base.id in r.related_resources:
            score += 10
            why.append("Relacionado pela curadoria")
        shared = set(base.key_concepts) & set(r.key_concepts)
        if shared:
            score += 2 * len(shared)
            names = ", ".join(sorted(cat.concepts[c].name for c in shared)[:3])
            why.append(f"Conceitos em comum: {names}")
        if r.category == base.category:
            score += 3
            why.append("Mesmo tema")
        common = set(r.areas) & set(base.areas)
        if common:
            score += len(common)
            why.append("Areas em comum: " + ", ".join(sorted(cat.areas[a].name for a in common if a in cat.areas)))
        gap = DIFFICULTY_ORDER[r.difficulty] - DIFFICULTY_ORDER[base.difficulty]
        if gap in (0, 1):
            score += 1
        elif abs(gap) >= 2:
            score -= 2
        if r.parent == base.id or base.parent == r.id:
            score -= 1  # pai/filho ja aparecem em outra secao
        if score >= 3 and why:
            recs.append(Recommendation(r, score, why))
    recs.sort(key=lambda x: (-x.score, x.resource.sequence))
    return recs[:k]
