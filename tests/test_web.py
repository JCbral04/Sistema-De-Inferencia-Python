"""Pruebas de la aplicación web: acceso por rol, CSRF y el flujo completo de un caso."""
import re
import tempfile
import unittest
from pathlib import Path

from src.web import create_app


class WebTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.tmp.name) / "web.db")
        self.app.config["TESTING"] = True

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
        self.post(otro, "/registro", {"nombre": "Otra Persona", "correo": "otra@correo.com", "clave": "clave12345"})
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


if __name__ == "__main__":
    unittest.main()
