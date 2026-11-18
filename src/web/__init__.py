"""Fábrica de la aplicación Flask."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Flask, g, render_template

from src.dao.base import abrir_conexion
from src.dao.inicializador import RUTA_BD, crear_base_datos
from src.web import seguridad


def _zona_horaria():
    """Zona en la que se muestran las fechas (la base las guarda en UTC). Por defecto, Colombia (UTC-5, sin
    horario de verano); se cambia con la variable ZONA_HORARIA, por ejemplo «America/Mexico_City»."""
    try:
        return ZoneInfo(os.environ.get("ZONA_HORARIA", "America/Bogota"))
    except (ZoneInfoNotFoundError, ValueError):     # equipos sin base de zonas horarias (p. ej. Windows sin tzdata)
        return timezone(timedelta(hours=-5), "COT")


def create_app(ruta_bd: Path | str | None = None) -> Flask:
    app = Flask(__name__)
    ruta_bd = Path(ruta_bd or os.environ.get("SISTEMA_EXPERTO_DB", RUTA_BD))
    if not ruta_bd.exists():
        crear_base_datos(ruta_bd)
    app.config.update(
        RUTA_BD=ruta_bd,
        SECRET_KEY=seguridad.clave_secreta(ruta_bd),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Con HTTPS (producción) se define COOKIE_SEGURA=1 para que la cookie viaje solo cifrada.
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SEGURA") == "1",
        # La sesión se cierra tras estos minutos sin actividad (cada petición renueva el plazo).
        PERMANENT_SESSION_LIFETIME=timedelta(minutes=int(os.environ.get("SESION_MINUTOS", "30"))),
        MAX_CONTENT_LENGTH=64 * 1024,
    )
    app.extensions["limitadores"] = seguridad.Limitadores()

    @app.before_request
    def abrir():
        g.con = abrir_conexion(app.config["RUTA_BD"])
        seguridad.cargar_usuario()
        seguridad.verificar_csrf()

    app.after_request(seguridad.agregar_cabeceras)

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
        """Fecha guardada en UTC (AAAA-MM-DD HH:MM:SS) mostrada como AAAA-MM-DD HH:MM en la zona local."""
        try:
            instante = datetime.strptime(valor[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return (valor or "")[:16]
        return instante.astimezone(_zona_horaria()).strftime("%Y-%m-%d %H:%M")

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

    @app.errorhandler(413)
    def demasiado_grande(_):
        return render_template("error.html", codigo=413, mensaje="La solicitud es demasiado grande."), 413

    @app.errorhandler(429)
    def demasiados_intentos(error):
        return render_template("error.html", codigo=429, mensaje=getattr(error, "description", "")), 429

    @app.errorhandler(400)
    def solicitud_invalida(error):
        return render_template("error.html", codigo=400, mensaje=getattr(error, "description", "Solicitud inválida.")), 400

    return app
