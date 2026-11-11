"""Sesión, control de acceso por rol y protección CSRF."""
from __future__ import annotations

import secrets
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from src.dao.usuario_dao import UsuarioDAO


def token_csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def verificar_csrf() -> None:
    if request.method == "POST":
        enviado = request.form.get("csrf", "")
        if not enviado or not secrets.compare_digest(enviado, session.get("csrf", "")):
            abort(400, "Token CSRF inválido. Recargue la página e intente de nuevo.")


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
