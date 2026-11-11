"""DAO de roles y usuarios."""
from __future__ import annotations

import sqlite3

from src.dao.base import BaseDAO
from src.domain.models import Rol, Usuario

_SELECT_USUARIO = """
    SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.creado_en
    FROM usuario u JOIN rol r ON r.id = u.rol_id
"""


def _usuario(fila) -> Usuario:
    return Usuario(fila["id"], fila["nombre"], fila["correo"], fila["rol"],
                   bool(fila["activo"]), fila["creado_en"])


class RolDAO(BaseDAO):
    def listar(self) -> list[Rol]:
        return [Rol(**dict(f)) for f in self._todos(
            "SELECT id, nombre, descripcion FROM rol ORDER BY id")]

    def id_por_nombre(self, nombre: str) -> int | None:
        fila = self._uno("SELECT id FROM rol WHERE nombre = ?", (nombre,))
        return fila["id"] if fila else None


class UsuarioDAO(BaseDAO):
    def crear(self, nombre: str, correo: str, clave_hash: str, rol_id: int) -> int:
        try:
            return self._ejecutar(
                "INSERT INTO usuario(nombre, correo, clave_hash, rol_id) VALUES(?, ?, ?, ?)",
                (nombre, correo.strip().lower(), clave_hash, rol_id))
        except sqlite3.IntegrityError as error:
            raise ValueError("Ya existe un usuario con ese correo.") from error

    def obtener(self, usuario_id: int) -> Usuario | None:
        fila = self._uno(_SELECT_USUARIO + " WHERE u.id = ?", (usuario_id,))
        return _usuario(fila) if fila else None

    def obtener_credenciales(self, correo: str) -> tuple[Usuario, str] | None:
        fila = self._uno(
            """SELECT u.id, u.nombre, u.correo, r.nombre AS rol, u.activo, u.creado_en,
                      u.clave_hash
               FROM usuario u JOIN rol r ON r.id = u.rol_id WHERE u.correo = ?""",
            (correo.strip().lower(),))
        return (_usuario(fila), fila["clave_hash"]) if fila else None

    def listar(self) -> list[Usuario]:
        return [_usuario(f) for f in self._todos(_SELECT_USUARIO + " ORDER BY u.id")]

    def listar_por_rol(self, rol: str) -> list[Usuario]:
        return [_usuario(f) for f in self._todos(
            _SELECT_USUARIO + " WHERE r.nombre = ? AND u.activo = 1 ORDER BY u.nombre", (rol,))]

    def cambiar_estado(self, usuario_id: int, activo: bool) -> None:
        self._ejecutar("UPDATE usuario SET activo = ? WHERE id = ?", (int(activo), usuario_id))

    def cambiar_rol(self, usuario_id: int, rol_id: int) -> None:
        self._ejecutar("UPDATE usuario SET rol_id = ? WHERE id = ?", (rol_id, usuario_id))

    def cambiar_clave(self, usuario_id: int, clave_hash: str) -> None:
        self._ejecutar("UPDATE usuario SET clave_hash = ? WHERE id = ?", (clave_hash, usuario_id))
