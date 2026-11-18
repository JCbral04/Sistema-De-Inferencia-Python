# Sistema experto para el diagnóstico de fallas de computadores

Aplicación web (Flask y SQLite) que orienta el diagnóstico inicial de fallas de computadores de escritorio y
portátiles. El conocimiento se representa como un **árbol de decisión de 30 preguntas y 31 fallas** del que se
derivan **31 reglas SI-ENTONCES** (una por camino de la raíz a una hoja). El sistema incluye los procesos
transaccionales del servicio de soporte con cuatro roles: Cliente, Técnico, Experto y Administrador.

Autores: Juan Cabral y Laura Ruiz. Curso: Sistemas expertos.

> **Estado del conocimiento.** El árbol, las soluciones y los factores de certeza son una propuesta elaborada por
> el equipo; falta validarlos con un técnico experto. Por eso el registro del experto de la base de conocimiento
> figura como «por registrar» (`data/conocimiento_experto.json`, bloque `experto`).

## Qué contiene esta entrega

| Entregable | Dónde está |
|---|---|
| Documento de formulación del proyecto | `docs/entregables/1_Formulacion_del_proyecto.docx` |
| Manual técnico del sistema experto | `docs/entregables/2_Manual_tecnico.docx` |
| Aplicación web (código fuente) | este repositorio |

Los dos documentos siguen el formato de la 7.ª edición de las normas APA. El manual incluye los procesos, los
requerimientos, el árbol de decisión, las reglas, el modelo relacional exportado, la carga del conocimiento y las
consultas de gránulos por hipótesis, el diagrama de flujo de datos, los roles, los casos de uso y el diagrama de
clases DAO.

## Requisitos

- Python 3.10 o superior (probado con 3.13).
- Flask 3.0 o superior (`requirements.txt`). SQLite viene incluido con Python.

## Ejecución

```bash
pip install -r requirements.txt
python scripts/crear_bd.py                    # carga el conocimiento y crea los usuarios de demostración
python app.py                                 # abre http://127.0.0.1:5000
python -m unittest discover -s tests -v       # 55 pruebas automatizadas
```

Cualquier persona puede crear su cuenta desde la pantalla de ingreso («Crear cuenta»); las cuentas nuevas son de
rol Cliente. Usuarios de demostración (cámbielos o elimínelos antes de un uso real; cada usuario puede cambiar su
contraseña desde la aplicación):

| Rol | Correo | Contraseña |
|---|---|---|
| Administrador | admin@sistemaexperto.local | Admin123* |
| Experto | experto@sistemaexperto.local | Experto123* |
| Técnico | tecnico@sistemaexperto.local | Tecnico123* |
| Cliente | cliente@sistemaexperto.local | Cliente123* |

Si la base de datos no existe, `app.py` la crea con el conocimiento y los usuarios de demostración; para usar otro
archivo defina `SISTEMA_EXPERTO_DB`.

Variables de entorno opcionales:

| Variable | Efecto |
|---|---|
| `SECRET_KEY` | Clave que firma la sesión. Si no se define, se genera una vez y se guarda en `data/.clave_secreta` (permisos 0600), así que las sesiones sobreviven a un reinicio. |
| `SESION_MINUTOS` | Minutos de inactividad antes de cerrar la sesión (30 por defecto). |
| `COOKIE_SEGURA` | Con `1`, la cookie de sesión solo viaja por HTTPS; actívela al publicar la aplicación. |
| `ZONA_HORARIA` | Zona en que se muestran las fechas (`America/Bogota` por defecto; la base guarda UTC). |
| `SISTEMA_EXPERTO_DB` | Ruta del archivo SQLite. |

## Acceso seguro

- **Registro:** nombre, correo y contraseña confirmada; el rol Cliente lo asigna el servidor y la sesión se inicia al registrarse.
- **Contraseñas:** de 8 a 128 caracteres, con letras y números, fuera de una lista de contraseñas comunes y distintas del
  correo y del nombre; se guardan solo como hash con sal (Werkzeug).
