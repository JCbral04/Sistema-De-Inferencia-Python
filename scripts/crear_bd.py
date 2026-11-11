"""Reconstruye data/sistema_experto.db desde el esquema y el conocimiento del experto."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.dao.inicializador import RUTA_BD, crear_base_datos  # noqa: E402

if __name__ == "__main__":
    crear_base_datos()
    print(f"Base de datos creada en {RUTA_BD}")
