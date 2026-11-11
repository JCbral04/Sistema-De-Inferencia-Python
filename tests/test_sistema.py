"""Pruebas del conocimiento, el motor de inferencia y los procesos transaccionales."""
import itertools
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.dao.base import abrir_conexion
from src.dao.conocimiento_dao import HipotesisDAO, NodoArbolDAO, ReglaDAO
from src.dao.inicializador import RUTA_CONOCIMIENTO, crear_base_datos, validar_arbol
from src.services.motor_inferencia import MotorInferencia
from src.services.servicios import (
    AutenticacionService, DiagnosticoService, EquipoService, ErrorNegocio,
)


class BaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self.tmp.name) / "test.db"
        crear_base_datos(self.ruta)
        self.con = abrir_conexion(self.ruta)

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()


class TestConocimiento(BaseTest):
    def test_minimo_25_ramas_y_una_regla_por_hoja(self):
        nodos = NodoArbolDAO(self.con)
        reglas = ReglaDAO(self.con).listar()
        self.assertGreaterEqual(nodos.contar_hojas(), 25)
        self.assertEqual(len(reglas), nodos.contar_hojas())
        self.assertEqual(len({r.hipotesis_id for r in reglas}), len(reglas))

    def test_cada_ruta_dispara_exactamente_su_regla(self):
        motor = MotorInferencia(NodoArbolDAO(self.con), ReglaDAO(self.con))
        for regla in motor.reglas:
            evidencia = {c.sintoma_id: c.valor for c in regla.condiciones}
            disparadas = motor.reglas_disparadas(evidencia)
            self.assertEqual([r.id for r in disparadas], [regla.id], regla.codigo)
            self.assertEqual(motor.diagnosticar(evidencia).hipotesis_id, regla.hipotesis_id)

    def test_reglas_son_mutuamente_excluyentes(self):
        motor = MotorInferencia(NodoArbolDAO(self.con), ReglaDAO(self.con))
        for a, b in itertools.combinations(motor.reglas, 2):
            ca = {c.sintoma_id: c.valor for c in a.condiciones}
            cb = {c.sintoma_id: c.valor for c in b.condiciones}
            self.assertTrue(any(ca[s] != cb[s] for s in ca.keys() & cb.keys()), (a.codigo, b.codigo))

    def test_validacion_detecta_falla_sin_hoja(self):
        datos = json.loads(Path(RUTA_CONOCIMIENTO).read_text(encoding="utf-8"))
        datos["arbol"]["nodos"][2]["no"] = "F02"  # F01 queda sin hoja y F02 repetida
        with self.assertRaises(ValueError):
            validar_arbol(datos)

    def test_granulos_por_hipotesis(self):
        h = HipotesisDAO(self.con).obtener_por_codigo("F17")
        reglas = ReglaDAO(self.con).por_hipotesis(h.id)
        self.assertEqual(len(reglas), 1)
        # F17 (fuente insuficiente): enciende, sin pitidos, con imagen, sin error de BIOS,
        # carga el SO, se apaga solo con temperatura normal y solo bajo tareas exigentes.
        esperado = [("S01", "si"), ("S05", "no"), ("S07", "si"), ("S09", "no"), ("S10", "si"),
                    ("S15", "si"), ("S16", "no"), ("S18", "si")]
        self.assertEqual([(c.sintoma_codigo, c.valor) for c in reglas[0].condiciones], esperado)


