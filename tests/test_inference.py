import tempfile
import unittest
from pathlib import Path

from src.application.diagnosis_service import DiagnosisService
from src.application.inference_engine import BayesianInferenceEngine
from src.domain.entities import Answer
from src.infrastructure.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
    initialize_database,
)


ROOT = Path(__file__).resolve().parents[1]


class BayesianInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary_directory = tempfile.TemporaryDirectory()
        database = Path(cls.temporary_directory.name) / "test_knowledge.db"
        initialize_database(ROOT / "data" / "knowledge_base.json", database)
        cls.repository = SQLiteKnowledgeRepository(database)
        cls.engine = BayesianInferenceEngine(cls.repository)

    @classmethod
    def tearDownClass(cls):
        cls.temporary_directory.cleanup()

    def test_without_evidence_returns_the_five_priors(self):
        diagnoses = self.engine.diagnose({})
        self.assertEqual(5, len(diagnoses))
        for diagnosis in diagnoses:
            self.assertAlmostEqual(diagnosis.prior, diagnosis.posterior)

    def test_positive_power_symptom_increases_power_failure_probability(self):
        initial = {item.hypothesis.id: item.posterior for item in self.engine.diagnose({})}
        updated = {
            item.hypothesis.id: item.posterior
            for item in self.engine.diagnose({"S1": Answer.YES})
        }
        self.assertGreater(updated["H1"], initial["H1"])
        self.assertTrue(all(0.0 <= value <= 1.0 for value in updated.values()))

    def test_negative_disk_symptom_decreases_storage_failure_probability(self):
        initial = {item.hypothesis.id: item.posterior for item in self.engine.diagnose({})}
        updated = {
            item.hypothesis.id: item.posterior
            for item in self.engine.diagnose({"S5": Answer.NO})
        }
        self.assertLess(updated["H4"], initial["H4"])

    def test_unknown_answer_does_not_change_evidence(self):
        service = DiagnosisService(self.repository)
        service.register_answer("S1", Answer.UNKNOWN)
        self.assertEqual({}, service.evidence)
        self.assertNotEqual("S1", service.next_question().id)

    def test_question_ranking_uses_nonnegative_information_gain(self):
        ranking = self.engine.rank_questions({})
        self.assertEqual(10, len(ranking))
        self.assertTrue(all(item.information_gain >= 0.0 for item in ranking))
        self.assertGreaterEqual(
            ranking[0].information_gain, ranking[-1].information_gain
        )

    def test_all_cpts_are_complete(self):
        for symptom in self.repository.get_symptoms():
            cpt = self.repository.get_cpt(symptom.id)
            self.assertEqual(2 ** len(symptom.parent_ids), len(cpt.probability_yes))


if __name__ == "__main__":
    unittest.main()
