"""Clase base de los DAO: acceso común a la conexión SQLite."""
from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def abrir_conexion(ruta: Path | str) -> sqlite3.Connection:
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA foreign_keys = ON")
    return conexion


class BaseDAO:
    """Cada DAO recibe una conexión; la transacción la controla quien la creó."""

    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion

    def _uno(self, sql: str, parametros: Iterable[Any] = ()) -> sqlite3.Row | None:
        return self.conexion.execute(sql, tuple(parametros)).fetchone()

    def _todos(self, sql: str, parametros: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return self.conexion.execute(sql, tuple(parametros)).fetchall()

    def _ejecutar(self, sql: str, parametros: Iterable[Any] = ()) -> int:
        cursor = self.conexion.execute(sql, tuple(parametros))
        return cursor.lastrowid or 0
