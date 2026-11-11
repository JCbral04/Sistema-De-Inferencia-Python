"""Manual técnico del sistema experto (trabajo estudiantil en formato APA 7)."""
from __future__ import annotations

import json

from PIL import Image

from apa7 import DocumentoAPA
from documentos_comun import (AUTORES, CAPTURAS, DIAGRAMAS, RAIZ, REFERENCIAS, REPOSITORIO, TITULO_PROYECTO,
                              ajustar_codigo, decimal, lineas_de_portada)

TITULO = f"Manual técnico del {TITULO_PROYECTO}"
MEDIDAS = json.loads((DIAGRAMAS / "medidas.json").read_text(encoding="utf-8"))
SEVERIDADES = ["Baja", "Media", "Alta", "Crítica"]

# --------------------------------------------------------------------------- contenido tabular
PROCESOS = [
    ("P01", "Autenticación y control de acceso", "Todos", "Correo y contraseña", "Sesión con rol"),
    ("P02", "Gestión de usuarios y roles", "Administrador", "Datos del usuario y rol",
     "Usuario creado, activado o desactivado"),
    ("P03", "Gestión de equipos", "Cliente", "Tipo, marca, modelo y serial",
     "Equipo registrado, editado o eliminado"),
    ("P04", "Apertura de casos", "Cliente", "Equipo y descripción del problema", "Caso en estado Abierto"),
    ("P05", "Consulta de diagnóstico (navegación del árbol)", "Cliente", "Respuestas de sí o no",
     "Siguiente pregunta o conclusión"),
    ("P06", "Inferencia por reglas y emisión del diagnóstico", "Sistema", "Evidencia de la consulta",
     "Diagnóstico, solución y factor de certeza"),
    ("P07", "Atención técnica del caso", "Técnico", "Caso diagnosticado y observaciones",
     "Seguimiento, validación del diagnóstico y caso Resuelto"),
    ("P08", "Mantenimiento de la base de conocimiento", "Experto", "Cambios a fallas, soluciones y preguntas",
     "Conocimiento actualizado"),
    ("P09", "Supervisión y reportes", "Administrador", "Filtro por estado del caso",
     "Casos y frecuencia de diagnósticos"),
    ("P10", "Adquisición y carga del conocimiento", "Experto e ingeniero de conocimiento",
     "Conocimiento del experto en un archivo JSON", "Base de conocimiento cargada y reglas derivadas"),
]

REQ_FUNCIONALES = [
    ("El sistema permitirá iniciar y cerrar sesión con correo y contraseña.", "P01"),
    ("El sistema permitirá que una persona cree su cuenta; las cuentas nuevas tendrán el rol Cliente.", "P01"),
    ("Todo usuario con sesión podrá cambiar su contraseña indicando la actual.", "P01"),
    ("El sistema restringirá cada función según el rol del usuario.", "P01"),
    ("El administrador podrá crear usuarios con cualquier rol y cambiar el rol o el estado (activo o inactivo) "
     "de los demás usuarios; no podrá modificar su propia cuenta de ese modo.", "P02"),
    ("El cliente podrá registrar, editar y eliminar sus equipos; no podrá eliminar un equipo que tenga casos.", "P03"),
    ("El cliente podrá abrir un caso sobre uno de sus equipos con una descripción del problema.", "P04"),
    ("El cliente podrá consultar el historial y el detalle de sus casos, sin ver los de otros clientes.", "P04"),
    ("El sistema conducirá la consulta mostrando una pregunta de sí o no por vez, a partir de la raíz del árbol.", "P05"),
    ("El sistema mostrará cuántas reglas siguen siendo compatibles con las respuestas dadas.", "P05"),
    ("El cliente podrá corregir su última respuesta durante la consulta.", "P05"),
    ("Al llegar a una hoja, el sistema evaluará las reglas y emitirá el diagnóstico con la solución recomendada "
     "y el factor de certeza.", "P06"),
    ("El sistema registrará cada respuesta, la regla disparada y el diagnóstico asociados a la consulta.", "P06"),
    ("El técnico verá la cola de casos diagnosticados que no tienen técnico y podrá tomar uno; dos técnicos no "
     "podrán tomar el mismo caso.", "P07"),
    ("El técnico asignado podrá registrar seguimientos con la acción realizada y una observación.", "P07"),
    ("El técnico asignado podrá resolver el caso e indicar si el diagnóstico fue correcto.", "P07"),
    ("El experto podrá consultar el árbol, las reglas y la ficha de conocimiento de cada hipótesis.", "P08"),
    ("El experto podrá editar el nombre, la descripción, la severidad, el factor de certeza y la solución de "
     "cada falla.", "P08"),
    ("El experto podrá editar el texto de las preguntas (síntomas).", "P08"),
    ("El administrador podrá filtrar todos los casos por estado y consultar la frecuencia de cada diagnóstico "
     "con su tasa de confirmación.", "P09"),
    ("El sistema cargará el conocimiento desde un archivo JSON y validará que el árbol sea completo y que cada "
     "falla sea una hoja única.", "P10"),
    ("El sistema derivará automáticamente una regla por cada camino de la raíz a una hoja del árbol.", "P10"),
]

REQ_NO_FUNCIONALES = [
    ("Seguridad de las credenciales",
     "Las contraseñas se guardan con hash (Werkzeug), nunca en texto claro, y deben tener al menos ocho "
     "caracteres. La cookie de sesión es HttpOnly y SameSite=Lax, y los formularios que modifican datos llevan "
     "un token CSRF por sesión {c:owasp}.",
     "Revisión del código y prueba de rechazo de formularios sin token"),
    ("Control de acceso",
     "Toda ruta valida la sesión y el rol en el servidor; un cliente no puede ver los casos ni los equipos de otro.",
     "Pruebas de acceso por rol y de casos ajenos"),
    ("Integridad de los datos",
     "El esquema define claves foráneas, restricciones CHECK y UNIQUE; las claves foráneas se activan en cada "
     "conexión y la asignación del técnico es atómica.",
     "Esquema SQL y prueba de asignación exclusiva"),
    ("Rendimiento",
     "Cada respuesta de la consulta se procesa en menos de un segundo con 31 reglas.",
     "Medición con el cliente de pruebas de Flask: unos 3 ms por respuesta"),
    ("Mantenibilidad",
     "Arquitectura en tres capas con patrón DAO: el SQL está en los DAO y la lógica de negocio en los servicios.",
     "Revisión de la estructura de carpetas"),
    ("Extensibilidad del conocimiento",
     "Agregar una falla o una pregunta implica editar el archivo JSON y recargar la base; el motor no cambia, "
     "porque lee el árbol y las reglas de la base de datos.",
     "Recarga de la base desde el JSON"),
    ("Usabilidad",
     "Interfaz en español, una pregunta por pantalla con dos botones, posibilidad de corregir la última "
     "respuesta y mensajes de error claros.",
     "Inspección de las pantallas ({a:F})"),
    ("Portabilidad",
     "Se ejecuta con Python 3.10 o superior y Flask, sin servidor de base de datos: SQLite guarda todo en un "
     "solo archivo.",
     "Análisis de la versión mínima de Python; ejecución en Linux con Python 3.13"),
    ("Trazabilidad",
     "Cada diagnóstico conserva la consulta, las respuestas en orden, la regla disparada, el factor de "
     "certeza y la fecha de emisión.",
     "Detalle del caso en la aplicación"),
    ("Calidad verificable",
     "El conocimiento, el motor, los procesos y las rutas web se prueban de forma automática.",
     "Ejecución de las 27 pruebas"),
    ("Compatibilidad",
     "Las páginas son HTML y CSS sin JavaScript obligatorio, de modo que funcionan en los navegadores actuales.",
     "Revisión de las plantillas"),
    ("Consistencia del conocimiento",
     "Las reglas son mutuamente excluyentes y completas: cada recorrido del árbol dispara exactamente una "
     "regla. La carga rechaza árboles incompletos, con nodos inalcanzables o con fallas repetidas.",
     "Pruebas de exclusión mutua y de validación del árbol"),
]

