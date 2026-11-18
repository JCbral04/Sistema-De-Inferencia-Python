"""Pruebas de la aplicación web: acceso por rol, CSRF y el flujo completo de un caso."""
import logging
import re
import tempfile
import unittest
from pathlib import Path

from src.web import create_app
from src.web.seguridad import LimitadorIntentos, Limitadores


class WebBase(unittest.TestCase):
    """Aplicación sobre una base temporal y ayudas para iniciar sesión y enviar formularios con CSRF."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.tmp.name) / "web.db")
        self.app.config["TESTING"] = True
        self.app.logger.setLevel(logging.ERROR)      # los ingresos fallidos de las pruebas no ensucian la salida

    def tearDown(self):
        self.tmp.cleanup()

    def cliente(self, correo=None, clave=None):
        c = self.app.test_client()
        if correo:
            self.post(c, "/login", {"correo": correo, "clave": clave}, "/login")
        return c

    @staticmethod
    def token(c, ruta):
        html = c.get(ruta).get_data(as_text=True)
        return re.search(r'name="csrf" value="([^"]+)"', html).group(1)

    def post(self, c, ruta, datos, ruta_token=None, **kw):
        datos = dict(datos, csrf=self.token(c, ruta_token or ruta))
        return c.post(ruta, data=datos, **kw)


class WebTest(WebBase):
    def test_login_y_redireccion(self):
        c = self.cliente()
        self.assertEqual(c.get("/panel").status_code, 302)
        r = self.post(c, "/login", {"correo": "x@x.com", "clave": "mala"})
        self.assertIn("incorrectos", r.get_data(as_text=True))
        c = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.assertEqual(c.get("/panel").status_code, 200)

    def test_post_sin_csrf_es_rechazado(self):
        c = self.cliente()
        self.assertEqual(c.post("/login", data={"correo": "a", "clave": "b"}).status_code, 400)

    def test_control_de_acceso_por_rol(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        for ruta in ("/admin/usuarios", "/tecnico/cola", "/conocimiento/arbol"):
            self.assertEqual(cli.get(ruta).status_code, 403, ruta)
        tec = self.cliente("tecnico@sistemaexperto.local", "Tecnico123*")
        self.assertEqual(tec.get("/cliente/equipos").status_code, 403)
        exp = self.cliente("experto@sistemaexperto.local", "Experto123*")
        self.assertEqual(exp.get("/admin/usuarios").status_code, 403)
        adm = self.cliente("admin@sistemaexperto.local", "Admin123*")
        for ruta in ("/admin/usuarios", "/admin/reportes", "/conocimiento/arbol",
                     "/conocimiento/hipotesis", "/conocimiento/reglas", "/conocimiento/sintomas"):
            self.assertEqual(adm.get(ruta).status_code, 200, ruta)

    def test_el_arbol_se_dibuja_completo(self):
        exp = self.cliente("experto@sistemaexperto.local", "Experto123*")
        html = exp.get("/conocimiento/arbol").get_data(as_text=True)
        self.assertIn("<svg", html)
        self.assertEqual(html.count('class="nodo pregunta"'), 30)
        self.assertEqual(html.count('class="nodo hoja"'), 31)
        for codigo in ("N01", "N30", "F01", "F31"):
            self.assertIn(f">{codigo}</text>", html)
        self.assertIn('href="/conocimiento/hipotesis/', html)    # cada falla enlaza con su ficha

    def test_flujo_completo_cliente_tecnico(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Portátil", "marca": "HP", "modelo": "Pavilion",
                                                   "serial": "A1"})
        self.assertIn("Pavilion", cli.get("/cliente/equipos").get_data(as_text=True))
        r = self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "El equipo no enciende"},
                      follow_redirects=False)
        self.assertEqual(r.status_code, 302)
        ruta_consulta = "/casos/1/consulta"
        self.assertIn("Pregunta 1", cli.get(ruta_consulta).get_data(as_text=True))
        # S01 no, S02 no, S03 no -> F01
        for _ in range(3):
            self.post(cli, "/casos/1/responder", {"valor": "no"}, ruta_consulta)
        detalle = cli.get("/casos/1").get_data(as_text=True)
        self.assertIn("F01", detalle)
        self.assertIn("Diagnosticado", detalle)

        tec = self.cliente("tecnico@sistemaexperto.local", "Tecnico123*")
        self.assertIn("El equipo no enciende", tec.get("/tecnico/cola").get_data(as_text=True))
        self.post(tec, "/tecnico/casos/1/tomar", {}, "/tecnico/cola")
        self.post(tec, "/tecnico/casos/1/seguimiento", {"accion": "Cambio de cable", "observacion": "Cable roto"}, "/casos/1")
        self.post(tec, "/tecnico/casos/1/resolver", {"correcto": "si", "observacion": "Se cambió el cable"}, "/casos/1")
        self.assertIn("Resuelto", tec.get("/casos/1").get_data(as_text=True))

        adm = self.cliente("admin@sistemaexperto.local", "Admin123*")
        self.assertIn("F01", adm.get("/admin/reportes").get_data(as_text=True))

    def test_un_cliente_no_ve_casos_ajenos(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Escritorio", "marca": "Dell", "modelo": "Optiplex", "serial": ""})
        self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "Problema de arranque"})
        otro = self.cliente()
        self.post(otro, "/registro", {"nombre": "Otra Persona", "correo": "otra@correo.com", "clave": "clave12345",
                                      "confirmacion": "clave12345"})
        otro = self.cliente("otra@correo.com", "clave12345")
        self.assertEqual(otro.get("/casos/1").status_code, 403)

    def test_experto_edita_conocimiento(self):
        exp = self.cliente("experto@sistemaexperto.local", "Experto123*")
        self.post(exp, "/conocimiento/hipotesis/1/editar",
                  {"nombre": "Falla eléctrica", "descripcion": "x", "severidad": "Media",
                   "factor_certeza": "0.95", "solucion": "Nueva solución"}, "/conocimiento/hipotesis/1/editar")
        self.assertIn("Nueva solución", exp.get("/conocimiento/hipotesis/1").get_data(as_text=True))
        r = self.post(exp, "/conocimiento/hipotesis/1/editar",
                      {"nombre": "x", "descripcion": "x", "severidad": "Media",
                       "factor_certeza": "7", "solucion": "y"}, "/conocimiento/hipotesis/1/editar")
        self.assertIn("mayor que 0", r.get_data(as_text=True))

    def abrir_caso_de_prueba(self, cli):
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Portátil", "marca": "HP", "modelo": "Pavilion",
                                                   "serial": ""})
        self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "El equipo no enciende"})

    def test_entradas_no_numericas_no_producen_error_500(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        r = self.post(cli, "/cliente/casos/nuevo", {"equipo_id": "abc", "descripcion": "Descripción suficiente"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("Seleccione uno de sus equipos", r.get_data(as_text=True))
        exp = self.cliente("experto@sistemaexperto.local", "Experto123*")
        r = self.post(exp, "/conocimiento/sintomas", {"sintoma_id": "x", "pregunta": "Pregunta de prueba válida"},
                      follow_redirects=True)
        self.assertEqual(r.status_code, 200)

    def test_retroceder_sin_consulta_iniciada_da_404(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.abrir_caso_de_prueba(cli)
        self.assertEqual(self.post(cli, "/casos/1/retroceder", {}, "/panel").status_code, 404)

    def test_pregunta_repetida_no_avanza_la_consulta(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.abrir_caso_de_prueba(cli)
        ruta = "/casos/1/consulta"
        nodo = re.search(r'name="nodo" value="(\d+)"', cli.get(ruta).get_data(as_text=True)).group(1)
        self.post(cli, "/casos/1/responder", {"valor": "no", "nodo": nodo}, ruta)
        # Reenvío de la misma pregunta (doble clic o botón «atrás» del navegador).
        r = self.post(cli, "/casos/1/responder", {"valor": "si", "nodo": nodo}, ruta, follow_redirects=True)
        self.assertIn("ya fue respondida", r.get_data(as_text=True))
        self.assertIn("Pregunta 2", r.get_data(as_text=True))

    def test_cambio_de_clave(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        r = self.post(cli, "/cuenta/clave", {"actual": "mala", "nueva": "NuevaClave1", "confirmacion": "NuevaClave1"})
        self.assertIn("no es correcta", r.get_data(as_text=True))
        r = self.post(cli, "/cuenta/clave", {"actual": "Cliente123*", "nueva": "NuevaClave1", "confirmacion": "otra"})
        self.assertIn("no coincide", r.get_data(as_text=True))
        r = self.post(cli, "/cuenta/clave", {"actual": "Cliente123*", "nueva": "NuevaClave1",
                                             "confirmacion": "NuevaClave1"})
        self.assertEqual(r.status_code, 302)
        anonimo = self.cliente()
        r = self.post(anonimo, "/login", {"correo": "cliente@sistemaexperto.local", "clave": "Cliente123*"})
        self.assertIn("incorrectos", r.get_data(as_text=True))
        self.assertEqual(self.cliente("cliente@sistemaexperto.local", "NuevaClave1").get("/panel").status_code, 200)

    def test_los_reportes_concuerdan_en_singular_y_plural(self):
        filtro = self.app.jinja_env.filters["casos_por_estado"]
        self.assertEqual(filtro("Resuelto", 1), "caso resuelto")
        self.assertEqual(filtro("Resuelto", 4), "casos resueltos")
        self.assertEqual(filtro("En atención", 0), "casos en atención")
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Portátil", "marca": "HP", "modelo": "Pavilion",
                                                   "serial": "A1"})
        for descripcion in ("El equipo no enciende", "El equipo se apaga solo"):
            self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": descripcion})
        adm = self.cliente("admin@sistemaexperto.local", "Admin123*")
        html = adm.get("/admin/reportes").get_data(as_text=True)
        self.assertIn("casos abiertos", html)
        self.assertNotIn("casos abierto<", html)

    def test_el_login_no_redirige_a_sitios_externos(self):
        for destino in ("//sitio-externo.com", "/%5Csitio-externo.com", "https://sitio-externo.com"):
            c = self.cliente()
            r = self.post(c, f"/login?siguiente={destino}",
                          {"correo": "cliente@sistemaexperto.local", "clave": "Cliente123*"}, "/login")
            self.assertEqual(r.status_code, 302, destino)
            self.assertTrue(r.headers["Location"].endswith("/panel"), (destino, r.headers["Location"]))


class AccesoSeguroTest(WebBase):
    """Acceso seguro: registro, ingreso, bloqueo por intentos, sesión y cabeceras."""

    REGISTRO = {"nombre": "Laura Ruiz", "correo": "laura@correo.com", "clave": "Mi-clave-2026",
                "confirmacion": "Mi-clave-2026"}

    def test_el_registro_crea_una_cuenta_de_cliente_y_abre_la_sesion(self):
        c = self.cliente()
        r = self.post(c, "/registro", self.REGISTRO)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/cliente/consultas"))
        self.assertIn("Laura Ruiz", c.get("/panel").get_data(as_text=True))
        self.assertEqual(c.get("/cliente/consultas").status_code, 200)
        self.assertEqual(c.get("/admin/usuarios").status_code, 403)

    def test_el_registro_no_permite_elegir_el_rol(self):
        c = self.cliente()
        self.post(c, "/registro", dict(self.REGISTRO, rol="Administrador"))
        self.assertEqual(c.get("/admin/usuarios").status_code, 403)
        self.assertEqual(c.get("/cliente/equipos").status_code, 200)

    def test_el_registro_valida_los_datos_y_conserva_lo_escrito(self):
        casos = {
            "no coincide": dict(self.REGISTRO, confirmacion="otra"),
            "letras y números": dict(self.REGISTRO, clave="sololetrasaqui", confirmacion="sololetrasaqui"),
            "demasiado fácil": dict(self.REGISTRO, clave="password1", confirmacion="password1"),
            "combinar letras": dict(self.REGISTRO, clave="12345678", confirmacion="12345678"),
            "al menos 8": dict(self.REGISTRO, clave="a1b2", confirmacion="a1b2"),
            "correo válido": dict(self.REGISTRO, correo="no-es-un-correo"),
            "entre 3 y 80": dict(self.REGISTRO, nombre="Al"),
        }
        for esperado, datos in casos.items():
            r = self.post(self.cliente(), "/registro", datos)
            self.assertEqual(r.status_code, 200, esperado)
            html = r.get_data(as_text=True)
            self.assertIn(esperado, html)
            self.assertNotIn("Mi-clave-2026", html)                      # nunca se devuelve la contraseña
        r = self.post(self.cliente(), "/registro", dict(self.REGISTRO, confirmacion="otra"))
        self.assertIn('value="laura@correo.com"', r.get_data(as_text=True))   # sí se conserva el correo
        self.post(self.cliente(), "/registro", self.REGISTRO)
        repetido = self.post(self.cliente(), "/registro", self.REGISTRO)
        self.assertIn("Ya existe un usuario con ese correo", repetido.get_data(as_text=True))

    def test_la_clave_se_guarda_cifrada(self):
        self.post(self.cliente(), "/registro", self.REGISTRO)
        from src.dao.base import abrir_conexion
        con = abrir_conexion(self.app.config["RUTA_BD"])
        guardada = con.execute("SELECT clave_hash FROM usuario WHERE correo = 'laura@correo.com'").fetchone()[0]
        con.close()
        self.assertNotIn("Mi-clave-2026", guardada)
        self.assertRegex(guardada, r"^(scrypt|pbkdf2):")

    def test_el_ingreso_se_bloquea_tras_cinco_intentos_fallidos(self):
        tiempo = [0.0]
        self.app.extensions["limitadores"] = Limitadores(reloj=lambda: tiempo[0])
        malos = {"correo": "cliente@sistemaexperto.local", "clave": "incorrecta1"}
        for _ in range(4):
            r = self.post(self.cliente(), "/login", malos)
            self.assertEqual(r.status_code, 200)
            self.assertIn("incorrectos", r.get_data(as_text=True))
        r = self.post(self.cliente(), "/login", malos)                         # quinto intento
        self.assertEqual(r.status_code, 429)
        self.assertIn("Demasiados intentos", r.get_data(as_text=True))
        buenos = dict(malos, clave="Cliente123*")
        self.assertEqual(self.post(self.cliente(), "/login", buenos).status_code, 429)   # ni con la clave correcta
        otro = self.post(self.cliente(), "/login", {"correo": "tecnico@sistemaexperto.local",
                                                    "clave": "Tecnico123*"})
        self.assertEqual(otro.status_code, 302)                                # otra cuenta no se ve afectada
        tiempo[0] += 5 * 60 + 1
        self.assertEqual(self.post(self.cliente(), "/login", buenos).status_code, 302)

    def test_un_ingreso_correcto_reinicia_el_conteo(self):
        self.app.extensions["limitadores"] = Limitadores(reloj=lambda: 0.0)
        malos = {"correo": "cliente@sistemaexperto.local", "clave": "incorrecta1"}
        for _ in range(3):
            self.post(self.cliente(), "/login", malos)
        self.assertEqual(self.post(self.cliente(), "/login", dict(malos, clave="Cliente123*")).status_code, 302)
        for _ in range(4):
            self.assertEqual(self.post(self.cliente(), "/login", malos).status_code, 200)

    def test_el_limitador_respeta_la_ventana_de_tiempo(self):
        tiempo = [0.0]
        lim = LimitadorIntentos(maximo=3, ventana=60, bloqueo=120, reloj=lambda: tiempo[0])
        lim.registrar("a"); lim.registrar("a")
        tiempo[0] = 61                                    # los dos intentos anteriores ya no cuentan
        lim.registrar("a")
        self.assertEqual(lim.segundos_restantes("a"), 0)
        lim.registrar("a"); lim.registrar("a")
        self.assertGreater(lim.segundos_restantes("a"), 0)
        self.assertEqual(lim.segundos_restantes("b"), 0)
        tiempo[0] += 121
        self.assertEqual(lim.segundos_restantes("a"), 0)

    def test_quien_ya_tiene_sesion_no_ve_el_login_ni_el_registro(self):
        c = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        for ruta in ("/login", "/registro"):
            r = c.get(ruta)
            self.assertEqual(r.status_code, 302, ruta)
            self.assertTrue(r.headers["Location"].endswith("/panel"))

    def test_cerrar_sesion_exige_post_y_termina_la_sesion(self):
        c = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.assertEqual(c.get("/logout").status_code, 405)
        self.assertEqual(c.get("/panel").status_code, 200)
        r = self.post(c, "/logout", {}, "/panel")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get("/panel").status_code, 302)

    def test_la_cookie_de_sesion_es_segura_y_caduca(self):
        c = self.cliente()
        token = self.token(c, "/login")
        r = c.post("/login", data={"correo": "cliente@sistemaexperto.local", "clave": "Cliente123*", "csrf": token})
        cookie = r.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Expires=", cookie)                 # sesión permanente: caduca por inactividad
        self.assertEqual(self.app.config["PERMANENT_SESSION_LIFETIME"].total_seconds(), 30 * 60)

    def test_cabeceras_de_seguridad_y_sin_cache_en_las_paginas(self):
        c = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        r = c.get("/panel")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertEqual(r.headers["Cache-Control"], "no-store")
        estilo = c.get("/static/estilo.css")
        estilo.close()
        self.assertNotEqual(estilo.headers.get("Cache-Control"), "no-store")

    def test_las_fechas_se_muestran_en_hora_de_colombia(self):
        filtro = self.app.jinja_env.filters["fecha"]
        self.assertEqual(filtro("2026-11-18 23:18:05"), "2026-11-18 18:18")     # la base guarda UTC
        self.assertEqual(filtro("2026-11-19 03:00:00"), "2026-11-18 22:00")     # cruza la medianoche
        self.assertEqual(filtro(None), "")
        self.assertEqual(filtro("sin formato conocido"), "sin formato cono")

    def test_la_clave_secreta_persiste_entre_reinicios(self):
        otra = create_app(self.app.config["RUTA_BD"])
        self.assertEqual(otra.config["SECRET_KEY"], self.app.config["SECRET_KEY"])
        self.assertGreaterEqual(len(self.app.config["SECRET_KEY"]), 32)


class ConsultasTest(WebBase):
    """Formulario para iniciar una consulta e historial de las últimas cinco."""

    def preparar(self, n=0):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Portátil", "marca": "HP", "modelo": "Pavilion", "serial": ""})
        for i in range(n):
            self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": f"Problema número {i + 1} del equipo"},
                      "/cliente/consultas")
        return cli

    def terminar_consulta(self, cli, caso_id):
        ruta = f"/casos/{caso_id}/consulta"
        for _ in range(3):                                   # S01 no, S02 no, S03 no -> F01
            self.post(cli, f"/casos/{caso_id}/responder", {"valor": "no"}, ruta)

    def test_la_pantalla_muestra_el_formulario_y_el_historial_vacio(self):
        cli = self.preparar()
        html = cli.get("/cliente/consultas").get_data(as_text=True)
        self.assertIn("Iniciar una consulta", html)
        self.assertIn("Todavía no ha hecho consultas", html)
        self.assertIn("Pavilion", html)

    def test_sin_equipos_pide_registrar_uno(self):
        cli = self.cliente("cliente@sistemaexperto.local", "Cliente123*")
        self.assertIn("registrar primero un equipo", cli.get("/cliente/consultas").get_data(as_text=True))

    def test_el_formulario_inicia_la_consulta_guiada(self):
        cli = self.preparar()
        r = self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "El equipo no enciende"},
                      "/cliente/consultas")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/casos/1/consulta"))

    def test_un_formulario_invalido_conserva_lo_escrito(self):
        cli = self.preparar()
        r = self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "corto"}, "/cliente/consultas")
        html = r.get_data(as_text=True)
        self.assertEqual(r.status_code, 200)
        self.assertIn("al menos 10 caracteres", html)
        self.assertIn(">corto</textarea>", html)
        largo = self.post(cli, "/cliente/casos/nuevo", {"equipo_id": 1, "descripcion": "x" * 1001}, "/cliente/consultas")
        self.assertIn("1000 caracteres", largo.get_data(as_text=True))

    def test_el_historial_muestra_solo_las_ultimas_cinco_de_la_mas_reciente_a_la_mas_antigua(self):
        cli = self.preparar(6)
        html = cli.get("/cliente/consultas").get_data(as_text=True)
        self.assertNotIn("Problema número 1 del equipo", html)       # la más antigua queda fuera
        posiciones = [html.index(f"Problema número {i} del equipo") for i in (6, 5, 4, 3, 2)]
        self.assertEqual(posiciones, sorted(posiciones))
        self.assertIn("últimas 5 consultas", html)

    def test_elegir_una_consulta_muestra_su_detalle_y_la_marca(self):
        cli = self.preparar(2)
        self.terminar_consulta(cli, 1)
        html = cli.get("/cliente/consultas?ver=1").get_data(as_text=True)
        self.assertIn('aria-current="true"', html)
        self.assertEqual(html.count('class="etiqueta elegida"'), 1)
        self.assertIn("Consulta elegida · caso #1", html)
        self.assertIn("F01", html)                                  # diagnóstico de la consulta elegida
        self.assertIn("Respuestas dadas", html)
        otra = cli.get("/cliente/consultas?ver=2").get_data(as_text=True)
        self.assertIn("Consulta elegida · caso #2", otra)
        self.assertIn("Continuar la consulta", otra)                # esa quedó sin terminar

    def test_el_historial_muestra_el_diagnostico_de_las_consultas_terminadas(self):
        cli = self.preparar(1)
        self.terminar_consulta(cli, 1)
        html = cli.get("/cliente/consultas").get_data(as_text=True)
        self.assertIn("F01", html)
        self.assertNotIn("Consulta sin terminar", html)

    def test_no_se_puede_elegir_la_consulta_de_otro_cliente_ni_valores_raros(self):
        cli = self.preparar(1)
        otro = self.cliente()
        self.post(otro, "/registro", {"nombre": "Otra Persona", "correo": "otra@correo.com", "clave": "clave12345",
                                      "confirmacion": "clave12345"})
        self.assertEqual(otro.get("/cliente/consultas?ver=1").status_code, 404)
        self.assertNotIn("Problema número 1", otro.get("/cliente/consultas").get_data(as_text=True))
        self.assertEqual(cli.get("/cliente/consultas?ver=999").status_code, 404)
        self.assertEqual(cli.get("/cliente/consultas?ver=abc&equipo=zzz").status_code, 200)

    def test_consultar_de_nuevo_preselecciona_el_equipo(self):
        cli = self.preparar(1)
        self.post(cli, "/cliente/equipos/nuevo", {"tipo": "Escritorio", "marca": "Dell", "modelo": "Optiplex", "serial": ""})
        html = cli.get("/cliente/consultas?equipo=1").get_data(as_text=True)
        self.assertRegex(html, r'<option value="1" selected>')

    def test_solo_el_cliente_usa_la_pantalla_de_consultas(self):
        for correo, clave in (("tecnico@sistemaexperto.local", "Tecnico123*"), ("admin@sistemaexperto.local", "Admin123*")):
            self.assertEqual(self.cliente(correo, clave).get("/cliente/consultas").status_code, 403)
        self.assertEqual(self.cliente().get("/cliente/consultas").status_code, 302)


if __name__ == "__main__":
    unittest.main()