- **Ingreso:** mismo mensaje y tiempo parecido si el correo no existe; tras 5 intentos fallidos en 15 minutos con el mismo
  correo y origen, el ingreso se bloquea 5 minutos (también hay límites por origen y por registros). El límite vive en la
  memoria del proceso: se reinicia con el servidor y no se comparte entre varios procesos.
- **Sesión:** cookie HttpOnly y SameSite=Lax, caducidad por inactividad, token CSRF en cada formulario y cierre de sesión por POST.
- **Cabeceras:** Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy y `Cache-Control: no-store`.

## Flujo principal

1. El cliente se registra (o ingresa), registra un equipo y, en la pantalla **Consultas**, inicia una consulta: elige el
   equipo y describe el problema; el sistema abre el caso (estado *Abierto*). En esa misma pantalla ve sus **últimas 5
   consultas**, elige una y revisa su diagnóstico, su solución y las respuestas dadas.
2. Responde la consulta con sí o no. El motor navega el árbol y, al llegar a una hoja, evalúa las reglas.
3. Se emite el diagnóstico con su solución y su factor de certeza; el caso pasa a *Diagnosticado*.
4. Un técnico toma el caso (*En atención*), registra seguimiento y lo resuelve (*Resuelto*) indicando si el
   diagnóstico fue correcto.
5. El experto ajusta fallas, soluciones, certezas y preguntas, y puede ver el árbol dibujado (menú *Árbol*); el
   administrador gestiona usuarios y consulta los reportes.

## Estructura

| Ruta | Contenido |
|---|---|
| `app.py` | Punto de entrada de la aplicación web. |
| `src/web/` | Rutas por rol, seguridad (sesión, roles, CSRF, límite de intentos y cabeceras), plantillas y estilos. |
| `src/services/` | Servicios de negocio y motor de inferencia. |
| `src/dao/` | Patrón DAO (acceso a datos) y cargador del conocimiento. |
| `src/domain/` | Entidades del dominio. |
| `data/conocimiento_experto.json` | Conocimiento del experto (fuente editable). |
| `database/` | `schema.sql` (esquema), `modelo_relacional.sql` (volcado exportado de SQLite) y `carga_conocimiento.sql` (carga del conocimiento sin Python). |
| `sql/consultas_granulos.sql` | Consultas de gránulos de conocimiento por hipótesis (G1 a G7). |
| `scripts/` | Creación de la base, consulta de gránulos y herramientas para regenerar diagramas, capturas y documentos. |
| `tests/` | Pruebas del conocimiento, del motor, de los procesos y de las rutas web. |
| `docs/` | Diagramas (PNG y SVG; el árbol de decisión con texto y el modelo relacional completo también en PDF), capturas de pantalla, salidas de las consultas y documentos Word. |

## Conocimiento y consultas de gránulos

Para modificar el conocimiento, edite `data/conocimiento_experto.json` y ejecute `python scripts/crear_bd.py` (borra y
recrea la base). También puede cargarlo sin Python:

```bash
sqlite3 sistema.db < database/schema.sql
sqlite3 sistema.db < database/carga_conocimiento.sql
```

Esa carga incluye solo el conocimiento (experto, categorías, síntomas, fallas, árbol y reglas); los roles y los
usuarios de demostración los crea `scripts/crear_bd.py`.

Para ver el gránulo de conocimiento de una o varias hipótesis (ficha, regla, premisas y camino del árbol):

```bash
python scripts/consultas_granulos.py F05 F17 F21
```

## Regenerar diagramas, capturas y documentos (opcional)

Estas herramientas no forman parte de la aplicación. Necesitan Graphviz (`dot`), matplotlib, Pillow, python-docx,
LibreOffice y poppler (`pdftotext`); las capturas, además, Playwright con Chromium.

```bash
python scripts/crear_bd.py
python scripts/generar_diagramas.py      # diagramas y modelo relacional exportado de la base
python scripts/exportar_carga_sql.py     # database/carga_conocimiento.sql
python scripts/capturas_pantalla.py      # docs/capturas
python scripts/generar_documentos.py     # docs/entregables/*.docx (formato APA 7)
```
