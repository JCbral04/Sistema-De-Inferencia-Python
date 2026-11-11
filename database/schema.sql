-- Esquema del sistema experto de diagnóstico de fallas de computadores (SGBD: SQLite 3)
PRAGMA foreign_keys = ON;

-- ============================================================
-- BASE DE CONOCIMIENTO
-- ============================================================
CREATE TABLE experto (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT    NOT NULL,
    especialidad      TEXT    NOT NULL,
    anios_experiencia INTEGER NOT NULL CHECK (anios_experiencia >= 0),
    fuente            TEXT    NOT NULL
);

CREATE TABLE categoria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL
);

CREATE TABLE hipotesis (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT    NOT NULL UNIQUE,
    nombre         TEXT    NOT NULL,
    descripcion    TEXT    NOT NULL,
    categoria_id   INTEGER NOT NULL REFERENCES categoria(id),
    experto_id     INTEGER NOT NULL REFERENCES experto(id),
    severidad      TEXT    NOT NULL CHECK (severidad IN ('Baja', 'Media', 'Alta', 'Crítica')),
    factor_certeza REAL    NOT NULL CHECK (factor_certeza > 0 AND factor_certeza <= 1),
    solucion       TEXT    NOT NULL
);

CREATE TABLE sintoma (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo   TEXT NOT NULL UNIQUE,
    pregunta TEXT NOT NULL
);

-- Un nodo del árbol hace una pregunta (síntoma) o es una hoja que concluye una hipótesis.
CREATE TABLE nodo_arbol (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT    NOT NULL UNIQUE,
    padre_id    INTEGER REFERENCES nodo_arbol(id),
    rama        TEXT    CHECK (rama IN ('si', 'no')),
    sintoma_id  INTEGER REFERENCES sintoma(id),
    hipotesis_id INTEGER REFERENCES hipotesis(id),
    CHECK ((sintoma_id IS NULL) <> (hipotesis_id IS NULL)),
    CHECK ((padre_id IS NULL) = (rama IS NULL)),
    UNIQUE (padre_id, rama)
);

CREATE TABLE regla (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT    NOT NULL UNIQUE,
    hipotesis_id   INTEGER NOT NULL REFERENCES hipotesis(id),
    nodo_hoja_id   INTEGER NOT NULL UNIQUE REFERENCES nodo_arbol(id),
    factor_certeza REAL    NOT NULL CHECK (factor_certeza > 0 AND factor_certeza <= 1)
);

CREATE TABLE regla_condicion (
    regla_id   INTEGER NOT NULL REFERENCES regla(id) ON DELETE CASCADE,
    orden      INTEGER NOT NULL,
    sintoma_id INTEGER NOT NULL REFERENCES sintoma(id),
    valor      TEXT    NOT NULL CHECK (valor IN ('si', 'no')),
    PRIMARY KEY (regla_id, orden),
    UNIQUE (regla_id, sintoma_id)
);

-- ============================================================
-- SISTEMA TRANSACCIONAL
-- ============================================================
CREATE TABLE rol (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL
);

CREATE TABLE usuario (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre     TEXT    NOT NULL,
    correo     TEXT    NOT NULL UNIQUE,
    clave_hash TEXT    NOT NULL,
    rol_id     INTEGER NOT NULL REFERENCES rol(id),
    activo     INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE equipo (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES usuario(id),
    tipo       TEXT    NOT NULL CHECK (tipo IN ('Escritorio', 'Portátil', 'Todo en uno')),
    marca      TEXT    NOT NULL,
    modelo     TEXT    NOT NULL,
    serial     TEXT,
    creado_en  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE caso (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id   INTEGER NOT NULL REFERENCES equipo(id),
    cliente_id  INTEGER NOT NULL REFERENCES usuario(id),
    tecnico_id  INTEGER REFERENCES usuario(id),
    descripcion TEXT    NOT NULL,
    estado      TEXT    NOT NULL DEFAULT 'Abierto'
                CHECK (estado IN ('Abierto', 'Diagnosticado', 'En atención', 'Resuelto')),
    abierto_en  TEXT    NOT NULL DEFAULT (datetime('now')),
    cerrado_en  TEXT
);

CREATE TABLE consulta (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id        INTEGER NOT NULL REFERENCES caso(id),
    nodo_actual_id INTEGER NOT NULL REFERENCES nodo_arbol(id),
    estado         TEXT    NOT NULL DEFAULT 'En curso' CHECK (estado IN ('En curso', 'Finalizada')),
    iniciada_en    TEXT    NOT NULL DEFAULT (datetime('now')),
    finalizada_en  TEXT
);

CREATE TABLE respuesta (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id   INTEGER NOT NULL REFERENCES consulta(id) ON DELETE CASCADE,
    nodo_id       INTEGER NOT NULL REFERENCES nodo_arbol(id),
    sintoma_id    INTEGER NOT NULL REFERENCES sintoma(id),
    valor         TEXT    NOT NULL CHECK (valor IN ('si', 'no')),
    orden         INTEGER NOT NULL,
    respondida_en TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (consulta_id, orden),
    UNIQUE (consulta_id, sintoma_id)
);

CREATE TABLE diagnostico (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    consulta_id    INTEGER NOT NULL UNIQUE REFERENCES consulta(id),
    hipotesis_id   INTEGER NOT NULL REFERENCES hipotesis(id),
    regla_id       INTEGER NOT NULL REFERENCES regla(id),
    factor_certeza REAL    NOT NULL,
    emitido_en     TEXT    NOT NULL DEFAULT (datetime('now')),
    confirmado     INTEGER CHECK (confirmado IN (0, 1))
);

CREATE TABLE seguimiento (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_id          INTEGER NOT NULL REFERENCES caso(id),
    tecnico_id       INTEGER NOT NULL REFERENCES usuario(id),
    observacion      TEXT    NOT NULL,
    accion_realizada TEXT,
    registrado_en    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_caso_cliente   ON caso(cliente_id);
CREATE INDEX idx_caso_tecnico   ON caso(tecnico_id);
CREATE INDEX idx_caso_estado    ON caso(estado);
CREATE INDEX idx_equipo_cliente ON equipo(cliente_id);
CREATE INDEX idx_respuesta_cons ON respuesta(consulta_id);
CREATE INDEX idx_diag_hipotesis ON diagnostico(hipotesis_id);
