# Vigilancia SIVIGILA — por qué se construye así

`calendarios/vigilancia/sivigila.py` (eventos colectivos 995 y 998; los individuales y la vía Power BI de 2026, en la última parte de este documento) baja los microdatos del INS y escribe dos archivos:
`calendarios/vigilancia_sivigila.csv.gz` (formato largo, municipio × semana
epidemiológica) y `calendarios/vigilancia_sivigila_instituciones.csv.gz` (Manizales, por
institución). Este documento explica **por qué** está hecho así y con qué evidencia. Cómo
funciona está en el docstring del script.

```
python calendarios/vigilancia/sivigila.py --eventos 995 998 --desde 2011     # todo
python calendarios/vigilancia/sivigila.py --sin-descargar --eventos 995      # sin red
```

Escrito el 2026-09-28. Sustituye a las «ventanas estacionales» del CSV manual
`vigilancia_salud_manizales_caldas.csv`, que no se borra: el 67 % de sus filas eran las
mismas fechas cada año, y el mes explicaba el 92,6 % de su bandera IRA (`docs/CONTEXTO.md`,
2026-09-28). Era calendario disfrazado.

---

## Las fuentes

| Evento | Qué es | Años usables | Denominador |
|---|---|---|---|
| **995** | Morbilidad por IRA, notificación **colectiva semanal** de cada institución (UPGD) | **2012-2025** (calidad baja 2012-2014) | **Sí**: consultas por todas las causas |
| **998** | Morbilidad por EDA, colectiva | 2011-2025 | No: se usa el del 995 |

Los archivos son `https://portalsivigila.ins.gov.co/Microdatos/Datos_{AÑO}_{EVENTO}.xlsx`.
Se publican con ~8 meses de rezago: 2025 salió el 25-ago-2026 y **2026 no existe**. Sirven
para entrenar y medir, no para operar.

### El 995: por qué es la fuente buena

La ficha (FOR-R02.0000-044 V:03, 2015, leída del PDF del INS) pide a cada institución, cada
semana y a partir de los RIPS, **numerador y denominador** en 7 grupos de edad:

| Bloque | Columna total | Variable de salida |
|---|---|---|
| Consulta externa + urgencias por IRA (J00-J22) | `tot_iraext` | `consultas_ira_*` |
| Consulta externa + urgencias, todas las causas | `tot_exturg` | `consultas_todas_causas_*` |
| Hospitalización por IRAG / todas las causas | `tot_irag` / `tot_cau_h` | `hospitalizaciones_*` |
| UCI por IRAG / todas las causas | `tot_irauci` / `tot_h_uci` | `uci_*` |
| Muertes por IRAG / todas las causas | `tot_mu_ira` / `tot_muerte` | `muertes_*` |

Grupos de edad: `< 1`, `1`, `2 a 4`, `5 a 19`, `20 a 39`, `40 a 59`, `>= 60` →
`menor_1`, `1`, `2_4`, `5_19`, `20_39`, `40_59`, `60_mas`. Se añade `0_4` (suma de los tres
primeros) porque es la banda pediátrica del hospital. **5-14 no se puede construir**: la
ficha junta 5 a 19.

Las proporciones (`proporcion_consultas_ira_*`, `proporcion_hospitalizaciones_irag_total`,
`proporcion_uci_irag_total`) salen **por ámbito y semana**, cociente de sumas. Es la regla del
proyecto —proporción con denominador— y aquí es imprescindible, por lo que se ve en
«Escalones».

Coherencia interna medida: el total de cada bloque es la suma de sus 7 edades en todas las
filas salvo 23 (IRA), 2 (IRAG) y 1 (UCI IRAG), en ~3,1 millones de filas de 2012-2025.

### El 998: por qué entra, y con qué límite

La ficha de datos colectivos (FOR-R02.0000-002 V:05, 2016) es compartida con varicela,
chikunguña y «evento sin establecer»: **casos**, en 18 grupos de edad quinquenales, sexo,
clasificación, hospitalizados y barrio. **No trae denominador.** Se integra como conteo, y
la proporción se calcula contra el `consultas_todas_causas` del 995 del mismo ámbito y
semana (`proporcion_eda_sobre_consultas_995_*`). Es una aproximación: las instituciones que
notifican el 998 no son exactamente las del 995 (Manizales, 2025: 27,7 contra 53,5 por
semana).

Los 18 grupos se agregan a las **bandas del hospital** (`salidas/triage_edad.parquet`):
`0_4`, `5_14`, `15_44`, `45_64`, `65_mas`, que en el 998 sí se pueden construir exactas.

Tres formatos según el año:

| Años | Formato | Qué se puede sacar |
|---|---|---|
| 2011, 2012, 2014 | Tabla municipal de 10 columnas: `semana`, `ano`, municipio, `casos` | Solo el total. Sin edad, sin institución |
| 2013, 2015-2025 | Una fila por institución, 18 edades | Total, bandas, hospitalizados, instituciones |

Comprobación externa: Manizales 2012 da **31.606 casos**, la misma cifra que obtuvo por su
lado el agente de investigación de la sesión.

---

## Privacidad: se descarta en el mismo paso de lectura

Los Excel traen, además de los conteos, **nombre (`diligencia`), cargo, teléfono y correo**
de quien notifica, y `num_con`, que en 2025 toma valores con forma de número de cédula
(`1000xxxxxx`). El lector recorta cada fila a una **lista blanca** antes de guardarla: lo
que no está en la lista no llega a existir en un DataFrame. Solo se registra el **nombre**
de lo descartado, por año, en la auditoría.

