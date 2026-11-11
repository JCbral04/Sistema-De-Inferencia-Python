"""DAO de los procesos transaccionales: equipos, casos, consultas y diagnósticos."""
from __future__ import annotations

from src.dao.base import BaseDAO
from src.domain.models import (
    Caso, Consulta, Diagnostico, Equipo, Respuesta, Seguimiento,
)


class EquipoDAO(BaseDAO):
    def crear(self, cliente_id: int, tipo: str, marca: str, modelo: str, serial: str | None) -> int:
        return self._ejecutar(
            "INSERT INTO equipo(cliente_id, tipo, marca, modelo, serial) VALUES(?, ?, ?, ?, ?)",
            (cliente_id, tipo, marca, modelo, serial or None))

    def obtener(self, equipo_id: int) -> Equipo | None:
        fila = self._uno("SELECT * FROM equipo WHERE id = ?", (equipo_id,))
        return Equipo(**dict(fila)) if fila else None

    def listar_por_cliente(self, cliente_id: int) -> list[Equipo]:
        return [Equipo(**dict(f)) for f in self._todos(
            "SELECT * FROM equipo WHERE cliente_id = ? ORDER BY id DESC", (cliente_id,))]

    def actualizar(self, equipo_id: int, tipo: str, marca: str, modelo: str, serial: str | None) -> None:
        self._ejecutar("UPDATE equipo SET tipo = ?, marca = ?, modelo = ?, serial = ? WHERE id = ?",
                       (tipo, marca, modelo, serial or None, equipo_id))

    def eliminar(self, equipo_id: int) -> None:
        self._ejecutar("DELETE FROM equipo WHERE id = ?", (equipo_id,))

    def tiene_casos(self, equipo_id: int) -> bool:
        return self._uno("SELECT 1 FROM caso WHERE equipo_id = ? LIMIT 1", (equipo_id,)) is not None


_SELECT_CASO = """
    SELECT c.id, c.equipo_id, c.cliente_id, c.tecnico_id, c.descripcion, c.estado,
           c.abierto_en, c.cerrado_en,
           e.marca || ' ' || e.modelo AS equipo, cl.nombre AS cliente, t.nombre AS tecnico
    FROM caso c
    JOIN equipo  e  ON e.id  = c.equipo_id
    JOIN usuario cl ON cl.id = c.cliente_id
    LEFT JOIN usuario t ON t.id = c.tecnico_id
"""


class CasoDAO(BaseDAO):
    def crear(self, equipo_id: int, cliente_id: int, descripcion: str) -> int:
        return self._ejecutar(
            "INSERT INTO caso(equipo_id, cliente_id, descripcion) VALUES(?, ?, ?)",
            (equipo_id, cliente_id, descripcion))

    def obtener(self, caso_id: int) -> Caso | None:
        fila = self._uno(_SELECT_CASO + " WHERE c.id = ?", (caso_id,))
        return Caso(**dict(fila)) if fila else None

    def listar(self, cliente_id: int | None = None, tecnico_id: int | None = None,
               estado: str | None = None) -> list[Caso]:
        condiciones, parametros = [], []
        if cliente_id is not None:
            condiciones.append("c.cliente_id = ?"); parametros.append(cliente_id)
        if tecnico_id is not None:
            condiciones.append("c.tecnico_id = ?"); parametros.append(tecnico_id)
        if estado is not None:
            condiciones.append("c.estado = ?"); parametros.append(estado)
        where = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
        return [Caso(**dict(f)) for f in self._todos(
            _SELECT_CASO + where + " ORDER BY c.id DESC", parametros)]

    def cola_sin_tecnico(self) -> list[Caso]:
        return [Caso(**dict(f)) for f in self._todos(
            _SELECT_CASO + " WHERE c.estado = 'Diagnosticado' AND c.tecnico_id IS NULL ORDER BY c.id")]

    def cambiar_estado(self, caso_id: int, estado: str) -> None:
        cierre = "datetime('now')" if estado == "Resuelto" else "NULL"
        self._ejecutar(f"UPDATE caso SET estado = ?, cerrado_en = {cierre} WHERE id = ?",
                       (estado, caso_id))

    def asignar_tecnico(self, caso_id: int, tecnico_id: int) -> bool:
        """Asigna solo si el caso sigue libre (evita que dos técnicos tomen el mismo caso)."""
        cursor = self.conexion.execute(
            """UPDATE caso SET tecnico_id = ?, estado = 'En atención'
               WHERE id = ? AND tecnico_id IS NULL AND estado = 'Diagnosticado'""",
            (tecnico_id, caso_id))
        return cursor.rowcount == 1

    def contar_por_estado(self) -> dict[str, int]:
        return {f["estado"]: f["n"] for f in self._todos(
            "SELECT estado, COUNT(*) AS n FROM caso GROUP BY estado")}


