"""
Fase 7: agrupar los motivos de consulta ya vectorizados.

POR DONDE SE ENTRA
    python -m clustering              agrupa, imprime los temas y abre el mapa
    python -m clustering --barrido    prueba parametros y dice cual conviene
    python -m clustering --vivo       deja la ventana llenandose sola

    Es un solo comando y hace la fase entera.

DOS NIVELES, Y EL QUE IMPORTA ES EL DE ARRIBA
    grupo  lo que encuentra HDBSCAN. Especifico y apretado; son mas de cien.
           Sirve para leer el corpus y para auditar.
    tema   los grupos que hablan de lo mismo, juntos. Son unas decenas, y es
           el nivel con el que se cuenta por dia y se cruza contra el clima,
           el calendario y los eventos -- que es el objetivo del proyecto.

    La perilla del nivel de arriba es --umbral (cuanto se tienen que parecer
    dos grupos para ser el mismo tema). Las del de abajo son --tamano-minimo y
    --muestras-minimas, y esas no se eligen a ojo: para eso esta --barrido.

QUE HACE CADA MODULO
    __main__.py  el comando: que se hace y en que orden. Sin calculo dentro.
    rutas.py     donde vive cada archivo. Nada mas.
    corpus.py    la entrada: lee embedding/salidas/ sin tocarlo, y decide
                 que se agrupa (textos distintos, no notas).
    agrupar.py   UMAP + HDBSCAN, los parametros y como se mide una corrida.
    etiquetas.py el nombre de cada cluster y de cada tema, por TF-IDF de clase.
    temas.py     el segundo nivel: fundir los grupos que dicen lo mismo.
    corrida.py   encadena los cinco pasos y escribe salidas/.
    barrido.py   prueba combinaciones de parametros y las mide.
    mapa.py      el dibujo.
    visor.py     el bucle que refresca la ventana con --vivo.

EL ORDEN EN QUE CONVIENE LEERLOS
    corpus.py primero: ahi esta la decision de la que cuelga todo lo demas --
    se agrupan textos distintos y no notas -- y sin eso el resto no se explica.
    Despues agrupar.py, que dice por que UMAP y HDBSCAN y no otra cosa, y
    temas.py, que dice por que hay un segundo nivel en vez de un agrupamiento
    mas flojo.
"""