- Lo descartado en el 995 es siempre un subconjunto de `num_con`, `fec_aju`, `diligencia`,
  `cargo`, `telefono`, `correo`, `nit_upgd`, `nom_eve`, `version`, `conteo`. 2023 y 2024 ya
  vienen sin las columnas de persona.
- En el 998 se descarta además todo lo del caso: sexo, clasificación, procedencia. El
  **barrio** (`bar_sector`) se lee solo para distinguir dos brotes legítimos de una fila
  repetida, y se tira antes de guardar nada.
- El nombre y el código de la **institución** se conservan: no son dato personal.
- `calendarios/vigilancia/crudo/` está en `.gitignore`, en el bloque «NUNCA» del final,
  para que ninguna regla `!` posterior lo vuelva a incluir.

---

## Semana epidemiológica → fechas

**Domingo a sábado. La SE1 es la semana que contiene el 4 de enero** (la regla MMWR:
la primera semana con al menos cuatro días del año nuevo).

Comprobado contra el INS:

| Fuente del INS | Dice | La regla da |
|---|---|---|
| Calendario epidemiológico 2025 (PDF del portal) | SE1 = 29-dic-2024 a 4-ene-2025; SE53 = 28-dic-2025 a 3-ene-2026; SE52 de 2024 = 22 a 28-dic-2024 | Igual |
| Boletín 2019 SE52 | 22 a 28-dic-2019 | Igual |
| Boletín 2020 SE1 | 29-dic-2019 a 4-ene-2020 | Igual |
| Boletín 2020 SE53 | 27-dic-2020 a 2-ene-2021 | Igual |
| Boletín 2021 SE52 | 26-dic-2021 a 1-ene-2022 | Igual |

Y contra los propios datos: el instructivo de la ficha 995 dice que `fec_not` es **el último
día de la semana notificada**. La moda de `fec_not` en cada semana cae en el sábado que da la
regla en **todas las semanas de 2012 y de 2014 a 2025**, salvo una de 2014 y una de 2015.
En 2013, en 33 de 52 (ver «Escalones»).

**Años de 53 semanas** entre 2007 y 2026: **2008, 2014, 2020 y 2025**. 2021 **no** tiene
semana 53.

### Dos errores de datos que esto destapó

1. **2021 trae `fec_not` como texto `dd/mm/aaaa`.** pandas lo leía como mes/día sin avisar
   de error: el 05/01/2021 salía 1 de mayo, y solo 1 de las 52 semanas cuadraba con su
   sábado. Con el formato explícito cuadran **52 de 52**. Afectaba a la deduplicación, que
   desempata por fecha.
2. **2021 trae 39 filas en la «semana 53».** Todas con `fec_not` = 1-ene-2021, que por la
   regla es la **SE53 de 2020**. Algunos calendarios internos le asignaban una 53 a 2021 por
   error. El script reasigna por `fec_not` cuando la semana es imposible, y descarta si la
   fecha cae en otro año, como aquí. De esas 39 instituciones, 24 ya están en la SE53 del
   archivo 2020; ninguna es de Manizales y una de Caldas.

---

## Qué municipio se asigna a cada fila

**Los cinco primeros dígitos del código de la institución** (`cod_pre`: 2 de departamento +
3 de municipio, según el instructivo de la ficha). No `cod_mun`.

Por qué: `cod_pre` existe y tiene el mismo significado todos los años. `cod_mun` cambia de
formato (2019 lo parte en `cod_dep` + 3 dígitos) y trae valores imposibles (`17000`,
`00000`). En Manizales los dos criterios son idénticos desde 2016; antes difieren en pocas
filas:

| Año | Filas por código de UPGD | Por `cod_mun` | Prop. IRA UPGD | Prop. IRA `cod_mun` | r semanal IRA |
|---|---|---|---|---|---|
| 2012 | 1.009 | 961 | 16,15 % | 16,57 % | 0,996 |
| 2013 | 1.811 | 1.788 | 12,16 % | 12,22 % | 0,998 |
| 2014 | 1.819 | 1.787 | 10,96 % | 11,09 % | 0,998 |
| 2015 | 1.936 | 1.932 | 10,21 % | 10,19 % | 0,995 |
| 2016-2025 | idénticas | | | | 1,000 |

Casi todas las diferencias son instituciones con código de Manizales y `cod_mun` = `17000`,
que no es un municipio. **La elección no mueve la serie.**

---

## Auditoría del 995, Manizales

| Año | Filas | Instituciones | Semanas | Inst./semana (media, mín.) | Consultas IRA | Todas las causas | Prop. IRA |
|---|---|---|---|---|---|---|---|
| 2012 | 1.009 | 31 | 52 | 19,4 (12) | 77.435 | 479.549 | 16,2 % |
| 2013 | 1.811 | 72 | 52 | 34,8 (**2**) | 81.330 | 668.816 | 12,2 % |
| 2014 | 1.819 | 74 | 53 | 34,3 (24) | 59.487 | 542.856 | 11,0 % |
| 2015 | 1.936 | 71 | 52 | 37,2 (32) | 64.048 | 627.569 | 10,2 % |
| 2016 | 2.907 | 74 | 52 | 55,9 (45) | 82.486 | 886.471 | 9,3 % |
| 2017 | 2.617 | 60 | 52 | 50,3 (40) | 79.259 | 902.920 | 8,8 % |
| 2018 | 2.526 | 61 | 52 | 48,6 (43) | 77.002 | 848.803 | 9,1 % |
| 2019 | 2.301 | 59 | 52 | 44,3 (33) | 65.291 | 786.067 | 8,3 % |
| 2020 | 1.814 | 54 | 53 | 34,2 (27) | 39.261 | 700.847 | 5,6 % |
| 2021 | 1.911 | 50 | 52 | 36,8 (33) | 31.648 | 1.121.559 | 2,8 % |
| 2022 | 1.992 | 52 | 52 | 38,3 (33) | 56.388 | 1.206.056 | 4,7 % |
| 2023 | 2.105 | 53 | 52 | 40,5 (37) | 58.878 | 1.318.518 | 4,5 % |
| 2024 | 2.604 | 63 | 52 | 50,1 (39) | 65.791 | 1.773.774 | 3,7 % |
| 2025 | 2.838 | 65 | 53 | 53,5 (47) | 67.220 | 1.864.363 | 3,6 % |

