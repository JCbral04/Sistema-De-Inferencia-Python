"""Puerto de acceso a la base de conocimiento."""
from abc import ABC, abstractmethod

from .entities import ConditionalProbabilityTable, Hypothesis, Symptom


class KnowledgeRepository(ABC):
    """Define consultas pequeñas e independientes sobre el conocimiento."""

    @abstractmethod
    def get_hypotheses(self) -> list[Hypothesis]:
        raise NotImplementedError

    @abstractmethod
    def get_symptoms(self) -> list[Symptom]:
        raise NotImplementedError

    @abstractmethod
    def get_symptom(self, symptom_id: str) -> Symptom:
        raise NotImplementedError

    @abstractmethod
    def get_question(self, symptom_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_cpt(self, symptom_id: str) -> ConditionalProbabilityTable:
        raise NotImplementedError