class TestProcesos(BaseTest):
    def setUp(self):
        super().setUp()
        self.auth = AutenticacionService(self.con)
        self.cliente_id = self.auth.registrar("Ana Pérez", "ana@correo.com", "clave12345")
        self.tecnico = self.auth.autenticar("tecnico@sistemaexperto.local", "Tecnico123*")
        self.servicio = DiagnosticoService(self.con)
        self.equipo_id = EquipoService(self.con).registrar(
            self.cliente_id, "Portátil", "Lenovo", "IdeaPad 3", "SN123")

    def _recorrer(self, caso_id, respuestas):
        consulta = self.servicio.iniciar_consulta(self.servicio.casos.obtener(caso_id))
        diagnostico = None
        for valor in respuestas:
            diagnostico = self.servicio.responder(consulta.id, valor)
        return consulta, diagnostico

    def test_flujo_completo_hasta_resolver(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "No enciende nada")
        # S01 no, S02 no, S03 no -> F01
        consulta, diag = self._recorrer(caso_id, ["no", "no", "no"])
        self.assertEqual(HipotesisDAO(self.con).obtener(diag.hipotesis_id).codigo, "F01")
        self.assertEqual(self.servicio.casos.obtener(caso_id).estado, "Diagnosticado")
        self.servicio.tomar_caso(caso_id, self.tecnico.id)
        caso = self.servicio.casos.obtener(caso_id)
        self.assertEqual(caso.estado, "En atención")
        self.servicio.registrar_seguimiento(caso, self.tecnico.id, "Se cambió el cable", "Cambio de cable")
        self.servicio.resolver_caso(caso, self.tecnico.id, True, "Equipo enciende con cable nuevo")
        self.assertEqual(self.servicio.casos.obtener(caso_id).estado, "Resuelto")
        self.assertTrue(self.servicio.diagnosticos.por_caso(caso_id).confirmado)
        frecuencia = self.servicio.diagnosticos.frecuencia_por_hipotesis()
        self.assertEqual((frecuencia[0]["codigo"], frecuencia[0]["total"], frecuencia[0]["tasa_confirmacion"]),
                         ("F01", 1, 100))

    def test_responder_rechaza_una_pregunta_ya_respondida(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "Falla al arrancar")
        consulta = self.servicio.iniciar_consulta(self.servicio.casos.obtener(caso_id))
        pregunta = consulta.nodo_actual_id
        self.servicio.responder(consulta.id, "no", pregunta)
        with self.assertRaises(ErrorNegocio):  # esa pregunta ya no es la actual
            self.servicio.responder(consulta.id, "si", pregunta)
        self.assertEqual(len(self.servicio.respuestas.listar(consulta.id)), 1)

    def test_responder_rechaza_valores_distintos_de_si_o_no(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "Falla al arrancar")
        consulta = self.servicio.iniciar_consulta(self.servicio.casos.obtener(caso_id))
        with self.assertRaises(ErrorNegocio):
            self.servicio.responder(consulta.id, "quizás")
        self.assertEqual(self.servicio.respuestas.listar(consulta.id), [])

    def test_responder_no_deja_la_consulta_a_medias_si_el_motor_es_inconsistente(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "No enciende nada")
        consulta = self.servicio.iniciar_consulta(self.servicio.casos.obtener(caso_id))
        self.servicio.responder(consulta.id, "no")
        self.servicio.responder(consulta.id, "no")
        antes = self.servicio.consultas.obtener(consulta.id)
        with mock.patch.object(self.servicio.motor, "diagnosticar", return_value=None):
            with self.assertRaises(ErrorNegocio):
                self.servicio.responder(consulta.id, "no")  # última pregunta: llegaría a la hoja F01
        self.assertEqual(len(self.servicio.respuestas.listar(consulta.id)), 2)
        self.assertEqual(self.servicio.consultas.obtener(consulta.id), antes)
        self.assertEqual(self.servicio.casos.obtener(caso_id).estado, "Abierto")
        self.assertIsNone(self.servicio.diagnosticos.por_consulta(consulta.id))

    def test_cambiar_clave(self):
        usuario = self.auth.autenticar("ana@correo.com", "clave12345")
        with self.assertRaises(ErrorNegocio):
            self.auth.cambiar_clave(usuario, "incorrecta", "nuevaclave1")
        with self.assertRaises(ErrorNegocio):
            self.auth.cambiar_clave(usuario, "clave12345", "corta")
        with self.assertRaises(ErrorNegocio):
            self.auth.cambiar_clave(usuario, "clave12345", "clave12345")
        self.auth.cambiar_clave(usuario, "clave12345", "nuevaclave1")
        self.auth.autenticar("ana@correo.com", "nuevaclave1")
        with self.assertRaises(ErrorNegocio):
            self.auth.autenticar("ana@correo.com", "clave12345")

    def test_retroceder_deshace_la_ultima_respuesta(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "Falla al arrancar")
        consulta = self.servicio.iniciar_consulta(self.servicio.casos.obtener(caso_id))
        self.servicio.responder(consulta.id, "no")
        self.servicio.retroceder(consulta.id)
        self.assertEqual(self.servicio.respuestas.listar(consulta.id), [])
        self.assertEqual(self.servicio.consultas.obtener(consulta.id).nodo_actual_id,
                         self.servicio.motor.nodo_inicial().id)

    def test_dos_tecnicos_no_toman_el_mismo_caso(self):
        caso_id = self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "Equipo muy lento hoy")
        self._recorrer(caso_id, ["no", "no", "no"])
        otro = self.auth.registrar("Otro Técnico", "otro@correo.com", "clave12345", "Técnico")
        self.servicio.tomar_caso(caso_id, self.tecnico.id)
        with self.assertRaises(ErrorNegocio):
            self.servicio.tomar_caso(caso_id, otro)

    def test_validaciones_de_negocio(self):
        with self.assertRaises(ErrorNegocio):
            self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "corto")
        with self.assertRaises(ErrorNegocio):
            self.auth.registrar("Ana Pérez", "ana@correo.com", "clave12345")  # correo repetido
        with self.assertRaises(ErrorNegocio):
            self.auth.autenticar("ana@correo.com", "incorrecta")

    def test_equipo_con_casos_no_se_elimina(self):
        self.servicio.abrir_caso(self.cliente_id, self.equipo_id, "Descripción suficiente")
        with self.assertRaises(ErrorNegocio):
            EquipoService(self.con).eliminar(self.cliente_id, self.equipo_id)

    def test_no_se_puede_usar_equipo_ajeno(self):
        otro = self.auth.registrar("Luis Gómez", "luis@correo.com", "clave12345")
        with self.assertRaises(ErrorNegocio):
            self.servicio.abrir_caso(otro, self.equipo_id, "Intento con equipo ajeno")


if __name__ == "__main__":
    unittest.main()