Caldas y Colombia tienen la misma forma: Colombia pasa de 67 millones de consultas por
todas las causas en 2013 a 182 millones en 2025, con la IRA entre 4,3 (2020) y 7,8 millones.

Semanas sin dato: la proporción de UCI queda vacía en 3 semanas de 2012-2013 en las que
ninguna institución reportó camas de UCI (denominador cero). Son las únicas 6 filas con
`valor` nulo del archivo.

Deduplicación: filas idénticas (misma institución, semana y conteos) se dejan en una; si la
misma institución y semana tiene dos versiones distintas, gana la de ajuste 7 y, a igualdad,
la notificada más tarde. En 2019-2025 son 20-429 idénticas y 18-87 resueltas por año, sobre
~250.000; en 2012-2018, hasta 5.785 resueltas.

---

## Escalones

La regla del proyecto: antes de usar una columna, mirar su serie buscando escalones. Esta
tiene varios, y el más grande está en el **denominador**.

### 1. 2011 no es el mismo evento

El archivo 995 de 2011 es la ficha colectiva de casos (18 edades, sin denominador), no la de
morbilidad con RIPS. **No se procesa**: el script lo reporta como formato no reconocido.

### 2. 2012-2014: calidad baja

- **2012**: no trae las columnas `tot_*` (se reconstruyen como suma de edades, que es lo que
  valen en los años que sí las traen); 31 instituciones en Manizales frente a 72 en 2013; y
  27.181 filas del país con más IRA que consultas totales.
- **2013**: la SE21 tiene **2** instituciones en Manizales; la SE37 suma 43.000 consultas,
  3,5 veces una semana normal; **desde la SE39 las instituciones se duplican** (29 → 58)
  sin que la IRA cambie; 27.937 filas del país con IRA > total; `fec_not` cuadra solo en
  33 de 52 semanas.
- **2014**: 4.652 filas del país con IRA > total (35 en Manizales).

Desde 2015 las filas incoherentes son decenas o ninguna. **La serie usable empieza en
2015.**

### 3. El denominador crece por escalones, y arrastra la proporción

En Manizales la IRA se mueve entre 56.000 y 82.000 consultas al año fuera de la pandemia,
pero **las consultas por todas las causas casi se triplican** (669.000 en 2013 → 1.864.000
en 2025). Dos saltos:

| Salto | Todas las causas | IRA | Lectura |
|---|---|---|---|
| 2020 → 2021 | 700.847 → 1.121.559 (**+60 %**) | 39.261 → 31.648 | Mientras la IRA seguía deprimida por la pandemia |
| 2023 → 2024 | 1.318.518 → 1.773.774 (**+35 %**) | 58.878 → 65.791 | 11 instituciones nuevas, **11,7 %** del volumen |

Por eso **la caída de la proporción IRA de 12 % a 3,6 % no es una caída de la IRA**: es el
denominador. Lo mismo pasa en Colombia (7,8 % en 2014 → 3,9 % en 2025), así que es un
cambio de cómo se cuenta, no de Manizales.

El denominador también mezcla instituciones que **nunca** ven una IRA: en 2025, 15
instituciones de Manizales con cero consultas IRA en todo el año suman el **15,9 %** de las
consultas (una IPS de salud mental, por ejemplo, con ~30.000 por trimestre). Quitarlas sube
la proporción de 2025 de 3,6 % a 4,3 %.

Consecuencia para el modelo: **la proporción IRA es comparable dentro del año, no entre
años.** Un modelo que la use necesita nivel por año (o anomalía respecto a la media móvil),
igual que el conteo de triage necesita su tendencia.

### 4. Cambio de peso entre instituciones

Dentro de 2024-2025 hay movimientos grandes que no son epidemiología: la Caja de
Compensación de Caldas entra en 2024 (0,5 → 35.000 consultas por trimestre en un año);
Interconsultas SAS cae de 80.500 a 42.000 entre el primer y el segundo trimestre de 2025.

### 5. El 998 cae a la mitad desde 2020

Manizales: ~29.000-37.000 casos de EDA al año en 2013-2019, 13.000-24.000 desde 2020, con
las instituciones notificando bajando de ~33 a ~21-28 por semana. En Colombia la caída es
menor (3,4 → 2,6 millones). Puede ser real (la EDA bajó tras la pandemia) o de notificación;
**no está resuelto**.

---

## Estacionalidad

Índice mensual (media del mes / media del año), Manizales, años 2015-2019 y 2022-2025:

| | ene | feb | mar | abr | may | jun | jul | ago | sep | oct | nov | dic |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Consultas IRA 0-4 | 0,68 | 0,96 | **1,20** | **1,14** | **1,28** | **1,25** | 0,99 | 1,03 | 1,00 | 0,80 | 0,92 | 0,76 |
| Proporción IRA 0-4 | 0,90 | 0,88 | 1,09 | 1,09 | 1,13 | **1,21** | 1,00 | 1,02 | 0,95 | 0,84 | 0,97 | 0,93 |
| Consultas IRA total | 1,08 | 0,93 | 0,93 | 0,91 | 1,07 | **1,11** | 1,01 | 0,97 | 1,02 | 0,92 | 1,03 | 1,02 |
| Proporción IRA total | **1,23** | 0,86 | 0,91 | 0,95 | 1,02 | **1,15** | 0,99 | 0,93 | 0,92 | 0,88 | 1,03 | 1,13 |
| Casos EDA total | 0,97 | 1,15 | **1,20** | 1,08 | 1,01 | 0,85 | 0,90 | 0,94 | 1,08 | 0,99 | 0,87 | 1,00 |

Lectura:

- **El primer pico (marzo-junio) es claro**, sobre todo en los niños: +20 a +28 % sobre la
  media del año. Coincide con la primera temporada de lluvias.
- **El segundo pico (octubre-noviembre) no aparece.** Octubre es el mes más bajo del 0-4; el
  total tiene una joroba pequeña en noviembre-enero.
- El pico de enero en la proporción total es de **denominador**: en vacaciones cae la
  consulta programada (todas las causas, índice 0,89) y la IRA no.
- La EDA tiene otra forma: pico en febrero-marzo, valle en junio-julio.

---

## Contra el hospital

`salidas/triage_edad.parquet`, banda 0-4, sumada por semana epidemiológica (solo semanas
de 7 días), contra la IRA 0-4 de Manizales en el 995. **312 semanas de 2020-2025**:

| SIVIGILA Manizales | r en nivel | r normalizando por la media de cada año | r de diferencias log semana a semana |
|---|---|---|---|
| **Consultas IRA 0-4** | **0,703** | **0,808** | 0,176 |
| Proporción IRA 0-4 | 0,429 | 0,665 | 0,104 |
| Consultas todas las causas 0-4 (control) | 0,273 | 0,164 | 0,068 |
| Casos EDA 0-4 (998) | 0,192 | 0,476 | 0,097 |

Por año, en nivel: 2020 0,92 · 2021 0,80 · 2022 0,63 · 2023 0,44 · 2024 0,79 · 2025 0,73.
Solo 2022-2025, normalizado por año: 0,66. Normalizar por la media anual quita la tendencia
y el cráter de 2020, y la correlación **sube**: **no es tendencia compartida, es la forma de
la temporada.**

**Corrección del mismo día.** La primera versión daba r = 0,685 sobre 303 semanas. El
parquet del hospital sale de un `GROUP BY`, que no emite ceros: los 124 días sin ningún
triage 0-4 (82 de 2020, 28 de 2021) no tenían fila y se trataban como hueco, lo que tiraba
semanas enteras. Contados como cero: 312 semanas y r = 0,703.

Lectura: el pediátrico del hospital se mueve con la IRA de la ciudad, y **no** con el
volumen general de consultas pediátricas (0,27, y 0,16 dentro del año). Con la EDA hay algo
dentro del año (0,48), mucho menos que con la IRA. Es la señal que
buscaba la validación del 2026-09-28 (el 0-14 era lo único que respondía a las externas),
ahora con una variable medida en vez de una ventana fija. La correlación semana a semana es
mucho menor (0,22): el acuerdo está en la forma de la temporada, no en cada semana.

**Un límite que no se pudo cerrar:** el hospital podría ser una de las instituciones que
notifican el 995, y entonces parte de la correlación sería mecánica. No se identificó cuál.

---

## Instituciones: los cierres a Nueva EPS

Consultas por todas las causas por trimestre, en miles:

| | 2024 T1-T4 | 2025 T1 | 2025 T2 | 2025 T3 | 2025 T4 |
|---|---|---|---|---|---|
| Clínica Avidanti Manizales | 3,89 · 3,70 · 3,89 · 3,88 | 3,84 | 3,61 | **2,54** | **2,40** |
| Hospital Santa Sofía de Caldas | 1,84 · 1,76 · 1,51 · 1,56 | 1,77 | 1,30 | 1,47 | 1,84 |
| Todo Manizales | 390 · 454 · 477 · 452 | 470 | 444 | 481 | 469 |

- **Avidanti baja un 39 %**: de 274 consultas por semana (SE1-33 de 2025) a 168 (SE34-53).
  En 2024, las mismas semanas no cambian (293 → 300). La caída empieza en la **SE32**
  (3-9 de agosto), dos semanas antes del cierre del 21 de agosto. La IRA de Avidanti baja
  igual (8,0 → 4,8 por semana).
- **Santa Sofía no muestra nada todavía**: el cierre es el 1 de diciembre y solo quedan 5
  semanas de 2025 después.
- **No se ve desplazamiento en el agregado.** Lo que pierde Avidanti (~106 consultas por
  semana) es el 0,3 % del volumen de la ciudad. El resto de Manizales sube un 3,9 % entre
  antes y después del cierre (SE1-33 contra SE34-48), menos que el 10,2 % que subió toda la
  ciudad en las mismas semanas de 2024.

El volumen que Avidanti reporta al 995 (~270 consultas por semana) parece pequeño para una
clínica de su tamaño. Puede que solo reporte urgencias, o una parte. **Con estos datos no se
puede saber a dónde fue la demanda.**

