# Paquete patrones — fase 8

Le pega la fecha a los temas de triage de `clustering/` y los cruza contra
`calendarios/` para buscar patrones entre los motivos de consulta y el clima,
los festivos, los eventos de la ciudad y las alertas de vigilancia. Eso es todo
lo que hace.

No agrupa notas ni vectoriza: eso son las fases 6 y 7 y llegan hechas. No
predice: la prediccion es la fase siguiente y necesita un modelo distinto del
que se usa para estimar una asociacion — ver el final de este archivo.

```bash
# desde la raiz del repositorio
python -m patrones                     # todo
python -m patrones --potencia          # solo: ¿alcanza para algo?
python -m patrones --bloque dia        # por dia en vez de por semana
python -m patrones --comparar          # solo los tres agrupamientos
python -m patrones --panorama          # el historico entero en un eje de tiempo
python -m patrones --ventana           # y ademas abierto en pantalla
python -m patrones --sin-base          # sin consultar DIM_TRIAGE
```

| archivo | que hace |
| --- | --- |
| `__main__.py` | decide que se hace y en que orden; no calcula nada |
| `calendario.py` | unifica los cinco archivos de `calendarios/` en una tabla diaria |
| `tablero.py` | **la tabla**: un renglon por bloque de tiempo y tema, con el clima al lado |
| `potencia.py` | que efecto se podria detectar. Corre ANTES que cualquier analisis |
| `asociacion.py` | busqueda exploratoria de correlaciones con rezago |
| `modelos.py` | el analisis principal: diseno cruzado por estratos de tiempo |
| `agrupamiento.py` | K-Prototypes, HDBSCAN y jerarquico sobre bloques de tiempo |
| `comparacion.py` | los pone en la misma mesa: estabilidad, ARI/AMI, forma |
| `panorama.py` | agrupa los TEMAS por la forma de su serie semanal y arma el panorama |
| `vistas.py` | los calendarios alineados, las matrices y el panorama |
| `rutas.py` | unico sitio que sabe donde vive cada archivo |

## La fecha se inyecta AQUI y no antes, y esa fue la decision correcta

`NLP/` baja de `DIM_TRIAGE` solo el `OID` y el motivo de consulta. La fecha se
recupera despues, por `OID`, contra la misma tabla — verificado: cero perdidas.

Haberla arrastrado desde el principio habria metido la fecha DENTRO del texto
que se vectoriza, y entonces dos notas del mismo dia se habrian parecido entre
si por ser del mismo dia. Una fractura y una gripa a la misma hora habrian
quedado a la misma distancia, el agrupamiento se habria contaminado y los temas
— que son las unidades de todo este analisis — no significarian lo que dicen.

El costo de hacerlo asi es una consulta mas a la base. El beneficio es que los
temas son limpios. No hay comparacion.

## Lo primero que hace el paquete es decir que no alcanza

`potencia.py` calcula, con la formula de Armstrong et al. (2020) y antes de
mirar un solo resultado, el efecto mas pequeno que estos datos podrian
distinguir del azar. Sobre el corpus actual:

- el tema mas grande tiene 672 notas en 615 dias;
- la sobredispersion medida contra el modelo base es 1,61;
- el efecto mas pequeno detectable ronda un **riesgo relativo de 1,15**, o sea
  un 15%;
- los efectos de clima sobre urgencias que se publican estan entre el **2% y el
  10%**.

O sea que con el corpus de hoy lo unico que puede salir es nada, o algo falso.
Lo dice al principio y no al final, que es la diferencia entre un analisis y una
tarde perdida interpretando ruido.

**Y dice cuanto falta.** La extraccion completa de `NLP/` multiplica el corpus
por 14 (93.991 notas con motivo contra las 6.751 procesadas), lo que llevaria el
tema mayor a unas 9.300 notas y el efecto detectable a un RR de 1,04 — ya dentro
del rango de lo que existe. Ampliar la extraccion no mejora este analisis: lo
hace posible.

