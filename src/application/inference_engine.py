"""Inferencia exacta por enumeración en una red bayesiana discreta."""
from __future__ import annotations

import itertools
import math
from collections.abc import Mapping, Sequence

from src.domain.entities import Answer, Diagnosis, Hypothesis, QuestionScore, Symptom
from src.domain.knowledge_repository import KnowledgeRepository


class BayesianInferenceEngine:
    """Calcula P(H_i | evidencias) sin reglas diagnósticas codificadas."""

    def __init__(self, repository: KnowledgeRepository):
        self.repository = repository
        self.hypotheses: list[Hypothesis] = repository.get_hypotheses()
        self.symptoms: list[Symptom] = repository.get_symptoms()
        self._hypothesis_index = {item.id: index for index, item in enumerate(self.hypotheses)}
        self._assignments = list(itertools.product((False, True), repeat=len(self.hypotheses)))
        self._prior_weights = [self._prior_weight(assignment) for assignment in self._assignments]

    def _prior_weight(self, assignment: tuple[bool, ...]) -> float:
        weight = 1.0
        for present, hypothesis in zip(assignment, self.hypotheses):
            weight *= hypothesis.prior if present else 1.0 - hypothesis.prior
        return weight

    def _states(self, assignment: Sequence[bool]) -> dict[str, bool]:
        return {
            hypothesis.id: assignment[index]
            for index, hypothesis in enumerate(self.hypotheses)
        }

    def _posterior_assignment_weights(
        self, evidence: Mapping[str, Answer]
    ) -> list[float]:
        weights = self._prior_weights.copy()
        for symptom_id, answer in evidence.items():
            if answer == Answer.UNKNOWN:
                continue
            cpt = self.repository.get_cpt(symptom_id)
            observed = answer == Answer.YES
            for index, assignment in enumerate(self._assignments):
                weights[index] *= cpt.probability(observed, self._states(assignment))
        evidence_probability = sum(weights)
        if evidence_probability <= 0.0:
            raise ValueError("La evidencia ingresada tiene probabilidad cero en la red.")
        return [weight / evidence_probability for weight in weights]

    def diagnose(self, evidence: Mapping[str, Answer]) -> list[Diagnosis]:
        posterior_weights = self._posterior_assignment_weights(evidence)
        diagnoses = []
        for hypothesis_index, hypothesis in enumerate(self.hypotheses):
            posterior = sum(
                weight
                for assignment, weight in zip(self._assignments, posterior_weights)
                if assignment[hypothesis_index]
            )
            diagnoses.append(Diagnosis(hypothesis, hypothesis.prior, posterior))
        return sorted(diagnoses, key=lambda item: item.posterior, reverse=True)

    @staticmethod
    def _entropy(weights: Sequence[float]) -> float:
        return -sum(weight * math.log2(weight) for weight in weights if weight > 0.0)

    def rank_questions(
        self, evidence: Mapping[str, Answer], excluded: set[str] | None = None
    ) -> list[QuestionScore]:
        """Ordena las preguntas por ganancia de información esperada."""
        excluded = excluded or set()
        posterior = self._posterior_assignment_weights(evidence)
        current_entropy = self._entropy(posterior)
        scores: list[QuestionScore] = []

        for symptom in self.symptoms:
            if symptom.id in excluded:
                continue
            cpt = self.repository.get_cpt(symptom.id)
            likelihoods = []
            for observed in (True, False):
                likelihoods.append([
                    cpt.probability(observed, self._states(assignment))
                    for assignment in self._assignments
                ])
            p_yes = sum(
                weight * likelihood
                for weight, likelihood in zip(posterior, likelihoods[0])
            )
            expected_entropy = 0.0
            for likelihoods_for_answer, p_observation in zip(likelihoods, (p_yes, 1.0 - p_yes)):
                if p_observation <= 1e-15:
                    continue
                updated = [
                    weight * likelihood / p_observation
                    for weight, likelihood in zip(posterior, likelihoods_for_answer)
                ]
                expected_entropy += p_observation * self._entropy(updated)
            scores.append(QuestionScore(symptom, max(0.0, current_entropy - expected_entropy)))
        return sorted(scores, key=lambda item: item.information_gain, reverse=True)

    def next_question(
        self, evidence: Mapping[str, Answer], excluded: set[str] | None = None
    ) -> Symptom | None:
        ranking = self.rank_questions(evidence, excluded)
        return ranking[0].symptom if ranking else None