---

## Lo que queda abierto

- **2026 no existe en los microdatos.** ~~No verificado aquí.~~ **Verificado y congelado
  el 2026-09-28** (ver «Power BI: la vía de 2026», al final): el tablero 995 trae la tabla
  `IRA` con numerador y denominador por edad para 2015-2019 y 2021-2026, **falta 2020**, y
  sus totales de Manizales van un 3-8 % por encima de los microdatos todos los años. Sirve
  para 2026, pero **no se empalma sin corregir ese nivel**.
- Qué institución es el hospital, si es que notifica.
- Una proporción con **panel fijo** de instituciones (las que notifican todo el periodo),
  que quitaría los escalones de cobertura en vez de solo documentarlos.
- Por qué cae la EDA desde 2020.

## Cómo comprobar que sigue bien

El script imprime la auditoría al final. Lo que hay que mirar:

- **`semanas_con_fec_not_en_sabado_esperado` igual a `semanas`** desde 2014. Si baja,
  cambió el formato de fecha de algún año.
- **Criterio de municipio**: r semanal 1,000 desde 2016.
- **Filas con total distinto de la suma de edades**: decenas como mucho.
- **Correlación con el hospital**: ~0,70 en nivel para la IRA 0-4, sobre 312 semanas. Si cae
  a cero, se rompió la unión por semana; si bajan las semanas, volvieron a perderse los días
  con cero triages pediátricos.

---

# Eventos individuales, marcadores y la vía de 2026

Añadido el 2026-09-28. Dos módulos hermanos de `sivigila.py`:

```
python calendarios/vigilancia/eventos.py --descargar --desde 2023          # catálogo entero, 3 años
python calendarios/vigilancia/eventos.py --descargar --seleccionados       # 2007-2025 de lo elegido
python calendarios/vigilancia/eventos.py --sin-red                         # censo + series + auditoría
python calendarios/vigilancia/powerbi.py                                   # congela la descarga de hoy
python calendarios/vigilancia/powerbi.py --empalme                         # tablero contra microdatos
```

| Salida | Qué es |
|---|---|
| `calendarios/vigilancia_sivigila_eventos.csv.gz` | Formato largo, **la misma estructura** que `vigilancia_sivigila.csv.gz`: `evento, anio, semana_epi, fecha_inicio_semana, fecha_fin_semana, ambito, variable, valor`. 99.729 filas, 26 códigos, sin nulos |
| `calendarios/vigilancia_sivigila_eventos_censo.csv` | Una fila por evento del catálogo: casos de Manizales por año 2015-2025, media semanal 2023-2025 y estado |
| `calendarios/vigilancia/powerbi/AAAA-MM-DD/` | Una descarga congelada por día (ver abajo) |

**Por qué un archivo hermano y no el mismo `vigilancia_sivigila.csv.gz`.** `sivigila.py`
reescribe su archivo entero y conserva de la versión anterior lo que no procesa. Dos
escritores sobre un mismo archivo es la forma de que uno pise al otro sin avisar. Con un
archivo por módulo, cada uno es dueño del suyo; como la estructura es idéntica, se unen con
un `concat`.

## Selección: el censo

Se bajaron **2023-2025 de todos los eventos individuales del catálogo** (1,9 GB, 236
archivos), más los 3 últimos años publicados de los 11 eventos que dejaron de publicarse
antes de 2023. Para cada uno se contaron los casos de Manizales por municipio de ocurrencia.
Después se bajó 2015-2022 de lo que entró (~3 GB). A ~1,3 MB/s, la descarga es secuencial y
se reanuda sola (`.part`). Pico de memoria en el archivo mayor (300 de 2025, 130 MB, 199.257
filas): 1,3 GB, 51 s.

**Regla, fijada por el propietario:** entra como serie el evento con **media ≥ 1 caso por
semana en 2023-2025**. Lo demás queda como «volumen insuficiente», con sus casos por año en
el censo. Resultado: **14 integrados, 3 marcadores, 56 con volumen insuficiente y 11 sin
publicar desde antes de 2023.**

| Código | Evento | 2023 | 2024 | 2025 | Media/sem. | Estado |
|---|---|---|---|---|---|---|
| 300 | Agresiones por animales (rabia) | 1.364 | 1.345 | 1.555 | 27,2 | integrada |
| 875 | Violencias de género e intrafamiliar | 1.255 | 1.308 | 1.332 | 24,8 | integrada |
| 356 | Intento de suicidio | 703 | 596 | 566 | 11,9 | integrada |
| 365 | Intoxicaciones (360+370+380+390+400+410+412+414) | 548 | 510 | 444 | 9,6 | integrada |
| 370 | Intoxicación por fármacos | 419 | 375 | 325 | 7,1 | integrada |
| 549 | Morbilidad materna extrema | 247 | 251 | 253 | 4,8 | integrada |
| 831 | Varicela | 222 | 211 | 237 | 4,3 | integrada |
| 155 | Cáncer de mama y cuello uterino | 248 | 216 | 200 | 4,2 | integrada |
| 850 | VIH / sida | 207 | 173 | 170 | 3,5 | integrada |
| 813 | Tuberculosis (810+820+825) | 148 | 170 | 138 | 2,9 | integrada |
| 820 | Tuberculosis pulmonar | 131 | 155 | 125 | 2,6 | integrada |
| 346 | IRA por virus nuevo (COVID-19) | — | 202 | 20 | 2,1 | integrada (solo 2024-2025) |
| 113 | Desnutrición aguda < 5 años | 105 | 81 | 49 | 1,5 | integrada |
| 620 | Parotiditis | 63 | 53 | 47 | 1,04 | integrada (en el límite) |
| 452 | Pólvora y explosivos | 14 | 22 | 25 | 0,39 | marcador |
| 349 | Brotes de ETA (brotes) | 5 | 7 | 10 | 0,14 | marcador |
| 348 | IRAG inusitado | 164 | 5 | 17 | — | marcador |
| 414 · 735 · 750 | Psicoactivas · anomalías congénitas · sífilis gestacional | 58·31·56 | 58·60·40 | 35·59·51 | 0,94-0,96 | insuficiente, **en el límite** |