## Por que el bloque es la semana

Medido sobre `clustering/salidas/serie_diaria.csv`:

| bloque | tema mas grande | ancla mediana en cero | bloques |
| --- | --- | --- | --- |
| dia | 1,09 notas/dia | 88,5% de los dias | 615 |
| **semana** | **12,1 notas/semana** | **41% de las semanas** | **89** |
| mes | 51,1 notas/mes | 4,8% de los meses | 21 |

El mes arregla la escasez y rompe otra cosa: 21 observaciones para 24 variables
externas no es un modelo. La semana es el unico punto donde las dos cosas son
tolerables a la vez.

Con el corpus completo el bloque correcto vuelve a ser el **dia** — 615
observaciones y unas 153 notas diarias — y por eso es un parametro y no una
constante.

## La diferencia entre buscar y concluir

Son dos modulos distintos a proposito, y el orden importa.

`asociacion.py` **busca**. Recorre los pares (tema, variable, ventana) y mide
correlaciones. Lo hace sobre series **pre-blanqueadas**: se ajusta un AR(7) a la
exposicion y se filtran las dos series con el mismo polinomio, porque dos series
con tendencia correlacionan aunque no tengan nada que ver, y esta serie tiene
tendencia (la cobertura del motivo cae 9 puntos por año) y ciclo semanal (la
señal mas grande de todas). Lo que sale de ahi es una **hipotesis**.

`modelos.py` **concluye**. Diseño cruzado por estratos de tiempo: los estratos
son (año, mes, dia de la semana), de modo que cada dia se compara solo contra
los otros dias del mismo mes y el mismo dia de la semana. La tendencia, la
estacionalidad, el ciclo semanal y la deriva de la cobertura no entran — no
porque se ajusten, sino porque son constantes dentro del estrato.

Se eligio eso y no una regresion de serie temporal por el tamaño de la ventana:
615 dias son 1,7 ciclos anuales, y una curva estacional ajustada sobre un ciclo
y medio no esta estimada, esta inventada.

El precio es que la pregunta contestable es mas estrecha, y conviene decirlo:
*entre dos lunes de marzo de 2026, ¿consulto mas gente por este motivo en el que
llovio mas?*. **"¿La temporada de lluvias trae mas consultas respiratorias?" no
se puede responder con estos datos, y no hay diseño que lo arregle.** Hace falta
mas historia.

## Los tres agrupamientos agrupan SEMANAS, no notas

`clustering/` ya agrupa notas por lo que dicen. Aqui las filas son bloques de
tiempo descritos por la composicion de temas mas el clima mas categoricas de
cuando fue. Lo que sale es una tipologia de semanas.

K-Prototypes **no** va sobre los embeddings aunque se pueda: mezclar 384
dimensiones continuas con tres categoricas mediante un `gamma` escalar hace que
el resultado dependa enteramente de un numero que nadie sabe fijar. Sobre una
docena de columnas numericas contra tres categoricas, `gamma` hace lo que dice.

Y **Ward no se usa**: su criterio esta definido sobre geometria euclidea y es
invalido con coseno — `scikit-learn` lanza error si se le pide. Aqui seria legal
porque las columnas van estandarizadas, pero se usa enlace promedio igual,
porque Ward parte en grupos de tamaño parecido y no hay razon para creer que los
tipos de semana vengan en porciones iguales.

**El criterio que decide no es la silueta: es la estabilidad.** Se remuestrea el
80% de los bloques cien veces y se mide con Jaccard si cada grupo reaparece
(procedimiento de Hennig; ≥0,75 valido, ≤0,50 disuelto). Un grupo que no
reaparece no es un grupo: es una particion del ruido que el algoritmo devolvio
porque se le pidio devolver algo.

La silueta se deja **vacia para HDBSCAN** a proposito. Mide compacidad segun
distancia; HDBSCAN busca densidad. Compararlos con ella es una competencia
amañada cuyo ganador esta decidido antes de empezar.

