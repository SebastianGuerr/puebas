# Paquete NLP — limpieza y correccion del texto de triage

Este paquete cubre las fases 1 a 3 del pipeline: toma la columna `HCTMOTCON` de
la tabla de triage y devuelve un texto limpio, corregido y normalizado. Al final
aplica una depuracion que saca del CSV las notas que no dicen nada del paciente.
La extraccion estructurada y los embeddings viven en `embedding/`, y el
planteamiento completo de las ocho fases esta en
[docs/planteamiento.md](docs/planteamiento.md).

## Como se ejecuta

Todo se corre **desde la raiz del repositorio** con `python -m`, no entrando a la
carpeta. El paquete usa imports absolutos (`from NLP.nucleo import reglas`), asi
que ejecutar un archivo suelto (`python NLP/recursos/lexico.py`) falla con
`ModuleNotFoundError`: es el precio de que las carpetas signifiquen algo.

```bash
# de la base de datos a NLP/salidas/triage_limpio.csv, ya depurado.
# Lo que queda fuera va a salidas/notas_descartadas.csv con su motivo.
python -m NLP.procesar

# recursos: se construyen una vez y se reutilizan en cada corrida
python -m NLP.recursos.extraer_cie10    # PDF del CIE-10  -> datos/lexico_externo.txt
python -m NLP.recursos.lexico           # lexico clinico  -> salidas/lexico_clinico.json
python -m NLP.recursos.casing           # capitalizacion  -> salidas/lexico_casing.json
python -m NLP.recursos.detectar_siglas  # que falta en el diccionario
python -m NLP.reduccion.frases          # clasificador de tramos del embedding

# medicion
python -m NLP.evaluacion.auditoria      # que cambio el pipeline y donde
python -m NLP.evaluacion.escaneo        # que problemas trae el corpus
python -m NLP.evaluacion.referencia     # mide contra las correcciones a mano

# fase 4
python -m embedding.estructurar
```

El orden importa la primera vez: `extraer_cie10` alimenta a `lexico`, y `lexico`
y `casing` tienen que existir antes de `procesar`. Despues de eso solo se
regeneran cuando cambia un diccionario.

## Las tres columnas de `triage_limpio.csv`

Son tres textos con tres propositos, y por eso viajan los tres:

| columna | que es | para que |
| --- | --- | --- |
| `texto_original` | la nota tal como se digito | trazabilidad; no se toca nunca |
| `texto_normalizado` | corregida, con siglas y coloquialismos anotados | leer un caso, auditar una decision |
| `texto_embedding` | solo el motivo de consulta | lo que consume el modelo |

La diferencia entre las dos ultimas no es de limpieza sino de proposito:

```text
original    TENGO FIEBRE HACE 3 DIAS
normalizado tengo fiebre hace 3 dias
embedding   tengo fiebre
```

El objetivo del proyecto es cruzar motivos de consulta con factores externos, no
diagnosticar. Para eso 'hace 3 dias' es precision que no se usa y que separa dos
notas que dicen lo mismo. Para revisar un caso concreto, en cambio, hace falta.

## El mapa

```text
                      nucleo/            (lo usan todas las fases)
                         |
    datos/  ------------ + ------------  salidas/
  (a mano)               |               (generado)
                      recursos/          lexicos contra los que se decide
                         |               que NO se corrige
                         v
  fase1_limpieza  ->  fase2_ortografia  ->  fase3_normalizacion
       forma            palabra                 concepto
                         |                          |
                         v                          v
                     evaluacion/               depuracion/
                 mide, no corrige nada    descarta lo que no dice nada
```

### `nucleo/` — transversal

Lo que no pertenece a ninguna fase porque lo consumen todas.

| archivo | que aporta |
| --- | --- |
| `morfologia.py` | que forma tiene una palabra y que significa esa forma. Sin diccionario, sin corpus, sin spaCy. |
| `linguistica.py` | spaCy: vocabulario amplio del espanol y entidades nombradas. |
| `clinico.py` | spaCy + medspaCy cargados una sola vez y compartidos. |
| `reglas.py` | que tokens NO se tocan nunca: numeros, siglas, entidades, patrones. |
| `lt_compat.py` | diferencias de API entre versiones de LanguageTool. |
| `conexion_bd.py` | el engine de SQLAlchemy contra DWSES. |

