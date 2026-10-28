"""Caso de uso: conducir una sesión de diagnóstico."""
from __future__ import annotations

from src.application.inference_engine import BayesianInferenceEngine
from src.domain.entities import Answer, Diagnosis, Symptom
from src.domain.knowledge_repository import KnowledgeRepository


class DiagnosisService:
    def __init__(self, repository: KnowledgeRepository):
        self.engine = BayesianInferenceEngine(repository)
        self._evidence: dict[str, Answer] = {}
        self._asked: set[str] = set()

    @property
    def evidence(self) -> dict[str, Answer]:
        return self._evidence.copy()

    def register_answer(self, symptom_id: str, answer: Answer) -> None:
        self.engine.repository.get_symptom(symptom_id)
        self._asked.add(symptom_id)
        if answer != Answer.UNKNOWN:
            self._evidence[symptom_id] = answer

    def next_question(self) -> Symptom | None:
        return self.engine.next_question(self._evidence, self._asked)

    def current_diagnosis(self) -> list[Diagnosis]:
        return self.engine.diagnose(self._evidence)