El resto, y los casos de cada año, están en `INVENTARIO.md` y en el censo. **365 y 813** son
los códigos agrupados con los que el INS notifica en 2026. Se construyen sumando los códigos
antiguos, y solo en los años en que están todos los componentes que el portal publica. Sus
componentes se guardan también por separado; 370 y 820 pasan el umbral por sí solos.

**Marcadores.** Para 452, 349 y 348 se guardan los conteos y además `semana_con_casos`
(0/1). El 349 es otra ficha: una fila por **brote**, 137-140 columnas (hasta 2017, la del
antiguo 350, con 188-230). Se guarda `brotes` y `enfermos`, y el municipio sale de `cod_mun`
(`cod_mun_` en la ficha antigua).

## Cómo se cuenta

- **Privacidad.** Lista blanca en el mismo paso de lectura: evento, semana, año, códigos de
  municipio de ocurrencia, residencia y notificación, ajuste, hospitalizado, tipo de caso y
  condición final. También tres fechas (notificación, inicio de síntomas y consulta), que
  **se convierten en semana y se descartan** antes del resumen. Edad, sexo, fecha de
  nacimiento, ocupación, etnia, grupos poblacionales, aseguradora e institución no se leen.
  Nunca se imprimió un valor de columna de persona. El 349 trae `num_con`, que no está en su
  lista blanca.
- **Caso** = fila de la ficha, menos `AJUSTE` 6 (descartado) y D (error). En Manizales, esto
  solo quita filas del 348: 2 a 860 por año, casi todas en 2022-2023, cuando se descartó en
  masa lo que era COVID.
- **Municipio** = el de **ocurrencia** (`COD_DPTO_O` 2 dígitos + `COD_MUN_O` 3 dígitos), que
  es el que filtran los tableros. También se guardan `casos_residencia`,
  `casos_notificacion` (`COD_MUN_N`, 5 dígitos) y `casos_ocurrencia_hospitalizados`. La
  notificación supera a la ocurrencia en un 5-15 %: Manizales recibe remitidos.
- **Formato:** todas las celdas llegan como `="…"`, y las fechas como texto
  `d/mm/aaaa hh:mm:ss a. m.`. El `S.fecha` de `sivigila.py` corta a 10 caracteres y perdía
  los días de un dígito (8.718 de 29.557 filas en 831 de 2025). `eventos.fecha` parte por el
  espacio. El esquema de 69 columnas se confirmó en **todos los archivos individuales
  leídos**.
- **Ceros.** Cada evento-año se pone sobre la rejilla completa de semanas (52 o 53), con 0
  donde no hubo casos: un `GROUP BY` no emite ceros.

## Qué semana es `SEMANA`: la decisión

La ficha dice «semana epidemiológica», pero **no dice de qué fecha**. Se midió, por archivo,
el porcentaje de filas cuya `SEMANA` coincide con la semana de cada fecha (N = notificación,
I = inicio de síntomas, C = consulta; «?» = ninguna llega al 97 %). Lo imprime la
auditoría (`sem=not%`, `sem=ini%`, `sem=con%`):

| | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 300 | N100 | I98 | I98 | I99 | I99 | I99 | I100 | I100 | I100 | I99 | I99 |
| 875 | ?C79 | ?I84 | ?I77 | ?I76 | ?C96 | C99 | C100 | C100 | C100 | C100 | C100 |
| 356 | | N100 | N100 | N100 | N100 | ?N93 | ?C90 | ?I92 | ?I94 | ?I92 | ?I92 |
| 549 | N100 | N100 | N100 | N100 | N100 | N100 | N100 | N100 | C100 | C100 | C100 |
| 113 | | N100 | N100 | N100 | N100 | ?N93 | C99 | C100 | C100 | C100 | C100 |
| 850 | ?N33 | ?C37 | ?N72 | N100 | N100 | N100 | N100 | N100 | N100 | N100 | N100 |
| 370 | I100 | I100 | I100 | ?N95 | ?N94 | ?N90 | ?I96 | ?I97 | ?I97 | I97 | I100 |
| 155 | | N99 | N100 | N100 | N100 | N100 | N100 | | N100 | N100 | N100 |
| 831, 348, 414, 452, 346 | I | I | I | I | I | I | I | I | I | I | I |
| 810, 820 | C | C | C | C | C | C | C | C | C | C | C |

**Escalón de definición:** el INS cambia la fecha que define la semana por evento y por
año. Por ejemplo: 875 pasa a consulta en 2020, 549 en 2023, 113 en 2021, y 356 deja la
notificación en 2020-2021. Un cambio así desplaza días o semanas los casos de cada semana
sin cambiar el total anual.

