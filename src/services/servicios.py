"""Servicios de aplicación: reglas de negocio de los procesos transaccionales."""
from __future__ import annotations

import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from src.dao.conocimiento_dao import HipotesisDAO, NodoArbolDAO, ReglaDAO, SintomaDAO
from src.dao.transaccional_dao import (
    CasoDAO, ConsultaDAO, DiagnosticoDAO, EquipoDAO, RespuestaDAO, SeguimientoDAO,
)
from src.dao.usuario_dao import RolDAO, UsuarioDAO
from src.domain.models import Caso, Consulta, Diagnostico, NodoArbol, Usuario
from src.services.motor_inferencia import MotorInferencia

_CORREO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CLAVES_COMUNES = {"12345678", "123456789", "1234567890", "11111111", "password", "password1", "contrasena1",
                   "contraseña1", "qwerty123", "abc12345", "admin123", "iloveyou1"}
_HASH_FALSO = generate_password_hash("contraseña-inexistente-1")   # para igualar el tiempo si el correo no existe


class ErrorNegocio(Exception):
    """Violación de una regla de negocio; el mensaje es apto para mostrar al usuario."""


class AutenticacionService:
    def __init__(self, conexion: sqlite3.Connection):
        self.usuarios = UsuarioDAO(conexion)
        self.roles = RolDAO(conexion)

    def autenticar(self, correo: str, clave: str) -> Usuario:
        encontrado = self.usuarios.obtener_credenciales(correo)
        # Se verifica un hash aunque el correo no exista: así la respuesta tarda igual y no revela qué correos
        # tienen cuenta. El mensaje también es el mismo en ambos casos.
        if not check_password_hash(encontrado[1] if encontrado else _HASH_FALSO, clave) or not encontrado:
            raise ErrorNegocio("Correo o contraseña incorrectos.")
        if not encontrado[0].activo:
            raise ErrorNegocio("El usuario está desactivado. Contacte al administrador.")
        return encontrado[0]

    @staticmethod
    def _validar_clave(clave: str, correo: str = "", nombre: str = "") -> None:
        """Política de contraseñas: 8 a 128 caracteres, con letras y números, que no sea una clave
        típica ni coincida con el correo o el nombre de la persona."""
        if len(clave) < 8:
            raise ErrorNegocio("La contraseña debe tener al menos 8 caracteres.")
        if len(clave) > 128:
            raise ErrorNegocio("La contraseña no puede superar los 128 caracteres.")
        if not re.search(r"[^\W\d_]", clave) or not re.search(r"\d", clave):
            raise ErrorNegocio("La contraseña debe combinar letras y números.")
        propios = {correo.strip().lower(), correo.strip().lower().split("@")[0], nombre.strip().lower()} - {""}
        if clave.lower() in _CLAVES_COMUNES or clave.lower() in propios:
            raise ErrorNegocio("Esa contraseña es demasiado fácil de adivinar. Elija otra.")

    def registrar(self, nombre: str, correo: str, clave: str, rol: str = "Cliente") -> int:
        nombre, correo = " ".join(nombre.split()), correo.strip()
        if not 3 <= len(nombre) <= 80:
            raise ErrorNegocio("Ingrese un nombre de entre 3 y 80 caracteres.")
        if len(correo) > 120 or not _CORREO.match(correo):
            raise ErrorNegocio("Ingrese un correo válido.")
        self._validar_clave(clave, correo, nombre)
        rol_id = self.roles.id_por_nombre(rol)
        if rol_id is None:
            raise ErrorNegocio("Rol inexistente.")
        try:
            return self.usuarios.crear(nombre, correo, generate_password_hash(clave), rol_id)
        except ValueError as error:
            raise ErrorNegocio(str(error)) from error

    def cambiar_clave(self, usuario: Usuario, actual: str, nueva: str) -> None:
        """Cambia la contraseña del propio usuario; exige conocer la contraseña actual."""
        credenciales = self.usuarios.obtener_credenciales(usuario.correo)
        if credenciales is None or not check_password_hash(credenciales[1], actual):
            raise ErrorNegocio("La contraseña actual no es correcta.")
        self._validar_clave(nueva, usuario.correo, usuario.nombre)
        if check_password_hash(credenciales[1], nueva):
            raise ErrorNegocio("La nueva contraseña debe ser distinta de la actual.")
        self.usuarios.cambiar_clave(usuario.id, generate_password_hash(nueva))


