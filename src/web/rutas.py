"""Rutas web agrupadas por rol (blueprints)."""
from __future__ import annotations

from flask import (
    Blueprint, abort, flash, g, redirect, render_template, request, session, url_for,
)

from src.dao.conocimiento_dao import (
    CategoriaDAO, HipotesisDAO, NodoArbolDAO, ReglaDAO, SintomaDAO,
)
from src.dao.transaccional_dao import CasoDAO, DiagnosticoDAO, EquipoDAO, SeguimientoDAO
from src.dao.usuario_dao import RolDAO, UsuarioDAO
from src.services.servicios import (
    AutenticacionService, DiagnosticoService, EquipoService, ErrorNegocio,
)
from src.web.seguridad import requiere_rol

publico = Blueprint("publico", __name__)
cliente = Blueprint("cliente", __name__, url_prefix="/cliente")
casos = Blueprint("casos", __name__, url_prefix="/casos")
tecnico = Blueprint("tecnico", __name__, url_prefix="/tecnico")
conocimiento = Blueprint("conocimiento", __name__, url_prefix="/conocimiento")
admin = Blueprint("admin", __name__, url_prefix="/admin")
cuenta = Blueprint("cuenta", __name__, url_prefix="/cuenta")


def _error(mensaje: str) -> None:
    flash(mensaje, "error")


def _entero(texto, defecto: int | None = 0) -> int | None:
    """Convierte un campo de formulario a entero; si no es un número, devuelve ``defecto``."""
    try:
        return int(str(texto).strip())
    except (TypeError, ValueError):
        return defecto


def _destino_seguro(ruta: str) -> bool:
    """Acepta solo rutas internas (evita redirecciones abiertas como //sitio o /\\sitio)."""
    return ruta.startswith("/") and not ruta.startswith("//") and "\\" not in ruta


def _caso_visible(caso_id: int):
    """Devuelve el caso si el usuario actual tiene derecho a verlo; si no, 404/403."""
    caso = CasoDAO(g.con).obtener(caso_id)
    if caso is None:
        abort(404)
    u = g.usuario
    permitido = (
        u.rol == "Administrador"
        or (u.rol == "Cliente" and caso.cliente_id == u.id)
        or (u.rol == "Técnico" and (caso.tecnico_id == u.id
                                    or (caso.tecnico_id is None and caso.estado == "Diagnosticado")))
    )
    if not permitido:
        abort(403)
    return caso


# ============================================================ públicas
@publico.route("/")
def inicio():
    return redirect(url_for("publico.panel" if g.usuario else "publico.login"))