## Ver los clusters dentro de la temporada climática

Es la figura de `exploracion.ipynb` (celda 20) —el calendario donde cada día se
pinta con la escala de color de su temporada climática— pero generada **una vez
por tema**, con la misma rejilla y los mismos colores. Al pasar de una a otra se
ve si un tema se oscurece dentro de un bloque de color y no en los otros.

```bash
python -m patrones --temporadas --vistas
# salidas/figuras/temporada_00_todas.png        dónde cayó cada temporada
# salidas/figuras/temporada_04_diarrea_*.png    ese tema, dentro de las temporadas
```

La clasificación es la misma del notebook, sin tocar parámetros (ventanas de 30
días, umbrales 16,0 / 17,5 °C, terciles de lluvia, suavizado por moda de 21
días). Dos cosas que conviene saber antes de leerla:

- **El eje térmico casi no separa.** De los 2.432 días con clima, el 85,9% cae
  en «templada», 12,8% en «fría» y 1,3% en «cálida». De las nueve casillas se
  usan tres. No es un defecto de los umbrales: la media móvil de temperatura se
  mueve menos de tres grados en seis años. Léase como tres temporadas de humedad.
- **Los terciles de lluvia cambian el resultado entero.** Con la referencia
  histórica (2020-2026) la ventana sale Seca 347 / Intermedia 122 / Lluviosa 107
  — o sea, 2025-2026 fue un periodo seco para Manizales. Con terciles de la
  propia ventana sale 192/195/194, balanceado por construcción. Por defecto va la
  histórica, que es lo que hace el notebook y lo que conserva el significado de
  la palabra «seca»; `referencia="ventana"` da más potencia para comparar.

Dos cambios respecto al notebook, los dos por defectos reales:

- **Las escalas se truncan al 18%.** `Greys` empieza en blanco puro, así que un
  día de pocas notas en «Intermedia fría» salía **más claro** que el `#eeeeee`
  del día sin dato y se leía como un hueco. Cortando el arranque de las nueve
  rampas, el fondo vuelve a ser inconfundible sin cambiar ninguna familia de color.
- **La leyenda es un eje más de la figura.** La del notebook coloca las barras
  con `fig.add_axes()` en coordenadas absolutas, y eso se rompe al guardar con
  recorte ajustado según cuántas temporadas haya.

### Y la pregunta admite **una sola prueba**

`composicion_por_temporada()` arma la tabla tema × temporada con la fracción de
las notas de cada temporada que fueron de cada tema, y la contrasta con un
chi-cuadrado. Una prueba, sin corrección por multiplicidad que reparta el
presupuesto — **es el análisis con más potencia de todo el paquete**.

Sobre el corpus actual da **χ² = 46,2, 14 gl, p < 0,0001**: la composición sí
cambia entre temporadas. `diarrea vomito fiebre` sobra en Lluviosa y falta en
Seca; `sangrado alta presion` al revés.

**Pero no lo reportes como efecto del clima.** Las temporadas son bloques de
meses seguidos, así que van confundidas con el tiempo. `replicacion_por_anio()`
parte el análisis por año, que es lo que rompe esa confusión, y el resultado es:

| año | χ² | p | notas |
| --- | --- | --- | --- |
| 2025 | 40,8 | 0,0002 | 2.101 |
| 2026 | 14,8 | 0,39 | 980 |

Correlación entre las tablas de residuos de los dos años: **+0,31**. Si el patrón
fuera del clima, las celdas que sobran un año sobrarían el otro y esto estaría
cerca de +1. No replica: el agregado lo sostiene 2025 solo, y para `diarrea` la
dirección se invierte en 2026. La explicación más económica es que lo que separa
a las temporadas sea el momento —la seca cae sobre todo en la segunda mitad de
la ventana, donde también está la caída de la cobertura del motivo— y no el
clima. Queda como hipótesis para un tercer año.

## Lo que se mira a ojo y lo que se prueba

