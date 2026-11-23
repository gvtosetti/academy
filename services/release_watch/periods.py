"""Periodos de publicacao das release notes do Azure Databricks (calendario UTC).

A URL de cada mes e DERIVADA da data real de execucao em UTC; nenhuma URL mensal fica
fixa no codigo. Estrategia:
- weekly:     mes corrente (prioritario)
- monthly:    consolidacao do mes corrente + revisao do mes anterior (publicacoes tardias)
- revalidate: mes anterior + meses historicos de candidatos ainda em preview/beta
- auto:       weekly; na primeira execucao de cada mes inclui tambem o monthly
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable, Optional

BASE_URL = "https://learn.microsoft.com/en-us/azure/databricks/release-notes/product/"
MONTH_SLUGS = ("january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december")
MODES = ("auto", "weekly", "monthly", "revalidate")
MAX_HISTORY_PERIODS = 3


@dataclass(frozen=True, order=True)
class Period:
    year: int
    month: int

    def __post_init__(self):
        if not (1 <= self.month <= 12) or not (2015 <= self.year <= 2100):
            raise ValueError(f"periodo invalido: {self.year}-{self.month}")

    @property
    def key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def url(self) -> str:
        return f"{BASE_URL}{self.year}/{MONTH_SLUGS[self.month - 1]}"

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    def previous(self) -> "Period":
        return Period(self.year - 1, 12) if self.month == 1 else Period(self.year, self.month - 1)

    @classmethod
    def parse(cls, key: str) -> "Period":
        y, m = key.split("-")
        return cls(int(y), int(m))

    @classmethod
    def of(cls, d: date | datetime) -> "Period":
        return cls(d.year, d.month)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(now: Optional[datetime] = None) -> datetime:
    now = now or utc_now()
    if now.tzinfo is None:  # datetime ingenuo e tratado como UTC, nunca como hora local
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def current_period(now: Optional[datetime] = None) -> Period:
    return Period.of(to_utc(now))


@dataclass(frozen=True)
class Target:
    period: Period
    role: str  # current | previous | history


def plan(mode: str, now: Optional[datetime] = None, *, monthly_due: bool = False,
         history: Iterable[str] = ()) -> list[Target]:
    """Lista de paginas mensais a consultar, sem duplicatas, na ordem de prioridade."""
    if mode not in MODES:
        raise ValueError(f"modo invalido: {mode}")
    cur = current_period(now)
    prev = cur.previous()
    out: list[Target] = [Target(cur, "current")] if mode in ("auto", "weekly", "monthly") else []
    if mode == "monthly" or mode == "revalidate" or (mode == "auto" and monthly_due):
        out.append(Target(prev, "previous"))
    if mode == "revalidate" or (mode == "auto" and monthly_due):
        seen = {t.period for t in out}
        for key in sorted(set(history), reverse=True):
            try:
                p = Period.parse(key)
            except (ValueError, AttributeError):
                continue
            if p not in seen and p < prev and len([t for t in out if t.role == "history"]) < MAX_HISTORY_PERIODS:
                out.append(Target(p, "history"))
                seen.add(p)
    return out