### `recursos/` — el vocabulario contra el que se decide

No corrigen texto: construyen y cargan las fuentes que el corrector consulta.

| archivo | produce |
| --- | --- |
| `extraer_cie10.py` | `datos/lexico_externo.txt` desde el PDF del CIE-10-ES |
| `lexico.py` | `salidas/lexico_clinico.json`, 32.310 formas de cuatro fuentes |
| `casing.py` | `salidas/lexico_casing.json`, la capitalizacion aprendida del corpus |
| `detectar_siglas.py` | `salidas/siglas_detectadas.csv`, lo que el diccionario aun no cubre |
| `ambiguedad.py` | control de que una entrada de diccionario no se aplique a ciegas |

### Las fases

| carpeta | que cambia | que NO cambia |
| --- | --- | --- |
| `fase1_limpieza/` | mayusculas, espacios, saltos, simbolos | ninguna palabra |
| `fase2_ortografia/` | palabras mal escritas | la terminologia clinica, que se enmascara antes |
| `fase3_normalizacion/` | coloquialismos y siglas a terminologia | lo que dice la nota |
| `depuracion/` | que notas salen del CSV | el texto de las que se quedan |
| `reduccion/` | cuanto texto ve el modelo | `texto_normalizado`, que queda entero al lado |

Dentro de `reduccion/`, `reduccion.py` quita lo que sobra con patrones enumerados
y `frases.py` cubre lo que ellos no ven: clasifica cada tramo de la nota como
del paciente o del servicio, con un codificador clinico congelado y una
regresion logistica encima. Se entrena con `python -m NLP.reduccion.frases`, que
etiqueta el corpus usando las propias reglas como etiquetador debil y escribe
`datos/frases_etiquetadas.csv`. Ese archivo se corrige a mano: es como se mejora
el clasificador sin tocar codigo.

Dentro de `fase2_ortografia/`, `ortografia.py` solo orquesta. El trabajo esta
repartido: `pesos.py` decide cuanto hay que proteger cada palabra,
`enmascarado.py` aparta lo clinico antes de que lo vea LanguageTool,
`candidatos.py` y `sugerencias.py` eligen el reemplazo, `vocabulario.py` cubre
con SymSpell los typos que LanguageTool no propone, `contexto.py` juzga si la
palabra tiene sentido donde esta, y `terminologia.py` con `alarmas.py` vetan y
registran lo que no se hizo.

### `depuracion/` — qué notas no aportan nada

Decide si una nota tiene contenido clínico o es una plantilla en blanco, trámite
puro o un fragmento suelto, y **siempre devuelve el motivo**. Va la última a
propósito: aplicado antes de la normalización, el mismo criterio descarta notas
que sí dicen algo, solo porque el diccionario todavía no las sabía traducir.
Revisar los descartes es la forma de encontrar el siguiente hueco de vocabulario.

### `evaluacion/` — la vara

No modifica texto. `auditoria.py` mide que cambio el pipeline en las tres fases,
`escaneo.py` clasifica que problemas trae el corpus y muestrea de forma
estratificada, y `referencia.py` compara la salida contra las correcciones
hechas a mano en `datos/referencia_correcciones.json`.

## `datos/` y `salidas/`: la regla que decide donde va un archivo

**Si un script del proyecto lo puede volver a crear, va en `salidas/`.** Esa
carpeta esta ignorada por git entera; se puede borrar sin perder nada y se
reconstruye corriendo el script que la escribe.

`datos/` es lo contrario: se edita a mano, se versiona, y si se borra se pierde
trabajo humano. Ahi viven los dos diccionarios, el vocabulario del CIE-10 y las
correcciones de referencia.

Las rutas concretas no se escriben en los modulos: estan todas en
[rutas.py](rutas.py), que es el unico archivo que sabe donde vive cada cosa.
Para mover un archivo de sitio se edita ahi y nada mas.