class EquipoService:
    TIPOS = ("Escritorio", "Portátil", "Todo en uno")

    def __init__(self, conexion: sqlite3.Connection):
        self.equipos = EquipoDAO(conexion)

    def _validar(self, tipo: str, marca: str, modelo: str) -> None:
        if tipo not in self.TIPOS:
            raise ErrorNegocio("Tipo de equipo no válido.")
        if not marca.strip() or not modelo.strip():
            raise ErrorNegocio("Marca y modelo son obligatorios.")

    def registrar(self, cliente_id: int, tipo: str, marca: str, modelo: str, serial: str) -> int:
        self._validar(tipo, marca, modelo)
        return self.equipos.crear(cliente_id, tipo, marca.strip(), modelo.strip(), serial.strip())

    def actualizar(self, cliente_id: int, equipo_id: int, tipo: str, marca: str, modelo: str,
                   serial: str) -> None:
        self._validar(tipo, marca, modelo)
        self._propio(cliente_id, equipo_id)
        self.equipos.actualizar(equipo_id, tipo, marca.strip(), modelo.strip(), serial.strip())

    def eliminar(self, cliente_id: int, equipo_id: int) -> None:
        self._propio(cliente_id, equipo_id)
        if self.equipos.tiene_casos(equipo_id):
            raise ErrorNegocio("No se puede eliminar un equipo que tiene casos registrados.")
        self.equipos.eliminar(equipo_id)

    def _propio(self, cliente_id: int, equipo_id: int):
        equipo = self.equipos.obtener(equipo_id)
        if equipo is None or equipo.cliente_id != cliente_id:
            raise ErrorNegocio("Equipo no encontrado.")
        return equipo


