"""Entidades del dominio del sistema experto."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Answer(str, Enum):
    """Respuesta suministrada por el usuario para un síntoma."""

    YES = "si"
    NO = "no"
    UNKNOWN = "no_se"


@dataclass(frozen=True, slots=True)
class Hypothesis:
    id: str
    name: str
    description: str
    prior: float


@dataclass(frozen=True, slots=True)
class Symptom:
    id: str
    question: str
    parent_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConditionalProbabilityTable:
    """Tabla P(Síntoma=sí | estados binarios de sus padres)."""

    symptom_id: str
    parent_ids: tuple[str, ...]
    probability_yes: Mapping[tuple[bool, ...], float]

    def probability(self, observed: bool, hypothesis_states: Mapping[str, bool]) -> float:
        key = tuple(hypothesis_states[parent] for parent in self.parent_ids)
        p_yes = self.probability_yes[key]
        return p_yes if observed else 1.0 - p_yes


@dataclass(frozen=True, slots=True)
class Diagnosis:
    hypothesis: Hypothesis
    prior: float
    posterior: float

    @property
    def variation(self) -> float:
        return self.posterior - self.prior


@dataclass(frozen=True, slots=True)
class QuestionScore:
    symptom: Symptom
    information_gain: float
