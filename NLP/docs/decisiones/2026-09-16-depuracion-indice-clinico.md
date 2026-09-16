# Índice de evidencia clínica y reconocimiento de apartados en depuración

Fecha: 2026-09-16. Ítem: E1.5 (migración de documentación desde el código). Módulo:
`depuracion/depuracion.py`. Autor: sesión de ejecución (agente de documentación).

Este documento reúne tres decisiones medidas que vivían como comentarios con cifras
dentro del código (contrario a la guía de estilo, `ARQUITECTURA.md` §6.3) y se trasladan
aquí sin cambiar lo que afirman.

## 1. Comparar por raíz morfológica, no por igualdad exacta, contra el léxico

### Pregunta

`depuracion.es_clinica()` necesita decidir si una palabra de la nota es evidencia de
contenido clínico. El léxico curado (`recursos/lexico.py`) existe y ya tiene las formas
base de la terminología: ¿basta con consultarlo por igualdad exacta?

### Opciones consideradas

1. Igualdad exacta contra `lexico.contiene()` (la interfaz que ya expone el léxico).
2. Indexar la raíz morfológica de cada término curado (mismo `SnowballStemmer` que usa
   `embedding/extraccion.py`) y comparar raíz contra raíz.

### Medición

El léxico clínico se construye para el corrector ortográfico: guarda formas base y
descarta las palabras de menos de cuatro letras (a dos ediciones de una palabra de tres
letras hay medio diccionario — decisión correcta para corregir, no para juzgar contenido).
Consultarlo por igualdad exacta descartaba:

| Caso | Notas | Por qué fallaba |
|---|---|---|
| dicen "tos" | 136 | no entra por tener 3 letras |
| dicen "tengo colicos" | 23 | el léxico tiene "colico", no el plural |
| dicen "convulsiono" | 17 | el léxico tiene "convulsion", no la forma verbal |
| dicen "esta vomitando" | 8 | el léxico tiene "vomito", no el gerundio |

Las cuatro son motivos de consulta perfectamente claros. El problema no es el léxico:
preguntarle por igualdad responde "está escrita así en el CIE-10", y lo que hace falta
saber aquí es "habla de algo clínico".

### Decisión y motivo

Se indexa la raíz morfológica de cada término curado (`cargar()`, con
`nltk.stem.SnowballStemmer("spanish")` si está instalado). "vomitando" y "vomito"
comparten la raíz "vomit", y una sola entrada cubre la familia entera sin enumerar
conjugaciones. El catálogo de síntomas se lee además por separado y sin el mínimo de
longitud, porque es la fuente que declara que "tos" es un síntoma.

**El riesgo de la raíz, y cómo se acota**: truncar aumenta las coincidencias, también las
falsas — "consulta" y "consultar" comparten raíz, y "consulta" está en el CIE-10. Por eso
las raíces de trámite y de anatomía (`PALABRAS_TRAMITE`, `PALABRAS_ANATOMIA`) se restan
del índice al **construirlo**, no al consultarlo: si una raíz es ambigua entre las dos
poblaciones, no cuenta como evidencia clínica. `LONGITUD_MINIMA_RAIZ = 3` porque por
debajo truncar deja de discriminar.

### Qué la invalidaría

Que el stemmer de NLTK cambie de versión y deje de compartir raíz en casos como
"vomitando"/"vomito" (no medido tras una actualización), o que una auditoría de
`notas_descartadas.csv` muestre raíces ambiguas nuevas que las listas de exclusión no
cubran.

## 2. Reconocer un apartado sin los dos puntos a partir de cierta longitud de rótulo

### Pregunta

`sin_apartados_no_clinicos()` necesita saber dónde termina un apartado ("ap:", "aa:"...)
para no perder el motivo de consulta que sigue. Un apartado termina donde empieza el
siguiente. ¿Basta con detectar el siguiente rótulo por los dos puntos?

### Opciones consideradas

1. Exigir siempre los dos puntos para reconocer el arranque de un apartado.
2. Reconocer también rótulos sin dos puntos, a partir de una longitud mínima del rótulo.

### Medición

El corpus escribe muchísimas veces notas con esta forma, con el último rótulo **sin** dos
puntos:

    'ap: niega; aa: niega; motivo de consulta hace 10 dias me cai'

Con la opción 1, el apartado de alérgicos se extiende hasta el final y se traga el motivo
de consulta. Medido: **287 notas** con un motivo perfectamente legible se descartaban así.

Lo contrario tampoco vale: aceptar cualquier rótulo sin dos puntos haría que "af" o "ax"
cortaran dentro de una palabra corriente.

### Decisión y motivo

Se adopta un corte por longitud: `LONGITUD_ROTULO_SIN_DOSPUNTOS = 8`. Los rótulos largos
("motivo de consulta", 8+ caracteres) se reconocen sueltos, sin exigir los dos puntos; los
cortos ("ap", "aa", "mc") siguen exigiéndolos. Un rótulo de tres palabras no aparece por
casualidad dentro de una nota; uno de dos letras sí.

### Qué la invalidaría

Un rótulo largo nuevo en `nucleo/clinico.SECCIONES` que coincida por casualidad con una
frase corriente de más de 8 caracteres, o una medición posterior que muestre notas donde
el corte por longitud sigue tragándose texto clínico.

## 3. Quitar la expansión del rótulo de apartado antes de juzgar la nota

### Pregunta

La fase 3 (`normalizacion.py`) expande el rótulo de un apartado, por ejemplo "ap:" pasa a
"ap (antecedentes personales):". Esa expansión es terminología clínica de pleno derecho
("antecedentes", "alérgicos", "patológicos"). `depuracion.py` recibe el texto ya expandido:
¿debe juzgar la nota tal cual llega, o quitar antes esa expansión?

### Medición

Sin quitarla, las **296 notas** que dicen exactamente

    'ap (antecedentes personales): niega; aa (antecedentes alergicos): niega'

contaban como notas con contenido clínico, por la expansión del rótulo. Y son justo lo
contrario: una plantilla contestada en blanco, sin una sola palabra sobre el paciente. El
rótulo del formulario lo escribió el formulario, no quien atendió.

### Decisión y motivo

`RE_ENCABEZADO` quita el encabezado del formulario **con su expansión** entre paréntesis
antes de que `con_contenido()` cuente palabras. `sin_encabezados()` se aplica siempre,
antes de cualquier juicio sobre la nota.

### Qué la invalidaría

Que la fase 3 cambie el formato de expansión (otro separador, sin paréntesis) sin
actualizar `RE_ENCABEZADO`, o una auditoría que muestre plantillas en blanco coladas como
`util=True` por una expansión con un formato no cubierto por la expresión regular.
