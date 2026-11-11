"""Fábrica de la aplicación Flask."""
from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask, g, render_template

from src.dao.base import abrir_conexion
from src.dao.inicializador import RUTA_BD, crear_base_datos
from src.web import seguridad


def create_app(ruta_bd: Path | str | None = None) -> Flask:
    app = Flask(__name__)
    ruta_bd = Path(ruta_bd or os.environ.get("SISTEMA_EXPERTO_DB", RUTA_BD))
    if not ruta_bd.exists():
        crear_base_datos(ruta_bd)
    app.config.update(
        RUTA_BD=ruta_bd,
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )

    @app.before_request
    def abrir():
        g.con = abrir_conexion(app.config["RUTA_BD"])
        seguridad.cargar_usuario()
        seguridad.verificar_csrf()

    @app.teardown_request
    def cerrar(error):
        con = g.pop("con", None)
        if con is not None:
            con.commit() if error is None else con.rollback()
            con.close()

    # Global de Jinja (y no solo contexto) para que también lo vean las macros importadas.
    app.jinja_env.globals["csrf_token"] = seguridad.token_csrf

    @app.context_processor
    def contexto():
        return {"usuario_actual": g.get("usuario")}

    @app.template_filter("fecha")
    def fecha(valor):
        return (valor or "")[:16]

    @app.template_filter("casos_por_estado")
    def casos_por_estado(estado, cantidad):
        """'caso resuelto' si hay uno y 'casos resueltos' en cualquier otro caso."""
        singular = {"Abierto": "abierto", "Diagnosticado": "diagnosticado", "En atención": "en atención",
                    "Resuelto": "resuelto"}
        plural = {"Abierto": "abiertos", "Diagnosticado": "diagnosticados", "En atención": "en atención",
                  "Resuelto": "resueltos"}
        if cantidad == 1:
            return f"caso {singular.get(estado, estado.lower())}"
        return f"casos {plural.get(estado, estado.lower())}"

    from src.web import rutas
    for blueprint in rutas.BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.errorhandler(403)
    def prohibido(_):
        return render_template("error.html", codigo=403, mensaje="No tiene permiso para ver esta página."), 403

    @app.errorhandler(404)
    def no_encontrado(_):
        return render_template("error.html", codigo=404, mensaje="La página solicitada no existe."), 404

    @app.errorhandler(400)
    def solicitud_invalida(error):
        return render_template("error.html", codigo=400, mensaje=getattr(error, "description", "Solicitud inválida.")), 400

    return app
