"""Entidades del dominio (una por tabla relevante)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Rol:
    id: int
    nombre: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class Usuario:
    id: int
    nombre: str
    correo: str
    rol: str
    activo: bool
    creado_en: str = ""


@dataclass(frozen=True, slots=True)
class Equipo:
    id: int
    cliente_id: int
    tipo: str
    marca: str
    modelo: str
    serial: str | None
    creado_en: str = ""

    @property
    def etiqueta(self) -> str:
        return f"{self.marca} {self.modelo} ({self.tipo})"


@dataclass(frozen=True, slots=True)
class Caso:
    id: int
    equipo_id: int
    cliente_id: int
    tecnico_id: int | None
    descripcion: str
    estado: str
    abierto_en: str
    cerrado_en: str | None
    equipo: str = ""
    cliente: str = ""
    tecnico: str | None = None


@dataclass(frozen=True, slots=True)
class Categoria:
    id: int
    codigo: str
    nombre: str
    descripcion: str


@dataclass(frozen=True, slots=True)
class Hipotesis:
    id: int
    codigo: str
    nombre: str
    descripcion: str
    categoria_id: int
    categoria: str
    severidad: str
    factor_certeza: float
    solucion: str
    experto: str = ""


@dataclass(frozen=True, slots=True)
class Sintoma:
    id: int
    codigo: str
    pregunta: str


@dataclass(frozen=True, slots=True)
class NodoArbol:
    id: int
    codigo: str
    padre_id: int | None
    rama: str | None
    sintoma_id: int | None
    hipotesis_id: int | None

    @property
    def es_hoja(self) -> bool:
        return self.hipotesis_id is not None


@dataclass(frozen=True, slots=True)
class Condicion:
    sintoma_id: int
    sintoma_codigo: str
    pregunta: str
    valor: str


@dataclass(frozen=True, slots=True)
class Regla:
    id: int
    codigo: str
    hipotesis_id: int
    nodo_hoja_id: int
    factor_certeza: float
    condiciones: tuple[Condicion, ...] = ()

    def texto(self, codigo_hipotesis: str) -> str:
        partes = [f"{c.sintoma_codigo} = {c.valor.upper()}" for c in self.condiciones]
        return f"SI {' Y '.join(partes)} ENTONCES {codigo_hipotesis} (FC {self.factor_certeza:.2f})"


@dataclass(frozen=True, slots=True)
class Consulta:
    id: int
    caso_id: int
    nodo_actual_id: int
    estado: str
    iniciada_en: str
    finalizada_en: str | None


@dataclass(frozen=True, slots=True)
class Respuesta:
    id: int
    consulta_id: int
    nodo_id: int
    sintoma_id: int
    valor: str
    orden: int
    pregunta: str = ""
    sintoma_codigo: str = ""


@dataclass(frozen=True, slots=True)
class Diagnostico:
    id: int
    consulta_id: int
    hipotesis_id: int
    regla_id: int
    factor_certeza: float
    emitido_en: str
    confirmado: bool | None


@dataclass(frozen=True, slots=True)
class Seguimiento:
    id: int
    caso_id: int
    tecnico_id: int
    observacion: str
    accion_realizada: str | None
    registrado_en: str
    tecnico: str = ""
