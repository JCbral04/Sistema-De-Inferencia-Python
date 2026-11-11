"""DAO de la base de conocimiento. Cada método ejecuta una consulta granular."""
from __future__ import annotations

from src.dao.base import BaseDAO
from src.domain.models import (
    Categoria, Condicion, Hipotesis, NodoArbol, Regla, Sintoma,
)

_SELECT_HIPOTESIS = """
    SELECT h.id, h.codigo, h.nombre, h.descripcion, h.categoria_id,
           c.nombre AS categoria, h.severidad, h.factor_certeza, h.solucion,
           e.nombre AS experto
    FROM hipotesis h
    JOIN categoria c ON c.id = h.categoria_id
    JOIN experto   e ON e.id = h.experto_id
"""


def _hipotesis(fila) -> Hipotesis:
    return Hipotesis(**{k: fila[k] for k in fila.keys()})


class CategoriaDAO(BaseDAO):
    def listar(self) -> list[Categoria]:
        return [Categoria(**dict(f)) for f in self._todos(
            "SELECT id, codigo, nombre, descripcion FROM categoria ORDER BY codigo")]


class SintomaDAO(BaseDAO):
    def listar(self) -> list[Sintoma]:
        return [Sintoma(**dict(f)) for f in self._todos(
            "SELECT id, codigo, pregunta FROM sintoma ORDER BY codigo")]

    def obtener(self, sintoma_id: int) -> Sintoma | None:
        fila = self._uno("SELECT id, codigo, pregunta FROM sintoma WHERE id = ?", (sintoma_id,))
        return Sintoma(**dict(fila)) if fila else None

    def actualizar_pregunta(self, sintoma_id: int, pregunta: str) -> None:
        self._ejecutar("UPDATE sintoma SET pregunta = ? WHERE id = ?", (pregunta, sintoma_id))


class HipotesisDAO(BaseDAO):
    def listar(self) -> list[Hipotesis]:
        return [_hipotesis(f) for f in self._todos(_SELECT_HIPOTESIS + " ORDER BY h.codigo")]

    def obtener(self, hipotesis_id: int) -> Hipotesis | None:
        fila = self._uno(_SELECT_HIPOTESIS + " WHERE h.id = ?", (hipotesis_id,))
        return _hipotesis(fila) if fila else None

    def obtener_por_codigo(self, codigo: str) -> Hipotesis | None:
        fila = self._uno(_SELECT_HIPOTESIS + " WHERE h.codigo = ?", (codigo,))
        return _hipotesis(fila) if fila else None

    def listar_por_categoria(self, categoria_id: int) -> list[Hipotesis]:
        return [_hipotesis(f) for f in self._todos(
            _SELECT_HIPOTESIS + " WHERE h.categoria_id = ? ORDER BY h.codigo", (categoria_id,))]

    def actualizar(self, hipotesis_id: int, nombre: str, descripcion: str, severidad: str,
                   factor_certeza: float, solucion: str) -> None:
        self._ejecutar(
            """UPDATE hipotesis SET nombre = ?, descripcion = ?, severidad = ?,
                      factor_certeza = ?, solucion = ? WHERE id = ?""",
            (nombre, descripcion, severidad, factor_certeza, solucion, hipotesis_id))
        # La regla de la hipótesis hereda su factor de certeza.
        self._ejecutar("UPDATE regla SET factor_certeza = ? WHERE hipotesis_id = ?",
                       (factor_certeza, hipotesis_id))


class NodoArbolDAO(BaseDAO):
    _COLUMNAS = "id, codigo, padre_id, rama, sintoma_id, hipotesis_id"

    def raiz(self) -> NodoArbol:
        fila = self._uno(f"SELECT {self._COLUMNAS} FROM nodo_arbol WHERE padre_id IS NULL")
        return NodoArbol(**dict(fila))

    def obtener(self, nodo_id: int) -> NodoArbol | None:
        fila = self._uno(f"SELECT {self._COLUMNAS} FROM nodo_arbol WHERE id = ?", (nodo_id,))
        return NodoArbol(**dict(fila)) if fila else None

    def hijo(self, nodo_id: int, rama: str) -> NodoArbol | None:
        fila = self._uno(
            f"SELECT {self._COLUMNAS} FROM nodo_arbol WHERE padre_id = ? AND rama = ?",
            (nodo_id, rama))
        return NodoArbol(**dict(fila)) if fila else None

    def listar(self) -> list[NodoArbol]:
        return [NodoArbol(**dict(f)) for f in self._todos(
            f"SELECT {self._COLUMNAS} FROM nodo_arbol ORDER BY id")]

    def contar_hojas(self) -> int:
        return self._uno("SELECT COUNT(*) AS n FROM nodo_arbol WHERE hipotesis_id IS NOT NULL")["n"]


class ReglaDAO(BaseDAO):
    def _construir(self, filas_regla, filas_cond) -> list[Regla]:
        condiciones: dict[int, list[Condicion]] = {}
        for c in filas_cond:
            condiciones.setdefault(c["regla_id"], []).append(
                Condicion(c["sintoma_id"], c["sintoma_codigo"], c["pregunta"], c["valor"]))
        return [Regla(r["id"], r["codigo"], r["hipotesis_id"], r["nodo_hoja_id"],
                      r["factor_certeza"], tuple(condiciones.get(r["id"], ())))
                for r in filas_regla]

    _SQL_CONDICIONES = """
        SELECT rc.regla_id, rc.orden, rc.sintoma_id, s.codigo AS sintoma_codigo,
               s.pregunta, rc.valor
        FROM regla_condicion rc JOIN sintoma s ON s.id = rc.sintoma_id
    """

    def listar(self) -> list[Regla]:
        reglas = self._todos(
            "SELECT id, codigo, hipotesis_id, nodo_hoja_id, factor_certeza FROM regla ORDER BY codigo")
        condiciones = self._todos(self._SQL_CONDICIONES + " ORDER BY rc.regla_id, rc.orden")
        return self._construir(reglas, condiciones)

    def obtener(self, regla_id: int) -> Regla | None:
        reglas = self._todos(
            "SELECT id, codigo, hipotesis_id, nodo_hoja_id, factor_certeza FROM regla WHERE id = ?",
            (regla_id,))
        condiciones = self._todos(self._SQL_CONDICIONES + " WHERE rc.regla_id = ? ORDER BY rc.orden",
                                  (regla_id,))
        resultado = self._construir(reglas, condiciones)
        return resultado[0] if resultado else None

    def por_hipotesis(self, hipotesis_id: int) -> list[Regla]:
        """Gránulo de conocimiento: reglas y condiciones que sustentan una hipótesis."""
        reglas = self._todos(
            """SELECT id, codigo, hipotesis_id, nodo_hoja_id, factor_certeza
               FROM regla WHERE hipotesis_id = ? ORDER BY codigo""", (hipotesis_id,))
        condiciones = self._todos(
            self._SQL_CONDICIONES + """ JOIN regla r ON r.id = rc.regla_id
               WHERE r.hipotesis_id = ? ORDER BY rc.regla_id, rc.orden""", (hipotesis_id,))
        return self._construir(reglas, condiciones)
