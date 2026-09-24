# -*- coding: utf-8 -*-
"""
Salida a una GPU de un tercero: solo texto enmascarado, y el OID nunca sale.

    python -m NLP.nube --exportar --muestra 300     arma el paquete (sin llamar a ningun modelo)
    python -m NLP.nube --auditar                    revisa el paquete; si falla, lo borra
    python -m NLP.nube --importar RUTA              respuestas.jsonl -> resultados.parquet
    python -m NLP.nube --estado                     que hay en NLP/salidas/nube/

LOS CINCO MODULOS
    enmascarar.py      tapa identidad, numeros, fechas, correos, direcciones y
                       nombres de terceros en el texto de UNA nota
    exportar.py        base clinica -> paquete.jsonl ({"id","prompt"} y nada mas)
                       + mapa_local.parquet (id -> OID, solo en local)
    auditar.py         la compuerta: si una sola linea falla, el paquete se borra
    correr_en_gpu.py   lo UNICO que se copia a la maquina remota. Biblioteca
                       estandar y nada del proyecto
    importar.py        respuestas.jsonl -> resultados.parquet, emparejando en local

El porque de cada decision, el modelo de amenaza y el paso a paso en la GPU:
NLP/docs/NUBE.md.
"""

from NLP import rutas

CARPETA = rutas.NUBE

PAQUETE = "paquete.jsonl"          # sale a la nube
OPCIONES = "opciones.json"         # sale a la nube
MAPA = "mapa_local.parquet"        # NUNCA sale: id -> OID, texto original
LOTE = "lote.json"                 # NUNCA sale: huella del paquete, version, modelo
AUDITORIA = "auditoria.json"       # NUNCA sale: solo conteos
RESPUESTAS = "respuestas.jsonl"    # vuelve de la nube
RESULTADOS = "resultados.parquet"  # el producto, en local
SEGUNDA = "segunda_pasada.txt"     # NUNCA sale: OIDs descartados con evidencia clinica
REVISAR = "revisar.txt"            # NUNCA sale: OIDs descartados dos veces, para una persona

# Las marcas que deja el enmascarado. Las usan tambien la auditoria (para no
# confundir una marca con un resto) y la importacion (para quitarlas si el
# modelo las copia a su respuesta).
MARCAS = ("[DOC]", "[NOMBRE]", "[NUM]", "[FECHA]", "[CORREO]", "[URL]", "[LUGAR]")
