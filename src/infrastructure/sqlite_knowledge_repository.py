"""Persistencia SQLite y consultas granulares a la base de conocimiento."""
from __future__ import annotations

import itertools
import json
import sqlite3
from pathlib import Path

from src.domain.entities import ConditionalProbabilityTable, Hypothesis, Symptom
from src.domain.knowledge_repository import KnowledgeRepository


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE hypotheses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    prior REAL NOT NULL CHECK(prior > 0 AND prior < 1)
);
CREATE TABLE symptoms (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL
);
CREATE TABLE symptom_parents (
    symptom_id TEXT NOT NULL REFERENCES symptoms(id) ON DELETE CASCADE,
    hypothesis_id TEXT NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    parent_order INTEGER NOT NULL,
    PRIMARY KEY(symptom_id, hypothesis_id)
);
CREATE TABLE cpt_entries (
    symptom_id TEXT NOT NULL REFERENCES symptoms(id) ON DELETE CASCADE,
    parent_state TEXT NOT NULL,
    probability_yes REAL NOT NULL CHECK(probability_yes >= 0 AND probability_yes <= 1),
    PRIMARY KEY(symptom_id, parent_state)
);
"""


def initialize_database(json_path: Path, database_path: Path) -> None:
    """Crea y valida la base de conocimiento a partir de su fuente editable."""
    knowledge = json.loads(json_path.read_text(encoding="utf-8"))
    hypotheses = knowledge["hypotheses"]
    symptoms = knowledge["symptoms"]
    if len(hypotheses) != 5:
        raise ValueError("La base debe contener exactamente cinco hipótesis.")
    hypothesis_ids = {item["id"] for item in hypotheses}
    database_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists():
        database_path.unlink()

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.executemany(
            "INSERT INTO hypotheses(id, name, description, prior) VALUES(:id, :name, :description, :prior)",
            hypotheses,
        )
        for symptom in symptoms:
            parents = symptom["parents"]
            cpt = symptom["cpt"]
            if not set(parents).issubset(hypothesis_ids):
                raise ValueError(f"Padres desconocidos en {symptom['id']}.")
            expected_states = {
                "".join(bits)
                for bits in itertools.product("01", repeat=len(parents))
            }
            if set(cpt) != expected_states:
                raise ValueError(f"Tabla de probabilidad incompleta en {symptom['id']}.")
            if any(not 0.0 <= probability <= 1.0 for probability in cpt.values()):
                raise ValueError(f"Probabilidad inválida en {symptom['id']}.")
            connection.execute(
                "INSERT INTO symptoms(id, question) VALUES(:id, :question)", symptom
            )
            connection.executemany(
                "INSERT INTO symptom_parents(symptom_id, hypothesis_id, parent_order) VALUES(?, ?, ?)",
                [(symptom["id"], parent, order) for order, parent in enumerate(parents)],
            )
            connection.executemany(
                "INSERT INTO cpt_entries(symptom_id, parent_state, probability_yes) VALUES(?, ?, ?)",
                [(symptom["id"], state, probability) for state, probability in cpt.items()],
            )
        connection.commit()


class SQLiteKnowledgeRepository(KnowledgeRepository):
    """Cada método ejecuta una consulta específica; no devuelve reglas condicionales."""

    def __init__(self, database_path: Path):
        self.database_path = database_path

    def _connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def get_hypotheses(self) -> list[Hypothesis]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, name, description, prior FROM hypotheses ORDER BY id"
            ).fetchall()
        return [Hypothesis(row["id"], row["name"], row["description"], row["prior"]) for row in rows]

    def get_symptoms(self) -> list[Symptom]:
        with self._connection() as connection:
            rows = connection.execute("SELECT id FROM symptoms ORDER BY id").fetchall()
        return [self.get_symptom(row["id"]) for row in rows]

    def get_symptom(self, symptom_id: str) -> Symptom:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, question FROM symptoms WHERE id = ?", (symptom_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"Síntoma desconocido: {symptom_id}")
            parent_rows = connection.execute(
                """SELECT hypothesis_id FROM symptom_parents
                   WHERE symptom_id = ? ORDER BY parent_order""",
                (symptom_id,),
            ).fetchall()
        return Symptom(
            id=row["id"],
            question=row["question"],
            parent_ids=tuple(parent["hypothesis_id"] for parent in parent_rows),
        )

    def get_question(self, symptom_id: str) -> str:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT question FROM symptoms WHERE id = ?", (symptom_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Síntoma desconocido: {symptom_id}")
        return row["question"]

    def get_cpt(self, symptom_id: str) -> ConditionalProbabilityTable:
        symptom = self.get_symptom(symptom_id)
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT parent_state, probability_yes FROM cpt_entries
                   WHERE symptom_id = ? ORDER BY parent_state""",
                (symptom_id,),
            ).fetchall()
        probabilities = {
            tuple(bit == "1" for bit in row["parent_state"]): row["probability_yes"]
            for row in rows
        }
        return ConditionalProbabilityTable(symptom_id, symptom.parent_ids, probabilities)
