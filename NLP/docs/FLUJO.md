# Flujo de procesamiento del dato

Cómo viaja una nota de triage desde la base de datos hasta `triage_limpio.csv`.

## La pregunta que resuelve esta carpeta

`DIM_TRIAGE.HCTMOTCON` guarda lo que el auxiliar de triage escribió a toda prisa
mientras el paciente hablaba. Trae, mezclado en un solo campo:

- la dolencia real del paciente, casi siempre en habla popular caldense;
- erratas de digitación y abreviaturas del hospital;
- texto administrativo: EPS, remisiones, acompañantes, signos vitales normales;
- nombre, edad, procedencia y ocupación del paciente.

Lo único que sirve para contar y agrupar consultas es el motivo. El resto es
ruido, y una parte es dato identificable que no debe viajar aguas abajo.

**La salida de esta carpeta es una línea por nota con el motivo de consulta
estandarizado, y nada más.**

## El flujo, de punta a punta

```
        SQL Server · DIM_TRIAGE.HCTMOTCON
                      │
                      │  nucleo/conexion_bd.py   abre el engine
                      │  nucleo/datos.py         consulta OID + HCTMOTCON,
                      │                          excluyendo los OID ya escritos
                      ▼
            ┌──────── por cada nota ────────┐
            │                               │
            │   glosario.py                 │   busca en los 4 diccionarios de
            │      │                        │   recursos/ SOLO los términos que
            │      │                        │   aparecen en ESTA nota
            │      ▼                        │
            │   prompt.py::construir()      │   inyecta ese bloque + las 15
            │      │                        │   reglas + la nota cruda
            │      ▼                        │
            │   modelo.py::generar()        │   Ollama · qwen3:8b · temp 0
            │      │                        │
            │      ▼                        │
            │   modelo.py::limpiar()        │   quita <think>, encabezados y
            │                               │   deja UNA línea
            └───────────────┬───────────────┘
                            │
                            │  nucleo/salida.py · EscritorCSV
                            ▼
            salidas/triage_limpio.csv
            OID · texto_original · texto_optimizado
```

## Las cuatro decisiones que explican el diseño

### 1. El glosario se inyecta por nota, nunca entero

`glosario.py` no le pasa al modelo los 455 coloquialismos ni los 1.122
municipios: le pasa solo los que aparecen en la nota que está leyendo.

No es una optimización de tokens, es una corrección de un fallo medido:
**cualquier palabra clínica que aparezca en el prompt acaba saliendo en la
respuesta**, se ponga como ejemplo o como prohibición. Un glosario completo en
el prompt contamina todas las respuestas. Ver [PROMPT.md](PROMPT.md).

El bloque inyectado tiene cinco secciones, y cada una le dice al modelo qué
hacer con lo que encontró:

| Sección | Fuente | Instrucción implícita |
|---|---|---|
| Equivalencias del hospital | `siglas.json` + `coloquialismos.json` | tradúcelo así, no como tú creas |
| Erratas conocidas | `siglas.json` → `correcciones_directas` | lee la nota con esto ya corregido |
| Nombres propios | `siglas.json` → instituciones y geografía | elimínalo, no es una dolencia |
| Lugares de Colombia | `lugares.csv` (DIVIPOLA) | elimínalo, no es una dolencia |
| Terminología clínica | `terminologia_clinica.json` | consérvalo si la nota lo afirma |

### 2. La nota llega al modelo tal como está en la base

No hay fases de limpieza, corrección ortográfica ni normalización previas. El
modelo recibe `HCTMOTCON` sin tocar, y la columna `texto_original` del CSV es
exactamente lo que dice la base.

Eso hace el resultado auditable: cualquier fila se puede contrastar contra el
registro de origen sin preguntarse qué le hizo el pipeline por el camino.

La corrección ortográfica no desapareció: la hace el modelo, dentro del prompt
(regla 3), con el contexto clínico de la frase entera delante. Un corrector por
palabra no tiene ese contexto y por eso se equivocaba en las palabras que más
importan — convertía `entumida` en `entubada` y `picadas` en `picaduras`.

### 3. Se escribe nota a nota, no al final

`EscritorCSV` abre, escribe y cierra el archivo en cada nota. Es más lento por
fila y es deliberado: una corrida de horas que se cuelga no puede dejar el disco
vacío. El CSV se puede abrir y revisar mientras el proceso sigue corriendo.

### 4. La reanudación es por OID

Al arrancar, `llaves_escritas()` lee los OID que ya están en el CSV y la
consulta a la base los excluye. Consecuencias prácticas:

- interrumpir con `Ctrl+C` no pierde nada;
- volver a lanzar el comando continúa donde iba, no repite;
- para empezar de cero hay que pedirlo: `--rehacer` aparta el CSV con fecha y
  abre uno nuevo;
- si el CSV tiene columnas de un esquema anterior, se aparta solo.

## Cómo se ejecuta

```bash
python -m NLP.procesar                 # toda la tabla
python -m NLP.procesar --limite 500    # solo 500 notas nuevas
python -m NLP.procesar --modelo qwen3:4b
python -m NLP.procesar --rehacer       # aparta el CSV y empieza de cero
```

Antes de lanzarlo, Ollama tiene que estar respondiendo:

```bash
curl http://127.0.0.1:11434/api/tags
```

En Windows la aplicación de la bandeja arranca el servidor sola al iniciar
sesión; `ollama serve` fallará con «bind: solo se permite un uso de cada
dirección de socket» precisamente porque ya está levantado. Si el comando
arranca antes de que Ollama termine de cargar, `modelo.verificar()` corta la
corrida con el error concreto antes de consultar la base.

**No lanzar dos procesos a la vez.** Los dos escribirían el mismo CSV sin saber
uno del otro, y la exclusión por OID se calcula una sola vez, al arrancar: las
notas saldrían duplicadas.

## Lo que este flujo NO hace

- **No clasifica por tema.** Devuelve el motivo en texto libre estandarizado.
  Agrupar es trabajo de `clustering/`.
- **No decide si una nota se descarta.** Si no hay dolencia, el modelo responde
  `sin motivo clinico` (regla 8) y la fila se escribe igual. Descartar aquí
  borraría al paciente de la cuenta diaria, que es el desenlace del proyecto.
- **No es un predictor.** `texto_optimizado` describe una consulta que ya
  ocurrió; no puede ser entrada de un pronóstico.
