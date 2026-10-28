"""Interfaz de consola; no contiene conocimiento ni cálculo probabilístico."""
from __future__ import annotations

from src.application.diagnosis_service import DiagnosisService
from src.domain.entities import Answer, Diagnosis


class ConsoleApp:
    ANSWERS = {
        "s": Answer.YES,
        "si": Answer.YES,
        "sí": Answer.YES,
        "n": Answer.NO,
        "no": Answer.NO,
        "ns": Answer.UNKNOWN,
        "no se": Answer.UNKNOWN,
        "no sé": Answer.UNKNOWN,
    }

    def __init__(self, service: DiagnosisService):
        self.service = service

    @staticmethod
    def show_diagnosis(diagnoses: list[Diagnosis]) -> None:
        print("\nProbabilidad posterior de cada hipótesis:")
        for position, diagnosis in enumerate(diagnoses, start=1):
            change = diagnosis.variation * 100
            print(
                f"  {position}. {diagnosis.hypothesis.id} - {diagnosis.hypothesis.name}: "
                f"{diagnosis.posterior:.2%} (inicial {diagnosis.prior:.2%}, "
                f"variación {change:+.2f} pp)"
            )
        print("Nota: las fallas pueden coexistir; los porcentajes no tienen que sumar 100%.")

    def run(self) -> None:
        print("SISTEMA EXPERTO BAYESIANO: DIAGNÓSTICO DE FALLAS DE COMPUTADORES")
        print("Responda: s = sí, n = no, ns = no sé, salir = terminar.")
        print("Las probabilidades iniciales son valores académicos configurables.\n")
        self.show_diagnosis(self.service.current_diagnosis())
        question_number = 0

        while True:
            symptom = self.service.next_question()
            if symptom is None:
                break
            question_number += 1
            raw = input(f"\nPregunta {question_number}: {symptom.question} > ").strip().lower()
            if raw == "salir":
                break
            answer = self.ANSWERS.get(raw)
            if answer is None:
                print("Entrada no válida. Use s, n, ns o salir.")
                continue
            self.service.register_answer(symptom.id, answer)
            self.show_diagnosis(self.service.current_diagnosis())

        print("\nRESULTADO FINAL")
        self.show_diagnosis(self.service.current_diagnosis())
        print("\nEl resultado orienta el diagnóstico; debe confirmarse con pruebas técnicas.")
