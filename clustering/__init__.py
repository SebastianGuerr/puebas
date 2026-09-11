"""
Fase 7: agrupar los motivos de consulta ya vectorizados.

POR DONDE SE ENTRA
    python -m clustering.visor      abre la ventana con el mapa

QUE HACE CADA MODULO
    rutas.py     donde vive cada archivo. Nada mas.
    corpus.py    la entrada: lee embedding/salidas/ sin tocarlo, y decide
                 que se agrupa (textos distintos, no notas).
    agrupar.py   UMAP + HDBSCAN, y los parametros con que explorar.
    etiquetas.py el nombre de cada cluster, por TF-IDF de clase.
    corrida.py   encadena los cuatro pasos y escribe salidas/.
    mapa.py      el dibujo.
    visor.py     la ventana y la linea de comandos.
"""