**Se guardan las dos, y la principal es `casos_ocurrencia` (por `SEMANA`).**
- `casos_ocurrencia` es lo que publica el INS y **lo único que empalma con 2026**: el 006
  solo da la semana del INS. El 356 de 2025 coincide con el tablero en 43 de 53 semanas con
  la semana de `SEMANA` (r = 0,990), y en 4 con la de notificación.
- `casos_ocurrencia_semana_consulta` tiene **una definición fija en todos los años**: la de
  la fecha de consulta, que es la más cercana al momento en que la persona llega a
  urgencias. Suma sobre todos los archivos del evento, así que recoge también los casos que
  consultaron un año y se notificaron el siguiente. Los totales anuales difieren en 0-8
  casos. La correlación semanal con `casos_ocurrencia` es ≥ 0,9 donde `SEMANA` ya es de
  consulta o de inicio, pero baja a 0,07-0,45 en 155, 549 (2015), 620 y 850. Para analizar
  el histórico es la que no tiene escalón; para 2026 no existe.

## Auditoría por evento, Manizales (ocurrencia)

Casos por año (2015 → 2025) y semanas con ≥ 1 caso. Todos los archivos: 69 columnas, 0
semanas fuera de rango y 0 filas de otro año, **salvo el 349**: 1 fila de 2015, 1 de 2016, 4
de 2018, 1 de 2019 y 1 de 2020 traen otro año y se descartan.

| Evento | Casos por año | Semanas con casos | Escalones evidentes |
|---|---|---|---|
| 300 | 1.281 · 1.304 · 1.326 · 1.265 · 1.286 · **984** · 1.069 · 1.163 · 1.364 · 1.345 · 1.555 | 52/52 todos | Pandemia 2020 (−23 %) |
| 875 | 881 · 893 · 943 · 991 · 953 · 830 · 887 · 1.060 · 1.255 · 1.308 · 1.332 | 52/52 todos | Sube +51 % desde 2021. Máx. semanal de 68 en 2018 |
| 356 | — · 368 · 422 · 511 · 619 · 493 · 546 · 618 · 703 · 596 · 566 | 50/52 en 2016, luego todas | Existe desde 2016; crece hasta 2023 |
| 365 | 767 · 971 · 833 · 603 · 502 · 379 · 423 · 447 · 548 · 510 · 444 | todas | **Arrastrado por 414**: 399 · 565 · 371 · 194 · 81 · 52… (−93 % entre 2016 y 2021). Probablemente cambio de definición o notificación [I] |
| 370 | 239 → 419 (2023) → 325 | 51-53 | Suave |
| 549 | 66 · 45 · 76 · 90 · 89 · **183 · 266** · 265 · 247 · 251 · 253 | 28-43, luego 51-52 | **Escalón 2020-2021 (×3)**; en el país, 23.879 → 30.149 filas |
| 831 | **1.316** · 1.089 · 611 · 668 · 328 · **110** · 114 · 224 · 222 · 211 · 237 | 52, luego 36-52 | Caída ×12 hasta 2020: vacunación y pandemia [I] |
| 155 | — · 40 · 143 · 189 · 286 · 180 · 287 · **(2022 no publicado)** · 248 · 216 · 200 | 21 en 2016, luego 45-49 | Arranque 2016-2017; hueco en 2022 |
| 850 | 105 → 207 (2023) → 170 | 44-53 | Suave |
| 813 / 820 | 104 / 82 → 62 / 51 (2020) → 170 / 155 (2024) | 36-50 | Pandemia 2020 |
| 346 | 202 · 20 | 30 y 16 | Solo 2024-2025 |
| 113 | — · 8 · 35 · 44 · 36 · 15 · 29 · 36 · **105** · 81 · 49 | 6 en 2016; 12-41 | Arranque 2016; salto ×2,9 en 2023 |
| 620 | 53 · 58 · 62 · **328** · 83 · 25 · 41 · 57 · 63 · 53 · 47 | 18-49 | Brote de 2018 (máx. 28 por semana) |
| 348 | 23 · 28 · 18 · 8 · 4 · 45 · 1 · **363 · 164** · 5 · 17 | 1-45 | En 2022-2023 la ficha absorbió COVID (107.290 filas en el país) |
| 452 | 13 · 20 · 21 · 5 · 16 · 13 · 8 · 6 · 14 · 22 · 25 | 3-12 | Semanas de diciembre-enero |
| 349 | 0 · 2 · 2 · 3 · 3 · 1 · 3 · 3 · 5 · 7 · 10 brotes | 0-9 | Cambio de ficha en 2018 |

## Power BI: la vía de 2026

**Qué se congela** (`powerbi.py`, una carpeta por día, **nunca se sobrescribe** salvo con
`--rehacer`):

| Archivo | Tablero · tabla | Contenido | Cobertura el 2026-09-28 |
|---|---|---|---|
| `rutinaria_manizales.csv` | 006 · `Rutinaria {año}` | `SUM(conteo)` por evento × semana, `Cod_municipio = 17001` | 2026, SE1-38, 28 eventos, 3.747 casos |
| `ira_995_rutinaria.csv` | 006 · `salida_para_rutinaria_995 {año}` | Sumas de IRA, todas las causas, IRAG y UCI | 2026, 37 semanas |
| `ira_995_tablero.csv` | 995 · `IRA` | Sumas de `grupo_1..7`, `grup_total`, `Tot_1..7`, `Tot_tot` | 2015-2019 y 2021-2026 (**sin 2020**) |
| `evento_{300,356,831,875}.csv` | uno por evento | Medida `Calculos[Casos]` por año × semana, `CodMun = 17001` | 300: 2022-2026 · 356: 2016- · 831: 2007- · 875: 2017- |
| `metadatos.json` | | Clave, tabla, refresco del INS y la consulta enviada | 006: 26-sep 22:04 |