`vistas.py` dibuja el calendario del tema **encima** del calendario de la
lluvia, con las columnas alineadas: la celda del 14 de marzo esta en la misma
posicion arriba y abajo. Una racha en que las dos se oscurecen juntas se ve de
inmediato, y eso es lo que una correlacion global no puede mostrar porque la
promedia con los otros veinte meses.

La rejilla, los colores (`YlOrRd`, `#eeeeee` para el dia sin dato) y los remates
son los de `exploracion.ipynb`, para que quien ya leyo esas figuras no tenga que
aprender a leer estas. Lo unico que no se hereda es `calplot`: el notebook lo
importa, no esta instalado y esa celda hoy falla, mientras que las otras dos
celdas de calendario estan hechas a mano con `pcolormesh` y salen igual.

**El orden es mirar primero y probar despues, contra datos que no se usaron para
mirar.** Mirar, elegir lo que se ve mas bonito y probarlo sobre los mismos datos
es como se fabrica un resultado falso con todas las de la ley. Por eso
`datos/variables.csv` se edita **antes** de correr `--modelar`, y por eso es el
unico archivo de `salidas/` y `datos/` que se versiona: su valor depende de
haber sido escrito antes de ver los resultados, asi que tiene que quedar en el
historial con su fecha.

## El panorama: un eje de tiempo, cuatro familias de motivos

Los calendarios de `vistas.py` son ocho figuras separadas, cada una con su escala.
Para ver si un motivo sube cuando llueve hay que recordar una figura mientras se
mira la siguiente, y el ojo no hace eso. El panorama pone todo en **un solo eje
de tiempo compartido** —la lluvia arriba, la humedad y la temperatura debajo, los
motivos en medio, el volumen de triage y la cobertura del motivo abajo— con las
temporadas climáticas pintadas de fondo atravesando los cuatro paneles. Una
coincidencia aparece entonces como una columna vertical.

```bash
python -m patrones --panorama --sin-base    # escribe las tres figuras
python -m patrones --panorama --ventana     # y las abre para navegarlas
# salidas/figuras/panorama.png            los cuatro paneles alineados
# salidas/figuras/panorama_familias.png   qué motivos se mueven juntos
# salidas/figuras/panorama_rezagos.png    la forma de la relación con la lluvia
```

### Se agrupan los temas antes de dibujarlos, y no es cosmético

El tema mayor son 672 notas en 88 semanas: 7,5 por semana. Una línea de siete
notas semanales es casi toda ruido de muestreo. Juntar los temas que **se mueven
juntos** es la única palanca que sube la cuenta por serie sin esperar a la
extracción completa: la familia mayor queda en 29 notas/semana.

La idea es el modo *perfil (correlación)* del Time Series Clustering de ArcGIS
—agrupar series que suben y bajan a la vez, sin importar su tamaño— pero aplicada
a los **temas** y no a lugares. Esa herramienta agrupa celdas de un mapa y aquí
hay un solo lugar: el hospital. Se aprovecha el criterio, no el producto, y así
el cálculo se queda dentro del repositorio y es reproducible.

Tres trampas y cómo se esquiva cada una, en `panorama.py`:

| trampa | qué pasaría | qué se hace |
| --- | --- | --- |
| la tendencia del denominador | la cobertura cae 9 puntos/año: sobre conteos **todos** los temas bajan a la vez y sale una familia única que significa «el año va pasando» | se agrupa sobre la **proporción** respecto a las notas procesadas de esa semana |
| la composición | las proporciones de una semana suman uno, así que un tema que sube obliga a los demás a bajar: correlaciones negativas fabricadas por la aritmética | **log-ratio centrado** (CLR) de Aitchison, con el resto de la composición incluido como una parte más |
| el ciclo semanal | es la señal mayor de toda la serie y haría que todo correlacione con todo | el bloque es la **semana**: cada bloque tiene exactamente un lunes y un domingo |

### Y lo primero que dice el resultado es que no se lo crea

