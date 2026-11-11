"""Genera las capturas de pantalla de la aplicación web para el manual técnico.

Arranca el servidor Flask con una base de datos temporal (no toca data/sistema_experto.db), recorre un
escenario completo con Playwright (cliente, técnico, experto y administrador) y guarda las imágenes en
docs/capturas/. No hace parte de la aplicación: es una herramienta opcional.

Requisitos opcionales:  pip install playwright && playwright install chromium
Uso:                    python scripts/capturas_pantalla.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "capturas"
PUERTO = 5077
BASE = f"http://127.0.0.1:{PUERTO}"
VISTA = {"width": 1000, "height": 620}

CUENTAS = {
    "Cliente": ("cliente@sistemaexperto.local", "Cliente123*"),
    "Técnico": ("tecnico@sistemaexperto.local", "Tecnico123*"),
    "Experto": ("experto@sistemaexperto.local", "Experto123*"),
    "Administrador": ("admin@sistemaexperto.local", "Admin123*"),
}
# Recorrido del árbol que concluye F17 (fuente de poder insuficiente): S01 … S18.
RESPUESTAS = ["si", "no", "si", "no", "si", "si", "no", "si"]


def esperar_servidor() -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/login", timeout=1)
            return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError("El servidor no respondió a tiempo")


def entrar(page: Page, rol: str) -> None:
    correo, clave = CUENTAS[rol]
    page.goto(BASE + "/login")
    page.fill("#correo", correo)
    page.fill("#clave", clave)
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")


def salir(page: Page) -> None:
    page.click("header.nav button:has-text('Salir')")
    page.wait_for_load_state("networkidle")


def foto(page: Page, nombre: str, completa: bool = False) -> None:
    ruta = SALIDA / f"{nombre}.png"
    page.screenshot(path=str(ruta), full_page=completa)
    print("ok", ruta.relative_to(RAIZ))


def escenario(page: Page) -> None:
    # Pantalla de ingreso
    page.goto(BASE + "/login")
    foto(page, "01_ingreso")

    # Cliente: equipo, caso y consulta guiada
    entrar(page, "Cliente")
    page.goto(BASE + "/cliente/equipos/nuevo")
    page.select_option("#tipo", "Portátil")
    page.fill("#marca", "Lenovo")
    page.fill("#modelo", "IdeaPad Gaming 3")
    page.fill("#serial", "PF2XK41B")
    page.click("button:has-text('Guardar')")
    page.wait_for_load_state("networkidle")
    foto(page, "02_equipos_del_cliente")

    page.goto(BASE + "/cliente/casos/nuevo")
    page.fill("#descripcion", "El equipo se apaga solo cuando juego o abro programas pesados; "
                              "después de unos minutos vuelve a encender sin problema.")
    page.click("button:has-text('Abrir caso')")
    page.wait_for_load_state("networkidle")
    for i, valor in enumerate(RESPUESTAS):
        if i == 4:
            foto(page, "03_consulta_guiada")
        page.click(f"button[name=valor][value={valor}]")
        page.wait_for_load_state("networkidle")
    foto(page, "04_diagnostico_emitido", completa=True)
    salir(page)

    # Técnico: cola, toma del caso, seguimiento y resolución
    entrar(page, "Técnico")
    page.goto(BASE + "/tecnico/cola")
    foto(page, "05_cola_del_tecnico")
    page.click("button:has-text('Tomar caso')")
    page.wait_for_load_state("networkidle")
    page.fill("#accion", "Prueba de carga y revisión de la fuente de poder")
    page.fill("#obs", "La fuente de 350 W no sostiene la carga de la tarjeta gráfica; el voltaje de 12 V cae al jugar.")
    page.click("button:has-text('Guardar seguimiento')")
    page.wait_for_load_state("networkidle")
    page.fill("#obs2", "Se reemplazó la fuente por una de 550 W certificada. El equipo ya no se apaga bajo carga.")
    page.click("button:has-text('Marcar como resuelto')")
    page.wait_for_load_state("networkidle")
    foto(page, "06_caso_resuelto", completa=True)
    salir(page)

    # Experto: gránulo de conocimiento
    entrar(page, "Experto")
    page.goto(BASE + "/conocimiento/hipotesis")
    foto(page, "07_fallas_del_experto")
    page.click("tr:has-text('F17') a:has-text('Ver gránulo')")
    page.wait_for_load_state("networkidle")
    foto(page, "08_granulo_de_conocimiento", completa=True)
    salir(page)

    # Administrador: usuarios y reportes
    entrar(page, "Administrador")
    page.goto(BASE + "/admin/usuarios")
    foto(page, "09_usuarios_del_administrador")
    page.goto(BASE + "/admin/reportes")
    foto(page, "10_reportes", completa=True)


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        entorno = dict(os.environ, SISTEMA_EXPERTO_DB=str(Path(tmp) / "capturas.db"), SECRET_KEY="capturas")
        servidor = subprocess.Popen(
            [sys.executable, "-m", "flask", "--app", "app", "run", "--port", str(PUERTO)],
            cwd=RAIZ, env=entorno, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            esperar_servidor()
            with sync_playwright() as p:
                navegador = p.chromium.launch()
                contexto = navegador.new_context(viewport=VISTA, device_scale_factor=2, locale="es-CO")
                escenario(contexto.new_page())
                navegador.close()
        finally:
            servidor.terminate()
            servidor.wait(timeout=10)


if __name__ == "__main__":
    main()