class DiagnosticoService:
    """Orquesta el ciclo de vida de un caso: abrir, consultar, atender y resolver."""

    def __init__(self, conexion: sqlite3.Connection):
        self.conexion = conexion
        self.equipos = EquipoDAO(conexion)
        self.casos = CasoDAO(conexion)
        self.consultas = ConsultaDAO(conexion)
        self.respuestas = RespuestaDAO(conexion)
        self.diagnosticos = DiagnosticoDAO(conexion)
        self.seguimientos = SeguimientoDAO(conexion)
        self.nodos = NodoArbolDAO(conexion)
        self.sintomas = SintomaDAO(conexion)
        self.hipotesis = HipotesisDAO(conexion)
        self.reglas = ReglaDAO(conexion)
        self.motor = MotorInferencia(self.nodos, self.reglas)

    # --- casos ---------------------------------------------------------------
    def abrir_caso(self, cliente_id: int, equipo_id: int, descripcion: str) -> int:
        equipo = self.equipos.obtener(equipo_id)
        if equipo is None or equipo.cliente_id != cliente_id:
            raise ErrorNegocio("Seleccione uno de sus equipos.")
        if len(descripcion.strip()) < 10:
            raise ErrorNegocio("Describa el problema con al menos 10 caracteres.")
        if len(descripcion.strip()) > 1000:
            raise ErrorNegocio("La descripción no puede superar los 1000 caracteres.")
        return self.casos.crear(equipo_id, cliente_id, descripcion.strip())

    def historial(self, cliente_id: int, limite: int = 5):
        """Últimas consultas del cliente, de la más reciente a la más antigua."""
        return self.casos.resumen_consultas(cliente_id, limite)

    def ficha(self, caso: Caso) -> dict:
        """Todo lo que se muestra de una consulta ya hecha: diagnóstico, falla, regla y respuestas dadas."""
        diagnostico = self.diagnosticos.por_caso(caso.id)
        consulta = self.consultas.ultima_por_caso(caso.id)
        return {
            "diagnostico": diagnostico,
            "hipotesis": self.hipotesis.obtener(diagnostico.hipotesis_id) if diagnostico else None,
            "regla": self.reglas.obtener(diagnostico.regla_id) if diagnostico else None,
            "consulta": consulta,
            "respuestas": self.respuestas.listar(consulta.id) if consulta else [],
        }

    # --- consulta de diagnóstico ----------------------------------------------
    def iniciar_consulta(self, caso: Caso) -> Consulta:
        if caso.estado != "Abierto":
            raise ErrorNegocio("Solo se puede iniciar la consulta en un caso abierto.")
        existente = self.consultas.ultima_por_caso(caso.id)
        if existente and existente.estado == "En curso":
            return existente
        consulta_id = self.consultas.crear(caso.id, self.motor.nodo_inicial().id)
        return self.consultas.obtener(consulta_id)

    def evidencia(self, consulta_id: int) -> dict[int, str]:
        return {r.sintoma_id: r.valor for r in self.respuestas.listar(consulta_id)}

    def pregunta_actual(self, consulta: Consulta) -> tuple[NodoArbol, str]:
        nodo = self.nodos.obtener(consulta.nodo_actual_id)
        sintoma = self.sintomas.obtener(nodo.sintoma_id)
        return nodo, sintoma.pregunta

    def responder(self, consulta_id: int, valor: str, nodo_id: int | None = None) -> Diagnostico | None:
        """Registra la respuesta y avanza; devuelve el diagnóstico cuando se llega a una hoja.

        Todas las validaciones (incluida la coherencia entre el árbol y las reglas) se hacen antes
        de escribir, de modo que un error no deja la consulta a medias. ``nodo_id`` es la pregunta
        que el usuario tenía en pantalla: si ya no es la actual (doble clic, botón «atrás» del
        navegador), la respuesta se rechaza en lugar de aplicarse a otra pregunta.
        """
        consulta = self.consultas.obtener(consulta_id)
        if consulta is None or consulta.estado != "En curso":
            raise ErrorNegocio("La consulta ya finalizó.")
        if valor not in ("si", "no"):
            raise ErrorNegocio("Responda Sí o No.")
        if nodo_id is not None and nodo_id != consulta.nodo_actual_id:
            raise ErrorNegocio("Esa pregunta ya fue respondida. Continúe con la pregunta actual.")
        nodo = self.nodos.obtener(consulta.nodo_actual_id)
        siguiente = self.motor.siguiente_nodo(nodo, valor)

        resultado = None
        if siguiente.es_hoja:
            evidencia = self.evidencia(consulta_id)
            evidencia[nodo.sintoma_id] = valor
            resultado = self.motor.diagnosticar(evidencia)
            if resultado is None or resultado.hipotesis_id != siguiente.hipotesis_id:
                raise ErrorNegocio("Inconsistencia entre el árbol y las reglas de la base de conocimiento.")

        orden = len(self.respuestas.listar(consulta_id)) + 1
        self.respuestas.registrar(consulta_id, nodo.id, nodo.sintoma_id, valor, orden)
        if resultado is None:
            self.consultas.mover_a_nodo(consulta_id, siguiente.id)
            return None

        self.consultas.finalizar(consulta_id, siguiente.id)
        self.diagnosticos.crear(
            consulta_id, resultado.hipotesis_id, resultado.regla.id, resultado.factor_certeza)
        self.casos.cambiar_estado(consulta.caso_id, "Diagnosticado")
        return self.diagnosticos.por_consulta(consulta_id)

    def retroceder(self, consulta_id: int) -> None:
        consulta = self.consultas.obtener(consulta_id)
        if consulta is None or consulta.estado != "En curso":
            raise ErrorNegocio("La consulta ya finalizó.")
        ultima = self.respuestas.ultima(consulta_id)
        if ultima is None:
            raise ErrorNegocio("No hay respuestas anteriores.")
        self.respuestas.eliminar(ultima.id)
        self.consultas.mover_a_nodo(consulta_id, ultima.nodo_id)

    def candidatas(self, consulta_id: int) -> int:
        return len(self.motor.reglas_posibles(self.evidencia(consulta_id)))

    # --- atención técnica ------------------------------------------------------
    def tomar_caso(self, caso_id: int, tecnico_id: int) -> None:
        if not self.casos.asignar_tecnico(caso_id, tecnico_id):
            raise ErrorNegocio("El caso ya fue tomado por otro técnico o no está diagnosticado.")

    def registrar_seguimiento(self, caso: Caso, tecnico_id: int, observacion: str, accion: str) -> None:
        if caso.tecnico_id != tecnico_id or caso.estado != "En atención":
            raise ErrorNegocio("Solo el técnico asignado puede registrar seguimiento en un caso en atención.")
        if len(observacion.strip()) < 5:
            raise ErrorNegocio("Escriba una observación de al menos 5 caracteres.")
        self.seguimientos.crear(caso.id, tecnico_id, observacion.strip(), accion.strip())

    def resolver_caso(self, caso: Caso, tecnico_id: int, diagnostico_correcto: bool,
                      observacion: str) -> None:
        if caso.tecnico_id != tecnico_id or caso.estado != "En atención":
            raise ErrorNegocio("Solo el técnico asignado puede resolver un caso en atención.")
        diagnostico = self.diagnosticos.por_caso(caso.id)
        if diagnostico is None:
            raise ErrorNegocio("El caso no tiene diagnóstico.")
        if len(observacion.strip()) < 5:
            raise ErrorNegocio("Describa brevemente la solución aplicada.")
        self.seguimientos.crear(caso.id, tecnico_id, observacion.strip(), "Cierre del caso")
        self.diagnosticos.confirmar(diagnostico.id, diagnostico_correcto)
        self.casos.cambiar_estado(caso.id, "Resuelto")