@publico.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        try:
            usuario = AutenticacionService(g.con).autenticar(
                request.form.get("correo", ""), request.form.get("clave", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            session.clear()
            session["usuario_id"] = usuario.id
            siguiente = request.args.get("siguiente", "")
            if _destino_seguro(siguiente):
                return redirect(siguiente)
            return redirect(url_for("publico.panel"))
    return render_template("login.html")


@publico.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("publico.login"))


@publico.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        try:
            AutenticacionService(g.con).registrar(
                request.form.get("nombre", ""), request.form.get("correo", ""),
                request.form.get("clave", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            flash("Cuenta creada. Ya puede iniciar sesión.", "ok")
            return redirect(url_for("publico.login"))
    return render_template("registro.html")


@publico.route("/panel")
@requiere_rol()
def panel():
    dao_casos = CasoDAO(g.con)
    u = g.usuario
    datos: dict = {}
    if u.rol == "Cliente":
        datos["casos"] = dao_casos.listar(cliente_id=u.id)[:5]
        datos["equipos"] = len(EquipoDAO(g.con).listar_por_cliente(u.id))
    elif u.rol == "Técnico":
        datos["cola"] = dao_casos.cola_sin_tecnico()
        datos["mis_casos"] = [c for c in dao_casos.listar(tecnico_id=u.id) if c.estado == "En atención"]
    elif u.rol == "Experto":
        hip = HipotesisDAO(g.con).listar()
        datos["hipotesis"] = len(hip)
        datos["hojas"] = NodoArbolDAO(g.con).contar_hojas()
        datos["reglas"] = len(ReglaDAO(g.con).listar())
        datos["sintomas"] = len(SintomaDAO(g.con).listar())
    else:
        datos["por_estado"] = dao_casos.contar_por_estado()
        datos["usuarios"] = len(UsuarioDAO(g.con).listar())
    return render_template("panel.html", **datos)


# ============================================================ cliente: equipos y casos
@cliente.route("/equipos")
@requiere_rol("Cliente")
def equipos():
    return render_template("equipos.html", equipos=EquipoDAO(g.con).listar_por_cliente(g.usuario.id))


@cliente.route("/equipos/nuevo", methods=["GET", "POST"])
@cliente.route("/equipos/<int:equipo_id>/editar", methods=["GET", "POST"])
@requiere_rol("Cliente")
def equipo_form(equipo_id: int | None = None):
    servicio = EquipoService(g.con)
    equipo = None
    if equipo_id is not None:
        equipo = servicio.equipos.obtener(equipo_id)
        if equipo is None or equipo.cliente_id != g.usuario.id:
            abort(404)
    if request.method == "POST":
        f = request.form
        try:
            if equipo:
                servicio.actualizar(g.usuario.id, equipo.id, f.get("tipo", ""), f.get("marca", ""),
                                    f.get("modelo", ""), f.get("serial", ""))
            else:
                servicio.registrar(g.usuario.id, f.get("tipo", ""), f.get("marca", ""),
                                   f.get("modelo", ""), f.get("serial", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            flash("Equipo guardado.", "ok")
            return redirect(url_for("cliente.equipos"))
    return render_template("equipo_form.html", equipo=equipo, tipos=EquipoService.TIPOS)


@cliente.route("/equipos/<int:equipo_id>/eliminar", methods=["POST"])
@requiere_rol("Cliente")
def equipo_eliminar(equipo_id: int):
    try:
        EquipoService(g.con).eliminar(g.usuario.id, equipo_id)
        flash("Equipo eliminado.", "ok")
    except ErrorNegocio as error:
        _error(str(error))
    return redirect(url_for("cliente.equipos"))


@cliente.route("/casos/nuevo", methods=["GET", "POST"])
@requiere_rol("Cliente")
def caso_nuevo():
    lista = EquipoDAO(g.con).listar_por_cliente(g.usuario.id)
    if request.method == "POST":
        try:
            caso_id = DiagnosticoService(g.con).abrir_caso(
                g.usuario.id, _entero(request.form.get("equipo_id")), request.form.get("descripcion", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            flash("Caso abierto. Responda la consulta para obtener el diagnóstico.", "ok")
            return redirect(url_for("casos.consulta", caso_id=caso_id))
    return render_template("caso_nuevo.html", equipos=lista)


# ============================================================ casos (compartido por rol)
@casos.route("/")
@requiere_rol("Cliente", "Técnico", "Administrador")
def lista():
    u, dao = g.usuario, CasoDAO(g.con)
    if u.rol == "Cliente":
        filas = dao.listar(cliente_id=u.id)
    elif u.rol == "Técnico":
        filas = dao.listar(tecnico_id=u.id)
    else:
        filas = dao.listar(estado=request.args.get("estado") or None)
    return render_template("casos.html", casos=filas)


@casos.route("/<int:caso_id>")
@requiere_rol("Cliente", "Técnico", "Administrador")
def detalle(caso_id: int):
    caso = _caso_visible(caso_id)
    diagnostico = DiagnosticoDAO(g.con).por_caso(caso.id)
    hipotesis = HipotesisDAO(g.con).obtener(diagnostico.hipotesis_id) if diagnostico else None
    regla = ReglaDAO(g.con).obtener(diagnostico.regla_id) if diagnostico else None
    servicio = DiagnosticoService(g.con)
    consulta = servicio.consultas.ultima_por_caso(caso.id)
    respuestas = servicio.respuestas.listar(consulta.id) if consulta else []
    return render_template(
        "caso_detalle.html", caso=caso, diagnostico=diagnostico, hipotesis=hipotesis, regla=regla,
        respuestas=respuestas, seguimientos=SeguimientoDAO(g.con).listar_por_caso(caso.id))


@casos.route("/<int:caso_id>/consulta")
@requiere_rol("Cliente")
def consulta(caso_id: int):
    caso = _caso_visible(caso_id)
    servicio = DiagnosticoService(g.con)
    if caso.estado != "Abierto":
        return redirect(url_for("casos.detalle", caso_id=caso.id))
    consulta = servicio.iniciar_consulta(caso)
    nodo, pregunta = servicio.pregunta_actual(consulta)
    respuestas = servicio.respuestas.listar(consulta.id)
    return render_template(
        "consulta.html", caso=caso, consulta=consulta, nodo_id=nodo.id, pregunta=pregunta,
        numero=len(respuestas) + 1, respuestas=respuestas, candidatas=servicio.candidatas(consulta.id),
        total_reglas=len(servicio.motor.reglas))


@casos.route("/<int:caso_id>/responder", methods=["POST"])
@requiere_rol("Cliente")
def responder(caso_id: int):
    caso = _caso_visible(caso_id)
    servicio = DiagnosticoService(g.con)
    consulta = servicio.consultas.ultima_por_caso(caso.id)
    if consulta is None:
        abort(404)
    try:
        diagnostico = servicio.responder(
            consulta.id, request.form.get("valor", ""), _entero(request.form.get("nodo"), None))
    except (ErrorNegocio, ValueError, LookupError) as error:
        _error(str(error))
        return redirect(url_for("casos.consulta", caso_id=caso.id))
    if diagnostico:
        flash("Diagnóstico generado.", "ok")
        return redirect(url_for("casos.detalle", caso_id=caso.id))
    return redirect(url_for("casos.consulta", caso_id=caso.id))


@casos.route("/<int:caso_id>/retroceder", methods=["POST"])
@requiere_rol("Cliente")
def retroceder(caso_id: int):
    caso = _caso_visible(caso_id)
    servicio = DiagnosticoService(g.con)
    consulta = servicio.consultas.ultima_por_caso(caso.id)
    if consulta is None:
        abort(404)
    try:
        servicio.retroceder(consulta.id)
    except ErrorNegocio as error:
        _error(str(error))
    return redirect(url_for("casos.consulta", caso_id=caso.id))


# ============================================================ técnico
@tecnico.route("/cola")
@requiere_rol("Técnico")
def cola():
    return render_template("cola.html", casos=CasoDAO(g.con).cola_sin_tecnico())


@tecnico.route("/casos/<int:caso_id>/tomar", methods=["POST"])
@requiere_rol("Técnico")
def tomar(caso_id: int):
    try:
        DiagnosticoService(g.con).tomar_caso(caso_id, g.usuario.id)
        flash("Caso asignado a usted.", "ok")
    except ErrorNegocio as error:
        _error(str(error))
        return redirect(url_for("tecnico.cola"))
    return redirect(url_for("casos.detalle", caso_id=caso_id))


@tecnico.route("/casos/<int:caso_id>/seguimiento", methods=["POST"])
@requiere_rol("Técnico")
def seguimiento(caso_id: int):
    caso = _caso_visible(caso_id)
    try:
        DiagnosticoService(g.con).registrar_seguimiento(
            caso, g.usuario.id, request.form.get("observacion", ""), request.form.get("accion", ""))
        flash("Seguimiento registrado.", "ok")
    except ErrorNegocio as error:
        _error(str(error))
    return redirect(url_for("casos.detalle", caso_id=caso.id))


@tecnico.route("/casos/<int:caso_id>/resolver", methods=["POST"])
@requiere_rol("Técnico")
def resolver(caso_id: int):
    caso = _caso_visible(caso_id)
    try:
        DiagnosticoService(g.con).resolver_caso(
            caso, g.usuario.id, request.form.get("correcto") == "si", request.form.get("observacion", ""))
        flash("Caso resuelto.", "ok")
    except ErrorNegocio as error:
        _error(str(error))
    return redirect(url_for("casos.detalle", caso_id=caso.id))


# ============================================================ conocimiento
def _arbol(nodo, nodos: NodoArbolDAO, sintomas: dict, hipotesis: dict) -> dict:
    if nodo.es_hoja:
        h = hipotesis[nodo.hipotesis_id]
        return {"hoja": True, "id": h.id, "codigo": h.codigo, "texto": h.nombre, "rama": nodo.rama,
                "severidad": h.severidad}
    s = sintomas[nodo.sintoma_id]
    return {"hoja": False, "codigo": nodo.codigo, "texto": s.pregunta, "rama": nodo.rama,
            "sintoma": s.codigo,
            "hijos": [_arbol(nodos.hijo(nodo.id, r), nodos, sintomas, hipotesis) for r in ("si", "no")]}


def _dibujo_arbol(raiz: dict) -> dict:
    """Coordenadas (en píxeles de un lienzo SVG) para dibujar el árbol completo.

    Las hojas van de izquierda a derecha con la rama Sí siempre a la izquierda de la rama No; cada pregunta
    se centra sobre sus dos ramas y cada nivel del árbol ocupa una fila."""
    ancho, alto, paso_x, paso_y, margen, barra = 34, 22, 38, 52, 14, 11
    hojas_colocadas = [0]
    colocados: list[dict] = []

    def colocar(nodo: dict, nivel: int) -> dict:
        if nodo["hoja"]:
            columna, hijos = hojas_colocadas[0], []
            hojas_colocadas[0] += 1
        else:
            hijos = [colocar(h, nivel + 1) for h in nodo["hijos"]]
            columna = (hijos[0]["columna"] + hijos[1]["columna"]) / 2
        puesto = {"nodo": nodo, "nivel": nivel, "columna": columna, "hijos": hijos}
        colocados.append(puesto)
        return puesto

    colocar(raiz, 0)
    niveles = max(p["nivel"] for p in colocados)

    def centro(p: dict) -> tuple[float, float]:
        return margen + ancho / 2 + p["columna"] * paso_x, margen + alto / 2 + p["nivel"] * paso_y

    cajas, lineas, rotulos = [], [], []
    for p in colocados:
        cx, cy = centro(p)
        n = p["nodo"]
        if n["hoja"]:
            titulo = f"{n['codigo']} · {n['texto']} (severidad {n['severidad'].lower()})"
            enlace = url_for("conocimiento.hipotesis_detalle", hipotesis_id=n["id"])
        else:
            titulo, enlace = f"{n['codigo']} · {n['sintoma']}: {n['texto']}", None
        cajas.append({"x": cx - ancho / 2, "y": cy - alto / 2, "ancho": ancho, "alto": alto, "cx": cx, "cy": cy,
                      "codigo": n["codigo"], "hoja": n["hoja"], "titulo": titulo, "enlace": enlace})
        if p["hijos"]:
            y_barra = cy + alto / 2 + barra
            xs = [centro(h)[0] for h in p["hijos"]]
            lineas += [(cx, cy + alto / 2, cx, y_barra), (xs[0], y_barra, xs[1], y_barra)]
            for h, rama in zip(p["hijos"], ("Sí", "No")):
                hx, hy = centro(h)
                lineas.append((hx, y_barra, hx, hy - alto / 2))
                rotulos.append({"x": hx, "y": (y_barra + hy - alto / 2) / 2, "texto": rama})
    return {"ancho": 2 * margen + ancho + (hojas_colocadas[0] - 1) * paso_x,
            "alto": 2 * margen + alto + niveles * paso_y, "cajas": cajas, "lineas": lineas, "rotulos": rotulos}


@conocimiento.route("/hipotesis")
@requiere_rol("Experto", "Administrador")
def hipotesis_lista():
    dao = HipotesisDAO(g.con)
    grupos = [(c, dao.listar_por_categoria(c.id)) for c in CategoriaDAO(g.con).listar()]
    return render_template("hipotesis_lista.html", grupos=grupos)


@conocimiento.route("/hipotesis/<int:hipotesis_id>")
@requiere_rol("Experto", "Administrador")
def hipotesis_detalle(hipotesis_id: int):
    h = HipotesisDAO(g.con).obtener(hipotesis_id)
    if h is None:
        abort(404)
    reglas = ReglaDAO(g.con).por_hipotesis(h.id)
    return render_template("hipotesis_detalle.html", h=h, reglas=reglas)


@conocimiento.route("/hipotesis/<int:hipotesis_id>/editar", methods=["GET", "POST"])
@requiere_rol("Experto")
def hipotesis_editar(hipotesis_id: int):
    dao = HipotesisDAO(g.con)
    h = dao.obtener(hipotesis_id)
    if h is None:
        abort(404)
    if request.method == "POST":
        f = request.form
        try:
            certeza = float(f.get("factor_certeza", "").replace(",", "."))
            if not 0 < certeza <= 1:
                raise ValueError
            if f.get("severidad") not in ("Baja", "Media", "Alta", "Crítica"):
                raise ErrorNegocio("Severidad no válida.")
            if not f.get("nombre", "").strip() or not f.get("solucion", "").strip():
                raise ErrorNegocio("Nombre y solución son obligatorios.")
        except ValueError:
            _error("El factor de certeza debe ser un número mayor que 0 y hasta 1.")
        except ErrorNegocio as error:
            _error(str(error))
        else:
            dao.actualizar(h.id, f["nombre"].strip(), f.get("descripcion", "").strip(), f["severidad"],
                           certeza, f["solucion"].strip())
            flash("Conocimiento actualizado.", "ok")
            return redirect(url_for("conocimiento.hipotesis_detalle", hipotesis_id=h.id))
    return render_template("hipotesis_editar.html", h=h)


@conocimiento.route("/arbol")
@requiere_rol("Experto", "Administrador")
def arbol():
    nodos = NodoArbolDAO(g.con)
    sintomas = {s.id: s for s in SintomaDAO(g.con).listar()}
    hipotesis = {h.id: h for h in HipotesisDAO(g.con).listar()}
    raiz = _arbol(nodos.raiz(), nodos, sintomas, hipotesis)
    return render_template("arbol.html", raiz=raiz, dibujo=_dibujo_arbol(raiz))


@conocimiento.route("/reglas")
@requiere_rol("Experto", "Administrador")
def reglas():
    hip = {h.id: h for h in HipotesisDAO(g.con).listar()}
    return render_template("reglas.html", reglas=ReglaDAO(g.con).listar(), hipotesis=hip)


@conocimiento.route("/sintomas", methods=["GET", "POST"])
@requiere_rol("Experto", "Administrador")
def sintomas():
    dao = SintomaDAO(g.con)
    if request.method == "POST":
        if g.usuario.rol != "Experto":
            abort(403)
        pregunta = request.form.get("pregunta", "").strip()
        sintoma = dao.obtener(_entero(request.form.get("sintoma_id")))
        if sintoma is None or len(pregunta) < 10:
            _error("Escriba una pregunta de al menos 10 caracteres.")
        else:
            dao.actualizar_pregunta(sintoma.id, pregunta)
            flash(f"Pregunta {sintoma.codigo} actualizada.", "ok")
        return redirect(url_for("conocimiento.sintomas"))
    return render_template("sintomas.html", sintomas=dao.listar())


# ============================================================ administración
@admin.route("/usuarios")
@requiere_rol("Administrador")
def usuarios():
    return render_template("usuarios.html", usuarios=UsuarioDAO(g.con).listar(), roles=RolDAO(g.con).listar())


@admin.route("/usuarios/nuevo", methods=["GET", "POST"])
@requiere_rol("Administrador")
def usuario_nuevo():
    roles = RolDAO(g.con).listar()
    if request.method == "POST":
        f = request.form
        try:
            AutenticacionService(g.con).registrar(f.get("nombre", ""), f.get("correo", ""),
                                                  f.get("clave", ""), f.get("rol", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            flash("Usuario creado.", "ok")
            return redirect(url_for("admin.usuarios"))
    return render_template("usuario_form.html", roles=roles)


@admin.route("/usuarios/<int:usuario_id>/actualizar", methods=["POST"])
@requiere_rol("Administrador")
def usuario_actualizar(usuario_id: int):
    dao, roles = UsuarioDAO(g.con), RolDAO(g.con)
    objetivo = dao.obtener(usuario_id)
    if objetivo is None:
        abort(404)
    if objetivo.id == g.usuario.id:
        _error("No puede modificar su propio rol ni desactivarse.")
        return redirect(url_for("admin.usuarios"))
    rol_id = roles.id_por_nombre(request.form.get("rol", ""))
    if rol_id is None:
        _error("Rol no válido.")
        return redirect(url_for("admin.usuarios"))
    dao.cambiar_rol(objetivo.id, rol_id)
    dao.cambiar_estado(objetivo.id, request.form.get("activo") == "1")
    flash("Usuario actualizado.", "ok")
    return redirect(url_for("admin.usuarios"))


@admin.route("/reportes")
@requiere_rol("Administrador")
def reportes():
    return render_template(
        "reportes.html", por_estado=CasoDAO(g.con).contar_por_estado(),
        frecuencias=DiagnosticoDAO(g.con).frecuencia_por_hipotesis())


# ============================================================ cuenta propia
@cuenta.route("/clave", methods=["GET", "POST"])
@requiere_rol()
def clave():
    if request.method == "POST":
        f = request.form
        try:
            if f.get("nueva", "") != f.get("confirmacion", ""):
                raise ErrorNegocio("La confirmación no coincide con la nueva contraseña.")
            AutenticacionService(g.con).cambiar_clave(g.usuario, f.get("actual", ""), f.get("nueva", ""))
        except ErrorNegocio as error:
            _error(str(error))
        else:
            flash("Contraseña actualizada.", "ok")
            return redirect(url_for("publico.panel"))
    return render_template("clave.html")


BLUEPRINTS = [publico, cliente, casos, tecnico, conocimiento, admin, cuenta]
