"""Recomendacoes BASEADAS EM REGRAS (nao sao geradas por IA).

Criterios, em ordem de peso:
1. Relacao explicita definida pela curadoria (related_resources).
2. Proximo passo em uma trilha de aprendizado que contem o recurso.
3. Conceitos compartilhados.
4. Mesma categoria.
5. Trilhas em comum.
6. Dificuldade compativel (mesmo nivel ou um acima); penaliza saltos grandes.
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


def next_in_tracks(cat: Catalog, resource_id: str) -> list[tuple[str, Resource]]:
    """Recursos do modulo seguinte em cada trilha que contem o recurso."""
    out = []
    for t in cat.tracks.values():
        for i, m in enumerate(t.modules):
            if resource_id in m.resources:
                for nm in t.modules[i + 1:]:
                    nxt = [x for x in nm.resources if x != resource_id]
                    if nxt:
                        out += [(t.id, cat.resources[x]) for x in nxt]
                        break
                break
    return out


def recommend(cat: Catalog, resource_id: str, k: int = 4) -> list[Recommendation]:
    base = cat.resources[resource_id]
    nexts = {r.id: tid for tid, r in next_in_tracks(cat, resource_id)}
    recs: list[Recommendation] = []
    for r in cat.resources.values():
        if r.id == base.id:
            continue
        score, why = 0.0, []
        if r.id in base.related_resources:
            score += 10
            why.append("Relacionado pela curadoria")
        if r.id in nexts:
            score += 6
            why.append(f"Proximo passo na trilha '{cat.tracks[nexts[r.id]].title}'")
        shared = set(base.key_concepts) & set(r.key_concepts)
        if shared:
            score += 2 * len(shared)
            names = ", ".join(sorted(cat.concepts[c].name for c in shared)[:3])
            why.append(f"Conceitos em comum: {names}")
        if r.category == base.category:
            score += 3
            why.append("Mesma categoria")
        if set(r.learning_paths) & set(base.learning_paths):
            score += 2
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