SUBARBOLES = [  # nodo raíz, tema (el mismo del diagrama), figura donde se detalla
    ("N02", "Equipo sin encendido", "n02"), ("N06", "Pitidos largos o continuos", "n06_n08"),
    ("N08", "Sin imagen en pantalla", "n06_n08"), ("N11", "El sistema operativo no carga", "n11"),
    ("N16", "Apagados y reinicios repentinos", "n16"), ("N20", "Lentitud del equipo", "n20"),
    ("N25", "Problemas de conexión a internet", "n25"), ("N28", "Fallas de imagen", "n28_n30"),
    ("N30", "Periférico no reconocido", "n28_n30"),
]
RAICES = {nodo for nodo, _, _ in SUBARBOLES}

TABLAS_BD = [
    ("Conocimiento", "experto", "Experto humano que aporta el conocimiento (registro por completar)"),
    ("Conocimiento", "categoria", "Nueve categorías que agrupan las fallas"),
    ("Conocimiento", "hipotesis", "Fallas, con severidad, factor de certeza y solución recomendada"),
    ("Conocimiento", "sintoma", "Preguntas (síntomas) del árbol"),
    ("Conocimiento", "nodo_arbol", "Nodos del árbol: preguntas y hojas, con su padre y la rama (sí o no)"),
    ("Conocimiento", "regla", "Una regla por cada hoja del árbol"),
    ("Conocimiento", "regla_condicion", "Premisas de cada regla: síntoma y valor esperado, en orden"),
    ("Transaccional", "rol", "Los cuatro roles del sistema"),
    ("Transaccional", "usuario", "Usuarios, con contraseña cifrada, rol y estado"),
    ("Transaccional", "equipo", "Equipos de cada cliente"),
    ("Transaccional", "caso", "Caso de soporte, con su estado y el técnico asignado"),
    ("Transaccional", "consulta", "Sesión de diagnóstico de un caso"),
    ("Transaccional", "respuesta", "Respuestas de sí o no de una consulta, en orden"),
    ("Transaccional", "diagnostico", "Falla emitida, regla disparada, factor de certeza y confirmación del técnico"),
    ("Transaccional", "seguimiento", "Acciones y observaciones del técnico sobre el caso"),
]

ROLES = [
    ("Cliente", "Dueño del equipo: registra equipos, abre casos y responde la consulta de diagnóstico.",
     "P01, P03, P04, P05"),
    ("Técnico", "Atiende los casos ya diagnosticados, registra el seguimiento y valida el diagnóstico.",
     "P01, P07"),
    ("Experto", "Mantiene las fallas, las soluciones y las preguntas, y consulta el árbol, las reglas y los gránulos.",
     "P01, P08, P10"),
    ("Administrador", "Gestiona usuarios y roles, supervisa todos los casos y consulta los reportes.",
     "P01, P02, P09"),
]

PERMISOS = [  # función, cliente, técnico, experto, administrador
    ("Iniciar sesión y cambiar la contraseña", "●", "●", "●", "●"),
    ("Registrar equipos y abrir casos", "●", "", "", ""),
    ("Ejecutar la consulta de diagnóstico", "●", "", "", ""),
    ("Consultar casos", "Propios", "Asignados y en cola", "", "Todos"),
    ("Ver la cola de casos y tomar un caso", "", "●", "", ""),
    ("Registrar seguimiento y resolver casos asignados", "", "●", "", ""),
    ("Consultar fallas, árbol, reglas y preguntas", "", "", "●", "○"),
    ("Editar fallas, soluciones y preguntas", "", "", "●", ""),
    ("Gestionar usuarios y roles", "", "", "", "●"),
    ("Consultar reportes", "", "", "", "●"),
]

CASOS_DE_USO = [  # caso de uso, actor, descripción, procesos
    ("Registrarse e iniciar sesión", "Cliente", "Crea su cuenta e ingresa al sistema.", "P01"),
    ("Gestionar equipos", "Cliente", "Registra, edita y elimina sus equipos.", "P03"),
    ("Abrir caso", "Cliente", "Reporta el problema de uno de sus equipos.", "P04"),
    ("Ejecutar consulta de diagnóstico", "Cliente",
     "Responde preguntas de sí o no hasta obtener el diagnóstico; incluye inferir el diagnóstico.", "P05"),
    ("Inferir diagnóstico (árbol y reglas)", "Sistema", "Evalúa las reglas con las respuestas y emite la falla, "
     "la solución y el factor de certeza.", "P06"),
    ("Consultar historial de casos", "Cliente", "Revisa el estado, el diagnóstico y los seguimientos.", "P04"),
    ("Consultar cola de casos", "Técnico", "Ve los casos diagnosticados que no tienen técnico.", "P07"),
    ("Tomar caso", "Técnico", "Se asigna un caso de forma exclusiva.", "P07"),
    ("Registrar seguimiento", "Técnico", "Anota las acciones realizadas y sus observaciones.", "P07"),
    ("Resolver caso y validar diagnóstico", "Técnico", "Cierra el caso e indica si el diagnóstico acertó.", "P07"),
    ("Gestionar hipótesis y soluciones", "Experto", "Edita las fallas, su severidad, su certeza y su solución.", "P08"),
    ("Consultar árbol y reglas", "Experto", "Revisa el árbol de decisión y las reglas derivadas.", "P08"),
    ("Gestionar preguntas (síntomas)", "Experto", "Edita el texto de las preguntas del árbol.", "P08"),
    ("Consultar gránulos por hipótesis", "Experto", "Ve la ficha, la regla, las premisas y el camino de cada falla.", "P08"),
    ("Gestionar usuarios y roles", "Administrador", "Crea usuarios, cambia roles y activa o desactiva cuentas.", "P02"),
    ("Supervisar todos los casos", "Administrador", "Consulta y filtra los casos por estado.", "P09"),
    ("Consultar reportes", "Administrador", "Ve la frecuencia de los diagnósticos y su tasa de confirmación.", "P09"),
]

CARPETAS = [
    ("`app.py`", "Punto de entrada de la aplicación web."),
    ("`src/web/`", "Rutas por rol, seguridad (sesión, roles y CSRF), plantillas y estilos."),
    ("`src/services/`", "Servicios de negocio y motor de inferencia."),
    ("`src/dao/`", "DAO, conexión a la base y cargador del conocimiento."),
    ("`src/domain/`", "Entidades inmutables del dominio."),
    ("`database/`", "Esquema, modelo relacional exportado y script de carga del conocimiento."),
    ("`data/`", "Conocimiento del experto en JSON y base de datos SQLite generada."),
    ("`sql/`", "Consultas de los gránulos de conocimiento (G1 a G7)."),
    ("`scripts/`", "Creación de la base, consulta de gránulos, diagramas, capturas y documentos."),
    ("`tests/`", "Las 27 pruebas automatizadas."),
    ("`docs/`", "Diagramas, capturas de pantalla, salidas de las consultas y documentos Word."),
]

CAPTURAS_APP = [  # archivo, clave, título, nota
    ("01_ingreso", "cap01", "Pantalla de ingreso", None),
    ("02_equipos_del_cliente", "cap02", "Equipos del cliente", None),
    ("03_consulta_guiada", "cap03", "Consulta guiada, una pregunta de sí o no por pantalla",
     "Captura tomada durante la consulta del caso de ejemplo, un equipo que se apaga solo bajo carga."),
    ("04_diagnostico_emitido", "cap04", "Diagnóstico emitido para el caso",
     "El recorrido de esta consulta corresponde a la regla R17 (falla F17). La aplicación muestra el factor de "
     "certeza como porcentaje: 0.78 se presenta como 78 %."),
    ("05_cola_del_tecnico", "cap05", "Cola de casos del técnico", None),
    ("06_caso_resuelto", "cap06", "Caso resuelto por el técnico", None),
    ("07_fallas_del_experto", "cap07", "Lista de fallas del experto", None),
    ("08_granulo_de_conocimiento", "cap08", "Gránulo de conocimiento de la falla F17", None),
    ("09_usuarios_del_administrador", "cap09", "Usuarios del administrador", None),
    ("10_reportes", "cap10", "Reportes del administrador", None),
]

