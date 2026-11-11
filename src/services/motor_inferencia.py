"""Motor de inferencia: árbol de decisión + reglas SI-ENTONCES con encadenamiento hacia adelante."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from src.dao.conocimiento_dao import NodoArbolDAO, ReglaDAO
from src.domain.models import NodoArbol, Regla


@dataclass(frozen=True, slots=True)
class ResultadoInferencia:
    regla: Regla
    hipotesis_id: int
    factor_certeza: float


class MotorInferencia:
    """Trabaja sobre la evidencia {sintoma_id: 'si' | 'no'} acumulada en la consulta."""

    def __init__(self, nodos: NodoArbolDAO, reglas: ReglaDAO):
        self._nodos = nodos
        self._reglas_dao = reglas
        self._reglas: list[Regla] | None = None

    @property
    def reglas(self) -> list[Regla]:
        if self._reglas is None:
            self._reglas = self._reglas_dao.listar()
        return self._reglas

    # --- navegación del árbol -------------------------------------------------
    def nodo_inicial(self) -> NodoArbol:
        return self._nodos.raiz()

    def siguiente_nodo(self, nodo: NodoArbol, valor: str) -> NodoArbol:
        if valor not in ("si", "no"):
            raise ValueError("La respuesta debe ser 'si' o 'no'.")
        if nodo.es_hoja:
            raise ValueError("El nodo actual ya es una conclusión.")
        hijo = self._nodos.hijo(nodo.id, valor)
        if hijo is None:
            raise LookupError(f"El nodo {nodo.codigo} no tiene rama '{valor}'.")
        return hijo

    # --- encadenamiento hacia adelante ---------------------------------------
    def reglas_posibles(self, evidencia: Mapping[int, str]) -> list[Regla]:
        """Reglas que la evidencia aún no contradice (candidatas durante la consulta)."""
        return [r for r in self.reglas
                if all(evidencia.get(c.sintoma_id, c.valor) == c.valor for c in r.condiciones)]

    def reglas_disparadas(self, evidencia: Mapping[int, str]) -> list[Regla]:
        """Reglas cuyas condiciones están todas presentes y se cumplen."""
        return [r for r in self.reglas
                if all(evidencia.get(c.sintoma_id) == c.valor for c in r.condiciones)]

    def diagnosticar(self, evidencia: Mapping[int, str]) -> ResultadoInferencia | None:
        disparadas = self.reglas_disparadas(evidencia)
        if not disparadas:
            return None
        # Resolución de conflictos: mayor factor de certeza, luego mayor especificidad.
        regla = max(disparadas, key=lambda r: (r.factor_certeza, len(r.condiciones)))
        return ResultadoInferencia(regla, regla.hipotesis_id, regla.factor_certeza)
