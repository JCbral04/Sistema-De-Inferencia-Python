"""Punto de entrada y composición de las tres capas."""
from pathlib import Path

from src.application.diagnosis_service import DiagnosisService
from src.infrastructure.sqlite_knowledge_repository import (
    SQLiteKnowledgeRepository,
    initialize_database,
)
from src.presentation.console_app import ConsoleApp


ROOT = Path(__file__).resolve().parent
DATABASE = ROOT / "data" / "knowledge.db"
SOURCE = ROOT / "data" / "knowledge_base.json"


def main() -> None:
    if not DATABASE.exists():
        initialize_database(SOURCE, DATABASE)
    repository = SQLiteKnowledgeRepository(DATABASE)
    service = DiagnosisService(repository)
    ConsoleApp(service).run()


if __name__ == "__main__":
    main()