La clave de cada tablero se lee **en cada corrida** de `MenuReporteNivel2` (37 tableros), y
el nombre de la tabla con año, de `conceptualschema`. **Privacidad:** `consulta_agregada()`
solo deja agrupar por año, semana y código o nombre de evento. Todo lo demás va sumado o
como filtro, y ninguna consulta pide una columna de persona. Los modelos de 365 y 549 exponen
`num_ide_`, `edad_` y otras; solo se leyeron sus nombres. Por qué 365 y 549 no se congelan
por evento: su modelo no tiene `Calendario × Municipio[CodMun] × Calculos[Casos]`, y 549
filtra por residencia (`CodMunR`).

**Dos trampas de la API.** La tabla `Fechas` del 875 empieza en el año 987: sin un corte
(`desde_anio`), la respuesta son mil años de ceros y se trunca. Y las tablas de calendario
rellenan con 0 años y semanas futuras (300 devolvía 2007-2028); se quitan los años sin casos
y las semanas posteriores al refresco. Además, la consulta falla si se llena la ventana de
filas: no se acepta una respuesta truncada en silencio.

**Versionado: sí**, con excepción comentada en `.gitignore`. Son agregados sin persona, y
lo que el tablero decía en cada fecha no se puede recuperar después: las 2-3 últimas semanas
se reescriben con la notificación tardía. `powerbi.rutinaria_largo()` convierte una descarga
al formato largo del proyecto (`variable = casos_ocurrencia`, ceros incluidos, columna
`descarga` con la fecha).

### Empalme: tablero contra microdatos

**Eventos individuales, Manizales.** Casos por año, tablero contra microdatos por ocurrencia:

| Evento | 2022 | 2023 | 2024 | 2025 | 2025 semana a semana |
|---|---|---|---|---|---|
| 356 | 612 / 618 | 711 / 703 | 601 / 596 | 575 / 566 (+1,6 %) | 43 de 53 iguales, r = 0,990 |
| 875 | 1.063 / 1.060 | 1.274 / 1.255 | 1.313 / 1.308 | 1.328 / 1.332 (−0,3 %) | 40 de 53 iguales, r = 0,965 |
| 831 | 227 / 224 | 220 / 222 | 214 / 211 | 236 / 237 (−0,4 %) | 10 de 53, r = 0,673 |
| 300 | 1.149 / 1.163 | 1.362 / 1.364 | **1.233 / 1.345 (−8,3 %)** | 1.538 / 1.555 (−1,1 %) | 9 de 53, r = 0,805 |

- **En el total anual empalman**: ±2 % por ocurrencia, salvo **300 de 2024 (−8,3 %)**, que
  no tiene explicación. 356 de 2016, 2017 y 2019 es idéntico; 831 de 2015-2025, dentro del
  ±3,5 %.
- **875 de 2017** da 3 en el tablero contra 943 en los microdatos: el tablero no tiene ese
  año.
- **Semana a semana no empalman en 300 y 831.** Diagnóstico sobre 2025: el tablero agrupa
  por la semana de **notificación** (300: 51 de 53 semanas iguales, r = 0,973; 831: 52 de
  53, r = 0,999). En cambio, la `SEMANA` de esos eventos es la de inicio de síntomas. En 356
  y 875 el tablero coincide con `SEMANA`.
- **Consecuencia:** los tableros por evento **no tienen una definición única de semana**.
  El 006 contra el tablero de cada evento en 2026: 356 casi idéntico (36 de 38 semanas),
  875 con r = 0,26 semanal pese a totales iguales (901 / 902). Así que el 006 tampoco agrupa
  siempre como el tablero por evento. **Qué semana usa el 006 no está verificado**: no tiene
  2025 para medirlo contra los microdatos.

**995 (IRA), tablero contra microdatos, Manizales:** el tablero va **siempre por encima**,
IRA +3,4 a +7,9 % y todas las causas +4,5 a +9,7 %, en todos los años. Semana a semana,
r = 0,999 pero 0 de 53 semanas iguales: **es un nivel, no un desfase**. Probablemente el
tablero cuenta por `cod_mun` y no por el código de la UPGD, o no deduplica [I]. En 2026, la
tabla 995 del 006 (40.596 IRA) queda un 4,8 % por debajo del tablero 995 (42.623).

**Para empalmar 2026 con la historia:** los conteos individuales se pueden unir en total,
con un error del ±2 %. Semana a semana, antes hay que fijar qué semana usa el 006 y comparar
con la columna equivalente de los microdatos. Esto es posible cuando salgan los microdatos
de 2026, contra las instantáneas congeladas. El 995 necesita un factor de nivel por año, o
usar la proporción, que ya es cociente.

## Pendientes de esta parte

- Congelar una descarga **cada semana** (hoy hay una, la del 2026-09-28). No hay tarea
  programada.
- Qué semana agrupa el 006, por evento.
- El −8,3 % del 300 de 2024 y el nivel +4-8 % del 995 en el tablero.
- 155 de 2022 no está en el portal.
- El 998 del 006 (`Salida_para_rutinaria_998 2026`) no se descargó: el municipio de
  procedencia no se validó.
- Umbral en el límite: 620 entra con 1,04; 414, 735 y 750 quedan fuera con 0,94-0,96.
