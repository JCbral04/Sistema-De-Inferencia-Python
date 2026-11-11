"""Documento de formulación del proyecto (trabajo estudiantil en formato APA 7)."""
from __future__ import annotations

from apa7 import DocumentoAPA
from documentos_comun import AUTORES, REFERENCIAS, TITULO_PROYECTO, lineas_de_portada

TITULO = f"Formulación del proyecto: {TITULO_PROYECTO}"


def construir(previo: dict, datos: dict) -> DocumentoAPA:
    n_preguntas, n_fallas = datos["n_preguntas"], datos["n_fallas"]
    d = DocumentoAPA(REFERENCIAS, previo, titulo=TITULO, autores=AUTORES,
                     asunto="Sistemas expertos: documento de formulación del proyecto")
    d.portada(TITULO, AUTORES, lineas_de_portada())

    # ---------------------------------------------------------------- introducción (sin encabezado)
    d.titulo_inicial(TITULO)
    d.p("Los computadores de escritorio y portátiles son herramientas de trabajo y de estudio de uso diario. "
        "Cuando fallan, el usuario rara vez sabe si el origen está en la energía, la memoria, el almacenamiento, "
        "el sistema operativo, la red o un periférico. Este documento formula un proyecto cuyo propósito es "
        "orientar ese diagnóstico inicial con un sistema experto web. Presenta el planteamiento del problema, el "
        "objetivo general y los objetivos específicos, cuatro de proyecto y dos de negocio.")
    d.p("Un sistema experto es un programa que reproduce el razonamiento de un especialista en un dominio acotado "
        "a partir de conocimiento representado de forma explícita, por lo general como reglas {c:giarratano}. "
        f"El conocimiento del proyecto es un árbol de decisión de {n_preguntas} preguntas de sí o no y {n_fallas} fallas, "
        f"del que se derivan {datos['n_reglas']} reglas SI-ENTONCES. Esa base es una propuesta elaborada por el equipo a partir "
        "de procedimientos habituales de diagnóstico de hardware y software; queda pendiente validarla con un "
        "técnico experto, que además deberá quedar registrado como fuente del conocimiento.")

    # ---------------------------------------------------------------- planteamiento del problema
    d.h1("Planteamiento del problema")
    d.h2("Descripción del problema")
    d.p("Cuando un computador falla, el usuario común no puede distinguir si el origen del problema está en el "
        "suministro eléctrico, la memoria, el disco, el sistema operativo, la red o un periférico. Esa "
        "incertidumbre lleva a visitas técnicas innecesarias, reparaciones por ensayo y error, pérdida de "
        "información por apagados o reinicios repetidos y tiempo de inactividad que podría evitarse.")
    d.p("En los servicios de soporte técnico, el diagnóstico inicial depende de la experiencia de pocas personas. "
        "Cada técnico aplica su propio criterio, no queda registro de las preguntas que hizo ni de la falla que "
        "sospechó, y lo que sabe el técnico más experimentado no se transmite a quien recién ingresa. Además, el "
        "cliente no cuenta con un canal ordenado para reportar el problema: describe los síntomas de forma "
        "incompleta y el técnico debe repetir el interrogatorio al recibir el equipo.")
    d.p("Estas dificultades se concretan en cuatro problemas. Primero, el diagnóstico inicial es subjetivo y "
        "varía de un técnico a otro. Segundo, el conocimiento del experto está en su memoria y no en un medio que "
        "pueda reutilizarse, revisarse o corregirse. Tercero, no existe trazabilidad entre lo que el cliente "
        "reportó, la falla sospechada y la solución aplicada. Cuarto, no se mide cuántas veces acertó el "
        "diagnóstico inicial, de modo que no hay forma de mejorarlo.")

    d.h2("Formulación del problema")
    d.p("A partir de lo anterior, la pregunta que guía el proyecto es la siguiente: ¿cómo puede un sistema experto "
        "basado en un árbol de decisión y en reglas SI-ENTONCES, construido con el conocimiento de un técnico "
        "experto, orientar de forma consistente el diagnóstico inicial de fallas de computadores de escritorio y "
        "portátiles y registrar el proceso de atención de cada caso?")

    d.h2("Delimitación")
    d.p("El proyecto se limita al diagnóstico inicial de fallas de hardware, software, red y periféricos de "
        "computadores de escritorio y portátiles, mediante preguntas de sí o no que el cliente pueda responder "
        "observando el equipo o con pruebas sencillas, como probar otro cable o otro monitor. El sistema no "
        "repara ni sustituye al técnico: entrega una falla probable, una "
        "solución recomendada y un factor de certeza, y el técnico confirma o rechaza ese diagnóstico.")
    d.p("El factor de certeza es un valor entre 0 y 1 que el experto asigna a cada regla, en la línea del modelo "
        "propuesto para el sistema MYCIN {c:shortliffe}. A diferencia de ese modelo, aquí no se combinan evidencias, "
        "porque las reglas son mutuamente excluyentes y en cada consulta se dispara una sola.")

    # ---------------------------------------------------------------- objetivo general
    d.h1("Objetivo general")
    d.p("Desarrollar un sistema experto web que diagnostique fallas de computadores de escritorio y portátiles "
        "mediante un árbol de decisión y reglas derivadas del conocimiento de un experto humano, y que gestione el "
        "ciclo de atención de los casos desde su apertura hasta su resolución.")

    # ---------------------------------------------------------------- objetivos específicos
    d.h1("Objetivos específicos")
    d.p("Los objetivos específicos se dividen en cuatro de proyecto, que describen lo que se construye, y dos de "
        "negocio, que describen el beneficio esperado para el servicio de soporte. La {t:objetivos} los relaciona "
        "con la evidencia que respalda cada uno.")

    d.h2("Objetivos de proyecto")
    d.numerada([
        f"Adquirir y estructurar el conocimiento de un experto humano en diagnóstico de computadores, "
        f"organizándolo en un árbol de decisión de {n_preguntas} preguntas y {n_fallas} fallas, y en una regla "
        "SI-ENTONCES por cada camino del árbol.",
        "Diseñar e implementar una base de datos relacional que separe la base de conocimiento (hipótesis, "
        "síntomas, árbol y reglas) del sistema transaccional (usuarios, equipos, casos, consultas, diagnósticos y "
        "seguimientos).",
        "Construir un motor de inferencia que conduzca la consulta pregunta por pregunta, evalúe las reglas por "
        "encadenamiento hacia adelante y emita el diagnóstico con su solución recomendada y su factor de certeza.",
        "Desarrollar una aplicación web con roles de cliente, técnico, experto y administrador que implemente los "
        "procesos transaccionales del servicio y se valide con pruebas automatizadas.",
    ])

    d.h2("Objetivos de negocio")
    d.numerada([
        "Reducir el tiempo del diagnóstico inicial y las visitas técnicas innecesarias, estandarizando las "
        "preguntas que se hacen al cliente y entregando al técnico un caso ya orientado hacia una falla probable.",
        "Conservar y mejorar el conocimiento del servicio de soporte, midiendo cuántos diagnósticos confirma o "
        "rechaza el técnico para que el experto ajuste las reglas y los factores de certeza.",
    ])

    d.tabla(
        "objetivos", "Relación entre los objetivos específicos y la evidencia que los respalda",
        ["Objetivo", "Evidencia en el sistema", "Sección del manual técnico"],
        [["Proyecto 1", f"Árbol de {n_preguntas} preguntas y {n_fallas} fallas; {datos['n_reglas']} reglas, una por camino",
          "Árbol de decisión; Reglas del sistema experto"],
         ["Proyecto 2", f"{len(datos['tablas_bd'])} tablas: siete de conocimiento y ocho transaccionales, con claves foráneas "
                        "y restricciones",
          "Base de datos del conocimiento y del sistema transaccional"],
         ["Proyecto 3", "Motor con navegación del árbol y encadenamiento hacia adelante, probado camino por camino",
          "Reglas del sistema experto; Diagrama de flujo de datos del sistema de inferencia"],
         ["Proyecto 4", "Aplicación con cuatro roles y 27 pruebas automatizadas",
          "Roles; Aplicación web"],
         ["Negocio 1", "Fecha de inicio y fin de cada consulta y número de preguntas respondidas por caso",
          "Base de datos del conocimiento y del sistema transaccional"],
         ["Negocio 2", "Tasa de confirmación de cada falla, en el reporte del administrador",
          "Requerimientos funcionales; Casos de uso de alto nivel"]],
        [0.95, 3.35, 2.2], "lll",
        nota="Los objetivos de negocio dependen del uso real del sistema; por ahora se dispone de los datos para "
             "medirlos, pero todavía no se han medido.")

    d.referencias()
    return d
