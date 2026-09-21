# Calidad de los vectores: la compuerta antes de agrupar

```bash
python -m embedding.diagnostico            # las 7 pruebas
python -m embedding.diagnostico --guardar  # y deja docs/diagnostico.json
```

Una matriz de embeddings mala **no da ningún error**. Tiene la forma correcta,
los números son finitos y el código corre. Los fallos que importan son
silenciosos y solo se ven midiendo. Estas siete pruebas son la compuerta antes
del clustering: si la 4 o la 6 salen mal, agrupar es perder el tiempo.

Esto **no** mide si el modelo entiende de clínica — eso es
[MODELO.md](MODELO.md). Mide si la matriz que quedó guardada es sana.

---

## Resultado del 2026-09-21 · 479 frases, 596 notas, SapBERT-es

**11/11.**

### 1 · Estructura

| | |
|---|---|
| dimensión | 768 (esperada 768) |
| NaN / infinitos | 0 / 0 |
| desvío máximo de la norma respecto a 1 | 1,2 × 10⁻⁷ |
| vectores nulos | 0 |

### 2 · Colapso

479 vectores, **479 distintos**. Ningún par por encima de 0,999. Un modelo roto
devuelve el mismo vector para todo; este no.

### 3 · Dimensiones

| | |
|---|---|
| dimensiones con varianza cero | 0 |
| **dimensión efectiva** (participation ratio) | **37,3** |
| componentes para el 90 % de la varianza | 102 |
| varianza de la 1.ª componente | 9,6 % |

Las 768 dimensiones nominales llevan la información de unas 37 efectivas. Eso
es normal y sano: lo preocupante sería que una sola componente se llevara la
mitad de la varianza, que es la firma de un espacio degenerado.

### 4 · Anisotropía — la prueba que decide si se puede agrupar

Coseno entre pares de frases tomadas al azar:

| | SapBERT-es | bge-m3 *(el anterior)* |
|---|---|---|
| media | **0,286** | 0,469 |
| desviación | **0,151** | 0,087 |
| percentil 1 | −0,005 | ~0,30 |
| percentil 99 | 0,695 | ~0,71 |
| **rango del 98 % central** | **0,70** | 0,41 |

Esto es lo más importante del diagnóstico. El docstring de
`clustering/agrupar.py` describía el problema con `bge-m3`:

> «la similitud coseno entre pares de frases tomadas al azar es 0,469 de media
> con desviación 0,087: el 98 % de los pares cae entre 0,30 y 0,71. **No hay
> frases lejanas.** Todo está a una distancia parecida de todo […] Un algoritmo
> de densidad necesita que haya zonas densas y zonas vacías. Sobre esa
> distribución no las hay.»

Con SapBERT-es la media baja 18 puntos y la dispersión se **hace 1,7× más
ancha**: el percentil 1 llega a cero, o sea que ahora sí existen pares de
frases ortogonales. El espacio tiene rango utilizable donde antes no lo tenía.

**Consecuencia práctica para el clustering:** esos párrafos de
`clustering/agrupar.py` están medidos sobre el modelo anterior y hay que
rehacerlos. En particular el suelo de coherencia —la tabla que decía que un
grupo de dos textos sin nada en común da 0,856— se calculó con 0,4636 de
correlación de fondo; con 0,286 los números son otros. **No usar esas tablas
tal cual.**

La regla que sí sigue valiendo, y más que nunca: nunca decidir nada con un
umbral absoluto de similitud. Se usa vecindad relativa.

### 5 · Separación clínica

| | |
|---|---|
| coseno medio, misma categoría | 0,408 |
| coseno medio, categoría distinta | 0,294 |
| **brecha** | **+0,114** |

Sobre 380 frases con categoría del catálogo y 10.440 pares de la misma. La
geometría codifica clínica, no solo parecido de letras.

### 6 · Hubness

En dimensión alta aparecen «hubs»: unos pocos vectores que entran en la lista
de *k* vecinos de casi todos. Rompen el clustering por densidad porque HDBSCAN
los toma por núcleos.

| | |
|---|---|
| asimetría de la distribución de 10-ocurrencias | **0,77** (problemático por encima de ~2) |
| media / máximo | 10,0 / 33 |
| frases que nunca son vecinas de nadie | 4 |

Los mayores hubs son frases genéricas con varios síntomas —*«dolor abdominal y
vómito»*, *«cefalea, náusea, mareo»*— lo cual es esperable y correcto: son
frases que de verdad están cerca de muchas otras.

### 7 · Determinismo

Codificar las mismas 24 frases dos veces da una diferencia máxima de **0,0**
exacto. El almacén es reproducible: una frase vectorizada hoy y otra idéntica
mañana caen en el mismo sitio.

---

## Qué esto no dice

- **No dice que el clustering vaya a salir bien.** Dice que no va a fallar por
  culpa de los vectores. Es una condición necesaria, no suficiente.
- **479 frases son pocas.** La anisotropía y la hubness empeoran con el tamaño
  del corpus; hay que repetir el diagnóstico con el corpus completo.
- **La separación clínica usa etiquetas débiles** (coincidencia de subcadena
  con el catálogo), con la misma fuga léxica que se documenta en
  [MODELO.md](MODELO.md). La brecha de 0,114 es real pero está inflada.