El criterio no es la silueta: es la **estabilidad**, igual que en
`comparacion.py`. Se recalculan las correlaciones con el 80% de las semanas, 200
veces, y se mira con Jaccard si cada familia reaparece. Se remuestrean las
*semanas* y no los temas porque lo escaso —lo que hace frágil la correlación— son
las 88 semanas.

Sobre el corpus actual: **1 de 4 familias reaparece** (F2, 0,78). Las otras tres
se disuelven (0,42, 0,43 y 0,37). Las disueltas se dibujan con línea punteada y
marcadas `[INESTABLE]` en la leyenda, y su línea **no se interpreta**: no es un
hallazgo débil, es una partición del ruido que el algoritmo devolvió porque se le
pidió devolver algo.

Hay una segunda señal de lo mismo, y conviene tenerla escrita: al quitar **una
sola semana** incompleta del final, la partición pasó de 12/10/4/4 temas a
10/9/8/3. Un agrupamiento que se reordena entero por una semana no está midiendo
la estructura de los motivos.

### Lo que hoy se ve en las figuras

- **La cobertura del motivo domina el panel de abajo**: baja de ~85% a ~75% a lo
  largo de la ventana. Es la razón de que ninguna serie de conteos sirva.
- **La temperatura es una recta.** Va dibujada con escala fija de ±2,5 °C justo
  para que se vea: es más convincente verla plana que leer que lo está.
- **El perfil de rezagos no tiene forma.** Las cuatro familias zigzaguean entre
  −0,12 y +0,12 sin subir, hacer máximo y bajar, que es como se vería un efecto
  real. Con 56 cifras sin corregir, que la mayor ronde p=0,005 es lo que pasa
  cuando no hay nada.
- **Hay un cambio de nivel a mediados de 2025** en la composición: F2 pasa de ~5%
  a ~18% entre julio y septiembre y no vuelve. No coincide con nada del panel de
  lluvia. Antes de buscarle explicación climática hay que descartar que sea de la
  tubería —un cambio en el agrupamiento de la fase 7 o en cómo se escribe el
  motivo—, y eso se mira en `clustering/salidas/validacion.txt`, no aquí.

Nada de esto es una prueba y no gasta ninguna. El orden sigue siendo mirar
primero y probar después, contra datos que no se usaron para mirar: lo que se vea
aquí se escribe en `datos/variables.csv` **antes** de correr `--modelar`.

## Lo que falta, en orden

1. **Ampliar la extraccion de `NLP/`** (`LIMITE_REGISTROS = None`). Es la unica
   condicion que hoy bloquea de verdad y de la que dependen todas las demas.
   Convierte 11 notas diarias en 153 y el efecto detectable del 15% al 4%.
2. **Actualizar el clima.** `clima_unificado.csv` llega a 2026-08-28 y el triage
   a 2026-09-14: 20 dias al final sin ninguna variable climatica. No se
   interpolan — rellenar la lluvia a partir del acumulado anterior inventaria
   justo la variable que se quiere medir. Se arregla corriendo
   `calendarios/clima/clima_manizales.py` y despues `clima_unificado.py`.
3. **Revalidar y reanclar** el agrupamiento sobre el corpus grande
   (`python -m clustering --validar`, luego `--anclar`).
4. Recien entonces, **volver a correr esto**.

## La prediccion es otra fase y otro modelo

Cuando llegue, no se debe usar el modelo de `modelos.py` para predecir: esta
construido para estimar una asociacion ajustada, no para acertar. Un modelo de
prediccion es otro — binomial negativa con armonicos, dia de la semana, festivos
y rezagos del propio conteo — y se evalua con **validacion de origen rodante**,
nunca con validacion cruzada aleatoria: en una serie temporal el corte aleatorio
filtra el futuro y produce metricas falsamente buenas.

Y hay una restriccion operativa que conviene tener escrita desde ahora: para
predecir de verdad haria falta el **pronostico** del clima, no la observacion. Un
modelo evaluado con el clima observado mide algo que en operacion no se va a
tener.