PSEUDOCODIGO = """\
evidencia <- {}
nodo <- raíz del árbol
MIENTRAS nodo sea una pregunta:
    respuesta <- preguntar(síntoma de nodo)        # sí o no
    evidencia[síntoma de nodo] <- respuesta
    nodo <- hijo de nodo según la respuesta
disparadas <- reglas cuyas premisas están todas en evidencia
regla <- la de mayor FC (si empatan, la de más premisas)
DIAGNÓSTICO <- falla de regla, con su FC y su solución"""


# --------------------------------------------------------------------------- utilidades
def rango(codigos: list[str]) -> str:
    """['F01', ..., 'F04'] -> 'F01–F04', como en los diagramas; un solo código queda igual."""
    numeros = [int(c[1:]) for c in codigos]
    assert numeros == list(range(numeros[0], numeros[0] + len(numeros))), f"códigos no consecutivos: {codigos}"
    return codigos[0] if len(codigos) == 1 else f"{codigos[0]}–{codigos[-1]}"


def unir(elementos: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b y c'."""
    return elementos[0] if len(elementos) == 1 else ", ".join(elementos[:-1]) + " y " + elementos[-1]


def rama(valor: str) -> str:
    return "Sí" if valor == "si" else "No"


def palabra(n: int) -> str:
    """APA: los números del cero al nueve se escriben con letras."""
    letras = ["cero", "uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve"]
    return letras[n] if n < 10 else str(n)


def en_subarbol(nodo: str, raices: set[str], acceso: dict) -> bool:
    """True si el nodo es una de las raíces de subárbol o desciende de una de ellas."""
    while nodo in acceso:
        if nodo in raices:
            return True
        nodo = acceso[nodo][0]
    return nodo in raices


def texto_regla(regla: dict) -> str:
    return " Y ".join(f"{s} = {'SÍ' if v == 'si' else 'NO'}" for s, v in regla["condiciones"])


def celda(valor) -> str:
    if valor is None:
        return "—"
    if isinstance(valor, float):
        return decimal(valor)
    return str(valor)


def diagrama(d: DocumentoAPA, clave: str, titulo: str, archivo: str, nota: str | None, alt: str) -> None:
    d.figura(clave, titulo, DIAGRAMAS / f"{archivo}.png", tuple(MEDIDAS[archivo]), nota, alt)


def indices(d: DocumentoAPA, previo: dict) -> None:
    paginas = previo.get("paginas", {})
    d.indice("Tabla de contenido", [e for e in previo.get("encabezados", []) if e["nivel"] <= 2], paginas)
    # La lista de figuras sigue a la de tablas en la misma página, para no dejar una página casi vacía.
    for titulo, tipo, pagina_nueva in (("Lista de tablas", "Tabla", True), ("Lista de figuras", "Figura", False)):
        entradas = [{"texto": f"{r['etiqueta']}. {r['titulo']}", "marcador": r["marcador"]}
                    for r in previo.get("rotulos", []) if r["tipo"] == tipo]
        d.indice(titulo, entradas, paginas, nueva_pagina=pagina_nueva)


def resultado_de_consulta(d: DocumentoAPA, clave: str, titulo: str, columnas: list[str], filas: list[tuple],
                          anchos: list[float], alineacion: str, nota: str | None = None, tam: float = 10) -> None:
    d.tabla(clave, titulo, columnas, [[celda(v) for v in fila] for fila in filas], anchos, alineacion, nota=nota,
            tam=tam)


def ficha(d: DocumentoAPA, clave: str, titulo: str, resultado: tuple, nota: str | None = None,
          tam: float = 10) -> None:
    """La consulta G1 devuelve una sola fila ancha; se presenta como pares campo-valor."""
    columnas, filas = resultado
    etiquetas = {"codigo": "Código", "nombre": "Nombre", "categoria": "Categoría", "severidad": "Severidad",
                 "factor_certeza": "Factor de certeza", "fuente_experto": "Fuente del experto",
                 "solucion": "Solución"}
    d.tabla(clave, titulo, ["Campo", "Valor"], [[etiquetas[c], celda(v)] for c, v in zip(columnas, filas[0])],
            [1.5, 5.0], "ll", nota=nota, tam=tam)


def construir(previo: dict, datos: dict) -> DocumentoAPA:
    hip, sint, reglas = datos["hipotesis"], datos["sintomas"], datos["reglas"]
    n_preg, n_fallas, n_reglas = datos["n_preguntas"], datos["n_fallas"], datos["n_reglas"]
    n_prem, n_nodos = datos["n_premisas"], datos["n_nodos"]
    cuenta = datos["cuenta"]
    regla17 = next(r for r in reglas if r["hipotesis"] == "F17")
    assert regla17["condiciones"] == [("S01", "si"), ("S05", "no"), ("S07", "si"), ("S09", "no"), ("S10", "si"),
                                      ("S15", "si"), ("S16", "no"), ("S18", "si")], "cambió R17: revise el ejemplo"
    assert set(datos["tablas_bd"]) == {t for _, t, _ in TABLAS_BD}, "cambió el esquema: revise la tabla de tablas"
    assert all(r["codigo"][1:] == r["hipotesis"][1:] for r in reglas), "el código de cada regla debe copiar el de su falla"

    d = DocumentoAPA(REFERENCIAS, previo, titulo=TITULO, autores=AUTORES,
                     asunto="Sistemas expertos: manual técnico del sistema experto")
    d.portada(TITULO, AUTORES, lineas_de_portada())
    indices(d, previo)

    # ======================================================================== introducción
    d.titulo_inicial(TITULO)
    d.p("Este manual técnico describe el diseño y la construcción de un sistema experto web que orienta el "
        "diagnóstico inicial de fallas de computadores de escritorio y portátiles. Reúne los productos de análisis "
        "y diseño que respaldan la aplicación: los procesos y los requerimientos, el árbol de decisión y sus reglas, "
        "la base de datos del conocimiento y del sistema transaccional, la carga del conocimiento y su consulta por "
        "hipótesis, el diagrama de flujo de datos del sistema de inferencia, los roles, los casos de uso y el "
        "diagrama de clases del acceso a datos.")
    d.p(f"El conocimiento se representa como un árbol de decisión binario de {n_preg} preguntas y {n_fallas} fallas. "
        f"De cada camino que va de la raíz a una falla se deriva una regla SI-ENTONCES; en total son {n_reglas} reglas "
        f"con {n_prem} premisas. El motor de inferencia recorre el árbol para decidir la siguiente pregunta y, al "
        "llegar a una falla, confirma la conclusión evaluando las reglas por encadenamiento hacia adelante "
        "{c:giarratano,russell}. Cada regla lleva un factor de certeza (FC) entre 0 y 1 que expresa la confianza "
        "del experto en su conclusión, a la manera del modelo de MYCIN {c:shortliffe}.")
    d.p("El contenido del árbol, de las fallas, de las soluciones y de los factores de certeza es una propuesta "
        "elaborada por el equipo del proyecto a partir de procedimientos habituales de diagnóstico; todavía no "
        "proviene de una validación con un técnico experto. Por eso, en la base de conocimiento el registro del "
        "experto figura como «por registrar». Cuando el experto revise el conocimiento, los cambios que indique se "
        "aplican como se explica en la sección Carga del conocimiento del experto.")
    d.p("El documento sigue el orden de los productos solicitados, y las tablas y figuras se numeran según el orden "
        "en que se mencionan. Los listados extensos están en los apéndices: las preguntas del árbol ({a:A}), las "
        "soluciones de cada falla ({a:B}), el script SQL del esquema ({a:C}), el modelo relacional en notación "
        "textual ({a:D}), los resultados de otras consultas de gránulos ({a:E}) y las capturas de pantalla de la "
        "aplicación ({a:F}).")

    # ======================================================================== procesos
    d.h1("Listado de procesos identificados")
    d.p("Se identificaron 10 procesos (P01 a P10). Nueve se ejecutan durante el servicio de soporte, por una "
        "persona o por el sistema, y uno (P10) corresponde a la adquisición del conocimiento, que ocurre antes de "
        "usar el sistema. La {t:procesos} los presenta con su actor, su entrada y su salida; los códigos se usan en "
        "el resto del manual.")
    d.tabla("procesos", "Procesos identificados del sistema experto",
            ["Cód.", "Proceso", "Actor", "Entrada", "Salida"], [list(p) for p in PROCESOS],
            [0.5, 1.7, 1.05, 1.65, 1.6], "lllll", nota="El actor «Sistema» indica un proceso automático.")
    d.p("El proceso central es el ciclo de vida de un caso, que cambia de estado a medida que avanzan los demás. "
        "Un caso nace en estado Abierto cuando el cliente lo registra (P04); pasa a Diagnosticado cuando termina la "
        "consulta y el motor emite el diagnóstico (P05 y P06); pasa a En atención cuando un técnico lo toma (P07) y "
        "a Resuelto cuando el técnico lo cierra e indica si el diagnóstico fue correcto.")

    # ======================================================================== requerimientos funcionales
    d.h1("Requerimientos funcionales")
    d.p("Los requerimientos funcionales describen lo que el sistema debe hacer {c:sommerville}. Se redactaron como "
        "enunciados verificables, con un código único y con el proceso que los origina, siguiendo las "
        "características que recomienda la norma ISO/IEC/IEEE 29148 {c:iso29148}. Se listan en la {t:rf}.")
    d.tabla("rf", "Requerimientos funcionales", ["Cód.", "Requerimiento", "Proceso"],
            [[f"RF{n:02d}", texto, proceso] for n, (texto, proceso) in enumerate(REQ_FUNCIONALES, 1)],
            [0.6, 5.1, 0.8], "lll", juntas=False)

    # ======================================================================== requerimientos no funcionales
    d.h1("Requerimientos no funcionales")
    d.p("Los requerimientos no funcionales describen cualidades del sistema, como la seguridad o el rendimiento, y "
        "no funciones concretas {c:sommerville}. Se formularon de modo que puedan comprobarse; la {t:rnf} indica en "
        "cada caso cómo se verifica.")
    d.tabla("rnf", "Requerimientos no funcionales", ["Cód.", "Atributo", "Descripción", "Verificación"],
            [[f"RNF{n:02d}", a, desc, v] for n, (a, desc, v) in enumerate(REQ_NO_FUNCIONALES, 1)],
            [0.7, 1.05, 3.05, 1.7], "llll", juntas=False)

    # ======================================================================== árbol de decisión
    d.h1("Árbol de decisión")
    d.p(f"El árbol de decisión organiza el conocimiento del experto como una secuencia de preguntas de sí o no. Cada "
        "nodo interno es una pregunta (un síntoma), cada rama se rotula Sí o No y cada hoja es una falla (una "
        f"hipótesis). Con {n_preg} preguntas y {n_fallas} hojas, el árbol tiene {n_nodos} nodos y supera el mínimo "
        f"de 25 ramas o fallas. Cada camino de la raíz a una falla contiene entre {datos['min_premisas']} y "
        f"{datos['max_premisas']} preguntas. Las fallas se reparten en nueve categorías y cuatro niveles de severidad, "
        "como muestra la {t:categorias}.")

    severidad_por_categoria = {c["codigo"]: {s: 0 for s in SEVERIDADES} for c in datos["categorias"]}
    for h in hip:
        severidad_por_categoria[h["cat_codigo"]][h["severidad"]] += 1
    filas = [[f"{c['nombre']}"] + [str(severidad_por_categoria[c["codigo"]][s]) for s in SEVERIDADES]
             + [str(sum(severidad_por_categoria[c["codigo"]].values()))] for c in datos["categorias"]]
    filas.append(["Total"] + [str(sum(severidad_por_categoria[c][s] for c in severidad_por_categoria))
                              for s in SEVERIDADES] + [str(n_fallas)])
    d.tabla("categorias", "Fallas por categoría y severidad", ["Categoría", "Baja", "Media", "Alta", "Crítica", "Total"],
            filas, [2.75, 0.75, 0.75, 0.75, 0.75, 0.75], "lccccc")

    # el tronco son las preguntas que no pertenecen a ningún subárbol; las fallas sueltas salen de él
    hojas_de, acceso = datos["hojas_de"], datos["acceso"]
    assert RAICES <= set(hojas_de), "un subárbol del manual no existe en el árbol cargado"
    tronco = [n for n in hojas_de if not en_subarbol(n, RAICES, acceso)]
    en_subarboles = {h for nodo in RAICES for h in hojas_de[nodo]}
    sueltas = [h["codigo"] for h in hip if h["codigo"] not in en_subarboles]
    d.p("La {f:arbol_completo} muestra el árbol entero en una sola página, con cada nodo rotulado por su código; la "
        "rama Sí queda siempre a la izquierda de la rama No. A esa escala no se alcanza a leer el texto de las "
        "preguntas, así que el árbol se presenta además en dos niveles de detalle. El tronco ({f:tronco}) es la "
        f"cadena de {len(tronco)} preguntas generales que se recorre desde la raíz mientras las respuestas no "
        "desvíen la consulta: en cada pregunta del tronco, una rama lleva a un subárbol o a una falla y la otra "
        "continúa por el tronco; en la última pregunta, las dos ramas salen del tronco. "
        f"Los {palabra(len(RAICES))} subárboles se detallan en figuras aparte. La "
        "{t:subarboles} indica el tema de cada uno, la pregunta del tronco de la que se llega a él, las fallas "
        "que contiene y la figura donde se detalla. En las figuras, cada pregunta se rotula con un nombre corto; "
        "el texto completo de las preguntas está en el {a:A}.")
    d.p("El orden de las preguntas del tronco expresa una prioridad: primero se descartan las fallas que impiden "
        "encender o arrancar el equipo, luego las que afectan su estabilidad y su rendimiento, y al final la red, "
        "la imagen y los periféricos. Por eso cada consulta entrega una sola falla probable, la de mayor "
        "prioridad; si el equipo tiene varios problemas a la vez, se abre un caso por cada uno. Este orden también "
        "es una propuesta del equipo que debe validar el experto.")
    nota_sub = None
    if sueltas:
        nota_sub = (f"Las fallas {unir(sueltas)} no tienen subárbol, porque salen directamente del tronco: "
                    + "; ".join(f"{h} desde {acceso[h][0]}, por la rama {rama(acceso[h][1])}" for h in sueltas) + ".")
    d.tabla("subarboles", "Subárboles del árbol de decisión y figura donde se detallan",
            ["Subárbol", "Tema", "Se llega desde", "Fallas", "Figura"],
            [[nodo, tema, f"{acceso[nodo][0]}, rama {rama(acceso[nodo][1])}", rango(hojas_de[nodo]),
              "{f:%s}" % figura] for nodo, tema, figura in SUBARBOLES],
            [0.8, 2.25, 1.3, 1.05, 1.1], "lllll", nota=nota_sub)

    nota_igual = "Mismos símbolos que en la Figura {#f:tronco}. FC = factor de certeza. Elaboración propia."
    diagrama(d, "arbol_completo", "Árbol de decisión completo", "arbol_completo",
             "N = pregunta; F = falla. Las preguntas están en el {a:A} y las fallas, en el {a:B}. "
             "Elaboración propia.",
             f"Árbol de decisión completo: {n_preg} preguntas y {n_fallas} fallas, con sus ramas Sí y No.")
    diagrama(d, "tronco", "Tronco del árbol de decisión", "arbol_tronco",
             "Entre paréntesis, las fallas de cada subárbol. N = nodo; S = síntoma. Elaboración propia.",
             f"Diagrama del tronco del árbol: {len(tronco)} preguntas en cadena, de las que salen ramas hacia "
             "subárboles o fallas.")
    subtitulos = {"n02": "Subárbol N02: equipo sin encendido",
                  "n06_n08": "Subárboles N06 y N08: pitidos y falta de imagen",
                  "n11": "Subárbol N11: el sistema operativo no carga",
                  "n16": "Subárbol N16: apagados y reinicios repentinos",
                  "n20": "Subárbol N20: lentitud del equipo",
                  "n25": "Subárbol N25: problemas de conexión a internet",
                  "n28_n30": "Subárboles N28 y N30: imagen y periféricos"}
    archivos = {"n02": "arbol_N02", "n06_n08": "arbol_N06_N08", "n11": "arbol_N11", "n16": "arbol_N16",
                "n20": "arbol_N20", "n25": "arbol_N25", "n28_n30": "arbol_N28_N30"}
    for figura in dict.fromkeys(f for _, _, f in SUBARBOLES):
        nodos_figura = [n for n, _, f in SUBARBOLES if f == figura]
        fallas_figura = sorted(h for n in nodos_figura for h in hojas_de[n])
        diagrama(d, figura, subtitulos[figura], archivos[figura], nota_igual,
                 f"{'Subárbol' if len(nodos_figura) == 1 else 'Subárboles'} de {unir(nodos_figura)} con las "
                 f"fallas {rango(fallas_figura) if len(nodos_figura) == 1 else unir(fallas_figura)}.")

    d.p("La {t:ramas} lista las 31 ramas del árbol, una por falla, con su categoría, su severidad, su factor de "
        "certeza y el número de preguntas de su camino. El texto completo de las preguntas está en el {a:A} y la "
        "solución recomendada de cada falla, en el {a:B}.")
    d.tabla("ramas", "Ramas (fallas) del árbol de decisión",
            ["Falla", "Nombre", "Categoría", "Severidad", "FC", "Preguntas"],
            [[h["codigo"], h["nombre"], h["categoria"], h["severidad"], decimal(h["factor_certeza"]),
              str(len(next(r for r in reglas if r["hipotesis"] == h["codigo"])["condiciones"]))] for h in hip],
            [0.5, 2.6, 1.5, 0.75, 0.4, 0.75], "lllccc", juntas=False,
            nota="FC = factor de certeza asignado a la falla. «Preguntas» es el número de preguntas del camino que "
                 "lleva a la falla.")

    # ======================================================================== reglas
    d.h1("Reglas del sistema experto")
    d.p("Cada regla corresponde a un camino del árbol, de la raíz a una hoja. Las premisas son pares síntoma-valor "
        "(por ejemplo, S01 = SÍ) unidos por Y, y la conclusión es la falla de la hoja. El código de la regla copia el "
        "de su falla: el camino que termina en F17 produce la regla R17. Como el árbol es binario y completo, dos "
        "caminos distintos difieren al menos en una respuesta, de modo que ninguna combinación de respuestas "
        "dispara dos reglas a la vez; las pruebas automatizadas lo verifican recorriendo los 31 caminos.")
    d.p("Por ejemplo, la regla R17 se lee así: SI el equipo enciende de forma sostenida (S01 = SÍ), no emite pitidos "
        "de error ni luces de diagnóstico (S05 = NO), muestra imagen al arrancar (S07 = SÍ), no muestra un error de BIOS "
        "(S09 = NO), llega a cargar el sistema operativo (S10 = SÍ), se apaga o se reinicia solo de forma repentina "
        "(S15 = SÍ), no tiene temperatura alta ni ventiladores ruidosos (S16 = NO) y se apaga al ejecutar tareas "
        "exigentes (S18 = SÍ), ENTONCES la falla es una fuente de poder o un cargador insuficiente o inestable "
        f"bajo carga (F17), con un factor de certeza de {decimal(regla17['fc'])}.")
    d.p("El motor de inferencia cumple dos tareas, que resume la {f:pseudocodigo}. Primero conduce la consulta: "
        "parte de la raíz, presenta la pregunta del nodo y avanza al hijo que corresponde a la respuesta. Luego, al "
        "llegar a una hoja, evalúa las reglas contra la evidencia reunida y elige la que se dispara. Si por una "
        "inconsistencia del conocimiento se dispararan varias, se aplicaría una resolución de conflictos: se "
        "escoge la de mayor FC y, si empatan, la más específica, es decir, la de más premisas {c:giarratano}.")
    d.figura_codigo("pseudocodigo", "Pseudocódigo del motor de inferencia", PSEUDOCODIGO,
                    nota="FC = factor de certeza. Elaboración propia.")
    d.p("La {t:reglas} presenta las 31 reglas derivadas del árbol. La solución recomendada de cada conclusión se "
        "recupera de la ficha de la falla ({a:B}).")
    d.tabla("reglas", "Reglas SI-ENTONCES derivadas del árbol de decisión", ["Regla", "SI (premisas)", "ENTONCES", "FC"],
            [[r["codigo"], texto_regla(r), r["hipotesis"], decimal(r["fc"])] for r in reglas],
            [0.6, 4.35, 1.0, 0.55], "llcc", juntas=False,
            nota="Cada premisa es un síntoma (S) con el valor SÍ o NO. Las premisas aparecen en el orden en que se "
                 "recorren en el árbol. FC = factor de certeza de la regla.")

    # ======================================================================== base de datos
    d.h1("Base de datos del conocimiento y del sistema transaccional")
    d.h2("Sistema gestor de base de datos")
    d.p("Se eligió SQLite 3 porque es relacional, no requiere un servidor, admite claves foráneas y restricciones "
        "CHECK y guarda toda la base en un solo archivo (data/sistema_experto.db). El modelo sigue el enfoque "
        "relacional {c:codd}. SQLite solo aplica las claves foráneas si se activan en cada conexión con la "
        "instrucción `PRAGMA foreign_keys = ON` {c:sqlite}; la clase base del acceso a datos lo hace al abrir cada "
        "conexión.")
    d.h2("Tablas")
    d.p(f"La base tiene {len(TABLAS_BD)} tablas: siete forman la base de conocimiento y ocho el sistema transaccional "
        "({t:tablas_bd}). Las restricciones del esquema protegen la consistencia del conocimiento: la severidad solo "
        "admite Baja, Media, Alta o Crítica; el factor de certeza debe ser mayor que 0 y no superar 1; cada nodo del "
        "árbol es una pregunta o una falla, nunca ambas, y el valor de una respuesta es «si» o «no».")
    d.tabla("tablas_bd", "Tablas de la base de datos", ["Grupo", "Tabla", "Contenido"],
            [[g, f"`{t}`", c] for g, t, c in TABLAS_BD], [1.1, 1.45, 3.95], "lll", juntas=False)
    d.h2("Modelo relacional exportado del sistema gestor")
    d.p("El modelo relacional se exportó del propio sistema gestor. Los diagramas se generan leyendo las tablas, las "
        "columnas y las claves foráneas con las instrucciones `PRAGMA table_info` y `PRAGMA foreign_key_list` y se "
        "dibujan con Graphviz {c:graphviz}. La base de conocimiento se muestra en la {f:mr_conocimiento} y el "
        "sistema transaccional, en las figuras {#f:mr_trans1} y {#f:mr_trans2}. El script SQL del esquema, volcado "
        "de la tabla `sqlite_master`, está en el {a:C}, y el modelo en notación textual, en el {a:D}.")
    nota_mr = ("PK = clave primaria; FK = clave foránea; UK = valor único. La pata de gallo marca el lado «muchos» "
               "de la relación y la barra, el lado «uno». Elaboración propia a partir del esquema real de SQLite.")
    diagrama(d, "mr_conocimiento", "Modelo relacional de la base de conocimiento", "modelo_relacional_conocimiento",
             nota_mr, "Modelo relacional de las siete tablas de conocimiento con sus claves y relaciones.")
    diagrama(d, "mr_trans1", "Modelo relacional del sistema transaccional: usuarios, equipos y casos",
             "modelo_relacional_transaccional_1", "Mismos símbolos que en la Figura {#f:mr_conocimiento}. "
             "Elaboración propia.", "Modelo relacional de las tablas rol, usuario, equipo, caso y seguimiento.")
    diagrama(d, "mr_trans2", "Modelo relacional del sistema transaccional: consultas y diagnósticos",
             "modelo_relacional_transaccional_2", "Mismos símbolos que en la Figura {#f:mr_conocimiento}. "
             "Elaboración propia.", "Modelo relacional de las tablas consulta, respuesta y diagnostico.")

    # ======================================================================== carga y gránulos
    d.h1("Carga del conocimiento y consultas de gránulos por hipótesis")
    d.h2("Carga del conocimiento del experto")
    d.p("El conocimiento está en el archivo `data/conocimiento_experto.json`, que tiene cinco bloques: experto, "
        "categorías, síntomas, hipótesis y árbol. El cargador (`src/dao/inicializador.py`) valida que el árbol sea "
        "binario y completo, que no tenga nodos inalcanzables y que cada falla aparezca una sola vez como hoja; "
        "luego inserta los datos en las tablas de conocimiento y genera las reglas recorriendo cada camino del "
        "árbol. La carga se ejecuta con el comando de la {f:carga}; también puede hacerse sin Python, con los "
        "scripts SQL del esquema y de la carga. La {t:registros} resume lo que queda cargado.")
    d.figura_codigo("carga", "Comandos para cargar el conocimiento",
                    "python scripts/crear_bd.py\n\n"
                    "sqlite3 sistema.db < database/schema.sql\n"
                    "sqlite3 sistema.db < database/carga_conocimiento.sql",
                    nota="Los dos últimos comandos son una alternativa al primero. Elaboración propia.")
    d.tabla("registros", "Registros cargados en la base de conocimiento", ["Tabla", "Registros"],
            [[f"`{t}`", str(cuenta[t])] for t in ("experto", "categoria", "sintoma", "hipotesis", "nodo_arbol", "regla",
                                                  "regla_condicion")],
            [2.4, 1.2], "lc",
            nota=f"`nodo_arbol` tiene {n_preg} nodos de pregunta y {n_fallas} hojas. `regla_condicion` guarda las "
                 f"{n_prem} premisas de las {n_reglas} reglas.")
    d.p(f"El bloque del experto es, por ahora, un registro provisional: su nombre es «{datos['experto']['nombre']}» y "
        "su fuente indica que el conocimiento es una propuesta del equipo pendiente de validar. Cuando el experto "
        "humano revise el árbol, el equipo reemplazará ese registro con sus datos reales (nombre, especialidad y "
        "años de experiencia), ajustará en el archivo las fallas, las soluciones y los factores de certeza que él "
        "indique y recargará la base con el mismo procedimiento. El rol Experto de la aplicación también permite "
        "editar las fallas, sus soluciones y el texto de las preguntas sin recargar la base.")

    d.h2("Gránulos de conocimiento")
    d.p("Un gránulo de conocimiento es la unidad mínima que el motor recupera por separado para una hipótesis. Aquí "
        "se compone de cuatro partes: la ficha de la falla, con su categoría, su fuente y su solución; la regla que "
        "la concluye; las premisas de esa regla, y el camino del árbol que lleva a ella. Siete consultas SQL "
        "(G1 a G7) recuperan los gránulos; el archivo `sql/consultas_granulos.sql` las contiene y "
        "`scripts/consultas_granulos.py` las ejecuta para cualquier hipótesis. Se muestran con la falla F17, "
        f"«{next(h['nombre'] for h in hip if h['codigo'] == 'F17').lower()}»; para consultar otra falla basta con "
        "reemplazar el código `'F17'` por el de la hipótesis deseada.")
    g = datos["granulos"]["F17"]
    sql = datos["consultas_sql"]
    d.p("La consulta G1 ({f:g1}) recupera la ficha de la hipótesis y su resultado es la {t:g1}.")
    d.figura_codigo("g1", "Consulta G1: ficha de la hipótesis", ajustar_codigo(sql["G1"]),
                    nota="Para otra falla se cambia `'F17'` por su código. Elaboración propia.")
    ficha(d, "g1", "Resultado de la consulta G1 para la hipótesis F17", g["G1"])
    d.p("La consulta G2 ({f:g2}) devuelve la regla que concluye la hipótesis ({t:g2}).")
    d.figura_codigo("g2", "Consulta G2: regla que concluye la hipótesis", ajustar_codigo(sql["G2"]))
    resultado_de_consulta(d, "g2", "Resultado de la consulta G2 para la hipótesis F17", ["Regla", "Hipótesis",
                          "Factor de certeza"], g["G2"][1], [1.4, 1.4, 1.6], "ccc")
    d.p("La consulta G3 ({f:g3}) lista las premisas de la regla, con el síntoma, la pregunta y el valor esperado, "
        "en el orden del camino ({t:g3}).")
    d.figura_codigo("g3", "Consulta G3: premisas de la regla", ajustar_codigo(sql["G3"]))
    resultado_de_consulta(d, "g3", "Resultado de la consulta G3 para la hipótesis F17",
                          ["Regla", "Orden", "Síntoma", "Pregunta", "Valor"], g["G3"][1],
                          [0.55, 0.55, 0.7, 4.0, 0.7], "ccclc")
    d.p("La consulta G4 ({f:g4}) recorre el árbol desde la hoja hasta la raíz con una expresión de tabla recursiva y "
        "devuelve el camino ordenado de la raíz a la hoja ({t:g4}).")
    d.figura_codigo("g4", "Consulta G4: camino del árbol hasta la hoja", ajustar_codigo(sql["G4"]))
    resultado_de_consulta(d, "g4", "Resultado de la consulta G4 para la hipótesis F17",
                          ["Pasos a la hoja", "Nodo", "Rama desde el padre", "Síntoma"], g["G4"][1],
                          [1.3, 1.1, 1.7, 1.1], "cccc",
                          nota="La raíz no tiene rama de origen, y la hoja no tiene síntoma.")
    d.p("La consulta G7 ({f:g7}) reúne la regla completa en una sola fila, con la forma SI … ENTONCES … ({t:g7}).")
    d.figura_codigo("g7", "Consulta G7: regla completa en una fila", ajustar_codigo(sql["G7"]))
    resultado_de_consulta(d, "g7", "Resultado de la consulta G7 para la hipótesis F17", ["Regla", "Regla textual"],
                          g["G7"][1], [0.8, 5.7], "ll")
    d.p("Las consultas G5 y G6 completan el conjunto: G5 resume el gránulo de cada una de las 31 hipótesis y G6 "
        "indica qué hipótesis comparten un síntoma, lo que sirve para validar el árbol con el experto. Sus "
        "resultados, y los de las consultas por hipótesis para las fallas F05 y F21, están en el {a:E}.")

    # ======================================================================== DFD
    d.h1("Diagrama de flujo de datos del sistema de inferencia")
    d.p("El diagrama de flujo de datos usa la notación de Gane y Sarson {c:gane}: rectángulos para las entidades "
        "externas, rectángulos de esquinas redondeadas para los procesos, rectángulos abiertos para los almacenes "
        "de datos y flechas rotuladas para los flujos. Cubre el sistema de inferencia; el registro de equipos y "
        "casos (P03 y P04) y la administración de usuarios y reportes (P02 y P09) quedan fuera de este diagrama.")
    d.p("El nivel 0 ({f:dfd0}) muestra el sistema como un único proceso que intercambia datos con tres entidades "
        "externas. El cliente entrega sus respuestas de sí o no y recibe las preguntas, el diagnóstico y la "
        "solución. El técnico entrega el seguimiento y la validación del diagnóstico y recibe el caso "
        "diagnosticado. El experto entrega los cambios al conocimiento y recibe el árbol, las reglas y los "
        "gránulos.")
    nota_dfd = ("Notación de Gane y Sarson. Los flujos externos coinciden con los del nivel 1 "
                "(figura siguiente). Elaboración propia.")
    diagrama(d, "dfd0", "Diagrama de flujo de datos, nivel 0 (contexto)", "dfd_nivel_0", nota_dfd,
             "Un proceso central conectado con Cliente, Técnico y Experto mediante flujos de datos.")
    d.p("El nivel 1 ({f:dfd1}) descompone el sistema en seis procesos y tres almacenes de datos. El proceso 1, "
        "gestionar consulta, recibe la respuesta del cliente, la registra en D2 (casos, consultas y respuestas) y "
        "pide al proceso 2 la siguiente pregunta; el proceso 2 obtiene de D1 (base de conocimiento) el nodo hijo "
        "que corresponde a la respuesta. Cuando se alcanza una hoja, el proceso 3 evalúa las reglas de D1 contra "
        "la evidencia de D2 y entrega la regla y su FC al proceso 4, que toma la falla y su solución de D1, emite "
        "el diagnóstico, lo guarda en D3 (diagnósticos y seguimientos) y lo entrega al cliente. El proceso 5, "
        "atender caso, lee el diagnóstico de D3, recibe el seguimiento del técnico y le devuelve el caso "
        "diagnosticado; la confirmación del técnico se guarda también en D3. El proceso 6, mantener conocimiento, "
        "aplica en D1 los cambios del experto y le devuelve el conocimiento vigente.")
    diagrama(d, "dfd1", "Diagrama de flujo de datos, nivel 1, del sistema de inferencia", "dfd_nivel_1_inferencia",
             "D1 = base de conocimiento; D2 = casos, consultas y respuestas; D3 = diagnósticos y seguimientos. "
             "FC = factor de certeza. Elaboración propia.",
             "Seis procesos, tres almacenes y tres entidades externas conectados por flujos de datos.")

    # ======================================================================== roles
    d.h1("Roles")
    d.p("El sistema define cuatro roles; cada usuario tiene exactamente uno, y las cuentas que se registran solas "
        "reciben el rol Cliente. La {t:roles} describe cada rol y los procesos en que participa, y la {t:permisos} "
        "detalla qué puede hacer cada uno. El control se aplica en el servidor, en cada ruta.")
    d.tabla("roles", "Roles del sistema", ["Rol", "Descripción", "Procesos"], [list(r) for r in ROLES],
            [1.2, 3.9, 1.4], "lll")
    d.tabla("permisos", "Matriz de permisos por rol", ["Función", "Cliente", "Técnico", "Experto", "Administrador"],
            [list(p) for p in PERMISOS], [2.9, 0.85, 0.85, 0.85, 1.05], "lcccc",
            nota="● = permitido; ○ = solo lectura. «Propios», «Asignados y en cola» y «Todos» indican qué casos puede ver cada rol.")

    # ======================================================================== casos de uso
    d.h1("Casos de uso de alto nivel")
    d.p("Los casos de uso describen, a alto nivel, lo que cada actor hace con el sistema, con la notación de UML "
        "{c:omg}. La {t:casos_uso} describe cada caso de uso y lo relaciona con su proceso. Los casos de uso se "
        "representan en dos diagramas: el de los actores que atienden el servicio, Cliente y Técnico "
        "({f:cu_cliente_tecnico}), y el de los actores que administran el conocimiento y el sistema, Experto y "
        "Administrador ({f:cu_experto_admin}).")
    d.tabla("casos_uso", "Casos de uso de alto nivel", ["Caso de uso", "Actor", "Descripción", "Proceso"],
            [list(c) for c in CASOS_DE_USO], [1.75, 1.15, 2.95, 0.65], "llll", juntas=False)
    nota_cu = ("Excepto el registro, todos los casos de uso exigen una sesión iniciada y un rol válido. "
               "Elaboración propia con base en UML {c:omg}.")
    diagrama(d, "cu_cliente_tecnico", "Casos de uso de alto nivel de los actores Cliente y Técnico",
             "casos_de_uso_cliente_tecnico", nota_cu + " «include» indica que el caso de origen incluye al otro.",
             "Cinco casos de uso del Cliente y cuatro del Técnico; la consulta incluye inferir el diagnóstico.")
    diagrama(d, "cu_experto_admin", "Casos de uso de alto nivel de los actores Experto y Administrador",
             "casos_de_uso_experto_admin", nota_cu,
             "Cuatro casos de uso del Experto y tres del Administrador.")

    # ======================================================================== clases DAO
    d.h1("Diagrama de clases DAO")
    d.p("El acceso a datos aplica el patrón Data Access Object (DAO), que encapsula todo el acceso a la fuente de "
        "datos detrás de una interfaz propia {c:alur}. Todas las clases DAO heredan de `BaseDAO`, que guarda la "
        "conexión y ofrece tres operaciones SQL protegidas: `_uno`, `_todos` y `_ejecutar`. Cada DAO devuelve "
        "entidades del dominio, que son clases inmutables, y no contiene reglas de negocio, que viven en los "
        "servicios. Los diagramas siguen la notación de clases de UML {c:omg}: los DAO de la base de conocimiento "
        "están en la {f:dao_conocimiento}, los de usuarios y casos en la {f:dao_usuarios_casos} y los de la "
        "consulta, el diagnóstico y el seguimiento en la {f:dao_consulta}.")
    nota_dao = ("La flecha con punta triangular vacía indica herencia; la flecha punteada «crea» indica que el DAO "
                "construye la entidad del dominio. # = miembro protegido; + = miembro público. Elaboración propia.")
    diagrama(d, "dao_conocimiento", "Clases DAO de la base de conocimiento", "clases_dao_conocimiento", nota_dao,
             "BaseDAO y los DAO de categoría, síntoma, hipótesis, nodo del árbol y regla, con sus entidades.")
    diagrama(d, "dao_usuarios_casos", "Clases DAO de usuarios, equipos y casos", "clases_dao_usuarios_casos",
             "Mismos símbolos que en la Figura {#f:dao_conocimiento}. Elaboración propia.",
             "BaseDAO y los DAO de rol, usuario, equipo y caso, con sus entidades.")
    diagrama(d, "dao_consulta", "Clases DAO de la consulta, el diagnóstico y el seguimiento",
             "clases_dao_consulta_diagnostico", "Mismos símbolos que en la Figura {#f:dao_conocimiento}. "
             "Elaboración propia.", "BaseDAO y los DAO de consulta, respuesta, diagnóstico y seguimiento.")

    # ======================================================================== aplicación web
    d.h1("Aplicación web")
    d.h2("Arquitectura")
    d.p("La aplicación sigue una arquitectura en tres capas sobre la base de datos ({f:arquitectura}): presentación, "
        "servicios y acceso a datos {c:sommerville}. La capa de presentación es una aplicación Flask {c:pallets} "
        "con una ruta por función y plantillas Jinja2; en cada petición valida la sesión y el rol, y protege los "
        "formularios con un token CSRF por sesión {c:owasp}. La capa de servicios concentra las reglas de negocio "
        "(`AutenticacionService`, `EquipoService` y `DiagnosticoService`) y el motor de inferencia "
        "(`MotorInferencia`). La capa de acceso a datos son los DAO descritos en la sección anterior.")
    diagrama(d, "arquitectura", "Arquitectura en capas de la aplicación web", "arquitectura",
             "Cada capa se comunica solo con la inmediata. Elaboración propia.",
             "Navegador, presentación Flask, servicios, acceso a datos con DAO y base de datos SQLite.")
    d.h2("Instalación y ejecución")
    d.p("La aplicación requiere Python 3.10 o superior (se probó con la versión 3.13) {c:python} y el paquete Flask. "
        "Los pasos de la {f:instalacion} instalan las dependencias, crean la base con el conocimiento y las cuentas de "
        "demostración, inician el servidor, que atiende en `http://127.0.0.1:5000`, y ejecutan las pruebas.")
    d.figura_codigo("instalacion", "Comandos de instalación, ejecución y prueba",
                    "pip install -r requirements.txt\n"
                    "python scripts/crear_bd.py\n"
                    "python app.py\n"
                    "python -m unittest discover -s tests -v",
                    nota="Se ejecutan desde la carpeta raíz del proyecto. Elaboración propia.")
    d.h2("Cuentas de demostración")
    d.p("Para probar el sistema se crean cuatro cuentas, una por rol ({t:cuentas}). Son solo de demostración y deben "
        "cambiarse o eliminarse antes de cualquier uso real; la aplicación permite cambiar la contraseña desde la "
        "cuenta de cada usuario. Para un uso real también se debe definir la variable de entorno `SECRET_KEY`; si "
        "no existe, la aplicación genera una clave aleatoria cada vez que inicia y las sesiones abiertas se pierden.")
    d.tabla("cuentas", "Cuentas de demostración", ["Rol", "Correo", "Contraseña"],
            [["Administrador", "admin@sistemaexperto.local", "`Admin123*`"],
             ["Experto", "experto@sistemaexperto.local", "`Experto123*`"],
             ["Técnico", "tecnico@sistemaexperto.local", "`Tecnico123*`"],
             ["Cliente", "cliente@sistemaexperto.local", "`Cliente123*`"]], [1.4, 3.1, 2.0], "lll")
    d.h2("Pruebas automatizadas")
    d.p("El proyecto incluye 27 pruebas con el módulo `unittest` {c:python}: 15 sobre el conocimiento, el motor y los "
        "procesos del servicio, y 12 sobre las rutas web. Verifican, entre otros aspectos, que el árbol tenga al "
        "menos 25 ramas y una regla por hoja, que cada camino dispare exactamente su regla y ninguna otra, que la "
        "carga rechace un árbol con una falla sin hoja, el flujo completo desde la apertura del caso hasta su "
        "resolución, la asignación exclusiva del técnico, el control de acceso por rol, la protección CSRF, el "
        "cambio de contraseña y el rechazo de redirecciones a sitios externos. En la última ejecución las 27 "
        "pruebas pasaron.")
    d.h2("Código fuente")
    d.p(f"El código fuente se entrega comprimido junto con este manual y está disponible en el repositorio del "
        f"proyecto ({REPOSITORIO}). La {{t:carpetas}} resume su estructura.")
    d.tabla("carpetas", "Estructura del código fuente", ["Carpeta o archivo", "Contenido"],
            [list(c) for c in CARPETAS], [1.7, 4.8], "ll")
    d.h2("Pantallas de la aplicación")
    d.p("Las capturas de pantalla de la aplicación en ejecución, tomadas con datos de demostración, están en el "
        "{a:F}; muestran las pantallas principales de cada uno de los cuatro roles.")

    # ======================================================================== referencias
    d.referencias()

    # ======================================================================== apéndices
    d.apendice("A", "Preguntas del árbol de decisión")
    d.p("La {t:preguntas} reúne el texto completo de las 30 preguntas del árbol, tal como se presentan al usuario.")
    d.tabla("preguntas", "Preguntas (síntomas) del árbol de decisión", ["Código", "Pregunta presentada al usuario"],
            [[s["codigo"], s["pregunta"]] for s in sint], [0.75, 5.75], "ll", juntas=False, tam=9)

    d.apendice("B", "Fallas con su factor de certeza y su solución recomendada")
    d.p("La {t:soluciones} lista, por cada falla, su severidad, su factor de certeza y la solución que el sistema "
        "recomienda. Es el contenido que el experto humano debe revisar y validar.")
    d.tabla("soluciones", "Fallas, factores de certeza y soluciones recomendadas",
            ["Falla", "Nombre", "Sev.", "FC", "Solución recomendada"],
            [[h["codigo"], h["nombre"], h["severidad"], decimal(h["factor_certeza"]), h["solucion"]] for h in hip],
            [0.5, 1.6, 0.6, 0.4, 3.4], "llccl", juntas=False, tam=9,
            nota="Sev. = severidad; FC = factor de certeza.")

    d.apendice("C", "Script SQL del esquema exportado del sistema gestor")
    d.p("La {f:ddl} es el volcado del esquema que hace el sistema gestor a partir de la tabla `sqlite_master` "
        "(archivo `database/modelo_relacional.sql`). Las líneas largas se dividieron para ajustarlas a la página.")
    d.figura_codigo("ddl", "Script SQL del esquema de la base de datos",
                    ajustar_codigo((RAIZ / "database" / "modelo_relacional.sql").read_text(encoding="utf-8")),
                    juntas=False)

    d.apendice("D", "Modelo relacional en notación textual")
    d.p("La {f:mr_texto} presenta el mismo modelo en notación textual (archivo `docs/salidas/modelo_relacional.txt`).")
    d.figura_codigo("mr_texto", "Modelo relacional en notación textual",
                    ajustar_codigo((RAIZ / "docs" / "salidas" / "modelo_relacional.txt").read_text(encoding="utf-8")),
                    juntas=False)

    d.apendice("E", "Consultas de gránulos de conocimiento: resumen y otras hipótesis")
    d.p("La consulta G5 resume el gránulo de cada hipótesis; su resultado está en la {t:g5}. La consulta G6 busca "
        "las hipótesis que comparten un síntoma, en este caso S01; su resultado está en la {t:g6}. Para las fallas "
        "F05 y F21 se muestran los resultados de las consultas G1, G3, G4 y G7, definidas en la sección Gránulos de "
        "conocimiento: las tablas {#t:g1_f05}, {#t:g3_f05}, {#t:g4_f05} y {#t:g7_f05} corresponden a F05, y las "
        "tablas {#t:g1_f21}, {#t:g3_f21}, {#t:g4_f21} y {#t:g7_f21}, a F21.")
    d.tabla("g5", "Resultado de la consulta G5: gránulos de las 31 hipótesis",
            ["Hipótesis", "Nombre", "Regla", "Premisas"], [[celda(v) for v in f] for f in datos["general"]["G5"][1]],
            [0.8, 4.2, 0.7, 0.8], "llcc", juntas=False, tam=9)
    d.tabla("g6", "Resultado de la consulta G6: hipótesis que usan el síntoma S01",
            ["Síntoma", "Valor", "Cantidad", "Hipótesis"],
            [[celda(v) for v in f] for f in datos["general"]["G6"][1]], [0.8, 0.6, 0.9, 4.2], "cccl",
            nota="Valor = respuesta (sí o no) que la regla exige para el síntoma. Cantidad = número de hipótesis cuya "
                 "regla usa el síntoma con ese valor.", tam=9)
    # Las tablas de los apéndices se componen a 9 pt (como A1 y B1) para que ninguna quede sola en una página.
    for codigo in ("F05", "F21"):
        g = datos["granulos"][codigo]
        c = codigo.lower()
        ficha(d, f"g1_{c}", f"Resultado de la consulta G1 para la hipótesis {codigo}", g["G1"], tam=9)
        resultado_de_consulta(d, f"g3_{c}", f"Resultado de la consulta G3 para la hipótesis {codigo}",
                              ["Regla", "Orden", "Síntoma", "Pregunta", "Valor"], g["G3"][1],
                              [0.55, 0.55, 0.7, 4.0, 0.7], "ccclc", tam=9)
        resultado_de_consulta(d, f"g4_{c}", f"Resultado de la consulta G4 para la hipótesis {codigo}",
                              ["Pasos a la hoja", "Nodo", "Rama desde el padre", "Síntoma"], g["G4"][1],
                              [1.3, 1.1, 1.7, 1.1], "cccc", tam=9)
        resultado_de_consulta(d, f"g7_{c}", f"Resultado de la consulta G7 para la hipótesis {codigo}",
                              ["Regla", "Regla textual"], g["G7"][1], [0.8, 5.7], "ll", tam=9)

    d.apendice("F", "Capturas de pantalla de la aplicación")
    d.p("Las capturas se tomaron con la aplicación en ejecución y datos de demostración. Del cliente se muestran el "
        "ingreso ({f:cap01}), sus equipos ({f:cap02}), la consulta guiada ({f:cap03}) y el diagnóstico emitido "
        "({f:cap04}); del técnico, la cola de casos ({f:cap05}) y el caso resuelto ({f:cap06}); del experto, la "
        "lista de fallas ({f:cap07}) y el gránulo de conocimiento de una falla ({f:cap08}), y del administrador, "
        "los usuarios ({f:cap09}) y los reportes ({f:cap10}).")
    for archivo, clave, titulo, nota in CAPTURAS_APP:
        ruta = CAPTURAS / f"{archivo}.png"
        with Image.open(ruta) as imagen:
            ancho_px, alto_px = imagen.size
        d.figura(clave, titulo, ruta, (6.5, 6.5 * alto_px / ancho_px), nota,
                 f"Captura de pantalla de la aplicación: {titulo.lower()}.")
    return d