class ConsultaDAO(BaseDAO):
    def crear(self, caso_id: int, nodo_inicial_id: int) -> int:
        return self._ejecutar("INSERT INTO consulta(caso_id, nodo_actual_id) VALUES(?, ?)",
                              (caso_id, nodo_inicial_id))

    def obtener(self, consulta_id: int) -> Consulta | None:
        fila = self._uno("SELECT * FROM consulta WHERE id = ?", (consulta_id,))
        return Consulta(**dict(fila)) if fila else None

    def ultima_por_caso(self, caso_id: int) -> Consulta | None:
        fila = self._uno("SELECT * FROM consulta WHERE caso_id = ? ORDER BY id DESC LIMIT 1", (caso_id,))
        return Consulta(**dict(fila)) if fila else None

    def mover_a_nodo(self, consulta_id: int, nodo_id: int) -> None:
        self._ejecutar("UPDATE consulta SET nodo_actual_id = ? WHERE id = ?", (nodo_id, consulta_id))

    def finalizar(self, consulta_id: int, nodo_hoja_id: int) -> None:
        self._ejecutar(
            """UPDATE consulta SET estado = 'Finalizada', nodo_actual_id = ?,
                      finalizada_en = datetime('now') WHERE id = ?""",
            (nodo_hoja_id, consulta_id))


class RespuestaDAO(BaseDAO):
    def registrar(self, consulta_id: int, nodo_id: int, sintoma_id: int, valor: str, orden: int) -> int:
        return self._ejecutar(
            """INSERT INTO respuesta(consulta_id, nodo_id, sintoma_id, valor, orden)
               VALUES(?, ?, ?, ?, ?)""", (consulta_id, nodo_id, sintoma_id, valor, orden))

    def listar(self, consulta_id: int) -> list[Respuesta]:
        return [Respuesta(**dict(f)) for f in self._todos(
            """SELECT r.id, r.consulta_id, r.nodo_id, r.sintoma_id, r.valor, r.orden,
                      s.pregunta, s.codigo AS sintoma_codigo
               FROM respuesta r JOIN sintoma s ON s.id = r.sintoma_id
               WHERE r.consulta_id = ? ORDER BY r.orden""", (consulta_id,))]

    def ultima(self, consulta_id: int) -> Respuesta | None:
        respuestas = self.listar(consulta_id)
        return respuestas[-1] if respuestas else None

    def eliminar(self, respuesta_id: int) -> None:
        self._ejecutar("DELETE FROM respuesta WHERE id = ?", (respuesta_id,))


class DiagnosticoDAO(BaseDAO):
    def crear(self, consulta_id: int, hipotesis_id: int, regla_id: int, factor_certeza: float) -> int:
        return self._ejecutar(
            """INSERT INTO diagnostico(consulta_id, hipotesis_id, regla_id, factor_certeza)
               VALUES(?, ?, ?, ?)""", (consulta_id, hipotesis_id, regla_id, factor_certeza))

    def por_consulta(self, consulta_id: int) -> Diagnostico | None:
        fila = self._uno("SELECT * FROM diagnostico WHERE consulta_id = ?", (consulta_id,))
        return self._construir(fila)

    def por_caso(self, caso_id: int) -> Diagnostico | None:
        fila = self._uno(
            """SELECT d.* FROM diagnostico d JOIN consulta c ON c.id = d.consulta_id
               WHERE c.caso_id = ? ORDER BY d.id DESC LIMIT 1""", (caso_id,))
        return self._construir(fila)

    def confirmar(self, diagnostico_id: int, confirmado: bool) -> None:
        self._ejecutar("UPDATE diagnostico SET confirmado = ? WHERE id = ?",
                       (int(confirmado), diagnostico_id))

    def frecuencia_por_hipotesis(self) -> list[dict]:
        return [dict(f) for f in self._todos(
            """SELECT h.codigo, h.nombre, COUNT(d.id) AS total,
                      SUM(CASE WHEN d.confirmado = 1 THEN 1 ELSE 0 END) AS confirmados,
                      SUM(CASE WHEN d.confirmado = 0 THEN 1 ELSE 0 END) AS rechazados,
                      ROUND(100.0 * SUM(CASE WHEN d.confirmado = 1 THEN 1 ELSE 0 END)
                            / NULLIF(SUM(CASE WHEN d.confirmado IS NOT NULL THEN 1 ELSE 0 END), 0))
                          AS tasa_confirmacion
               FROM hipotesis h JOIN diagnostico d ON d.hipotesis_id = h.id
               GROUP BY h.id ORDER BY total DESC, h.codigo""")]

    @staticmethod
    def _construir(fila) -> Diagnostico | None:
        if not fila:
            return None
        datos = dict(fila)
        datos["confirmado"] = None if datos["confirmado"] is None else bool(datos["confirmado"])
        return Diagnostico(**datos)


class SeguimientoDAO(BaseDAO):
    def crear(self, caso_id: int, tecnico_id: int, observacion: str, accion: str | None) -> int:
        return self._ejecutar(
            """INSERT INTO seguimiento(caso_id, tecnico_id, observacion, accion_realizada)
               VALUES(?, ?, ?, ?)""", (caso_id, tecnico_id, observacion, accion or None))

    def listar_por_caso(self, caso_id: int) -> list[Seguimiento]:
        return [Seguimiento(**dict(f)) for f in self._todos(
            """SELECT s.*, u.nombre AS tecnico FROM seguimiento s
               JOIN usuario u ON u.id = s.tecnico_id
               WHERE s.caso_id = ? ORDER BY s.id""", (caso_id,))]
