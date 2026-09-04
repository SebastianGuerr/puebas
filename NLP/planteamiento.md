# Propuesta de pipeline NLP para triage clínico

## Fase 1. Limpieza y normalización del lenguaje

### Librería principal: ConTexto

ConTexto es una librería orientada al procesamiento de texto en español que incluye herramientas para limpieza, corrección, normalización, eliminación de palabras irrelevantes y otras tareas de preparación textual.

### ¿Qué hace?

Transforma textos inconsistentes en textos más homogéneos.

### Ejemplo

```text
INGRESA PACIENTE REFIRIENDO QUE TIENE FIEBRE Y GRIPA
```

↓

```text
paciente refiriendo fiebre y gripa
```

### ¿Por qué se usa?

Porque los registros clínicos suelen tener:

- Errores ortográficos
- Abreviaturas
- Mayúsculas inconsistentes
- Información administrativa repetitiva
- Caracteres especiales

Todo esto introduce ruido.

### Objetivo de la fase

Pasar de:

```text
texto desordenado
```

a:

```text
texto limpio y consistente
```

### Resultado esperado

Eliminar aproximadamente:

- Mensajes administrativos
- Texto repetitivo
- Ruido documental

Y conservar únicamente la información clínica relevante.

---

## Fase 2. Comprensión lingüística básica

### Librería principal: spaCy

spaCy es una de las plataformas NLP más utilizadas para tokenización, lematización, análisis gramatical y extracción de entidades. Permite construir pipelines de procesamiento de lenguaje altamente extensibles.

### ¿Qué hace?

Divide y analiza el texto.

### Ejemplo

```text
Tengo dolores en el pecho
```

↓

Identifica:

```json
{
  "verbos": ["tener"],
  "sustantivos": ["dolor", "pecho"]
}
```

### ¿Por qué se usa?

Porque permite:

- Lematización
- Extracción de patrones
- Reconocimiento de entidades

#### Lematización

Convierte:

```text
dolores
doloroso
```

a:

```text
dolor
```

#### Extracción de patrones

Detecta expresiones médicas como:

```text
dolor en pecho
falta de aire
sangrado vaginal
accidente de tránsito
```

#### Reconocimiento de entidades

Detecta:

```text
Marmato
Chinchiná
EMI
Hospital Infantil
```

### Objetivo de la fase

Convertir texto limpio en componentes lingüísticos analizables.

### Resultado esperado

Extraer:

- Síntomas
- Eventos
- Ubicaciones
- Términos clínicos

---

## Fase 3. Estandarización médica

### Librerías principales

- spaCy
- Diccionario clínico propio
- MedSpaCy (posteriormente)

### ¿Qué hace?

Convierte múltiples formas de decir lo mismo en un único concepto.

### Ejemplo

```text
me siento ahogado
```

```text
me falta el aire
```

```text
tengo dificultad respiratoria
```

↓

```text
DISNEA
```

Otro ejemplo:

```text
caida
me cai
se resbalo
cayo de una moto
```

↓

```text
TRAUMA POR CAIDA
```

### ¿Por qué se usa?

Porque el lenguaje humano es extremadamente variable. Los pacientes describen el mismo problema de formas muy diferentes.

### Objetivo de la fase

Crear una taxonomía médica común.

### Resultado esperado

Transformar miles de expresiones diferentes en cientos de conceptos normalizados.

---

## Fase 4. Comprensión semántica

### Librería principal: Sentence Transformers

### ¿Qué hace?

Convierte cada comentario en un vector numérico que representa su significado.

### Ejemplo

```text
Tengo dificultad respiratoria
```

y

```text
Me siento ahogado
```

terminan cercanos matemáticamente.

### ¿Por qué se usa?

Porque las reglas tradicionales no detectan similitud semántica.

#### Método tradicional

```text
ahogado
```

≠

```text
dificultad respiratoria
```

#### Sentence Transformers

Entiende que ambos conceptos son similares.

### Objetivo de la fase

Capturar significado clínico.

### Resultado esperado

Representar todos los motivos de consulta mediante vectores comparables.

---

## Fase 5. Descubrimiento automático de patrones

### Librería principal: BERTopic

### ¿Qué hace?

Agrupa automáticamente comentarios similares.

### Ejemplo

Detecta un tema compuesto por:

```text
fiebre
gripa
tos
mialgias
```

↓

```text
SINDROME RESPIRATORIO
```

Otro ejemplo:

```text
caida
fractura
moto
herida
```

↓

```text
TRAUMA
```

### ¿Por qué se usa?

Porque permite descubrir patrones que no fueron definidos previamente.

### Objetivo de la fase

Encontrar categorías ocultas.

### Resultado esperado

Generar una primera clasificación automática de los motivos de consulta.

---

## Fase 6. Construcción de categorías clínicas definitivas

### Librerías principales

- Scikit-learn
- XGBoost

### ¿Qué hace?

Entrena un clasificador.

### Ejemplo

Etiquetas manuales:

```text
Respiratorio
Trauma
Obstétrico
Neurológico
Cardiovascular
Gastrointestinal
```

El modelo aprende y posteriormente clasifica automáticamente nuevos registros.

### ¿Por qué se usa?

Porque una vez entrenado es mucho más consistente que reglas manuales.

### Objetivo de la fase

Clasificar automáticamente todos los triages históricos.

### Resultado esperado

Cada registro tendrá una categoría clínica.

Ejemplo:

```text
Respiratorio
Trauma
Gastrointestinal
Neurológico
```

---

## Fase 7. Generación de variables analíticas

### Herramientas principales

- Pandas
- Scikit-learn

### ¿Qué hace?

Convierte texto en indicadores.

### Ejemplo

```text
Dolor torácico y mareo
```

↓

| Variable | Valor |
| --- | ---: |
| Cardiovascular | 1 |
| Respiratorio | 0 |
| Trauma | 0 |
| Neurológico | 1 |

### Objetivo de la fase

Transformar NLP en datos utilizables para estadística.

### Resultado esperado

Dataset completamente estructurado.

---

## Fase 8. Correlación con factores externos

### Herramientas principales

- Pandas
- SciPy
- Statsmodels
- Scikit-learn

### ¿Qué hace?

Relaciona las categorías clínicas con variables externas como:

- Temperatura
- Humedad
- Precipitación
- Calidad del aire
- Dengue
- Influenza
- COVID
- Accidentes
- Festivos
- Eventos masivos

### Objetivo de la fase

Descubrir patrones reales.

### Resultado esperado

Responder preguntas como:

- ¿Aumentan las consultas respiratorias cuando baja la temperatura?
- ¿Incrementan las caídas durante temporadas lluviosas?
- ¿Existe relación entre dengue y determinados síntomas reportados en triage?

---

## Arquitectura final recomendada

```text
FASE 1
ConTexto
↓
Limpieza y normalización

FASE 2
spaCy
↓
Procesamiento lingüístico

FASE 3
spaCy + Diccionario Clínico
↓
Estandarización médica

FASE 4
Sentence Transformers
↓
Comprensión semántica

FASE 5
BERTopic
↓
Descubrimiento de patrones

FASE 6
Scikit-learn / XGBoost
↓
Clasificación clínica

FASE 7
Pandas + Scikit-learn
↓
Generación de variables analíticas

FASE 8
Pandas + SciPy + Statsmodels
↓
Correlación con clima, dengue, calidad del aire y demás factores externos
```
