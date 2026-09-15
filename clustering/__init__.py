"""
Fase 7: agrupar los motivos de consulta ya vectorizados.

POR DONDE SE ENTRA
    python -m clustering              agrupa, imprime los temas y abre el mapa
    python -m clustering --barrido    prueba parametros y dice cual conviene
    python -m clustering --validar    pone a prueba que el resultado valga
    python -m clustering --anclar     fija la identidad de los temas (una vez)
    python -m clustering --serie      la serie diaria lista para la fase 8
    python -m clustering --puente     que falta para cruzar con el calendario
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
    validacion.py si lo que sale se distingue de agrupar datos sin estructura,
                 y si se repite al cambiar semilla, dimension o el 20% del
                 corpus. barrido elige entre configuraciones; esto dice si
                 alguna vale.
    anclas.py    la identidad PERMANENTE de cada tema. Es lo que permite que
                 la serie de esta semana se pueda comparar con la de la
                 anterior; sin esto los numeros de tema se renumeran solos.
    fechas.py    el puente a la fase 8: recupera la fecha de cada OID contra
                 DIM_TRIAGE y arma la serie diaria con sus denominadores.
    mapa.py      el dibujo.
    visor.py     el bucle que refresca la ventana con --vivo.

EL ORDEN EN QUE CONVIENE LEERLOS
    corpus.py primero: ahi esta la decision de la que cuelga todo lo demas --
    se agrupan textos distintos y no notas -- y sin eso el resto no se explica.
    Despues agrupar.py, que dice por que UMAP y HDBSCAN y no otra cosa, y
    temas.py, que dice por que hay un segundo nivel en vez de un agrupamiento
    mas flojo.

    Y validacion.py antes de apoyar cualquier decision en las cifras, porque
    ahi esta lo que corrige la forma de leer la coherencia y lo que dice hasta
    donde llega la estabilidad del agrupamiento.

ANTES DE PASAR A LA FASE 8, TRES COSAS QUE HAY QUE SABER
    Salieron de medir, no de suponer, y estan documentadas en anclas.py y
    fechas.py con los numeros:

    1. Los numeros de tema NO son identidades. Se renumeran por tamano en cada
       corrida. Por eso existe anclas.py y por eso --serie se niega a correr sin
       anclas: una serie sobre numeros que se renumeran no mide lo que dice.

    2. La columna que se modela es 'parte', no 'notas'. La fraccion de triages
       con motivo escrito cae unos 9 puntos porcentuales por ano, asi que una
       serie de conteos trae una tendencia a la baja que no es del hospital.

    3. El ciclo semanal domina todo lo demas: de lunes a domingo el volumen cae
       un 34%, y la autocorrelacion a 7 dias es 0,70. El dia de la semana y los
       festivos van en el modelo antes que cualquier variable de clima.

    'python -m clustering --puente' comprueba estas condiciones contra los datos
    de hoy y dice cuales faltan.
"""
