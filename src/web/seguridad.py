"""Sesión, control de acceso por rol, protección CSRF, límite de intentos y cabeceras de seguridad."""
from __future__ import annotations

import os
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable, Hashable
from functools import wraps
from pathlib import Path

from flask import abort, current_app, flash, g, redirect, request, session, url_for

from src.dao.usuario_dao import UsuarioDAO


# ---------------------------------------------------------------------------- CSRF
def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def verificar_csrf() -> None:
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        if not enviado or not secrets.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "Token CSRF inválido. Recargue la página e intente de nuevo.")


# ---------------------------------------------------------------------------- sesión y roles
def cargar_usuario() -> None:
    g.usuario = None
    usuario_id = session.get("usuario_id")
    if usuario_id:
        usuario = UsuarioDAO(g.con).obtener(usuario_id)
        if usuario and usuario.activo:
            g.usuario = usuario
        else:
            session.clear()


def requiere_rol(*roles: str):
    """Exige sesión iniciada y, si se indican roles, que el usuario tenga alguno de ellos."""
    def decorador(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if g.usuario is None:
                flash("Inicie sesión para continuar.", "aviso")
                return redirect(url_for("publico.login", siguiente=request.path))
            if roles and g.usuario.rol not in roles:
                abort(403)
            return vista(*args, **kwargs)
        return envoltura
    return decorador


def clave_secreta(ruta_bd: Path) -> str:
    """Clave que firma la cookie de sesión.

    Se toma de la variable SECRET_KEY; si no existe, se genera una vez y se guarda junto a la base de datos
    (``.clave_secreta``, solo legible por el dueño) para que las sesiones sobrevivan a un reinicio."""
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    archivo = Path(ruta_bd).parent / ".clave_secreta"
    try:
        if archivo.exists():
            clave = archivo.read_text(encoding="utf-8").strip()
            if len(clave) >= 32:
                return clave
        clave = secrets.token_hex(32)
        descriptor = os.open(archivo, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as f:
            f.write(clave)
        return clave
    except OSError:                       # carpeta de solo lectura: clave temporal, válida mientras corra el proceso
        return secrets.token_hex(32)


# ---------------------------------------------------------------------------- límite de intentos
class LimitadorIntentos:
    """Bloquea una clave (por ejemplo, IP y correo) que acumula demasiados intentos en una ventana de tiempo.

    Vive en la memoria del proceso: sirve contra la adivinanza de contraseñas desde un mismo origen, y se
    reinicia al reiniciar el servidor. ``reloj`` se inyecta para poder probarlo sin esperar."""

    def __init__(self, maximo: int, ventana: float, bloqueo: float,
                 reloj: Callable[[], float] = time.monotonic):
        self.maximo, self.ventana, self.bloqueo, self.reloj = maximo, ventana, bloqueo, reloj
        self._intentos: dict[Hashable, deque[float]] = defaultdict(deque)
        self._bloqueado_hasta: dict[Hashable, float] = {}
        self._candado = threading.Lock()

    def segundos_restantes(self, clave: Hashable) -> int:
        """Segundos que faltan para que la clave pueda volver a intentar (0 si no está bloqueada)."""
        with self._candado:
            hasta = self._bloqueado_hasta.get(clave)
            if hasta is None:
                return 0
            resto = hasta - self.reloj()
            if resto <= 0:
                del self._bloqueado_hasta[clave]
                self._intentos.pop(clave, None)
                return 0
            return int(resto) + 1

    def registrar(self, clave: Hashable) -> None:
        """Anota un intento (fallido); al llegar al máximo dentro de la ventana, bloquea la clave."""
        with self._candado:
            ahora = self.reloj()
            intentos = self._intentos[clave]
            intentos.append(ahora)
            while intentos and ahora - intentos[0] > self.ventana:
                intentos.popleft()
            if len(intentos) >= self.maximo:
                self._bloqueado_hasta[clave] = ahora + self.bloqueo

    def limpiar(self, clave: Hashable) -> None:
        with self._candado:
            self._intentos.pop(clave, None)
            self._bloqueado_hasta.pop(clave, None)


class Limitadores:
    """Los tres límites de la aplicación: intentos por cuenta, por origen y altas de cuentas por origen."""

    def __init__(self, reloj: Callable[[], float] = time.monotonic):
        self.cuenta = LimitadorIntentos(maximo=5, ventana=15 * 60, bloqueo=5 * 60, reloj=reloj)
        self.origen = LimitadorIntentos(maximo=20, ventana=15 * 60, bloqueo=5 * 60, reloj=reloj)
        self.altas = LimitadorIntentos(maximo=20, ventana=60 * 60, bloqueo=60 * 60, reloj=reloj)


def limitadores() -> Limitadores:
    return current_app.extensions["limitadores"]


def origen() -> str:
    return request.remote_addr or "desconocido"


def minutos(segundos: int) -> int:
    return max(1, -(-segundos // 60))


# ---------------------------------------------------------------------------- cabeceras
CABECERAS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                                "img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"),
}


def agregar_cabeceras(respuesta):
    """Cabeceras de seguridad en toda respuesta; las páginas dinámicas no se guardan en la caché del navegador
    (así, tras cerrar sesión, el botón «atrás» no muestra datos de la cuenta)."""
    for nombre, valor in CABECERAS.items():
        respuesta.headers.setdefault(nombre, valor)
    if request.endpoint != "static":
        respuesta.headers["Cache-Control"] = "no-store"
    return respuesta
