# Contexto — la bitácora de decisiones

**Este archivo solo crece.** Nada se borra. Una decisión que se revierte se marca como
revertida y se añade la nueva entrada debajo, con el motivo del cambio. El historial de por
qué se cambió de idea vale tanto como la idea: es lo único que evita volver a discutir lo
mismo dentro de tres meses.

Regla 9 de `CLAUDE.md`. Cada entrada lleva **fecha, qué se decidió, por qué y con qué
evidencia**. El «por qué» es el campo que importa: lo que se puede reconstruir leyendo el
código no hace falta guardarlo aquí; lo que no, se pierde al cerrar la sesión.

Para saber **dónde está todo ahora mismo**, este archivo no sirve — es historia. Eso está en
`docs/HANDOFF.md`.

---

## 2026-10-16 (correcciones) — Ni M3s-r ni M3s-rs mejoran a M3s en 2025: la operación no cambia

**Preregistro:** fila `m3s_correcciones_red_salud`, escrita antes de calcular ningún modelo y después de medir el
rezago (entrada «(rezago)», debajo). Código en `notebooks/validacion_anual.py`; resultados en
`salidas/pronostico/correcciones_red_salud/` (`tabla_principal.csv`, `regla.json`, `diebold_mariano.csv`,
`por_mes.csv`, `por_estado.csv`, `rho_2025.json`).

**Qué se probó.**
- **M3s-r:** M3s sin las cinco columnas de red que se calculan con el triage del SES (`ext_g_m_red_peso_*`,
  `cambio_*`, `herfindahl`). La resolución de la Supersalud se queda sin compuerta, como `ext_m_red_resolucion_nueva_eps_30d`.
- **M3s-rs:** M3s-r con la salud pública, y su compuerta, leídas 1 semana más tarde.
- Las dos son experimentos nuevos (`m3s_r`, `m3s_rs`) y combos nuevos (`M3s-r`, `M3s-rs`, en `semana.DIAGNOSTICO`).
  Su SARIMAX es el de M3s: se comprobó que sus exógenas son idénticas. El rezago entra como parámetro del experimento
  (`rezago_salud`, por `indices.salud_con_rezago`); el valor por defecto sigue en 0.

**Comprobaciones antes de lanzar.**
- **Reproducción:** con el código ya cambiado, M3s y C0r reproducen **exactamente** (diferencia 0,0) los 21 primeros
  días `q*_sin_red` de las corridas `2026-10-14_M3s` y `2026-10-14_C0r`.
- **Inyección** (LightGBM entrenado una vez en el origen 14-10 y el contexto cambiado después, como en «(reacción)»):

  | Escenario | M3s | M3s-r | M3s-rs |
  |---|---|---|---|
  | control sin cambio | 0 | 0 | 0 |
  | compuerta de red encendida en el origen | 21 de 21 días cambian (Δq50 de −5,0 a +6,5 %) | **0 exacto** | **0 exacto** |
  | red con los valores de julio + compuerta | −2,5 % de media | **0 exacto** | **0 exacto** |
  | red extrema desde el 01-09 + compuerta | 21 días cambian | **0 exacto** | **0 exacto** |
  | resolución encendida (compuerta apagada) | 0 (la compuerta la anula) | **−0,43 %** (de −1,3 a +0,2) | −0,54 % |

  M3s-r ya no responde a la red calculada con el triage y sí a la resolución.
- **Rezago:** con `rezago_salud = 1`, las columnas de salud y su compuerta son exactamente las de M3s desplazadas
  7 días (diferencia 0); el resto del contexto no cambia.

**Resultado, versión b (como se entrega), MAPE y rango del 80 %:**

| Año | Adelanto | C0r | M3s | M3s-r | M3s-rs |
|---|---|---|---|---|---|
| 2025 | 1-7 | 8,49 % · 82,1 % | **8,08 % · 79,9 %** | 8,09 % · 79,7 % | 8,16 % · 80,8 % |
| 2025 | 15-21 | 10,29 % · 85,4 % | 10,06 % · 82,1 % | 10,01 % · 81,3 % | 9,95 % · 81,6 % |
| 2026 | 1-7 | 8,51 % · 82,5 % | 8,57 % · 80,4 % | 8,57 % · 80,0 % | 8,58 % · 80,0 % |
| 2026 | 15-21 | 10,53 % · 79,7 % | 10,45 % · 78,2 % | 10,45 % · 76,7 % | 10,49 % · 76,7 % |

La tabla entera, con las versiones a y b, mediana, sesgo, error semanal y acierto, está en `tabla_principal.csv`.

**Regla.**
- **Elección con 2025 (1-7, b):** M3s-r +0,015 puntos de MAPE y −0,27 de cobertura; M3s-rs +0,087 y +0,82. Hacía falta
  bajar más de 0,1 puntos. **Ninguna mejora a M3s, así que no se elige ninguna.**
- **2026, solo informativo:** ninguna empeora. Frente a M3s: −0,002 y +0,008 puntos. Frente a C0r: +0,06 y +0,07 puntos,
  con −2,5 puntos de cobertura.
- **Veredicto: no pasa ninguna. La operación no cambia** (M3s principal, C0r de vara) y `operacion/` no se tocó.

**Diebold-Mariano (HLN, pérdida APE, versión b):**
- 2025, 1-7: M3s-r − M3s p = 0,75; M3s-rs − M3s p = 0,20; M3s-rs − M3s-r p = 0,11. **M3s − C0r: −0,41 puntos, p = 0,012.**
- 2025, 15-21: M3s-r − M3s p = 0,40; M3s-rs − M3s p = 0,14.
- 2026: ningún par baja de p = 0,45 (1-7) ni de p = 0,08 (15-21; M3s-rs − M3s-r).

**Dónde (1-7, b; diferencia de MAPE de M3s-r frente a M3s por estado del día, partición exclusiva):**
- **2025:** todo cerca de cero. Calendario +0,07 (89 días), red −0,01 (91), normal 0,00 (177), salud −0,12 (7).
- **2026:**
  - red −0,10 (131 días), con julio de 8,82 a 8,40 %. Ahí la red de dentro sí restaba, como se esperaba;
  - calendario −0,11 (31);
  - normal +0,08 (96);
  - **sismo +0,41** (22): sin la red, M3s pierde un apoyo para los días del terremoto, y se come la ganancia de julio.
- **La salud con rezago** cuesta en 2025 a 1-7: +0,07 frente a M3s-r, sobre todo en el calendario (+0,08) y en los días de
  red (+0,16). A 15-21 gana un poco (−0,06, p = 0,15). La compuerta de salud se encendió 7 días en 2025 y 0 en 2026.

**Lectura.**
- **Sacar la red de dentro de M3s es neutro en el total.** El daño de julio de 2026 era real, y M3s-r lo corrige, pero
  esas mismas columnas ayudaban en otros tramos. Los +0,13 puntos que la validación de 2026 atribuía a «las columnas de
  estado» no eran de la red sola.
- **El rezago de la salud no se puede juzgar con esta validación.** Aquí la salud se lee de semanas ya completas (los
  microdatos de 2025 y la foto del 15-10 para 2026), así que la prueba solo mide el coste de leer información una
  semana más vieja, y es pequeño. El beneficio esperado, no leer una semana a medias en la operación real, no aparece
  porque en estos datos esa semana ya está completa. **El hallazgo operativo del 16-10 sigue sin corregir:** el lunes,
  M3s lee una semana que en la foto llega a medias.
- **Hallazgo lateral:** con reajuste semanal, M3s gana a C0r en 2025 a 1-7 (8,08 % frente a 8,49 %, p = 0,012). En 2026
  empatan (p = 0,61). 2025 es el año con el que se eligió M3s, así que no es prueba de superioridad.

**Rho de la cópula medido en 2025** (`semana.resumen_validacion`, versión a, reajuste 1 y 4):
- M3s 0,302 (1) y 0,474 (15); C0r 0,321 y 0,489. Los de `operacion.RHO` son 0,318, 0,473, 0,337 y 0,487.
- M3s-r 0,305 y 0,467; M3s-rs 0,302 y 0,467.
- No se usan: ninguna variante pasa.

**Tiempos:**
- reproducción: 4 min; inyección: 3 min;
- un origen a 1-7: 101-137 s en 2025 (4 combos) y 60-84 s en 2026 (2 combos);
- 2025: 1-7 en 1 h 42 min, 15-21 en 30 min; 2026: 1-7 en 44 min, 15-21 en 12 min;
- total: 3 h 9 min (de 10:22 a 13:31). No hizo falta recortar 15-21.

**Decisión: no se cambia nada en la operación.** `M3s-r` y `M3s-rs` quedan como experimentos de diagnóstico. Lo que
queda abierto, para el propietario:
1. corregir la lectura de la semana a medias **sin cambiar el modelo**: es un problema de datos de la operación, no de
   lo que aprende M3s. Por ejemplo, no usar en el origen una semana con menos del 90 % de su valor esperado. Exige una
   fila propia;
2. la catástrofe por fecha del evento (propuesta 1 de «(reacción)»), que es donde M3s-r pierde.

---

## 2026-10-16 (rezago) — La salud pública del Power BI se lee con 1 semana de rezago: la semana que acaba la víspera trae el 0-17 % de la IRA

Primera parte del encargo de la entrada siguiente («Dos correcciones de M3s»). Se mide **antes** de escribir el
preregistro `m3s_correcciones_red_salud`, que usa este número.

**Método.** Con las tres fotos del Power BI del INS (28-09, 05-10 y 15-10) se toma, para cada familia operativa
(`indices.FAMILIAS_OPERATIVAS`), la suma de los conteos crudos de sus series (la respiratoria: IRA total, 0-4 y 60+;
violencias: 875 y 300; salud mental: 356 y 365; materno: 549; inmunoprevenibles: 831). La fracción es el valor de cada
semana en la foto del 28-09 o del 05-10 dividido por su valor en la del 15-10. **Edad** = semanas completas entre el
sábado en que acaba la semana y la foto (0 = acabó en los 7 días previos). Script en el scratchpad de la sesión
(`correcciones/rezago.py`).

**Resultado** (fracción mínima de las dos fotos):

| Familia | edad 0 | edad 1 | edad 2 | edad 3 | edad 4 |
|---|---|---|---|---|---|
| respiratoria | **0,00** (28-09: la SE38 no estaba) y 0,14 | **1,00** | 1,00 | 1,00 | 1,00 |
| violencias y agresiones | 0,62 | 1,00 | 0,99 | 1,00 | 1,00 |
| materno-perinatal | 0,00 | 1,00 | 1,00 | 1,00 | 1,00 |
| inmunoprevenibles | 0,13 | 1,00 | 1,00 | 1,00 | 1,00 |
| salud mental e intoxicaciones | 0,09 | 0,875 | 0,875 | 0,889 | 1,00 (y 1,06) |

**Rezago = 1 semana.** Es la menor edad con al menos el 90 % en la respiratoria, violencias, materno-perinatal e
inmunoprevenibles. **La salud mental se declara ruidosa y no decide:** son unos 20 casos por semana, la diferencia es
de 2 o 3 casos y las revisiones van en los dos sentidos hasta la edad 4 (1,06 y 1,10 en la serie 356). No es un retraso
que se cierre con la edad.

**Lectura.** `indices.contexto_holistico` lee, para cada día, la semana que acabó el sábado anterior: en el origen de
la operación (domingo) es una semana de edad 0, que en la respiratoria trae del 0 al 17 % de lo que acabará teniendo.
Con 1 semana de rezago se lee la de edad 1, que ya está completa en todas las familias que deciden.

**Límites.**
- Son dos mediciones por edad, y la foto de referencia es solo 10 días más reciente. La SE39 tiene edad 1 en la foto
  del 15-10, así que su fracción a edad 0 se mide contra una referencia que podría crecer algo más.
- El tablero de IRA de la foto del 28-09 no traía la SE38 (fracción 0). Es decir, la semana de edad 0 puede faltar
  entera.

---

## 2026-10-16 — Dos correcciones de M3s, razonadas antes de calcular: la red sale del modelo y la salud lee la última semana completa

**Pedido del propietario:** avanzar con lo que señalan la prueba de reacción y la validación de 2026, sin ensayo y
error. Por eso el porqué de cada cambio se escribe aquí antes de cualquier cálculo.

**(1) Las columnas de red salen de dentro de M3s.**
- **Mecanismo.** Cuando el SES cierra el convenio con Nueva EPS, sus afiliados consultan en otro sitio y el triage del
  SES baja. La causa externa es el **estado del convenio**.
- **El problema de las columnas actuales.** `ext_g_m_red_*` (peso y cambio de Nueva EPS y de SURA a 28 días,
  Herfindahl) no miden ese estado: se calculan **con el propio triage del SES**. Son una función rezagada del
  desenlace, no una causa externa. Al predecir, una caída reciente de Nueva EPS en la mezcla se parece a lo que
  sigue a cualquier bache, que es volver al nivel (reversión a la media). Eso explica el signo invertido medido en la
  prueba de reacción (+2 % con los valores de julio, cuando el total cayó un 19 %).
- **Lo que sí mide el mecanismo** es la corrección v2, que va fuera del modelo. Usa el estado del convenio medido con
  los ingresos no urgentes y los anuncios, y pasó su regla el 14-10. Tener las dos cosas cuenta la red dos veces, una
  de ellas al revés.
- **Evidencia que lo respalda:**
  - prueba de reacción: +2,1 % con los valores de julio;
  - validación de 2026: las columnas de estado cuestan +0,13 puntos, sobre todo en los días con la red encendida y en
    julio.
- **Se queda** la resolución de la Supersalud sobre Nueva EPS (`ext_g_m_red_resolucion_nueva_eps_30d`), que sí es
  externa. Va sin compuerta de red, porque esa compuerta también se calcula con el triage.

**(2) La salud pública lee la última semana epidemiológica completa.**
- `indices.contexto_holistico` toma la semana que terminó la víspera. En la foto del Power BI esa semana está a
  medias, por la notificación tardía: la SE39 de la foto del 05-10 traía 154 consultas de IRA frente a 935 completas,
  y el índice cae unas 5 desviaciones.
- En la operación real eso ocultaría justo una ola en curso.
- El retraso de notificación al SIVIGILA es un rasgo conocido de la vigilancia en salud pública. El rezago correcto
  se **mide** con las tres fotos (28-09, 05-10 y 15-10): es la menor edad a la que una semana alcanza el 90 % de su
  valor en la foto más reciente.
- Se aplica igual al entrenar y al predecir, para que el modelo aprenda con el mismo rezago con el que opera.

**Diseño de la prueba** (preregistro `m3s_correcciones_red_salud`):
- variantes: M3s-r (sin red) y M3s-rs (sin red y con la salud con el rezago medido);
- se elige con **2025** y se confirma con **2026**;
- solo entra en la operación si en 2025 mejora a M3s por la regla y en 2026 no empeora frente a C0r ni frente a M3s.

---

## 2026-10-16 — Validación de 2026 de la operación semanal: M3s se mantiene frente a C0r; lo que le resta es la red y el sismo

**Pregunta del propietario:** con datos reales de 2026, ¿la operación con M3s, que reentrena cada semana con el contexto
del momento, mejora, se mantiene o empeora frente a C0r? Si empeora, ¿qué factor lo causa?

**Preregistro:** fila `validacion_2026_operacion_semanal`, escrita el 2026-10-15 antes de calcular. Código en
`notebooks/validacion_2026.py`; resultados en `salidas/pronostico/validacion_2026/`.

**Diseño:**
- **Orígenes:** todos los domingos de 2026. Datos hasta el 14-10 (`pr.FIN = indices.FIN_RED = 2026-10-14`).
  - Adelanto 1-7: 40 orígenes, se reentrena cada domingo, igual que la operación.
  - Adelanto 15-21: 38 orígenes, se reentrena cada 4 domingos, por coste.
- **SARIMAX** arranca de cero en cada reentreno, como la operación.
- **Foto del Power BI** fija en la del 15-10, para que la tarea diaria no la cambiara a mitad del cálculo.
- **Dos versiones:**
  - (a) el modelo solo;
  - (b) como se entrega: red v2 con `tau = origen` y rango W tras quiebre.
- **M3cal**, solo diagnóstico: M3s con los 4 mecanismos de calendario y sin columnas de estado. Experimento `m3cal`
  y combo `M3cal`, fuera del valor por defecto de `semana.validar`.

**Reproducción:** el código de la validación reproduce **exactamente** (diferencia 0,0) los 21 primeros días
`q*_sin_red` de las corridas guardadas `2026-10-14_M3s` y `2026-10-14_C0r`.

**Resultado (versión b, la que se entrega):**

| | MAPE 1-7 | rango 80 % 1-7 | sesgo 1-7 | error semanal 1-7 | MAPE 15-21 | rango 80 % 15-21 |
|---|---|---|---|---|---|---|
| C0r | 8,51 % | 82,5 % | +0,9 % | 5,07 % | 10,53 % | 79,7 % |
| M3s | 8,57 % | 80,4 % | +1,1 % | 5,24 % | 10,45 % | 78,2 % |
| M3cal (diagnóstico) | 8,44 % | 80,4 % | +1,0 % | 5,17 % | 10,40 % | 78,2 % |

- **Regla, a 1-7 días: SE MANTIENE.** La diferencia de MAPE de M3s frente a C0r es de +0,06 puntos y la cobertura cae
  2,1 puntos; los umbrales eran ±0,5 y −5. A 15-21 días, que no decide: −0,08 puntos y −1,5 puntos de cobertura.
- **Diebold-Mariano con la corrección HLN:** ninguna diferencia se distingue del ruido.
  - M3s frente a C0r: p = 0,60 (1-7) y p = 0,78 (15-21);
  - M3cal frente a C0r: p = 0,47 (1-7);
  - M3s frente a M3cal: p = 0,11 (1-7; con varianza de Bartlett, p = 0,21).
- **La versión b mejora a todos:** C0r pasa de 8,85 a 8,51 % (1-7) y de 11,07 a 10,53 % (15-21), y la cobertura sube de
  81,1 a 82,5 % y de 75,6 a 79,7 %. Hay 124 días con factor de red y 3 orígenes con quiebre.

**Dónde gana y dónde pierde M3s (1-7, versión b).** La contribución de cada estado suma la diferencia total. La parte
de «estado» es M3s − M3cal; la de «calendario y entrenamiento» es M3cal − C0r.

| Estado del día (partición exclusiva) | días | M3s − C0r | por las columnas de estado | por el calendario y el entrenamiento |
|---|---|---|---|---|
| sismo (0-21 días después del 10-08) | 22 | **+0,064** | +0,046 | +0,017 |
| compuerta de red encendida en el origen | 131 | **+0,042** | +0,047 | −0,006 |
| calendario (fiesta lejana, Feria) | 31 | −0,020 | +0,001 | −0,022 |
| normal | 96 | −0,022 | +0,036 | −0,058 |
| **total** | 280 | **+0,062** | **+0,130** | **−0,068** |

- **El calendario ayuda poco pero en la buena dirección:** en sus días, 8,97 % frente a 9,16 %. En 2026 casi no hubo
  noches festivas ni Feria (31 días, 28 de ellos de fiesta lejana).
- **Las columnas de estado restan 0,13 puntos.**
  - Casi todo sale de **julio**, con el cierre del SES a Nueva EPS: M3s 8,82 %, C0r 7,79 %, M3cal 8,09 %.
  - También de **agosto**, con el sismo y la reapertura: M3s 14,13 %, C0r 13,63 %.
  - Coincide con lo visto en la prueba de reacción: la red de dentro de M3s tiene el signo invertido, y la catástrofe
    se congela en el origen.
- **La compuerta de salud y la social no se encendieron ningún día de 2026.** No pueden ser culpables por la predicción;
  como mucho, por el entrenamiento.
- **El rango de M3s es más estrecho** (27,1 % frente a 28,7 % del q50) y cubre menos: −2,1 puntos.
- **A 15-21 días** M3s gana en los días normales (−0,25) y pierde en los de red (+0,18). Esa pérdida no viene de sus
  columnas de red (M3s − M3cal = −0,03), sino del entrenamiento sin la COVID fuerte (M3cal − C0r = +0,20).

**Vintage** (el contexto se leyó de los archivos de hoy):
- **Power BI del INS:**
  - Las revisiones entre fotos son mínimas: en las semanas comunes, |Δ| medio de 0 a 0,03 desviaciones, salvo salud
    mental (hasta 0,33 en semanas sueltas).
  - La latencia es de 1-2 semanas: el 28-09 la última semana completa de IRA era la SE37, que acabó el 12-09.
  - Con las 3 fotos y con una semana más de retraso, la compuerta de salud queda apagada todo 2026: 0 cambios de estado.
  - M3s_vint (salud una semana más tarde) frente a M3s: −0,03 puntos (p = 0,37). **Optimismo por esta vía: nulo.**
- **Calendario de fiestas:** el archivo es del 29-09, a posteriori. Antes del sismo estaban programadas Aguadas (14-16
  ago), Samaná (14-17) y Anserma (14-18), que luego se aplazaron o cancelaron.
  - Con el +3,4 % de la fiesta lejana en esos días (3 a 1-7 y 8 a 15-21), M3s − C0r pasa de +0,06 a **+0,11** (1-7) y
    de −0,08 a +0,02 (15-21).
  - Es el único optimismo medible, y no cambia el veredicto.
- **Registro de la red** (`datos/eventos_red.csv`): filtra por `fecha_anuncio <= tau`, pero se escribió a posteriori.
  Afecta igual a los tres modelos de la versión b.

**Hallazgo operativo, no corregido.** La corrida del lunes lee la semana epidemiológica que acaba la víspera. En la foto
del 05-10 esa semana (SE39) estaba **a medias**: 154 consultas de IRA frente a 935 completas, un índice 5 desviaciones
más bajo. Hoy no cambia nada, porque la compuerta sigue apagada, pero en una ola real la ocultaría. Lo correcto sería leer
la última semana **completa**.

**Decisión: no se cambia la operación.** M3s sigue de principal y C0r de vara, con su regla de vuelta atrás a 84 días.
M3cal no se promueve: es diagnóstico sobre el año de prueba, y elegirlo con 2026 sería selección. Su ventaja frente a M3s
(−0,13) no se separa del ruido. Queda para el propietario la propuesta 2 de la entrada «(reacción)»: sacar la red de
dentro de M3s y dejarla solo en la corrección v2. Es la que estos números señalan, y exige una fila nueva y validación
sobre 2025.

**Tiempos:**
- reproducción: 4 min;
- un origen a 1-7 días con 4 modelos: 145-175 s;
- bloque 1-7: ~1,9 h; bloque 15-21: ~26 min;
- total de la corrida: 2 h 14 min (15-10, de 14:26 a 16:40).

---

## 2026-10-15 (reacción) — M3s reacciona bien al calendario; salud, red y catástrofe no se comportan como mecanismos

**Pregunta del propietario:** ¿se verificó que el modelo toma los datos externos actuales y los usa con lo aprendido?
Las columnas y la ausencia de fuga ya estaban probadas; faltaba probar que la predicción **reacciona**.

**Método.**
- Se entrena M3s una vez (origen 2026-10-14). Coincide exactamente con la corrida guardada en `*_sin_red`.
- Para cada escenario se modifica la salida real de `mecanismos.columnas`, se reconstruyen los modelos con el código
  real y se les trasplantan los parámetros entrenados. Así el modelo queda idéntico y solo cambia el contexto que ve.
- El control sin cambios da 0 exacto.
- Scripts en el scratchpad de la sesión (`reaccion/`); los números quedan aquí.

**Resultado** (Δ del valor central frente a la base):

| Escenario | Efecto | ¿Solo en sus días? |
|---|---|---|
| Quitar las fiestas lejanas del 27-oct al 5-nov | −2,6 % | sí: 10 de 10 días, el resto en 0 exacto |
| Añadir la Feria del 2 al 6 de noviembre | +2,7 % | sí: 5 de 5 días |
| Encender la compuerta de salud | +2,2 % en todo el horizonte, **igual con una ola de +2 que con −2** | no hay dosis |
| Red con los valores de julio de 2026 | **+2,1 %**, cuando el total real cayó un 19 % | dirección contraria |
| Terremoto el día antes del origen | −11 % el día 1, pero +3 a +5 % en los días 22-45 | no se propaga como dice su definición |
| Social (MinDefensa) | 0: NaN en el origen; con el máximo real, +0,06 % | factor muerto |

**Coeficientes aprendidos (SARIMAX):**
- noche festiva −22 % (IC −26 a −18);
- día siguiente +10 % (+5 a +15);
- fiesta lejana +3,4 % (+1,5 a +5,3);
- Feria +2,2 % (−2,5 a +7,2);
- catástrofe en la semana 1, −8 % (−18 a +3).

En el LightGBM, las columnas de mecanismo suman el 9,6 % de la importancia.

**Lectura.**
- **El calendario funciona como mecanismo:** dirección, tamaño y días correctos.
- **Las variables de estado no:** salud (sin dosis: actúa como marcador de época), red (signo invertido),
  catástrofe (congelada en el origen; con n = 1 evento, el coeficiente mide el rebote) y social (sin dato).
- Todo lo que no es calendario se congela en el valor del origen y se aplica igual a los 78 días.
- La predicción guardada no se entera de un cambio externo hasta la corrida siguiente, que hoy es semanal.

**Decisión: no se cambia nada todavía.** Cualquier corrección es un cambio de modelo que exige preregistro y
validación de origen rodante. Las propuestas, para el propietario:
1. la catástrofe por fecha del evento (los días desde el sismo se conocen en el origen), no como estado congelado;
2. quitar la red de dentro de M3s y dejarla solo en la corrección v2 externa, que sí pasó su regla;
3. la salud con dosis y sin compuerta, o fuera del modelo;
4. lo social, fuera;
5. predecir a diario, para que el estado del entorno se refresque cada día.

---

## 2026-10-15 (cierre) — Dos correcciones del orquestador al integrar, y verificación de punta a punta

**(1) La red de M3s estaba congelada en el 20-sep.** `notebooks/indices.red_diaria` tenía `fin="2026-09-20"` fijo, y
`regimenes_diarios` lo acotaba igual. Las columnas `ext_g_m_red_*` y `crisis_red` no avanzaban con la extracción y
valían 0 desde el 21-oct (fin del `ffill` de 30 días).
- **Arreglo:** `indices.FIN_RED`, que vale el 2026-09-20 por defecto para que los cuadernos publicados no cambien.
  `operacion._preparar` lo fija en el origen, lo que además evita la fuga, y `contexto/diario.py` en el último día
  completo.
- **Medido:** el contexto diario ya mueve la red hasta el 14-oct (cambio de Nueva EPS 0,289 → 0,044; `crisis_red`
  pasa a 0 el 15-oct).
- La corrida M3s hecha antes del arreglo se descartó y se rehízo.

**(2) Un dato tardío dejaba filas incoherentes en el clima unificado.** El modo incremental (`fusionar`, que rellena
celdas vacías) metía el pluviómetro IDEAM que llegó tarde en la columna cruda sin recalcular el consenso. Por ejemplo,
el 13-sep: pluviómetro 41,4 mm y consenso 4,1.
- **Arreglo:** un día del pasado al que le llega un dato tardío se recalcula entero, como la cola, hasta 120 días
  atrás (`LLEGADA_TARDIA_MAX`). Más atrás no se toca nada.
- **Medido:**
  - cambian solo las filas del 25-ago al 04-oct;
  - los 50 días nuevos entran al consenso con pluviómetro, sin ninguna falla;
  - 0 filas incoherentes;
  - una segunda corrida no toca el archivo.

**Verificación de punta a punta (15-oct):**
- `python -m contexto --todo --sin-hospital`: código 0 en 131 s. Todas las fuentes en verde salvo `mindefensa`
  (amarillo: la fuente publica tarde) y `por_confirmar` (amarillo: 7 fechas para confirmar a mano).
- `python -m operacion` no reentrena si ya existe la corrida de ese origen.
- AppTest del tablero: 0 excepciones.
- **Las tareas de Windows no se registraron.** El clasificador de permisos bloqueó al agente por persistencia. Las
  registra el propietario, con los comandos de `contexto/docs/CONTEXTO_EXTERNO.md`.

---

## 2026-10-15 (operación M3s) — M3s pasa a principal con C0r al lado como vara; regla de vuelta atrás a 12 semanas

**Qué se decidió.** Cumple la decisión de la entrada «El contexto externo se actualiza solo» de este mismo día y
**revierte el punto 2 de la entrada 2026-10-13 (5)** («C0r en producción; M3s como opción»).
- `operacion.MODELO = "M3s"` y `operacion.COMPARACION = "C0r"`. `python -m operacion` entrena los dos en secuencia
  (una sola cosa pesada a la vez), desde el mismo origen, y guarda `<origen>_M3s` y `<origen>_C0r`. Con `--modelo` se
  fuerza uno solo. Si ya existe la corrida de ese origen y modelo, no se reentrena.
- `--ajustar` aplica la red v2 a la última corrida de los dos.
- El semáforo calcula el error y el rango sobre el principal y suma dos señales:
  - **Contexto externo** (lee `salidas/contexto/frescura.csv`): rojo si una fuente que usa M3s está en rojo; amarillo
    si alguna está en amarillo o si está en rojo una que M3s no usa; gris sin el archivo. Entra en el estado general;
  - **Comparación**: M3s frente a C0r en los días comunes. No entra en el estado general que ve urgencias.
- El tablero muestra M3s y, en gris, C0r: una línea discontinua en el mes, el valor de C0r en el detalle del día, una
  columna en las semanas y las filas de los dos en «Qué tan confiable es». La cifra grande del calendario pasa a ser el
  **rango del 80 %**, y el valor central va debajo: urgencias tiene que leer un rango, no una cifra.

**Preregistro, escrito antes de correr M3s:** fila `operacion_m3s_contexto_automatico`.
- **Criterio:** error del día y % en rango con 15-21 días de adelanto, en corridas guardadas antes de que empiece el
  día, sobre los días comunes (mismo origen y dato real).
- **Regla de vuelta atrás:** se evalúa a los 84 días comunes y cada 84 más, sobre todo lo acumulado. Si M3s tiene
  más error del día que C0r, vuelve C0r. Volver a M3s exige una fila nueva.
- **Por qué N = 12 semanas y no 8:**
  - M3s solo difiere de C0r en los días con mecanismo. 8 semanas desde el primer día común (hacia el 27 de octubre)
    acabarían antes de las noches de diciembre y de la Feria de enero;
  - con correlación 0,47 entre días, 84 días equivalen a unos 30 independientes.

  La regla es una salvaguarda, no una prueba de superioridad.

**Corrección del orquestador durante la sesión.** `indices.red_diaria` tenía el fin fijo en el 2026-09-20: las
variables de red de M3s quedaban congeladas en esa fecha. Ahora `operacion._preparar` fija `indices.FIN_RED` en el
origen. La primera corrida `2026-10-12_M3s`, hecha antes del arreglo, **se borró** en la misma sesión (no se había
usado ni versionado) y se rehízo. Como los datos ya llegaban al 14-10, salió el origen 2026-10-14 para los dos.

**Evidencia medida.**
- **Corridas guardadas:** `2026-10-14_M3s` (373 s) y `2026-10-14_C0r` (229 s), horizonte de 78 días. El ciclo completo
  tarda 607 s. Reentrenar C0r con el origen del 12-10 reprodujo la corrida guardada exactamente (diferencia 0).
- **M3s a más de 28 días funciona y no tiene fuga.**
  - `pronostico.EXPERIMENTOS["m3s"]` lleva `semanal=True`, así que `mecanismos.contexto` no exige `H <= 7` y quita el
    clima de rezago corto.
  - Quedan 4 columnas que se leen del día predicho, todas de calendario (Feria, fiesta lejana, noche festiva, día
    siguiente) y 16 que se toman en el origen.
  - Para h = 1, 7, 15, 21, 28, 29, 45, 60 y 78, la fila que se predice no cambia si se altera todo lo posterior al
    origen.
  - Hay 0 NaN y los cuantiles están ordenados en los 78 días.
- **M3s frente a C0r con el mismo origen (14-10).**
  - En los 28 días validados, la diferencia media del valor central es del −0,5 % (media absoluta 1,2 %, máxima 2,9 %).
    Ningún día difiere más de un 10 %. En los 11 días de fiesta lejana (Pensilvania, 27-oct a 5-nov), +0,9 %.
  - Con todo el horizonte, 3 días pasan del 10 %, y los 3 son noches festivas: 7-dic (−16,6 %), 24-dic (−20,1 %) y
    31-dic (−17,9 %). El 26-dic, día siguiente, va un +8,1 %.
  - El rango de M3s es algo más estrecho: 49,7 frente a 53,6 pacientes.
- **Historia reconstruida a 15 días, sin red:** M3s 10,1 % (2025) y 11,3 % (2026); C0r 10,3 % y 11,5 %. Existen los
  conteos de reparto y de aseguradoras de M3s, pero **no los de la red v2 con el rango W**, que solo se reconstruyeron
  con C0r. No se inventaron: el historial de M3s es el del modelo solo, y el tablero lo dice.
- **Tablero:** probado con `AppTest`, 0 excepciones. Se probaron el cambio de mes, el día 24-dic, el año 2025 y el
  cambio de aseguradora.
- **Semáforo al cerrar:** amarillo por «Contexto externo» (clima_ideam, mindefensa y por_confirmar en amarillo).
  «Comparación» está en gris: 0 días comunes. La primera evaluación de la regla cae hacia mediados de enero de 2027.

**Límites.**
- La red v2 y el rango W se validaron solo encima de C0r. Sobre M3s se aplican igual porque los coeficientes no
  dependen del modelo base (se comprobó: los mismos `acceso` 0,1443 y `externos` −0,0102 en los dos), pero no hay una
  validación de M3s con la red.
- Lo reconstruido de M3s en 2025 es el año con el que se eligió.
- La prueba de fuga mira la fila que se predice, no si los índices de salud y de red se normalizan con datos
  posteriores al origen.
- El SARIMAX de M3s avisa de que no converge (`ConvergenceWarning`), igual que en la validación.

---

## 2026-10-15 (orquestador) — `python -m contexto`: frecuencias, umbrales de frescura y una tarea sin ventana y con sesión iniciada

Fase 2 de la entrada «El contexto externo se actualiza solo». Detalle en `contexto/docs/CONTEXTO_EXTERNO.md`.

**Qué se decidió.**
- **16 pasos con frecuencia propia** (diaria, semanal o mensual) según cómo publica cada fuente. Un paso toca si su
  última corrida exitosa tiene al menos esa edad; un fallo no la actualiza, así que **el reintento es la corrida del
  día siguiente**. Si un paso falla, solo se saltan sus dependientes (clima → unificado; sismos → desastres).
- **`ok` o `sin_cambios` se decide por el contenido** de las salidas (sha256 del CSV descomprimido y con las filas
  ordenadas), no por la fecha del archivo. Por qué ordenadas: `actualizar_eventos.py` y `actualizar_fiestas.py`
  reescriben cada uno su parte de `por_confirmar_eventos.csv` y el orden de las filas alterna en cada corrida
  (medido: la huella va A → B → A) sin que cambie nada.
- **Umbrales de frescura por cómo publica cada fuente**, no uno general. Los que no son obvios:
  - `mindefensa`: tolerado 75 días, **aviso 42**, porque M3s lee el dato de hace 42 días (`PUBLICACION_MINDEFENSA`);
  - `enso`: 95, porque la fecha del ONI es el mes central del trimestre;
  - `sismos`: 260, el hueco más largo entre sismos de 2010-2026 (258 días); `desastres` sin umbral, porque en un
    catálogo de eventos raros el atraso no mide frescura;
  - `sivigila`: 640, porque el año Y sale ~8 meses después de cerrarlo;
  - en los calendarios, el umbral es negativo: cobertura mínima hacia adelante (180 días; festivos, 365).
- **La tarea, con la cuenta del usuario y solo con sesión iniciada (`InteractiveToken`), no S4U.** Revierte la
  propuesta de `CAPTURAS.md` (entrada (3)). Por qué: la extracción del hospital usa la autenticación de Windows contra
  SQL Server en red, y S4U no tiene credenciales de red. La ventana, que fue lo que mató la tarea vieja, se quita de
  otra forma: `wscript` con `oculto.vbs` (estilo 0) y cada subproceso con `CREATE_NO_WINDOW`.
- **La tarea semanal de la operación espera a la corrida del día** (`python -m contexto --esperar 90`) para no leer
  los parquet mientras la extracción los escribe; las dos arrancan a la vez cuando el equipo estuvo apagado.
- **Las tareas no se registran desde código.** Quedan los XML y los comandos; las registra el propietario.

**Evidencia (2026-10-15).**
- `--todo --sin-hospital`: **143 s**. 13 pasos `sin_cambios`, 2 `ok`, `clima_ideam` omitido (no instalado) y
  `sivigila_eventos` en **fallo**: la lista SharePoint `Microdatos` del portal del INS respondió 500 (el mismo fallo de
  memoria del servidor que `CAPTURAS.md` describe para el Power BI). Código de salida 1.
- La segunda corrida (`--sin-hospital`) se saltó los 13 pasos al día y reintentó solo los que no tenían corrida
  exitosa: 17 s.
- Por `wscript` + `oculto.vbs` + `contexto.cmd`, fuera de la consola: el código llega intacto (1, 0 y 2) y la salida
  queda en `registro/tarea.log`. Una segunda corrida simultánea sale con 3 sin correr nada.
- `--solo hospital`: la extracción corrió en 16 s y el triage llega al 2026-10-15 (a medias).
- `contexto_diario.csv`: 3.288 días (2020-01-01 a 2028-12-31) y 45 columnas. Las 35 columnas de mecanismo coinciden
  **exactamente** con `mecanismos.columnas` en todo el rango; `fut_m_feria_d0_4` y `fut_m_fiesta_lejana`, también en
  ene-sep 2026 calculado aparte. 2027: Feria del 2 al 6 de enero y 66 días de fiesta lejana.

**Lo que se encontró y no se arregló aquí** (son de `notebooks/` o de la fase 1):
- `indices.red_diaria(fin="2026-09-20")` y `regimenes_diarios` (`red_diaria(min(fin, "2026-09-20"))`) tienen la fecha
  fija: las columnas de red de M3s se quedan en el 2026-09-20 aunque la extracción traiga datos nuevos, y pasados 30
  días de `ffill` valen 0. Medido: el contexto diario no cambió después de bajar el hospital, y la última fila con red
  distinta de 0 es el 2026-10-20.
- `sivigila.py` reescribe sus `.gz` aunque el contenido no cambie (cambia la cabecera gzip): ensucia git una vez al
  mes. Se restauraron los dos archivos tras la prueba (contenido idéntico a HEAD).
- `eventos.py` no tiene el respaldo de `powerbi.py` cuando la lista del portal del INS da 500.

## 2026-10-15 (3) — Los actualizadores existentes no reescriben el pasado; la tarea murió porque se cerró su ventana

**Decisión.** Los scripts de fuentes que ya existían (clima ×3, ENSO, sismos, MinDefensa, festivos, Power BI,
microdatos SIVIGILA, capturas) pasan a ser incrementales: lo ya escrito se conserva salvo una cola reciente
(10 días en clima, 30 en sismos, 90 en MinDefensa, 6 meses en ONI); si la fuente trae menos de lo que hay, se
aborta sin escribir; y salen con código distinto de cero al fallar. `--rehacer` (o `--forzar` en vigilancia)
acepta las revisiones del pasado y queda como decisión del propietario.

**Por qué.** Rehacerlo todo movía en silencio datos sobre los que se publicaron experimentos: NASA POWER sustituye
sus ~3 últimos meses provisionales (88 días cambiaron, r de 0,17 a 0,60 en esos días del clima unificado),
Open-Meteo cambió su máxima y mínima diarias en toda la serie (±0,05 °C), el ERA5 de los últimos días traía
mínimas de 3 °C, un sismo M4,5 pasó a 4,4, y los factores de `clima_unificado.py` movían el pasado solo con añadir
días. Y `sivigila.py --desde 2024` borraba 174.162 de 203.772 filas.

**Tarea del 2026-10-13.** Murió a los 27 s con `0xC000013A`: está como «Solo interactivo», abre una consola
visible tras el inicio de sesión y esa ventana se cerró. Se propone S4U o lanzarla oculta, con red requerida y
reintentos; la configura el orquestador.

**Evidencia:** `calendarios/docs/CAPTURAS.md`, secciones «Actualización incremental» y «Por qué falló la tarea».

## 2026-10-15 (2) — Actualizadores de desastres (terremotos del USGS) y del calendario escolar

Fase 1 de la entrada de abajo. Detalle y tablas en `calendarios/docs/ACTUALIZADORES.md`.

**Desastres.**
- **Qué se decidió.** `calendarios/fenomenos/actualizar_desastres.py` detecta terremotos con probable afectación en
  Manizales. El criterio se preregistró antes de bajar el catálogo: fila `desastre_terremoto_automatico` de
  `variables.csv`.
  - Intensidad estimada en Manizales por Bakun y Wentworth (1997), a partir de la magnitud y la distancia
    hipocentral: tiene que ser **≥ 5,0**.
  - Además, la compuerta de impacto del USGS: PAGER amarilla o más, o MMI ≥ 6, o `felt` ≥ 100.
- **Evidencia.** En 2020-2026 hay 130 eventos (M ≥ 4,5, a ≤ 300 km). El criterio detecta 1 de 1 fila real: el
  2026-08-10, con I = 5,44. Da **0 falsos positivos**. El siguiente evento, Cartago el 2024-01-19, queda en I = 4,10.
- **Consecuencia.** Por la regla preregistrada, lo que detecte después del 2026-10-15 entra solo como `terremoto_auto`.
- **Límites.**
  - Hay una sola fila real.
  - El umbral 5,0 se eligió sabiendo de qué evento se trataba; con 5,5 se habría perdido.
- **Lo que se cambió respecto al encargo, y por qué.** Los candidatos no confirmados **no se escriben en el CSV**,
  aunque lleven un subtipo distinto de `terremoto*`. Van solo a `salidas/contexto/por_confirmar_desastres.csv`.
  - `indices.py` (`desastre_activo`) y `pronostico.py` (`ext_cat_desastre`) marcan todas las filas, sin filtrar.
  - Si los candidatos estuvieran en el CSV, entrarían igual al modelo por esa vía.
- **Lo anterior al corte no se toca.** Las detecciones anteriores al 2026-10-15 nunca se añaden, porque ese tramo del
  catálogo lo revisó una persona. `catastrofes()` sigue igual: `[2026-08-10]`.

**Calendario escolar.**
- **Qué se decidió.** `calendarios/actualizar_escolar.py` deduce reglas tipo «primer lunes desde el día D» del
  histórico oficial y añade los años lectivos 2027 y 2028. Son 10 filas con `resolucion = estimada_auto` y la regla
  en `nota`.
- **Evidencia, con origen rodante (n = 4).**
  - Semana Santa (cómputo de Pascua): 4/4.
  - Octubre: 3/4.
  - Mitad de año: 3/4.
  - Arranque: 2/4.
  - Todos los fallos son de una semana justa.
- **Decisión tomada después de ver el origen rodante.** El cierre de fin de año se calcula con la **ley de las 40
  semanas de clase** (Decreto 1075 de 2015), no con un ancla fija.
  - Por qué: la ley se cumple 6 de 6 con los recesos reales, y el ancla fija (2/4 contra 1/4 en origen rodante) daría
    un 2027 de 39 semanas.
  - Qué cambia: el cierre de 2027 queda el 6-dic y no el 29-nov.
- **Pendiente.** La resolución de 2027 sale hacia finales de octubre. Cuando salga, se escribe a mano y se borran a
  mano las estimadas.

---

## 2026-10-15 — El contexto externo se actualiza solo y vuelve a la operación; revierte «C0r por mantenimiento»

**Qué se decidió (propietario).**
- Cada fuente externa del modelo tiene su script de actualización.
- Un orquestador las corre todas y deja un CSV de contexto diario (día × variable).
- Una tarea programada lo corre cada cierto tiempo.
- La predicción usa ese contexto **sin reentrenar**: los coeficientes aprendidos se aplican al estado actual del
  entorno.
- Power BI queda para después de tener esta base.

**Por qué.** El 13-10 (entrada (5)) se puso C0r en la operación y no M3s. El motivo fue de mantenimiento, no de
acierto: los calendarios de M3s se mantienen a mano, se acaban en 2026 y, sin nadie que los actualice, M3s se degrada
sin avisar. Ese motivo es justo lo que la automatización elimina. Además, C0r sin el contexto externo se acerca a la
proyección que `CLAUDE.md` descarta como producto. Con esta decisión se revierte esa parte de la entrada (5) y de
OPERACION.md, una vez que el contexto se mantenga solo.

**Evidencia de partida (no es una promesa de mejora):**
- M3s gana a C0r en 2025 (criterio 5,98 contra 4,46), empata en 2026 y no se separa en SPA (cuaderno 26);
- en la semana prospectiva del 5 al 11 de octubre, M3s tuvo un error del 6,8 % y C0r del 7,3 %.

Si el contexto automático reduce el error, se medirá de forma prospectiva y con los datos tal como lleguen el día de
la predicción.

**Estado de las fuentes al decidir:**
- la tarea `triage_capturas_semanales` se cortó el 13-10 (0xC000013A) y no captura nada desde el 05-10;
- `eventos_manizales`, `fiestas_caldas`, `desastres_manizales` y `calendario_escolar` se acaban entre noviembre y
  diciembre de 2026.

---

## 2026-10-14 (8) — Resiliencia: medida, reanclaje (no entra) y rango tras quiebre (entra)

**Pedido del propietario:** no se trata de que no falle. Se trata de saber por cuánto falla, cuánto tarda en
recuperarse después de un golpe y que se reajuste a lo que está pasando. Preregistro en la fila `resiliencia`, escrito
antes de calcular y declarado como tercera mirada. Código en `notebooks/resiliencia.py` y salida en
`salidas/pronostico/resiliencia/`.

**(1) Medida.** «Normal» es la mediana del error semanal de la base en ene-oct 2025, a 15 días: **7,9 %**. Semanas
hasta volver a 1,5 × lo normal dos semanas seguidas (tope 12), con el exceso de error entre paréntesis en
puntos-semana:

| Golpe | Sin red | v2A (en operación) |
|---|---|---|
| Cierre del SES, nov-2025 | 11 (139) | 11 (119) |
| Reapertura, mar-2026 | 5 (37) | 4 (30) |
| **Cierre del SES, jul-2026** | 3 (32) | **0 (1)** |
| Sismo, ago-2026 | 1 (30) | 1 (28) |
| Reapertura sin anuncio, ago-2026 | 12 (14) | 12 (14) |
| **Suma** | **32** | **28** |

Lectura:
- **Un golpe anunciado ya no cuesta semanas** (julio).
- Un golpe nuevo (nov-2025) o sin anuncio (ago-2026) sigue costando hasta 3 meses de error elevado. Ese es el límite
  medido.
- El sismo cuesta una semana y se recupera solo.

**(2) Reanclaje tras un quiebre (R): NO ENTRA.**
- A 15 días mejora 2025 (puntaje de 2,51 a 2,41; Nueva EPS de 16,6 % a 15,5 %) y Nueva EPS en 2026 (20,3 % → 19,1 %).
- Pero el puntaje de 2026 empeora (2,51 → 2,59) y Sura también (14,5 % → 15,2 %).
- Causa visible: la semana del sismo reancló a Sura hacia abajo, justo antes del rebote. El exceso de la reapertura de
  agosto pasa de 14 a 25.
- Reaccionar a la última semana confunde un golpe pasajero con un cambio de nivel.

**(3) Rango tras un quiebre (W): ENTRA.** Se aplica sobre la v2A, porque R quedó fuera. El preregistro lo definía
sobre v2AR; se declara la diferencia. Se activa en 7 de 90 orígenes. A 15 días:

| | v2A | v2A + W |
|---|---|---|
| Puntaje 2025 | 2,505 | 2,467 |
| Puntaje 2026 | 2,511 | 2,517 (+0,2 %) |
| Total en rango, 2025 | 83,5 % | 84,6 % |
| Total en rango, 2026 | 77,0 % | 79,4 % |
| Total en rango, semanas de recuperación | 53,7 % | 60,5 % |

**Decisión:** `operacion.RANGO_QUIEBRE = True`, que ensancha solo el rango del total de la corrida cuando el detector
dispara. El reanclaje no se usa. En el tablero, 2026 con red y W da 9,9 % de error y 81 % de días en rango.

---

## 2026-10-14 (7) — El digiturno está en la base: `DIM_HCNCONTRDT`; las solicitudes no atendidas son ~5-7 %

**Pedido del propietario** (tema de la reunión con urgencias): hay personas que piden triage y se van. Hay que entender
por qué y predecirlas. Si se predicen 10 en una hora pico y se ponen 3 personas, pero varias se fueron, se desperdicia
personal.

**Encontrado** (solo esquema y agregados).
- `DIM_HCNCONTRDT` es el control de turnos, es decir, el digiturno: 1.024.588 turnos desde 2020.
- Su catálogo de colas es `HCNCONCOTRI_DW`. Las colas con `HCAREA` = 1 son las de triage: general, preferencial, SOAT,
  adulto mayor, obstétrico, preferencial obstétrico, respiratorio, consulta inducida y pretriage. Las demás son
  laboratorio, citas, facturación y FOMAG.
- La entrada del 14-10 que decía que el digiturno no estaba en la base **queda corregida**: no aparecía con ese nombre.
- **Un turno de triage sin triage unido es una solicitud no atendida.**
  - 2025-2026: 6.317 de 116.869 turnos de las colas de triage (5,4 %). 4.963 tienen estado 2 y se cierran a los ~24
    minutos; 1.277, estado 1, a los ~18.
  - Por año: 8,3 % (2020), 8,8 %, 5,8 %, 5,6 %, 6,9 % (2024), 5,3 % y 5,6 % (2026).
  - **La base no trae el significado de `HCCESTADO`.** Lo confirma urgencias o sistemas.
- 11.962 triages de 2025-2026 no tienen turno: entran sin digiturno, probablemente por ambulancia o remisión.
- **Lo que hoy predecimos son triages realizados.** Las solicitudes son los realizados más los no atendidos.

**Extracción nueva:** `python -m extraccion --turnos` → `salidas/turnos_triage.parquet`. Trae día × hora × cola ×
estado × si llegó a triage × nivel, con sumas de minutos hasta el triage o hasta el cierre: 254.447 filas desde 2020.
También corre dentro de `--series`.

**Patrones descriptivos (2024-2026, sin modelo todavía):**

| Factor | Patrón |
|---|---|
| Espera de los atendidos en esa hora (quintiles) | < 6 min → 4,3 % no atendidos; 9 → 4,5 %; 12 → 4,7 %; 18 → 5,3 %; **35 min → 8,9 %** |
| Carga (turnos en la hora, quintiles) | 2 por hora → 5,1 %; **17 por hora → 6,7 %** |
| Hora | Mínimo a las 6 h (3,7 %); **máximo a las 13 h (7,2 %)**, con la espera más alta del día (30 min) aunque llegan menos que en la mañana; 0-1 h: 6,8 % con espera corta (12 min) |
| Cola | Preferencial 10,7 %, SOAT 8,2 %, general 5,8 %, adulto mayor 6,2 %, obstétrico 4,9 % |
| Día | Lunes 6,9 % → sábado 5,3 % |
| Tiempo hasta irse | 28 minutos de media |

Lectura provisional: **la espera duplica el abandono**, y eso apoya la teoría del propietario. Pero el patrón de la
madrugada (abandono alto con espera corta) dice que hay otra causa. La hora y la espera van juntas: separarlas pide el
análisis formal, que todavía no se ha hecho.

---

## 2026-10-14 (6) — Foco en el producto mínimo viable: nada de otros hospitales ni fuentes nuevas

**Decidido por el propietario.** El trabajo se ciñe a predecir bien el triage del SES y su reparto por aseguradora,
con lo que ya existe. Se detuvo la búsqueda en la web de cierres en otros hospitales y no se usará `RECEPCIONES_DW`.
El registro `datos/eventos_red.csv` y la v2 quedan como están.

**Por qué:** cada fuente nueva aplaza la entrega. En sus palabras: «nos vamos a terminar desviando cada vez más y
nunca sacamos el producto mínimo viable».

---

## 2026-10-14 (5) — La v2 pasa su regla: el estado medido del convenio evita el daño y conserva la mejora; entra en la operación

**Medido** (`python notebooks/red.py --v2`, `salidas/pronostico/red/resumen_v2.csv`). Misma validación, misma semilla
y 1.246 días. Adelanto 15, todos los días:

| | 2025 sin red | 2025 v2A | 2026 sin red | 2026 v1 A | 2026 v2A |
|---|---|---|---|---|---|
| Error del día | 10,28 % | **10,03 %** | 11,61 % | 14,25 % | **10,21 %** |
| Puntaje de cuantiles | 2,66 | **2,51** | 2,79 | 3,64 | **2,51** |
| Total en rango 80 % | 83 % | 84 % | 71 % | 67 % | **77 %** |
| Nueva EPS, error | 17,9 % | 16,6 % | 25,6 % | 26,6 % | **20,3 %** |
| Nueva EPS en rango 80 % | 76 % | 77 % | 54 % | 55 % | **62 %** |
| Sura, error | 15,2 % | 15,2 % | 14,5 % | — | 14,5 % |

**Regla de la fila `red_de_urgencias_v2`: v2A ENTRA.** Mejora 2026 un 10 % en el puntaje, también mejora 2025 y la
cobertura queda en 77-84 %. v2B y v2D también la pasan, con menos mejora:
- v2D, solo datos y sin registro: 2026 11,40 %;
- v2B: 2026 10,97 %.

Lectura: **el registro de prensa aporta la anticipación** (julio) y **el estado medido evita el daño** (abril).

**Mes a mes** (error del día, sin red → v2A):

| Mes | Sin red | v2A |
|---|---|---|
| Nov-2025 | 22,3 % | 17,8 % |
| Dic-2025 | 20,1 % | 19,7 % |
| Mar-2026 | 16,0 % | 15,0 % |
| Abr-2026 | 9,0 % | **8,2 %** (con la v1 era 36,7 %) |
| **Jul-2026** | 15,2 % | **6,8 %** |
| Ago-2026 | 15,9 % | 15,1 % |

Único mes peor: oct-2025, de 6,9 % a 8,2 %. A 1 día, 2026 mejora (9,28 % → 8,92 %) y 2025 empeora 0,1 puntos.

**Límites que quedan, dichos de frente:**
- **Es una segunda mirada a 2025-2026.** El diagnóstico de la v1 se vio antes de diseñar la v2. La confirmación es
  prospectiva: las corridas y los ajustes guardados con fecha desde hoy.
- **El coeficiente del acceso sale atenuado** (bA ≈ 0,10-0,15 por unidad de log): el ruido semanal de la señal
  diluye la pendiente. En julio el ajuste bajó a Nueva EPS un 26 %, y bajó un 45 %. Corregir eso sería otra versión,
  con otro preregistro.
- **Una reapertura sin anuncio no se anticipa** (ago-2026). Se ve en los datos con el rezago de la extracción.
- **La primera vez de un tipo de episodio** solo la cubre la ventana del mismo estado, cuando ya hay 7 días del
  nuevo estado antes del origen.
- **Diciembre de 2025 sigue en ~20 %**: los primeros días del primer cierre del SES no los cubre ninguna pieza.

**Decisión:** `operacion.USAR_RED = True` con la v2. `--ajustar` guarda un archivo por fecha y hora (ninguno se
rehace). El historial del tablero compara el modelo solo con la v2A. Requisito operativo: `ingresos_entidad.parquet`
se actualiza con `--series` cada semana. Sin él, el ajuste no se aplica y la operación lo avisa.

**Dato nuevo visto mientras corría, sin usar todavía:** `RECEPCIONES_DW`, las remisiones que otros hospitales ofrecen
al SES desde 2023 (21.204), con EPS y resultado. Para Nueva EPS, el «no aceptado» bajó de ~50 % (2024 a jul-2025) a
1-12 % durante los cierres (ya solo se ofrecían urgencias vitales) y volvió a 21-25 % desde agosto de 2026, otra
huella de la reapertura. Sura: el «no aceptado» sube del 0-20 % al 30-45 % desde sep-2025, una presión distinta que
no se ha estudiado. Es candidata para medir la saturación de la red.

---

## 2026-10-14 (4) — v2: el convenio medido con los ingresos no urgentes; extracción nueva y preregistro

**Autorizado por el propietario** («implementa y prueba»). Se añadió `python -m extraccion --ingresos` →
`salidas/ingresos_entidad.parquet`: ingresos por día × tipo × si vienen de triage × entidad, 45.108 filas. Las fechas
van de 2020 a 2026, pero **la entidad solo existe en `DIM_INGRESO` desde 2024**. También corre dentro de `--series`.

**Qué es cada ingreso** (la base no trae catálogo; cruce agregado de 2025-2026):

| | Sin triage | Con triage |
|---|---|---|
| Tipo 1 | ~253.000 (`AINURGCON` = 1) | ~26.500 |
| Tipo 2 | ~11.700 | ~12.300 |

Lectura: «sin triage» = **no urgentes** (consulta y procedimientos). Son los que desaparecen cuando el SES deja a una
EPS solo con urgencias vitales. Por eso la señal es esa, y no el tipo 1 entero, que mezcla las urgencias.

**La razón Nueva EPS / Sura de los no urgentes deriva sola**: 1,2 en ene-2024, 5,8 en oct-2025, 2,6 en jun-2026.
Refleja afiliados que se mueven entre EPS. Por eso la v2 no usa umbrales fijos de abierto o cerrado. Usa cambios, «días
en el mismo estado que hoy» y un abierto relativo al máximo de 26 semanas.

**Preregistro:** fila `red_de_urgencias_v2`, escrita antes de calcular y declarada como **segunda mirada** a
2025-2026. Las tres piezas son:
- la ventana del mismo estado, sin coeficiente, que sirve la primera vez;
- lo anunciado en el registro que todavía no se ve en los datos;
- los otros hospitales, que solo cuentan si el SES atiende a Nueva EPS.

Variantes: v2A, v2B y v2D (solo datos, sin registro).

---

## 2026-10-14 (3) — El estado del convenio SES–Nueva EPS está en la base: los ingresos ambulatorios lo miden día a día

**Pedido del propietario:** buscar en la base y en las fuentes externas el dato que faltaba (cuándo reabrió el SES a
Nueva EPS), porque «de nada sirve que arregle una parte y dañe la otra».

**Medido** (solo esquema y conteos agregados, protocolo de `extraccion/__init__.py`).
`DIM_INGRESO` cuenta por día, tipo de ingreso (`AINTIPING`) y entidad (`GEENENTADM`: Nueva EPS = 238 y 100, Sura =
227). Ninguna columna sensible. Guardado en el scratchpad, no en `salidas/`. El tipo 1 son 231.736 ingresos y el 2,
19.160. Ingresos de tipo 1 de Nueva EPS por semana:

| Periodo | Nueva EPS / semana | Lectura |
|---|---|---|
| jun-oct 2025 | 1.800-2.900 | abierto |
| semana del 3-nov-2025 | 2.077 | restricción de lo no urgente (4-nov) |
| desde el 24-nov-2025 | 90-250 | **solo urgencias vitales** (desde el 21-nov) |
| semana del 23-feb-2026 | 205 | empieza a reabrir: 32 el 25-feb, 51 el 26-feb |
| desde el 2-mar-2026 | 680 → 1.200-1.900 | **reabierto**: 118 el lunes 2-mar |
| desde el 29-jun-2026 | 760 → ~200 | **cerrado** desde el 1-jul |
| desde el 24-ago-2026 | 496 → 790 → 1.010 → 1.260 | **reapertura gradual que ninguna noticia publicó** |

Sura en esos periodos: 450-1.000 por semana, sin escalones.

**Consecuencias:**
1. **La fecha que faltaba existe y es interna:** el SES reabrió a Nueva EPS entre el 25-feb y el 2-mar de 2026, no el
   8-abr. Explica la subida del triage desde principios de marzo y la falla de abril de la entrada (2).
2. **El registro también está mal hoy.** Dice que el SES sigue cerrado desde el 1-jul, pero desde finales de agosto se
   volvió a atender a Nueva EPS, al menos en parte (la razón Nueva EPS / Sura va en 1,2, frente a 2,3 antes del cierre
   y 4-5 en 2025). Coincide con la subida del triage de Nueva EPS en septiembre (~50 → 68), que no tenía causa
   conocida.
3. **Los giros de la ADRES no sirven como señal del convenio.** Nueva EPS → SES, en miles de millones por mes: nov-2025
   10,9, mar-2026 4,5, abr-2026 3,1, ago-2026 7,8. El giro sigue pagando facturas viejas durante los cierres y cayó
   justo cuando el SES reabría.
4. **La prensa sirve para lo que viene** (anuncios con días de antelación). **La base sirve para lo que ya pasó**:
   mide el estado real con el mismo rezago que el triage. El fallo de la entrada (2) fue usar la prensa para el
   pasado.

**Decisión pendiente del propietario:** usarlo como estado medido del convenio en el ajuste (v2) y en la ventana de
aseguradoras. Eso implica una consulta agregada nueva en `extraccion/` y un preregistro nuevo, declarado como segunda
mirada a 2025-2026.

---

## 2026-10-14 (2) — Resultado de la red de urgencias: no pasa la regla; funciona en el caso limpio y falla con registro dudoso o episodios nuevos

**Medido** (`python notebooks/red.py`, salida en `salidas/pronostico/red/`). Validación semanal C0r, 1.246 días
predichos, misma semilla con y sin ajuste. Adelanto 15, todos los días:

| | 2025 sin red | 2025 A | 2025 B | 2026 sin red | 2026 A | 2026 B |
|---|---|---|---|---|---|---|
| Error del día | 10,28 % | 11,19 % | 10,04 % | 11,61 % | **14,25 %** | 11,56 % |
| Puntaje de cuantiles | 2,66 | 2,93 | 2,56 | 2,79 | 3,64 | 2,77 |
| Total en rango 80 % | 83 % | 82 % | 84 % | 71 % | 67 % | 72 % |
| Nueva EPS, error | 17,9 % | 19,1 % | 16,3 % | 25,6 % | 26,6 % | 23,3 % |
| Nueva EPS en rango 80 % | 76 % | 77 % | 79 % | 54 % | 55 % | 59 % |

**Regla preregistrada (variante A, adelanto 15): NO ENTRA.** No mejora 2026, empeora 2025 más del 1 % y la cobertura
de 2026 queda en 67 %. `operacion.USAR_RED` queda en `False`.

**Por qué falla, mes a mes** (error del día, sin red → A):
- **Julio de 2026 es el caso limpio y funciona:** de 15,2 % a 7,0 %. Nueva EPS predicha en 66, frente a 88 sin red y
  52 real. El cierre se anunció 6 días antes y el efecto ya se había visto en noviembre de 2025.
- **Abril de 2026 hunde el año:** de 9,0 % a 36,7 %. El fin del cierre del SES de noviembre (E25) estaba fechado el
  8-abr, **inferido** de una nota que en realidad dice que el SES «mantiene activo» a Nueva EPS. La reapertura fue
  antes, en fecha no encontrada. El ajuste «reabrió» en abril lo que ya estaba abierto y duplicó a Nueva EPS (141
  frente a 93).
- **Diciembre de 2025:** de 20,1 % a 27,4 %. El cierre del SES ocurría **por primera vez**, así que no tenía efecto
  estimado. El cierre de Santa Sofía del 1-dic, en cambio, sí lo tenía (positivo, aprendido de Avidanti), y empujó a
  Nueva EPS hacia arriba justo cuando bajaba.

**Sensibilidad declarada como posterior a ver el resultado** (no cambia la decisión): fin de E25 en los compromisos de
febrero (25-feb), conocido desde el 8-abr. En 2026: error de 11,61 % a 10,86 % y Nueva EPS de 25,5 % a 17,0 %, con
rango del 71 % en vez del 55 %. **2025 sigue peor** (10,30 % → 11,21 %, por diciembre). Tampoco pasaría la regla.
Archivos: `salidas/pronostico/red/sensibilidad_E25_*.csv`.

**La variante B** (solo lo sabido al cortar los datos) mejora un poco los dos años. No se adopta: la regla se fijó
sobre A, y la mejora es de 0,1-0,2 puntos.

**Aseguradora por hora** (informativo, sin regla; adelanto 15, sin red). Error absoluto medio por hora frente al piso
de ruido Poisson:
- Nueva EPS: 1,72 frente a 1,56 (2025) y 1,46 frente a 1,25 (2026);
- Sura: 1,16 frente a 1,08 y 1,26 frente a 1,17;
- rango del 80 % por hora: 86-89 %, un poco ancho.

Lectura: el reparto por hora está cerca del límite del azar y **se informa**.

**Lectura de conjunto.** El mecanismo es real, y cuando el registro es correcto y el tipo de episodio ya se vio, la
corrección es grande (julio). Hay dos debilidades que el diseño no resuelve con datos:
1. **El primer episodio de cada tipo no tiene efecto estimado**, y los de otro tipo pueden empujar en contra.
2. **Un error en la fecha de fin de un episodio pasado inyecta error.** La ventana de 28 días compara contra el estado
   que el registro dice, no contra el que hubo.

El registro escrito a mano es la pieza crítica: su calidad decide si el ajuste ayuda o daña.

**Qué queda en la operación:**
- la cadena nueva (aseguradoras por hora);
- `--ajustar` para refrescar a diario con el registro, sin reentrenar;
- el tablero, que muestra los episodios en curso y la comparación con y sin la red, para que se vea dónde ayuda y
  dónde no.

---

## 2026-10-14 — La red de urgencias entra como contexto que corrige sin reentrenar; digiturno no está en la base

**Cambio de alcance, decidido por el propietario.** El 13-10 dejó fuera el estado del convenio hospital-EPS. Hoy
pide integrarlo, junto con el estado de los demás hospitales de Manizales, y **revierte** esa exclusión. La forma la
fijó él: no son datos para reentrenar, son **variables del momento que corrigen el día o la semana, no el año**.

**Lo que se encontró antes de decidir** (búsqueda en la web del 14-10; detalle de fuentes en
`calendarios/docs/FUENTES_EXTERNAS.md`, actualización del 14-10):
- Los escalones de Nueva EPS en el SES tienen fecha en prensa. El **21-nov-2025** el SES deja de atenderla salvo
  urgencias vitales, y el **1-jul-2026** cierra sus servicios generales (anunciado el 26-jun).
- El escalón de **marzo de 2026** no fue una reapertura del SES. Coincide con cierres de **otros** hospitales a Nueva
  EPS (San Isidro en febrero, Santa Sofía el 26-mar), que mandan sus pacientes a las urgencias del SES. El estado de
  la red pesa tanto como el del convenio propio.
- Entre 2024 y 2026 hay unos 25 episodios fechados (cierres y reaperturas a Nueva EPS en el SES, Santa Sofía, Avidanti,
  el Infantil, San Isidro, y el cierre de urgencias de Ospedale de 2024). Se obtienen de la API WordPress de la Alcaldía
  y de la sección de salud de La Patria, con 0 a 1 día de rezago.
- Dos cifras de prensa, contrastadas con `salidas/` como prueba de plausibilidad:
  - del 1 al 5 de septiembre de 2025 la prensa dio ~240 triages diarios en el SES, y los datos dan 225-249;
  - tras el cierre de Avidanti (21-ago-2025), Nueva EPS en el SES pasó de 122,8 a 133,6 por día en 30 días. Es una
    comparación cruda, sin ajustar.

**Decisión de diseño.**
- Un **registro escrito a mano**, `datos/eventos_red.csv`, con fecha de inicio, de **anuncio**, de fin y de anuncio
  del fin.
- Un ajuste **después** del modelo: el factor de Nueva EPS se estima con la razón Nueva EPS / Sura en primeras
  diferencias semanales, y se aplica a su proporción del día y al total.
- La regla de evidencia es la misma del clima: **evaluar con lo que se sabía en su momento** (variantes A, el día
  anterior, y B, el corte de los datos).
- Preregistrado en `patrones/datos/variables.csv`, fila `red_de_urgencias`, **antes de calcular ningún resultado**.

**Por qué no meterlo en el entrenamiento.** Con unos 25 episodios, una variable más dentro de LightGBM o SARIMAX se
estima mal y se mezcla con la tendencia. Hay un mecanismo nombrado (la puerta de urgencias abierta o cerrada para
una aseguradora) y un grupo de control natural (Sura, que no tiene episodios). Eso deja estimar el efecto aparte, de
forma transparente, y aplicarlo solo mientras el episodio dura.

**Digiturno.** Pedido el 14-10 para tener la aseguradora con la que llega quien pide triage. Se miró solo el
esquema. **No existe una tabla de turnos en `DWSES`**: hay 174 tablas y ninguna con TURN o DIGI salvo
`TURNOS_ALIMENTOS`. Las demás bases del servidor (AM, Manillas, ControlPagos y otras 12) responden «sin acceso» a esta
cuenta. La aseguradora del triage ya está en `DIM_TRIAGE.GEENENTADM` (bajada en `salidas/triage_entidad.parquet`):
el reparto por aseguradora no depende de digiturno. Lo que digiturno aportaría es la **hora de llegada antes del
triage**. Hace falta el nombre de la base y el permiso, y eso lo da el superior.

---

## 2026-10-13 (6) — Datos al 12 de octubre: la precisión medida, el pronóstico hasta diciembre y el alcance de la entrega

**Extracción** (autorizada por el propietario). Se corrió `python -m extraccion --series`.
- `--series` **no refrescaba `triage_diario` ni `triage_horario`**: se escribían aparte. Se añadieron a `series()`
  desde `conteo_horario`.
- Los 2.453 días anteriores coinciden exactamente con los nuevos. Los datos llegan al 2026-10-12 completo (el 13,
  a medias).
- El 21-sep deja de estar incompleto, y se quitó de `reparto.MALOS`.
- Las fechas fijas de los módulos de análisis (`pronostico.FIN`, `madurez.ULTIMO`, `mes_a_ciegas.ULTIMO_DATO`) no se
  tocan: fijan experimentos ya publicados. La operación fija la suya en cada corrida.

**Precisión con los datos nuevos** (C0r; «reconstruido» = predicho 15-21 días antes en la validación semanal).

| | 2025, reconstruido | 2026, reconstruido | 21-sep a 12-oct, corrida del 20-sep |
|---|---|---|---|
| Días | 353 | 263 | 22 |
| Error del día | 10,3 % | 11,5 % | **5,9 %** |
| Días dentro del rango del 80 % | 84 % | 72 % | **95 %** |
| Error de mañana / tarde / noche | 16 / 14 / 16 % | 17 / 15 / 18 % | 9 / 11 / 14 % |
| Error de Nueva EPS / Sura | 18 / 15 % | 25 / 14 % | 8 / 12 % |
| Aseguradoras pequeñas | 2,1 pacientes, 82 % dentro | 2,4, 81 % | 2,7, 78 % |

Predicciones prospectivas verificadas (guardadas antes de que ocurriera el día):
- semana del 5 al 11 de octubre: M3s con 6,8 % de error y C0r con 7,3 %, los dos con 7 de 7 días dentro del rango;
  mañana y tarde con error del 13-14 %;
- octubre predicho el 07-10 desde el 20-sep, del 1 al 12 de octubre: M3s con 5,9 % y C0r con 6,4 %, los dos con
  12 de 12 días dentro;
- el lunes 12 de octubre, festivo: 155 anunciados y 158 reales.

**Pronóstico hasta diciembre.** El horizonte de la operación pasa de 28 días fijos a «hasta el 31 de diciembre», con un
mínimo de 28 y un máximo de 120 días.
- Los días a más de 28 días se marcan como largo plazo (`largo_plazo`) y el tablero los presenta como tendencia
  («≈»): la validación llega hasta 28.
- La corrida del 2026-10-12 predice 80 días y tarda unos 4 minutos.

**Historial.** `operacion.historial()` reúne para cada día lo que se habría dicho 15-21 días antes y lo real, con
jornadas y aseguradoras:
- de la validación reconstruida (C0r, adelanto 15) hasta el 20-sep;
- de las corridas guardadas desde entonces.

Se versiona junto con `estado.json` para que el tablero abra completo en un clon nuevo. El tablero tiene tres
pestañas: «Próximos días» (calendario por mes hasta diciembre), «Cómo ha predicho» (calendario por mes de 2025-2026,
lo real frente a lo predicho, con jornadas y aseguradoras) y «Qué tan confiable es».

**Festivo de la Virgen de Chiquinquirá: confirmado.** Es la Ley 2578 de 2026, sancionada en junio de 2026: fiesta
nacional el 9 de julio, trasladable al lunes. El calendario ya lo tenía desde el 13-jul-2026, con holidays 0.105.

**Alcance de la entrega inicial, fijado por el propietario:**
1. **No se programa la ejecución automática todavía.** Queda desarrollada hasta donde está (`operacion/semanal.cmd`,
   `OPERACION.md`). Antes de terminar la práctica se preguntará a urgencias si quieren el producto y quién se encarga.
2. **El estado del convenio queda fuera del alcance.** Aclaración: lo que se propuso era el convenio entre el
   **hospital** y la EPS (si el hospital atiende o no a sus afiliados en una fecha), no la afiliación del paciente. El
   propietario no lo considera necesario para esta entrega, y no se persigue.
   - El hallazgo medido sigue en pie: los meses de cambio de Nueva EPS son la causa principal de los días fuera del
     rango.
   - Se informa en el tablero como advertencia, no como dato que falte.

---

## 2026-10-13 (5) — La operación semanal y el tablero: reentrenar con receta fija, C0r en producción, semáforo

**Pedido del propietario.** Que la predicción siga funcionando cuando él se vaya (es practicante), reentrenando cada
cierto tiempo. Y un tablero en Streamlit, tipo calendario, para mostrarle a urgencias:
- las probabilidades;
- cómo va a estar de lleno cada jornada;
- la hora de más saturación;
- de qué aseguradora llegan.

Los cuadernos siguen siendo el lugar del análisis.

**Qué se decidió, y por qué.**
1. **Reentrenar cada semana con receta fija, no congelar.** La serie cambia de nivel, y un modelo congelado se desvía:
   el entrenado en 2022-2024 sobrepredice 2026. «Receta fija» quiere decir que lo único que cambia son los datos; las
   variables y los hiperparámetros no se vuelven a elegir. Es lo mismo que se validó: la validación semanal
   reajustaba cada 4 domingos. Reentrenar a 28 días tarda 86 s.
2. **C0r en producción; M3s como opción** (`--modelo M3s`).
   - M3s depende de `eventos_manizales_2020_2026.csv`, `fiestas_caldas_2020_2026.csv`,
     `desastres_manizales_2020_2026.csv` y `seguridad_mindefensa.csv.gz`. Se mantienen a mano y terminan en 2026: sin
     mantenimiento se degrada sin avisar.
   - En el SPA, M3 no se separa de C0r (cuaderno 26).
   - En la semana prospectiva del 5 al 11 de octubre: C0r, 7,3 %; M3s, 6,8 %.
   - Para un sistema que debe sobrevivir sin quien lo construyó, pesa más no tener piezas frágiles que 0,5 puntos.
3. **Horizonte de 28 días.** El adelanto operativo es de 15 a 21 días, y 28 cubre el mes siguiente. La curva del
   cuaderno 26 llega hasta ahí.
4. **«Lo habitual» = la vara única del 08-10.** Es la media del mismo día de la semana en las 8 semanas que terminan en
   el último dato. P(más que lo habitual) es el P(sube) validado en el cuaderno 26.
5. **Semáforo**, con umbrales fijados con la validación de 2025-2026, antes de tener días operativos verificados:
   - datos: verde hasta 8 días de antigüedad, rojo con más de 21;
   - error del día en los últimos 28 días verificados: verde ≤ 12 %, rojo > 18 %;
   - días dentro del rango del 80 %: verde ≥ 65 %, rojo < 50 %;
   - Nueva EPS: amarillo si sus 2 últimas semanas cambian un 20 % o más frente a las 8 anteriores;
   - solo cuentan los días predichos antes de empezar (`prospectiva`), y con menos de 14 queda en gris.
6. **Cada corrida se guarda una vez y se versiona** (`salidas/operacion/corridas/`, excepción en `.gitignore`). Es la
   misma razón que la de las predicciones semanales.
7. **El último día de datos siempre se descarta**, porque la extracción corre de día. Es conservador: cuesta un día.

**Lo construido.**
- `operacion/`: el ciclo (`python -m operacion [--extraer] [--estado] [--modelo]`), el tablero
  (`operacion/tablero.py`), los lanzadores `semanal.cmd` y `tablero.cmd`, y la guía de entrega
  `operacion/docs/OPERACION.md`.
- El tablero solo lee `salidas/operacion/`; no reentrena ni toca la base.
- Se probó con `AppTest` de Streamlit: 0 excepciones; el calendario, el detalle del día y el cambio de día funcionan.
- Los gráficos se revisaron renderizados. Se corrigió que las celdas de tono medio no mostraban el texto y que la
  escala divergente pasaba por un verde.

**Primera corrida** (2026-09-20, C0r): semáforo **rojo**, correctamente.
- Los datos tienen 23 días.
- Nueva EPS subió un 31 % en las 2 últimas semanas conocidas.

**Lo que queda abierto.**
- La extracción automática requiere una cuenta con lectura en `DWSES`. Es una decisión institucional.
- El estado de los convenios de Nueva EPS sigue sin fuente.

---

## 2026-10-13 (4) — De qué aseguradora llegan: Sura se predice bien, Nueva EPS no, y el calendario se extiende a 2030

**Pedido de urgencias** (vía el propietario). Además de cuántos llegan y a qué hora, urgencias quiere saber **de qué
aseguradora llegan y en qué jornada**. La institución necesita saber quién paga, y es la base de la fase siguiente:
cuántos pasan a consulta, cuántos de esos a hospitalización y en qué especialidad (por ejemplo, obstetricia).

**Qué se hizo.** Preregistro en la fila `reparto_por_aseguradora`; código en `notebooks/aseguradoras.py`; salidas en
`salidas/pronostico/aseguradoras/`. Hay ocho grupos fijos: Nueva EPS, Sura, otras EPS, régimen especial, SOAT, ARL,
prepagada y otros. La simulación encadena el total del día, las jornadas (P52) y los grupos dentro de cada jornada.

**Elección (2025, a 15 días, M3s; puntos del día mal repartidos entre aseguradoras).**

| T4 | T8 | T13 | T26 | D8 | D26 |
|---|---|---|---|---|---|
| **7,83** | 8,39 | 8,73 | 8,94 | 8,51 | 8,94 |

Gana **T4**: todos los días de las últimas 4 semanas. Lo contrario que en el reparto por hora: la forma del día es
estable, y conviene mucha historia; la mezcla de aseguradoras cambia rápido, y conviene la más reciente.

**Resultado (M3s, a 15 días: 2025 / 2026).**

| Grupo | Por día | Error | Piso de ruido | Rango 80 % | Rango en meses de cambio de Nueva EPS |
|---|---|---|---|---|---|
| Nueva EPS | 114 / 73 | 18 / 25 % | 8 / 10 % | 75 / **54 %** | 37 / **5 %** |
| Sura | 54 / 62 | 15 / 15 % | 11 / 10 % | 80 / 79 % | 87 / 82 % |
| Otras EPS, régimen especial, SOAT y otros | 6-10 | 2-3 pacientes | 28-37 % | 74-86 % | — |
| ARL y prepagada | 2-4 | 1-2 pacientes | 41-55 % | 87-92 % | — |

Por jornada, Sura queda dentro del rango entre el 77 y el 87 %. Nueva EPS, en 2026, entre el 64 y el 84 %.

**Lectura.**
1. **Sura se puede informar ya**, por día y por jornada, con un rango honesto.
2. **Nueva EPS es el fallo del total, aislado.** Por día tuvo 128 en octubre de 2025, 58 en diciembre, 89 en marzo,
   95 en junio, 52 en julio y 66 en septiembre de 2026. Ninguna ventana de datos pasados anticipa esos saltos, y en
   los meses de cambio el rango acierta el 5 %. **El dato que falta es el estado del convenio de Nueva EPS con fecha,
   conocido antes.** No es otra columna de nombre de aseguradora.
3. Los grupos pequeños se informan en rango, porque su error es de 1 a 3 pacientes al día. La pista de que «otros»
   absorbe a Nueva EPS en los meses de cambio no se sostiene: sus componentes casi no se mueven.

**Calendario hasta 2030.** `calendarios/calendario_Colombia.csv` terminaba el 2026-12-31, y la operación se habría
roto en enero sin aviso. Se regeneró con `calendario_colombia.py` (holidays 0.105) hasta el 2030-12-31.
- Para 2020-2026 reproduce el archivo anterior fila a fila, salvo el 2026-12-31, que pasa a víspera de festivo.
- En 2027 aparece el festivo de la Virgen de Chiquinquirá el 12 de julio. **Hay que confirmarlo.**

Se instaló Streamlit 1.65.0 (con altair 6.3.0) en `.venv`.

---

## 2026-10-13 (3) — La columna ASEGURADORA no trae nada nuevo; la base llega a hoy y la primera semana prospectiva acierta

**Qué pasó.** El superior del propietario añadió un dato de aseguradora a `DIM_TRIAGE`. A pedido del propietario se
revisó con el protocolo de `extraccion/__init__.py`: primero el esquema y después solo agregados. No se bajó ni se
imprimió ningún valor de la columna, ni ninguna fila.

**Lo que es la columna.**
- Se llama `ASEGURADORA`, es `nvarchar(100)` y ocupa la posición 16. La tabla se modificó el 2026-10-08 a las 11:34.
- Usa otra intercalación (`SQL_Latin1_General_CP1_CI_AS`; el resto de la base usa `Modern_Spanish_CI_AS`): se
  cargó desde otra fuente. Para compararla hace falta `COLLATE DATABASE_DEFAULT`.
- Está vacía en 2020-2021, llena al 100 % en 2022-2024 y al 99 % en 2025-2026.
- **En el 100 % de las filas con entidad es exactamente `DIM_ENTIDAD.ENTNOMBRE`** del `GEENENTADM` de la fila. Es
  nula exactamente cuando no hay entidad (718 filas en 2025 y 600 en 2026). Cada OID tiene un solo nombre; 52 nombres
  se reparten entre varios OID, como Nueva EPS con 238 y 100, ya agrupados en `entidades_clasificadas.csv`.

**Decisión.** No se usa. Repite lo que `triage_entidad.parquet` ya trae por el cruce, y con menos historia. Es el
nombre de una organización, no un dato personal. Si el superior quería añadir algo distinto (el estado del convenio,
el régimen, una agrupación propia), **no es esto**, y hay que preguntárselo.

**Lo que sí es nuevo: la base llega al 2026-10-13** (437.341 triages; hoy, incompleto). Lo local llega al 20-sep. Los
conteos por día del 21 al 27 de septiembre en la base (233, 206, 194, 161, 188, 156 y 147) coinciden con
`triage_entidad.parquet`. **El reporte del hospital de `datos/triage_reportado.csv` da entre un 3 % y un 8 % menos**
(218, 189…): ese reporte cuenta otra cosa o filtra algo. La verificación del 07-10 se hizo contra esos números más
bajos.

**Primera prueba prospectiva verificada: la semana del 5 al 11 de octubre.** La predicción se guardó el 06-10 con
datos hasta el 20-sep, de 15 a 21 días de adelanto. Los conteos son agregados por día y hora, sacados al scratchpad
de la sesión; no se reescribió `salidas/`.
- Real: media de 177,4 por día. La de los 3 meses previos es 164,8 y la de las 4 semanas previas, 181,8.
- **M3s: 178 (164-194); los 7 días dentro del rango; error del día del 6,8 %; sube o baja 6 de 7.** C0r: 180,
  7 de 7 y 7,3 %.
- El fallo es el **domingo 11**: 134 anunciados y 157 reales. Es el domingo de un puente (el lunes 12 es festivo), y
  sube sobre todo la mañana (51 contra 39).
- El lunes 12, festivo, de la semana guardada siguiente: 155 (136-181) anunciados y 158 reales.
- **Reparto P52** (calculado después con el origen del 20-sep; el método se fijó antes):
  - 26 de 28 franjas dentro del rango;
  - la mañana dentro 6 de 7 veces y la tarde 7 de 7; con el reparto viejo de 8 semanas, 4 de 7 y 6 de 7.
- La hora pico de la mañana cayó en el bloque anunciado los 7 días. La de la tarde, 4 de 7: el viernes fue a las 13,
  el sábado a las 17 y el domingo a las 20.

---

## 2026-10-13 (2) — Recalibrar el rango con los errores recientes no sirve: los cambios de nivel necesitan una señal externa

**Por qué.** La entrada anterior deja el error de las franjas en el total del día, cuyo rango cubre el 71 % en 2026 a
15 días. Se probó el arreglo más barato y más fácil de sostener sin nadie: un posproceso que ensancha el rango (R1) o
además lo desplaza (R2) según los errores ya conocidos en el origen, en las últimas 8 semanas. Preregistro en la fila
`rango_recalibrado`; código en `reparto.py --rango`; salida en `salidas/pronostico/reparto/rango_recalibrado.csv`.

**Resultado (M3s, a 15 días).**

| | Puntaje 2025 (elige) | Cobertura 2025 | Cobertura 2026 | Error del día 2026 |
|---|---|---|---|---|
| R0, sin cambio | **2,58** | 80 % | 71 % | 11,4 % |
| R1, escala | 2,63 | 73 % | 68 % | 11,4 % |
| R2, escala y desplazamiento | 2,70 | 71 % | 62 % | 12,7 % |

**Queda R0.** Las dos correcciones empeoran en todos los combos y adelantos. Hay dos motivos:
- **Los fallos llegan en racha y sin aviso.** Después de un día fuera del rango, el siguiente queda fuera el 44 % de
  las veces, cuando lo esperado es el 20 % (Christoffersen, p < 0,01). Las 8 semanas previas suelen estar tranquilas
  justo antes del salto. R1 ve poca dispersión y estrecha el rango.
- **Corregir el nivel con 15 días de retraso persigue el pasado.** R2 llega tarde al cambio y empeora el error.

**Conclusión.** El rango del total no se arregla mirando los propios errores. Los saltos de nivel (Nueva EPS en
noviembre de 2025, marzo y julio de 2026, y el terremoto) solo se anticipan con **una señal externa conocida antes**:
el estado de los convenios y de la atención de cada aseguradora, y datos más al día. Esto coincide con lo que pidió
urgencias sobre aseguradoras. Se descarta seguir puliendo el rango por la vía estadística.

---

## 2026-10-13 — El reparto del día ya está en su límite; lo que falla es el total del día en 2026

**Por qué.** Hubo una reunión del propietario con el personal de urgencias. El producto queda definido así: **la
herramienta informa y urgencias decide el personal.** No asigna turnos ni traduce a enfermeras por paciente. La
respuesta tipo es «de los 175 del día, X % en la mañana, Y % en la tarde y Z % en la noche y la madrugada; entre las
10 y las 12, posible saturación; de 23 a 5 h, tranquilo con N pacientes». El propietario pide **precisión** en eso, y
que siga funcionando cuando él se vaya del hospital.

Hasta hoy, `semana.py` cubría solo 12 de las 24 horas (mañana 6-11 y tarde 12-17), con el perfil de 8 semanas. El
rango de cada franja era el del día multiplicado por la proporción, como si el reparto fuera seguro.

**Qué se hizo.** La prueba se preregistró en las filas `reparto_del_dia` y `_enmienda`. La enmienda se escribió antes
de calcular: la fórmula de dispersión contaba dos veces el ruido de conteo. El módulo es `notebooks/reparto.py` y las
salidas están en `salidas/pronostico/reparto/`. No reentrena el total: usa las predicciones diarias de la validación
semanal (C0r y M3s, a 1-7 y a 15-21 días, 2025 y 2026). Hay cuatro franjas fijas: madrugada 0-5, mañana 6-11, tarde
12-17 y noche 18-23. El rango sale de una Dirichlet-multinomial sobre el total predicho.

**Elección (2025, a 15 días, M3s; puntos del día mal repartidos).**

| P8 (lo actual) | P26 | P52 | S26 | P52F (festivos aparte) |
|---|---|---|---|---|
| 13,58 | 13,04 | **12,93** | 13,04 | 12,85 |

Gana **P52**: el mismo día de la semana durante las últimas 52 semanas. P52F queda a menos de 0,1 puntos, y la regla
elige el más simple. Más historia reparte mejor que 8 semanas, porque la forma del día es estable y 8 días son pocos
para estimarla.

**Resultado (M3s; a 15 días: 2025 / 2026).**

| Franja | Media real | Error | Error con el total real | Piso de ruido | Rango 80 % (antes) |
|---|---|---|---|---|---|
| Madrugada | 13 / 12 | 32 / 27 % | 30 / 26 % | 24 / 24 % | 76 / 83 % |
| Mañana | 72 / 60 | 16 / 17 % | 9,6 / 10,9 % | 9,8 / 10,7 % | 75 / 78 % (62 / 59 %) |
| Tarde | 70 / 60 | 14 / 15 % | 8,8 / 8,6 % | 9,8 / 10,5 % | 81 / **73 %** (66 / 59 %) |
| Noche | 43 / 41 | 16 / 17 % | 12,2 / 13,4 % | 12,4 / 12,6 % | 80 / **71 %** |
| Hora | — | 2,2 / 2,1 pacientes | 2,1 / 2,0 | 2,1 / 2,0 | 87 / 87 % |

La tabla dice tres cosas:
1. **El reparto ya está en el límite.** Con el total del día real, el error de la mañana, la tarde, la noche y la hora
   es igual al piso de ruido: el que tendría quien conociera la tasa exacta, por puro azar de llegadas. Ningún modelo
   reparte mejor. Solo la madrugada queda unos 6 puntos por encima, con 12-13 pacientes.
2. **El rango de las franjas pasa de 59-68 % a 71-83 %**, frente al 80 % que promete. El de `semana.py` era demasiado
   estrecho.
3. **Lo que queda de error viene del total del día.** En 2026, a 15 días, la tarde y la noche se salen del rango
   (Kupiec p < 0,05) por lo mismo que se sale el día (71 %, cuaderno 26): los cambios de nivel de Nueva EPS.

**Ventanas de demanda.** El perfil anuncia **9-12 h** en la mañana y **14-17 h** en la tarde en todos los orígenes.
- Aciertos de la mañana: 86 % en 2025 y 86 % en 2026.
- Aciertos de la tarde: 79 % en 2025 y 72 % en 2026.
- Acierta lo mismo que el bloque fijo de 2024. Es un rasgo estructural del hospital, no algo que el modelo anticipe;
  se informa como tal.

**Criterio preregistrado.** Madrugada y mañana cumplen. Tarde y noche no cumplen en 2026 por la cobertura. El error
cumple en las cuatro, porque no supera el piso más el error del día más 3 puntos.

**Qué se decide.**
- El reparto de la respuesta semanal pasa a ser P52, con cuatro franjas, rango propio y ventanas de demanda.
- **Lo siguiente que hay que arreglar es el rango del total del día cuando cambia el nivel**, no el reparto.

---

## 2026-10-08 (tarde) — Resultado del cuaderno 26: ningún uso está maduro; el número sirve a 1-3 semanas, el rango no

**Qué se hizo.** Las cinco pruebas de la entrada siguiente, en `notebooks/26_madurez_de_la_prediccion.ipynb`
(constructor `construir/26_madurez_de_la_prediccion.py`, módulo `madurez.py`, salidas en
`salidas/pronostico/madurez/`). La curva de 8-14 y 22-28 días tardó 3 h 4 min, con dos pausas largas del equipo.
Corrección a la entrada siguiente: en 2026 son **32** diseños, no 33.

**Resultados.**
- **Vara única:** V y el control de 28 días clasifican distinto el 17,6 % (2025) y el 18,8 % (2026) de los días. Las
  cifras de acierto anteriores no eran comparables entre sí.
- **Curva** (M3s, error del día 2025 / 2026):
  - 1-7 días: 8,1 / 9,1 %; 8-14: 9,3 / 10,4 %; 15-21: 10,1 / 11,4 %; 22-28: 10,8 / 12,2 %;
  - el control va de 0,7 a 2,5 puntos por encima en todos los bloques;
  - útil por la regla en 24 de 28 adelantos (C0r, 21);
  - la cobertura del 80 % se mantiene en 2025 (78,6-81,0 %) y en 2026 cae de 78 % a 68 %.
- **SPA / MCS** (puntaje de cuantiles, 1-7 días):
  - 2025: el mejor diseño mejora al control un 13,3 %, pero SPA p = 0,124; el MCS retiene 15 de 26 **con el control
    dentro**;
  - 2026: un 18,0 %, SPA p = 0,027; M3 solo, p < 0,001; el control queda fuera del MCS;
  - **frente a C0r nada se separa con la selección corregida** (p de 0,60 a 0,99).
- **Cobertura:**
  - honesta en el rodante a 1 día (M3: p condicional 0,574 y 0,972);
  - desde los 8 días la independencia falla en todos los bloques: P(fuera | ayer fuera) del 33-51 % frente al 14-23 %;
  - a 15-21 días en 2026 queda fuera el 28,6 % de los días y el 42 % de las semanas;
  - la cola de abajo pesa más de lo anunciado (12-15 % de los días bajo el cuantil 10).
- **CUSUM:** 71 alarmas, 64 con choque conocido. Hay 4 en enero-octubre de 2025 sin choque, lo que da una falsa
  alarma por adelanto cada ~10 meses. Hay 3 entre el 30 de enero y el 1 de febrero de 2026, en tres adelantos a la
  vez: una semana baja sin explicación con los datos actuales.
- **Nivel estable** (11 meses): M3s no le gana al control en 2025 (65,7 % frente a 67,4 %). En 2026 lo supera por 1-2
  puntos, dentro del ruido. Su BSS sí es mejor (15,9 frente a 8,9).

**Veredicto, con el criterio preregistrado:**
- A, la semana siguiente con datos al día: falla en el rango semanal de 2026 y en 1 alarma aislada;
- B, la semana con el retraso real: falla en el rango (racha) y en 1 alarma;
- C, el día alto en un nivel estable: falla en la utilidad;
- D, un mes desde diciembre: falla en la utilidad y en el rango.

**Ninguno está maduro.**

**Lectura.** El número esperado a 1-3 semanas es confiable y escala: el error es estable entre años y la vigilancia
vuelve a su nivel tras cada choque. Lo que no está maduro es el rango a más de una semana, que falla en racha por el
error de nivel de la red de salud, y la anticipación del día en periodos estables. La ventaja demostrable sobre el
calendario es seguir el nivel; la de los mecanismos externos sobre C0r no se separa con la selección corregida.
Es un matiz medido, no una refutación del contexto: su efecto en el total diario es menor que lo que estas pruebas
alcanzan a separar.

**Reglas fijadas después del preregistro, pero antes de ver la curva de 8 y 22 días y el veredicto:**
- un bloque de 7 adelantos es útil si lo es la mayoría;
- para el uso D, los meses de 2026 se juntan.

Están declaradas en los límites del cuaderno.

**Dos defectos encontrados y corregidos en la sesión:**
- `semana.py` fija `pr.H = 21` al importarse, y la primera corrida de la curva lo pisaba;
- la columna «falla en» del veredicto no reconocía los booleanos de numpy.

## 2026-10-08 — ¿Está madura la predicción? Cinco pruebas preregistradas (cuaderno 26)

**Qué planteó el propietario.** Las predicciones «se ven bien», pero no sabe si lo están de verdad ni si van a
seguir así con el tiempo. Preguntó si existe algo como LazyPredict para escoger la técnica de validación.

**Respuesta de método.** La técnica de validación no se escoge por puntaje: si se elige el esquema que da mejores
números, deja de validar. Se fija por el uso: el adelanto real, la frecuencia con que llegan los datos y lo que se
sabe en el origen. Lo que sí existe son pruebas para la duda de fondo, y se aplican las cinco propuestas (fila
`madurez_de_la_prediccion`, escrita antes de calcular):
1. **Una sola vara de «sube»:** la media del mismo día de la semana en las 8 semanas que terminan en el origen.
   - **Por qué:** hasta hoy hubo tres varas (el control de 28 días, el control rápido y 8 semanas con banda de ±5 %),
     y los resultados no se podían comparar entre pruebas. Esta se conoce en el origen sin modelo y vale igual para
     todo adelanto.
   - **Revierte en parte** el sentido de «sube» de `CLAUDE.md` (sobre el control): el control de calendario pasa a
     ser competidor, no vara. Sigue siendo la referencia contra la que se mide todo.
   - La banda del ±5 % se quita porque se eligió después de ver la imagen del 07-10.
2. **El adelanto operativo es de 15 a 21 días, no de 1.** La base la actualiza un tercero una vez por semana: hoy,
   8 de octubre, los datos llegan al 20 de septiembre. La validación a 1-7 días es el caso de datos al día, no el
   de operación.
3. **SPA de Hansen y Model Confidence Set** (`arch` 8.0.0, instalado hoy; no movió numpy ni pandas). Se comparan
   todos los diseños guardados: 26 en 2025 y 33 en 2026, contando las combinaciones. La pregunta es si el elegido
   le gana al control después de corregir por haberlo escogido entre muchos.
4. **Kupiec y Christoffersen** para el rango del 80 %. Christoffersen detecta fallos agrupados, que es lo que pasa
   cuando el error es de nivel y se repite toda la semana.
5. **Vigilancia** con CUSUM sobre el PIT y la tabla de predicciones prospectivas con su estado.

**Cálculo nuevo.** Hoy la curva por adelanto tiene 1-7 y 15-21 días. Faltan 8-14 y 22-28: `python
notebooks/madurez.py --curva` (C0r y M3s, mismo diseño de `m3_semanal`). `semana.validar` acepta ahora
`adelantos` y `archivo`; con los valores por defecto no cambia nada.

**Criterio de madurez, fijado antes:** por uso.
- **A:** el nivel de la semana siguiente con datos al día.
- **B:** la semana con el adelanto operativo.
- **C:** anticipar el día alto dentro de un nivel estable.
- **D:** meses a ciegas.

Un uso es maduro si cumple las cuatro condiciones:
- el adelanto es útil;
- el elegido supera al control en el SPA, o al menos no sale del MCS;
- el rango es honesto;
- la vigilancia no da alarmas sin explicación.

## 2026-10-07 (noche, 2) — Cuaderno 25: revisión de predicciones en marzo, julio, agosto y octubre

**Por qué.** El propietario sospecha que el 6 % de septiembre es una coincidencia, y los datos le dan la razón:
septiembre fue el mes más tranquilo de 2026, con una variabilidad diaria del 8,2 % y el menor error a ciegas (4,5 %).
Para elegir los meses difíciles se midió, para cada mes de 2026, el cambio de nivel, la variabilidad diaria frente a
las 8 semanas previas, los días a más del 15 % y el error del SARIMAX ya guardado en `e1/anio`. Con eso se eligieron:
- **marzo**, por un salto de +28,7 % con el regreso de Nueva EPS (27 días a más del 15 %);
- **julio**, por un desplome de −17,2 % con la nueva caída de Nueva EPS;
- **agosto**, por el terremoto del 10, la mayor variabilidad del año (20,5 %) y el peor error a ciegas (18,5 %).

**Qué se decidió.** Lo eligió el propietario sobre la propuesta; está preregistrado en la fila `revision_de_predicciones`.
- **Marzo, julio y agosto se predicen desde el 31-dic-2025**, con el mismo modelo de `mes_a_ciegas` y sin
  reentrenar nada para elegir.
- **Octubre se predice desde el 2026-09-20** y se guarda como prospectivo, sin rehacerlo nunca. El propietario lo
  verifica durante el mes con una fuente externa.
- **Sube, normal o baja:** la vara es la media del mismo día de la semana en las 8 semanas previas al mes, o al
  2026-09-20 en el caso de octubre. La banda de «normal» es de ±5 %. Se reporta siempre la tasa base.

**Infraestructura.**
- `mes_a_ciegas.py` pasa a tener `predecir(o, fechas)`, `revisar()`, `vara()` y `reportado()`.
- Las salidas van a `salidas/pronostico/revision/`: parquet, json con fecha y commit, y la tabla legible de octubre.
- Nuevo `datos/triage_reportado.csv`: conteos escritos a mano de una fuente externa. Solo sirven para comparar,
  nunca para entrenar. Empieza con la semana del 21 al 27 de septiembre de la imagen del propietario.
- Esto cambia la vara de la entrada siguiente: de 8 semanas móviles a 8 semanas anteriores al mes. En el cuaderno
  25, septiembre se recalcula con la vara nueva.

**Resultados.** Ejecutado el 2026-10-07, sin reentrenar nada para elegir.

| Mes (desde el 31-dic-2025) | M3s | C0r | Calendario | Días en el rango 80 % | Acierto sube/normal/baja | Tasa base |
|---|---|---|---|---|---|---|
| Marzo | 13,1 % | 16,0 % | 22,1 % | 61 % | 93,5 % | 96,8 % (sube) |
| Julio | 11,9 % | 7,8 % | 7,2 % | 94 % | 61,3 % | 93,5 % (baja) |
| Agosto | 20,0 % | 16,6 % | 12,5 % | 68 % | 48,4 % | 77,4 % (baja) |
| Septiembre (27 días) | 5,6 % | 5,8 % | 12,1 % | 100 % | 88,9 % | 88,9 % (sube) |

Lectura:
- **La media de los cuatro meses es 12,7 %**, en línea con la validación de los septiembres de 2023-2025 (11,3 %).
  **El 5,6 % de septiembre fue un mes fácil, no la regla**: la sospecha del propietario se confirma.
- El modelo **no anticipa los cambios de nivel de Nueva EPS** desde diciembre:
  - en marzo se queda corto (de −10 % a −20 % casi todos los días);
  - en julio y agosto se pasa;
  - la semana del terremoto (10-16 de agosto) va un +44,6 % arriba.
- M3s le gana al calendario en marzo y septiembre, pero pierde en julio y agosto.
- **En ningún mes el acierto sube/normal/baja supera la tasa base.** Dentro de un mes en que todo sube o todo baja, el
  modelo no distingue día a día. Lo que sí acierta son los festivos: el 23 de marzo y el 7 y el 17 de agosto dicen
  «baja» y bajan.

**Octubre (prospectivo).** Guardado el 2026-10-07 a las 15:13, con datos hasta el 2026-09-20.
- Anuncia una semana de 180/día, de 164 a 196, entre el 5 y el 11; 176 y 178 las dos siguientes; 185 la última.
- El lunes 12 (festivo) da 157, «baja»; casi todos los demás días dan «sube».
- Ojo: la vara incluye el bache de agosto.
- El commit anotado (63059ef) es el HEAD, pero el código de `mes_a_ciegas` todavía no está en git. Hasta que se haga
  commit, la versión exacta no queda fijada.
- Los días del 1 al 7 de octubre ya habían pasado al guardarla, aunque no estaban en ningún dato del modelo; la
  prueba prospectiva en sentido estricto empieza el 8.

## 2026-10-07 (noche) — Mes a ciegas: la semana del 21 al 27 de septiembre, verificada con el reporte del propietario

**Dato real.** El propietario compartió un reporte del hospital (imagen: triages por hora × día de la semana). La
tabla no trae fechas; se asume que es la semana del 21 al 27 de septiembre de 2026, la primera que falta en
`salidas/`. Totales: lun 218, mar 189, mié 188, jue 152, vie 178, sáb 151, dom 141 (1.217). **No se reentrenó:** se
comparó con `salidas/pronostico/mes_a_ciegas/2026.parquet` (M3s entrenado hasta el 31-dic-2025).

**Resultado de la semana.**
- M3s: error del día del 4,2 % y 7 de 7 días dentro del rango del 80 %.
- La semana: 181,0 por día anunciado (165-197) contra 173,9 real, dentro del rango. En total, 1.248 contra 1.217.
- El peor día, el jueves 24: se anunciaron 182 y hubo 152.

**Sube, normal o baja (pedido del propietario).** Lo normal de la prueba (la regresión con el nivel de diciembre) no
sirve, porque sale bajo. Se usó otra vara: **la media del mismo día de la semana en las 8 semanas previas**, con
datos reales anteriores al día, y **una banda de ±5 %** para «normal». La banda reparte los días en tres grupos de
tamaño parecido con un ruido diario del 12,6 %. Se eligió después de ver la imagen pero antes de calcular las
categorías; se reporta la sensibilidad.

**Resultados, del 1 al 27 de septiembre.**
- M3s acierta 22 de 27; la semana del 21 al 27, 6 de 7. C0r acierta 21 de 27.
- Con banda de ±3 %, M3s acierta 24 de 27; con ±8 %, 20 de 27.

**La salvedad que manda.** De los 27 días, 22 subieron, 4 quedaron normales y 1 bajó: septiembre fue un mes de
recuperación frente a un agosto hundido (terremoto y Nueva EPS). Decir «sube» todos los días también da 22 de 27,
así que **el 81 % de M3s no supera esa tasa base**.
- Lo que el modelo sí mostró: desde diciembre anunció que septiembre quedaría por encima del nivel de las semanas
  previas, y la semana bien.
- Lo que no mostró: separar día a día lo normal de lo alto. Dijo «normal» 4 veces y acertó 2; nunca dijo «baja»,
  y el único día que bajó (jue 24) lo falló.

## 2026-10-07 (tarde) — El cuaderno 24 cambia a la prueba del mes a ciegas; revierte su prueba de una semana

**Decisión del propietario.** La predicción de una semana con datos de la víspera «no le gusta»: con un día de
adelanto el modelo se apoya en la memoria reciente y acierta cualquier semana tranquila (el calendario solo hizo
3,9 % en la del 14 al 20 de septiembre). Se pide, y se fija antes de calcular (fila `mes_a_ciegas` de
`patrones/datos/variables.csv`):
- **entrenar solo con el triage hasta el 31-dic-2025** y predecir de una vez **cada día de septiembre de 2026, del 1
  al 30** (244-273 días de adelanto), aunque del 21 al 30 no haya dato todavía;
- **las mismas variables de M3s, sin el terremoto.** El propietario siente que el terremoto no afectó; el cuaderno 20
  midió −48,7 % el día 0, pero **en este diseño no puede influir**: es del 10-ago-2026 (fuera de todo
  entrenamiento) y su ventana de 0 a 21 días termina el 31 de agosto. Quitarlo solo lo deja explícito;
- tabla de los registros de entrenamiento y tabla final día a día y por semana, predicción frente a realidad.

**Añadido sin pedirlo, y por qué.** El mismo diseño en septiembre de 2023, 2024 y 2025 (cada uno entrenado hasta el
31-dic anterior) como **validación**: es de donde salen porcentajes de confianza con 90 días y 15 semanas, en lugar
de 20 días de 2026. Lo que no se sabe el 31 de diciembre (salud, social, paro) va como año típico; la red se congela
en el origen; el clima de rezago corto sigue fuera, como en M3s. Código: `notebooks/mes_a_ciegas.py`, experimento
`m3s_ciego` (opción nueva `sin` en `mecanismos.contexto`); salidas en `salidas/pronostico/mes_a_ciegas/`. El LightGBM
es directo, con un modelo por adelanto (244-273). Unos 3-4 minutos por año.

**Evidencia.**

| Septiembre | M3s | C0r | Lo normal | Días de M3s en el rango del 80 % |
|---|---|---|---|---|
| 2023 (validación) | 9,6 % | 10,1 % | 9,0 % | 90 % |
| 2024 (validación) | 18,1 % | 17,8 % | 17,6 % | 43 % |
| 2025 (validación) | 6,1 % | 6,2 % | 7,0 % | 93 % |
| **2026 (prueba, 20 días)** | **6,0 %** | 6,2 % | 12,5 % | 100 % (20 de 20) |

Error medio del día. En 2026 M3s anunció 176,3 de media para los 20 días con dato y hubo 178,4. Por semanas:
169,2 real frente a 174,7 en la del 1 al 6 de septiembre, y 182,4 frente a 179,6 y 179,3 en las dos siguientes,
todas dentro de su rango.

**Lectura honesta.**
- **Con ocho meses de adelanto el modelo empata con el control de calendario** en la validación (11,3 % frente a
  11,2 %). Lo que aporta es el rango: el 76 % de los días cae dentro, frente al 62 % de lo normal.
- 2026 salió mejor que esa expectativa; con un mes no se separa el acierto de la suerte.
- 2024 es el año imposible: subió a su máximo histórico durante el año.
- **El sube/baja no informa en esta prueba.** Lo normal (regresión anual con el nivel de diciembre) queda un ~10 %
  por debajo de septiembre: el 86 % de los días de validación «suben», y decir siempre que sube acierta más que M3s
  (60 %). Se declara en el cuaderno y no se usa como medida.
- **El rango semanal es demasiado estrecho a este adelanto**: cubre el 56 % de las semanas, no el 80 %. El error es
  de nivel y se repite toda la semana; la rho de días consecutivos (0,14) no lo recoge. No se corrigió para no
  ajustar después de mirar. Arreglarlo exige una fila nueva.

**Revierte** la prueba de una semana de la entrada siguiente: se retiran sus secciones del cuaderno 24 (semana a
1-7 días y predicciones guardadas). El cuaderno pasa a llamarse `24_de_la_base_al_mes_a_ciegas`. La conexión, el
conteo y el calendario de calor se quedan igual.

## 2026-10-07 — Cuaderno 24: de la base a la semana predicha y verificada

**Decisión.** Se crea el cuaderno 24 (`notebooks/construir/24_de_la_base_a_la_semana_predicha.py`), pedido por el
propietario: conexión con la base y conteo de `DIM_TRIAGE`, el mismo calendario de calor (`calplot`) de
`exploracion.ipynb`, la predicción de una semana con M3s (y C0r de referencia) sin filtración, y la comparación con
lo ocurrido en el formato de `formato-verificacion-semanal`. Una sección final compara las predicciones guardadas
(`semanal/` y `prueba_ciega/`) con la fuente.

**Cómo se elige la semana, y por qué.** La primera semana completa posterior a `pr.FIN` (el último día con que se
entrenó el modelo), con origen en `pr.FIN`: es la única semana que ni los datos ni la elección de modelos han visto.
Si la fuente no tiene semana nueva, se toma la última semana completa y el origen pasa al domingo anterior; el
triage posterior al origen se borra igual, pero esa semana sí estuvo en el periodo de 2026 con que se compararon M3
y C0r. El último día de la extracción se descarta siempre: es el día en curso o el corte de la carga, y suele estar
a medias (el 21-sep-2026 tenía 94).

**Conexión.** El cuaderno no escribe SQL propio: llama a `extraccion.motor()` y a la nueva
`extraccion.__main__.conteo_horario()` (día × hora × `COUNT(*)`, sin escribir nada). Si la conexión falla, lo dice y
lee `salidas/triage_horario.parquet`. Compara además la base con `triage_diario.parquet` en los días comunes, para
detectar días corregidos después de la extracción.

**Evidencia (ejecutado sin conexión, fuente archivo).** Semana del 14 al 20 de septiembre con origen el 13 (1-7
días de adelanto): M3s anunció 183/día (171-195), real 182,4; error del día 4,6 %, 7 de 7 días en el rango, 6 de 7 en
sube/baja. C0r 4,5 %; el control de calendario solo, 3,9 %. Con 1 día de adelanto el lunes 14 da 221, la misma cifra
de la prueba de instalación del servidor (220). Contrasta con la prueba ciega a 14-20 días (M3s 155, falló): en esa
semana el adelanto pesó más que el modelo. Es una sola semana: no basta para concluirlo en general.

**Dependencia.** `calplot` 0.1.7.5 no estaba instalado en ningún entorno; se instaló en `.venv` con `--no-deps` y se
añadió a `requirements.txt`.

## 2026-10-06 (cierre) — M3s gana la regla semanal, pero falla la prueba ciega de septiembre a 14-20 días

**Decisión: M3s es el modelo de la respuesta semanal, por la regla `m3_semanal`.** M3s es M3 sin las 7 variables
de clima, para que sirva con cualquier adelanto.
- **2025, 52 domingos, adelantos 1 y 15:** criterio M3s 5,98 contra C0r 4,46. Cobertura semanal del 80 %: 80,8 % y
  82,7 % en los dos.
  - Brier M3s − C0r: adelanto 1, −3,27 ×1000 [−10,2; +3,7]; adelanto 15, −4,15 [−14,1; +6,5].
  - Mejora sin significancia.
- **2026, mirado una vez:** 13,55 contra 12,46. Pero la semana cae dentro del rango del 80 % solo el 60,5 % y el
  58,3 % de las veces (C0r: 68,4 % y 66,7 %). En 2026 los rangos semanales de los dos son demasiado estrechos.
- Logs en el scratchpad de la sesión: `mec/regla_m3s_2025.log` y `mec/regla_m3s_2026.log`.

**Predicciones guardadas antes de conocer lo real** (`salidas/pronostico/semanal/`, en git):
- semana del 2026-10-05: M3s y C0r;
- semana del 2026-10-12: solo M3s. La de C0r se cortó al cerrar la jornada.

Las dos usan datos hasta el 2026-09-20, así que tienen 15 y 22 días de adelanto.

**Prueba ciega pedida por el propietario** (`semana.py --origen 2026-08-31`, en `salidas/pronostico/prueba_ciega/`).
La semana del 14 al 20 de septiembre, predicha sin ningún dato de septiembre, con 14 a 20 días de adelanto:

| | Lun | Mar | Mié | Jue | Vie | Sáb | Dom | Media | Error medio | Días en rango |
|---|---|---|---|---|---|---|---|---|---|---|
| **Real** | 221 | 199 | 200 | 199 | 171 | 150 | 137 | **182,4** | — | — |
| M3s | 184 | 166 | 162 | 161 | 155 | 133 | 125 | 155 (142-168) | 14,3 % | 3 de 7 |
| C0r | 195 | 176 | 173 | 171 | 168 | 137 | 138 | 166 (151-182) | 8,9 % | **7 de 7** |

- La forma de la semana la aciertan los dos: el lunes es el más alto y el domingo el más bajo.
- Los dos predicen subida frente a las 4 semanas anteriores (148/día). Subió.
- M3s dio un 13 % de probabilidad de que la semana quedara sobre lo normal (167/día). Quedó en 182: se equivocó.
  C0r dio 49 %, sin opinión.
- **M3s subestimó los días laborables entre un 17 y un 19 %.**

**Por qué falló (hipótesis, no probada).** El 31 de agosto el triage venía deprimido: 147,6/día en las 4 semanas
previas, por el terremoto del 10 de agosto y la caída de Nueva EPS de julio. Del 1 al 13 de septiembre ya había
rebotado a 176/día. Con 14-20 días de adelanto, el contexto se congela en su valor del origen. Las variables de red
con compuerta y el nivel reciente arrastran el bache hacia la semana predicha, y M3s, con más variables de ese tipo,
lo arrastra más que C0r.
- Con 1 día de adelanto (origen rodante), M3s predijo esa misma semana con errores de −9 % a +6 % y los 7 días en
  rango.
- **Es una sola semana: no anula la validación de 52 semanas, pero es una alerta.** El modelo acierta a corto plazo
  y le cuesta anticipar el rebote después de un choque cuando el adelanto es de 2 a 3 semanas.

**Lo que queda por decidir con el propietario:**
- si M3s se mantiene en la semana mientras se acumulan semanas verificadas, o si se publica C0r junto a él;
- probar el congelamiento del contexto: anomalías a cero, como en `anio_a_ciegas`, en lugar de congelar en el
  origen. Requiere su propia fila preregistrada.

**Otros del día.**
- `semana.py` tenía un defecto previo: no podía predecir semanas posteriores al último dato. Se arregló, y la
  validación no cambia.
- `notebooks/servidor/modelos_pronostico.ipynb`: copia mínima del código de los dos modelos y de su combinación, para
  el equipo del servidor con Python. Sin datos. Con origen 2026-09-13 da una mediana de 220 para el lunes 14, y el
  real fue 221.

## 2026-10-06 — La vara de `CLAUDE.md` pasa a ser la reproducible; M3 va a la semana; el 00 cuenta la predicción

**Decisión 1 (el propietario la delegó al orquestador).** Las cifras «MAPE 10,13 %» y «acierto 77,2 %» de la tabla
«Lo ya medido» se quedan, pero marcadas como no reproducibles. Al lado va la referencia reproducible: C0r y M3
en 2025 y 2026, con origen rodante.
- **Por qué no se borran:** el archivo histórico vale, y el criterio con que se tacharon otras filas fue haberlas
  anulado por un error. Aquí no hay error demostrado, sino un script perdido.
- **Por qué cambia la vara:** ninguna mejora se puede medir contra un número que no se puede recalcular (regla 7).
- **Medias anuales:** 2024 es 226,9 y 2026 es 172,6 con la serie depurada.

**Decisión 2 (el propietario).** La tabla de frases de ejemplo del cuaderno 00 se queda. Al 00 se le añade al final
la historia de la predicción:
- la competencia de modelos;
- LazyPredict y la rejilla;
- la combinación SARIMAX + LightGBM;
- C0r;
- el entrenamiento por mecanismos y sus resultados.

Va en primera persona.

**Decisión 3 (el propietario).** M3 se lleva a la respuesta semanal, «que es lo que más se va a usar». Va con una
variante preregistrada antes de calcular, porque las variables de clima de M3 exigen adelantos de 7 días o menos.

## 2026-10-06 — Mecanismos, etapa 2: la regla elige M3; 2026 empata; lo que más ayuda es quitar la COVID fuerte

**Decisión.** Por la regla preregistrada (`mecanismos_regla`), **M3 reemplaza a C0r** como modelo principal
para adelantos de 1 a 7 días. M3 son los mecanismos más la exclusión de la fase fuerte de la COVID, del
2020-03-15 al 2020-08-31. Es el mismo criterio con que C0r reemplazó a C0: se elige con 2025, y 2026, que dio
empate, no revierte.

La respuesta semanal sigue con C0r: las variables de clima de M3 exigen adelantos de 7 días o menos, y la semana
usa 21. Pasar M3 a la semana requiere una variante preregistrada.

**2025, origen rodante (365 orígenes, h = 1 a 7):**

| Modelo | Criterio | Acierto (28 días) | BSS de pico | Cobertura del 80 % | MAPE | BSS en calma |
|---|---|---|---|---|---|---|
| C0r | 5,20 | 61,9 % | 2,9 | 80,5 % | 8,48 % | −5,3 |
| M1 | 6,88 | 62,4 % | 6,3 | 80,1 % | 8,19 % | −3,5 |
| M2 | 6,45 | 63,1 % | 5,5 | 80,9 % | 8,24 % | −5,8 |
| **M3** | **6,94** | **63,2 %** | **7,9** | 78,0 % | **8,17 %** | **−1,3** |

- Brier de M3 menos C0r: −3,39 ×1000 [−10,0; +2,5] con la vara de 28 días y −5,16 [−11,7; +0,5] con la rápida.

**2026, mirado una vez (257 orígenes):**
- M3 15,07 contra C0r 15,87; acierto 68,5 % contra 69,7 %.
- Brier: +1,90 [−2,9; +6,7]. **Es un empate.**
- La corrida de M3 en 2026 se calculó antes de aplicar la regla, para ganar tiempo de cómputo. No se abrió hasta
  después de elegir.

**Rejilla congelada 2023-2025** (enmienda `mecanismos_desglose_multianual`; 1.088 días, h = 1):
- M3 frente a C0r: Brier −4,7 ×1000 [−7,7; −2,0], significativo. Mejora en los 3 años: 2023 −2,5 → +0,2,
  2024 7,1 → 9,2 y 2025 8,5 → 10,0.
- **La noche festiva se aprende:** el error de la mediana baja de 21,2 % a 6,5 % en 9 noches.
- **La Feria empeora en M1** (error de 7,6 a 11,6 %). Probablemente se suma con el desplazamiento del día
  siguiente entre el 2 y el 4 de enero. Queda como hipótesis con su propia fila.
- La ola de salud y las fiestas lejanas no aportan.
- M1 y M2 **empeoran la calma** (+3,2 y +5,6 ×1000): las variables meten ruido donde no pasa nada. M3 no la
  empeora.
- **Lectura:** la mayor parte de la mejora viene de quitar la COVID fuerte, no de las variables externas. Es lo que
  el propietario sospechaba de la COVID. Bajarle el peso (T1) no servía; quitar solo la fase fuerte sí sirve.

**Curvas de aprendizaje (`curvas_de_aprendizaje`):**
- La historia ayuda mucho hasta 2021 y después se aplana. BSS de C0r en 2024 según desde dónde se entrena: desde
  2023 −9,1; desde 2022-03 −0,5; desde 2021 8,6; desde 2020 7,1.
- Lectura preregistrada: casi todo sale «indeterminado». La calma de C0r y todos los días de M1 sin la COVID salen
  «aplanado».
- **Para los días comunes no faltan registros históricos.**
- Los tipos raros no tienen muestra, y la base no tiene triage anterior a 2020: Feria 4 en el entrenamiento,
  El Niño o La Niña fuerte 1, catástrofe 0, olas del régimen actual 1. Llegarán con los años, o de otros
  hospitales o del CRUE.

**Límites:**
- La lluvia NASA de agosto de 2026 es provisional en `clima_completo`, aunque en esas semanas las variables de
  clima casi no se activaron.
- Las formas de la Feria, de las noches y del corte de 60 km se midieron con datos que incluyen 2025.

**Diagnóstico operativo:** los 2.746 s de m3 eran contención de la máquina, no código: el ajuste con h = 1 tarda
25 s en m3 y 26 s en m1.

## 2026-10-06 — Revisión de los 22 cuadernos: lo que cambió de conclusión al recalcular

**Decisión.** Cada cuaderno lo rehízo un agente, con voz de analista y sin tono de chat. Cada cifra tiene que
salir de una celda o de una línea citable, y el orquestador revisó cada informe cifra por cifra. Al recalcular,
estas conclusiones cambiaron. Valen más que las entradas anteriores que las contradigan:

**Desenlace y control**
- **Estancia (01, 02):** los regímenes salen distintos según el corte: 9,8 / 55,8 / 9,7 en el 01 y
  10,7 / 56,0 / 9,6 en el 02. Al cortar en el 20-09-2026, el 02 queda en 9,6.
- **Medias anuales (01, 05, 06):** 2024 es 226,9 y 2026 es 172,6 con la serie depurada (sin el 21-03-2024 ni el
  21-09-2026); `CLAUDE.md` da 226,4 y 172,3 con el archivo tal cual. La caída es del −23,9 % en los dos casos.
- **Amplitud anual (01):** el 19,7 % mezcla tendencia con ciclo. Relativa a la media de cada año, en 2022-2024 es
  18,6 %, con pico en mayo y valle en diciembre.
- **La tabla «Lo ya medido» de `CLAUDE.md` no se reproduce entera (05).** Se repitió el control con calendario
  más un escalón en 2025-11, en los mismos 615 días y con origen rodante:
  - ruido 12,3 % (12,6 % en la tabla), autocorrelación 0,438 (0,423) y bases simples parecidas;
  - el MAPE del control da 11,41 % (10,13 %) y el acierto en «sube» 70,2 % (77,2 %).
  - El script del 2026-09-17 ya no existe. **Esas dos cifras no se pueden reproducir con la especificación
    reconstruida.**

**Hospital**
- **El ingreso cae en escalón en mayo de 2024 (10):** del 44,4 % al 29,9 % de los triages.
  - Nivel IV: de 26,2 % a 0,8 %. Nivel III: de 59,3 % (ago-2024) a 1,0 % (ene-2025).
  - No es efecto de la mezcla de niveles, y es anterior a la crisis de Nueva EPS.
  - Obstetricia salta en 2024: no «crece de forma sostenida».
  - La diarrea de marzo-abril no es un patrón robusto.
- **Privacidad (10):** ninguna casilla de menos de 20 casos queda visible. Las de 5 a 12 casos del cuaderno
  anterior pasan a «otros» o a «<20».
- **Nivel frente a Nueva EPS (02):** r = −0,80 es en 22 meses, de ene-2024 a oct-2025, no solo en 2025.

**Red de aseguradores**
- **El pico de 2024 es de SURA (00, 01, 18):** pasa de 59,0 a 91,9 triages/día entre mar-2024 y abr-2024.
- **Nueva EPS frente a Salud Total (18):** la relación con el hospital es por contratación. Nueva EPS genera
  17,1 triages/mes por cada 1.000 afiliados; Salud Total, 0,7.
- **Concentración (18):** Nueva EPS + SURA es el 77-86 % del triage, no el 80-90 %.
- **Compensación de la caída de Nueva EPS:** depende de la ventana. Da 13 % y 22 % (01) o 16 % y 11 % (18).
- **Escalones y cierres (07):** los escalones son transiciones de semanas, no saltos de un día.
  - El «+15,5 % tras Avidanti» está dentro de lo habitual de esas fechas (control: +11,1, 0,0, +11,1).
  - La atribución del pico de 2021 a Medimás no tenía fuente y se retiró.

**Feria**
- **Firma por asegurador (07):** otras EPS +32,0 ± 6,3 frente a +11,1; SOAT +36,9 ± 5,5; Nueva EPS +14,4; SURA −4,2.
  - SOAT, otras EPS y particulares son el 9,0 % del triage: por eso el total solo sube +7,3 %.
  - La madrugada no se separa de otros regresos (+10,2 frente a +8,0).
- **Feria en el total (06):** el +6,3 % depende de 2022, que cae en la ventana COVID. Sin 2022 queda en +2,1 %, y
  sin 2020 ni 2022, en −0,3 %.

**Picos**
- **Diciembre falso (08):** el control A tenía 0 días de 2021 en su ajuste.
- **Los 30 picos notables (08):** 18 tienen factor identificado, 4 solo coinciden con fiestas lejanas y 8 no
  tienen explicación con los datos disponibles.
- **Un pico es de toda la demanda (08, 14):** todas las bandas suben, de +19 % a +27 %.
- **Dosis de marcas (14):** P(pico) pasa de 11,2 % sin marcas a 19,6 % con 3 o más. Es exploratorio y cambia de
  forma según el periodo.

**Clima**
- **El triage total no es la IRA diluida (17):** los efectos del clima sobre la IRA y sobre el total tienen
  correlación −0,35 entre 266 pares, y solo 6 sobreviven en los dos.
- **Las firmas de clima por banda no se confirman en 2025-26 (21):** de 32, 8 conservan el signo, 1 se confirma y 4
  se invierten. El «+4,6 % en 65+ con lluvia» es sobre todo de 2024. El «hasta 3 veces más fuerte por banda» vale
  solo para el descubrimiento. El 21 tenía 65 pruebas por parte, no 77.
- **Seco → lluvioso (07, 17):** +13,4 ± 15,0 en 0-4 años. Sin el episodio del 2024-04-03, que coincide con el
  escalón de SURA, queda en +8,2 ± 13,0. No es significativo, y en el total no se ve.
- **Frío por temporada (11):** el frío pesa más en temporada de lluvias que fuera de ella: +12,6 % frente a +4,7 %
  (p = 0,032). Es exploratorio: la partición no estaba fijada antes de mirar.
- **El método del cuaderno 06 (06):** con efectos inyectados, solo detecta efectos semanales de 5-10 % o más. El
  «ningún factor afecta» se reemplaza por esa cota.

**Vigilancia y familias**
- **Vigilancia por edad (13):** la IRA 0-4 sube el triage 0-4 un +9,2 % por desviación típica, y se confirma en
  2025. Pero el triage también «predice» a la IRA con 2 semanas de adelanto: no hay dirección.
- **Olas (13):** solo hay 5 olas respiratorias en 2022-2025, y no se separan de la estación.
- **Varicela y paro de 2021 (19):** se anula. Ventanas al azar dan un efecto igual o mayor el 17,6 % de las veces.
- **Salud mental y desastres (19):** descansa en un solo episodio, la alerta del volcán de 2023. Queda como
  hipótesis.

**Regímenes y catástrofes**
- **Terremoto (20):** día 0 −48,7 %; el peor día de 1.460 fechas al azar fue −37,9 %. Días 1-7, −22,3 %. Los
  niños de 0-14 siguen un −30 % hasta la tercera semana.
- **Sismos como clase (20):** 26 en la ventana del hospital, sin efecto.
- **Paro (20):** no se separa de la COVID.

**Calibración del azar (12), que corrige a las entradas del 2026-09-30 y a la cifra «36» del cuaderno 17**
- El barrido se repitió 300 veces con el desenlace desplazado en círculo. El azar real es de 66,7 de 693 pruebas
  con p < 0,05 (9,6 %, no 5 %) y está sobredispersado: el percentil 95 es 149.
- **IRA de la ciudad:** la señal es real y fuerte. Sobreviven 47 pruebas frente a 0,75 esperadas por azar, y 7 se
  confirman en 2025 frente a 0,08. La mueve el estado del último mes (menos sol, más humedad), no la transición
  semanal.
- **Triage total:** los «36 supervivientes» del 17 dependen de cómo se asigna el mes a cada semana. Con el mes del
  primer día salen 36; con el de la mitad, 18, frente a 12,7 del azar (p = 0,24).
  - **En el total, la señal del clima no se puede separar del azar ni de la fecha.**
  - «El entorno general no predice el triage total» (2026-09-30) pasa a esta formulación.
- **Hipótesis de dirección:** CP1 (soleado y seco) anticipa menos triage en 0-14 años. Los 10 coeficientes son
  negativos en descubrir y 9 de 10 en confirmar.
- **Lluvia reciente en 65+:** se reproduce en 2022-24 y se invierte en 2025-26 (+4,2 %, p = 0,033).
- **Defecto de datos:** `clima_completo.csv.gz` diverge del unificado en la lluvia de NASA del 1 al 24 de agosto
  de 2026 (49,7 frente a 154,3 mm). Parece provisional, y afecta solo a la prueba de 2026.

**Fuentes y método**
- **Defectos de fuente (03):**
  - la SE53-2025 del evento 998 sigue en el archivo (`indices.py` ya la anula);
  - NASA frente al pluviómetro da 0,28 / 0,46 / 0,66, no 0,30 / 0,52 / 0,80;
  - Power BI se fija por fecha de captura.
- **Primer entrenamiento (15):**
  - E2 empeora el Brier frente a E1;
  - ninguna externa pasa del 1,70 % de la ganancia;
  - «los 42 regresores empeoran» era falso: empeoran 32 de 42.
- **Bibliografía (23):** se retiraron Petravić 2025 y las cifras atribuidas a Marcilio 2013, que no se pudieron
  verificar. Murtas 2022 estaba mal atribuido.
- **`marcas.py`:** los umbrales dependían del rango de fechas: «red de salud» daba 36 días desde 2020 y 83 desde
  2022-03. Se fijó la referencia 2020-2024. Llamado desde 2020 da lo mismo que antes, así que nada registrado
  cambia.

## 2026-10-06 — Mecanismos en la forma en que se midieron: diseño, preregistro y prueba de humo

**Decisión del propietario.**
- El modelo toma lo descubierto con el subgrupo de días, la ventana, el rezago y el gatillo con que se midió.
- Los registros de entrenamiento se escogen para cubrir eventos y calma.
- La COVID se trata de otro modo.
- Se monitorea si faltan registros históricos, no variables.

**Qué se construyó.** El módulo `notebooks/mecanismos.py` y los experimentos m1, m2 y m3. Se preregistraron en 14
filas de `variables.csv` (`mecanismos_en_su_forma`, `mec_*`, `entrenamiento_repertorio`, `covid_sin_fase_fuerte`,
`mecanismos_regla`, `curvas_de_aprendizaje`) antes de calcular ningún resultado.

Variables:
- Feria, días 0-4;
- noche festiva (7, 24 y 31-dic) y día siguiente (26-dic, 2-4 ene);
- fiesta a ≥ 60 km, más 3 días;
- terremoto: semanas 1 y 2-3, al origen;
- paro de 2021 como marca;
- 5 familias de salud y 6 variables de red, con compuerta;
- transiciones de clima a 7-35 días;
- MinDefensa con 42 días de rezago de publicación.

Los coeficientes los aprende el modelo: las magnitudes medidas no entran como dato.

Brazos:
- **M1:** solo los mecanismos.
- **M2:** M1 más un repertorio en que calma y eventos pesan lo mismo dentro de cada año.
- **M3:** M1 sin la fase fuerte de la COVID.

Regla:
- La de siempre, con 2025 en origen rodante.
- Más la condición de no perder más de 2 puntos de BSS en los días de calma de 2025.
- Desglose obligatorio por tipo de día.
- 2026 se mira una sola vez.

**Por qué M3 y no bajar el peso de la COVID.** Bajar el peso ya se probó (T1) y empeoró los 4 años. Quitar solo
la fase fuerte (170 días, 79 triages/día) no se había probado.

**Hallazgo de método: el árbol del motor no puede ver un episodio raro.** Con `min_child_samples = 30`, ninguna
hoja aísla un tipo con menos de 30 días, y en el entrenamiento de 2025 LightGBM ve 15 días de Feria y 15 noches
festivas. Por eso los episodios raros entran además como desplazamiento lineal, estimado solo con el entrenamiento.
Con datos hasta 2024 salen:
- Feria +10,4 %;
- noche festiva −21,5 %;
- día siguiente +15,3 %.

Los tres tienen el signo de lo medido.

**Otros hallazgos.**
- e2 y e3 usaban MinDefensa al origen, aunque se publica con 2 a 6 semanas de rezago. Fue una fuga de
  disponibilidad, menor porque esos diseños perdieron.
- Con los mecanismos, la calma fuera de la COVID son 272 días (15,6 %), 70 de ellos en 2025.
- La compuerta de cambio brusco quedaba encendida el 77 % de los días. Antes de calcular nada se pasó al p90 por
  componente, y quedó en el 29 %.
- **2025 no puede juzgar los mecanismos raros:** trae 5 días de Feria, 3 noches, 7 días de ola y 0 catástrofes.

**Enmienda del orquestador, antes de calcular** (fila `mecanismos_desglose_multianual`). Además de la regla de
2025, que decide el reemplazo, se hace un desglose descriptivo por mecanismo con la rejilla anual en 2023, 2024 y
2025, juntando los episodios: 3 Ferias, 9 noches y las olas de 2023-2024. Responde si el modelo aprende cada
mecanismo; no decide reemplazos. 2026 queda fuera.

**No se construyó.**
- Fútbol: solo hay 2 partidos; la fuente propuesta es la API de ESPN.
- El paro de transportadores de 2024: solo está la fecha de la alerta.
- Los días antes y después de la Feria: no hay medición.
- El escalón del ingreso de mayo de 2024: mide el destino del paciente, no el conteo.

**Límites que se declaran.** La forma de la Feria, de las noches y el corte de 60 km se midieron con datos que
incluyen 2025; la del terremoto, con 2026.

## 2026-10-06 — Auditoría: casi nada de lo descubierto entró al modelo en la forma en que se descubrió

**Qué planteó el propietario.** El modelo vigente no recoge lo encontrado:
- clima;
- fiestas, Feria y fútbol;
- catástrofes distintas de la COVID;
- epidemias;
- EPS distintas de Nueva EPS.

Además, la COVID pesa demasiado. Y los cuadernos se leen como un chat con IA, no como texto suyo.

**Qué se midió.**
- **Modelo vigente:** C0r usa 28 entradas y **ninguna externa**: calendario, día de la semana, Fourier, nivel,
  memoria y 2 indicadores de COVID. Cg añade 5 familias de salud pública con compuerta y 8 marcas de tipo de día.
- **Peso de la COVID:** 716 días (170 fuertes y 546 parciales) son el **39,3 %** del entrenamiento en el origen
  2024-12-31, el **32,7 %** en el 2025-12-31 y el **29,3 %** en el 2026-09-13. Su volumen medio es de 79 y 144
  triages/día, frente a 198 desde 2022.
  - Matiz medido: bajarle el peso a 0,1 (T1) empeoró los 4 años, de −2 a −6 puntos.
  - Empezar en 2022 (e0) también rindió menos que empezar en 2020 (e1).
  - Sigue sin probarse **quitar solo la fase fuerte** o tratarla como serie aparte.
- **Lo descubierto entró, si entró, como indicador de volumen total y en bloque** (e2 con 49 variables, C1 con
  24). Nunca entró por el subgrupo, la hora o el corte con que se midió. Ejemplos:
  - La **Feria** mueve SOAT +36,9 ± 5,5 % y particulares +61 %, pero el total solo +7,3 ± 8,5 %. Entró como
    `fut_ev_feria` sobre el total.
  - Las **fiestas lejanas (≥ 60 km)**, +1,9 % [+0,5; +3,4]: en e2 los cortes eran 0-50, 51-100 y 101+.
  - La **noche de festivo** (madrugada +31-44 %) no tiene indicador propio en `CAL`.
  - El **terremoto de 2026** (−21,5 % en 2 semanas) quedó en un indicador genérico.
  - Las **otras EPS** (Sura, resto, concentración) solo entraron en C1, que perdió.
  - El **clima por banda de edad** (65+ +4,6 % con lluvia reciente) espera a C2, que no tiene resultado escrito.
  - El **fútbol** no tiene datos: hay 2 partidos del Once Caldas en `eventos_manizales`, y en septiembre se
    dejó fuera por alcance.

**Lectura.** Que e2, e3 y C1 perdieran no prueba que esos factores no actúen. Prueba que meterlos todos sobre el
total, en un solo modelo y con unos 2.400 días, ajusta ruido. Es la misma objeción de «mecanismos antes que
promedios».

**Decisión sobre los cuadernos.** Se escriben en voz impersonal de tesis:
- «se descubrió que», «se investigó que», «a partir de la gráfica anterior se puede interpretar que»;
- sin mencionar al propietario ni a las sesiones;
- sin secciones de pasos siguientes ni jerga de filas;
- los límites del análisis van como límites, no como tareas.

Lo operativo vive aquí y en `HANDOFF.md`.

Estado de los cuadernos:
- Los peores son el 23, el 16, el 03, el 02 y el 08.
- Del 00 al 13 no tienen generador y se corrigen en el `.ipynb`.
- Del 14 al 23 se corrigen en `construir/` y `*_lecturas.json`.

## 2026-10-05 (noche) — La compuerta empata con el protocolo completo: se queda C0r y Cg pasa a hipótesis prospectiva

**Decisión.** Por la regla de `contexto_con_compuerta_confirmacion` se queda C0r. Con origen rodante, Cg (SARIMAX
+ LightGBM con salud pública en compuerta) empata en 2025: criterio 5,1 contra 5,2, acierto −0,35 puntos
[−1,5; +0,7]. En 2026, mirado una sola vez: 15,4 contra 15,9, acierto −1,0 [−2,1; 0,0]. Cg mejora el BSS de pico
en 2025 (3,8 contra 2,9).

**Por qué no se confirma.** La ola de salud pública marcó 35 días en 2023 y 70 en 2024, pero 7 en 2025 y 0 en
2026. La compuerta casi no se encendió en los años de confirmación. **No es una refutación**: esos años no traen el
contexto en que la compuerta actúa.

**Consecuencia.** C0r es el modelo principal de la respuesta semanal. Cg se guarda **en paralelo** como hipótesis
prospectiva, para compararlo cuando haya olas (la temporada de lluvias de octubre-noviembre es la candidata).

## 2026-10-05 (noche) — El propietario corrige: no descartar el contexto; entrenar con fechas escogidas. Resultado: la compuerta

**Lo que dijo el propietario.** Las variables externas ya están medidas y validadas en los cuadernos 17 a 21. Lo
que hay que ajustar es **con qué registros se entrena**: una selección marcada y controlada, no aleatoria, de fechas
importantes y estables, para que el modelo tenga contexto de todo tipo. Preguntó por qué se estaba descartando
tan rápido.

**Reconocimiento.** Tenía razón en una parte:
- su idea de «datos escogidos» se había probado en una sola versión (T3, peso doble a tres tipos de días raros);
- la predicción semanal se había dejado sin contexto.

Medir «el contexto no mejora el total» con todos los días por igual y en el promedio dice más de la forma de
entrenar y evaluar que de las variables.

**Decisión 1: fechas marcadas** (`notebooks/marcas.py`). Salen solo del calendario y de las variables externas,
nunca del triage. Cada tipo marca lo excepcional, entre el 3 y el 15 % de los días. Hallazgo: **casi siempre pasa
algo**. Fuera del COVID, solo el 30 % de los días es estable (525 de 2.455 en total).

**Decisión 2: selección controlada, preregistrada en `entrenamiento_curado`.** Ningún diseño pasa la regla:
- S2, escoger fechas y quitar estables y COVID, empeora todo (de −6 a −11 puntos en los días marcados): pierde
  datos;
- S1, equilibrar los tipos por peso, queda casi neutro.

La pista decisiva: con las 24 variables H, el modelo **empeora en los días estables** (−6,8 puntos), donde el
contexto no debería actuar. Con unos 2.400 días, usa las variables para ajustar ruido.

**Decisión 3: contexto con compuerta, preregistrado en `contexto_con_compuerta`.** Cada capa se enciende solo cuando
su gatillo está activo; en el resto queda como faltante. Es el principio de «cada factor tiene su gatillo».

Resultados con G1 (todos los días con peso 1, más la compuerta):

| | ¿Pasa la regla? | Días marcados | Días estables | BSS de todos los días, 2023-2026 |
|---|---|---|---|---|
| base | — | — | — | −9,3 / +4,1 / +2,4 / +11,4 |
| G1 + salud pública | **sí** (3 de 4 años) | +1,3 de media | −0,8 | −7,7 / +4,1 / +2,7 / +11,4 |
| G1 + todo H | no | 1 de 4 años | −2,0 | −10,4 / +0,9 / +1,6 / +11,9 |
| S0 + todo H, sin compuerta (antes) | — | — | — | −14,1 / −1,2 / +1,3 / +8,5 |

G1 con salud pública **iguala o mejora a la base en los 4 años**. La compuerta repara casi todo el daño de las 24
variables: en 2026 el acierto sube de 61,2 % a 66,5 %. Por tipo de día, el contexto ayuda en olas de salud
pública (+8,3 contra +5,1) y en clima extremo (con S1: +5,7 contra +1,4).

**Por tipo de día, G1 con salud pública iguala o mejora a la base en los 7 tipos.** BSS de sube, base contra G1:

| Tipo de día | Base | G1 con salud pública |
|---|---|---|
| Ola de salud pública | +5,1 | +8,8 |
| El Niño o La Niña fuerte | +5,3 | +9,1 |
| Clima extremo | +1,4 | +6,2 |
| Sismo | +2,4 | +5,2 |
| Red de salud | +7,2 | +7,7 |
| Transición de clima | +6,8 | +6,9 |
| Calendario especial | +14,3 | +14,2 |

Las otras capas (clima, red y regímenes), aun con compuerta, restan en transiciones y en días de calendario. Su
lugar son las bandas de edad.

**Siguiente:** confirmar con origen rodante (fila `contexto_con_compuerta_confirmacion`, experimentos `g_2025` y
`g`). Para la semana del 5 al 11 de octubre se guardan dos predicciones, sin contexto y con contexto, y se
comparan con lo real.

## 2026-10-05 (noche) — El motor se corrige (C0r), C2 tenía un error con los ceros, y nace la respuesta semanal

**Contexto.** El propietario pidió arreglar lo que fallaba y dejar una predicción de la semana del 5 al 11 de
octubre guardada para verificarla después. **Él no tiene permiso para actualizar la base**: lo hace su superior al
final de la semana. Desde ahora no se propone correr `extraccion`; se predice con lo que hay (datos hasta el
2026-09-20) y se verifica cuando lleguen datos nuevos.

**Decisión 1: C0r reemplaza a C0** (fila `motor_objetivo_relativo`, regla del cuaderno 22). `lightgbm_rel` aprende
log(y) − nivel. Se decidió con 2025:

| | Criterio (promedio del BSS de sube, dos varas) | Acierto 28 días | Cobertura del 80 % | MAPE |
|---|---|---|---|---|
| C0 | 4,2 | 59,9 % | 78,0 % | 8,6 % |
| **C0r** | **5,2** | **61,9 %** | **80,5 %** | **8,5 %** |

Mirado una sola vez en 2026, C0r da 15,9 contra 15,2, acierto 69,6 % contra 69,4 %, y la diferencia es un
empate en el remuestreo por bloques: acierto +0,2 [−2,1; +3,1]. **Lectura:** con reentrenamiento semanal la
corrección no sube el acierto, pero quita el riesgo de desplome cuando el nivel sale de lo conocido (cuaderno 23).
Se adopta por la regla, no por 2026. `lightgbm` sigue en el motor para no romper lo ya registrado.

**Decisión 2: C2 tenía un error y se rehace** (fila `reentrenamiento_holistico_enmienda`). Las bandas 0-4 y 5-14
tienen 123 y 53 días en cero, y log(0) dio infinitos en 1.422 y 1.512 de 2.555 filas. La corrección es log(y + 1)
con la opción `desplazar` de `pronostico.py`, aplicada a las cinco bandas. Se rehacen los cinco `hb*_2025`.
Mientras tanto, C0 contra C1 en 2025 da 4,2 contra 1,1: **el contexto H no mejora el total en 2025**, coherente
con el cuaderno 23.

**Decisión 3: la respuesta semanal** (`notebooks/semana.py`, fila `pronostico_semanal`). Responde en el formato que
pidió el propietario:
- media diaria de la semana con rango del 80 % (cópula entre días);
- por día: esperado, rango, P(sube) y P(pico) frente a lo normal;
- reparto de mañana y tarde.

La predicción se guarda **una sola vez** y se versiona: `.gitignore` tiene una excepción para
`salidas/pronostico/semanal/`. Su valor de prueba depende de haberse escrito antes de conocer lo real.

## 2026-10-05 (noche) — Cuaderno 23: la mezcla aleatoria no es legítima; la investigación fija las técnicas, y aparece un error de método

**Pedido del propietario.** Un cuaderno «resumen» con todas las variables que quedan y por qué, que el modelo vea
«datos escogidos y aleatorios» de cada contexto, y validar todo con probabilidades razonables (60-70 %). Al saber
que la mezcla al azar filtra el futuro, pidió hacerlo «de la manera más adecuada posible, a base de
investigaciones».

**Decisión 1: no se mezclan días al azar para medir.** Evidencia bibliográfica: Bergmeir, Hyndman y Koo (2018,
*CSDA* 120:70-83) muestran que el k-fold aleatorio solo es válido si el modelo es autorregresivo puro, su residuo
no tiene memoria y la serie es estable. Aquí no se cumple ninguna: el residuo tiene +0,42 a 1 día, hay COVID,
tendencia y el escalón de Nueva EPS, y el modelo usa variables externas. Cerqueira, Torgo y Mozetič (2020,
*Machine Learning* 109) encuentran que con series no estacionarias solo los métodos que respetan el orden dan
estimaciones fieles. El cuaderno 23 lo demuestra con los datos (sección 3).

**Decisión 2: el equivalente legítimo de «escogidos y aleatorios».** Fila `tecnicas_de_entrenamiento`,
preregistrada:
- «escogidos» = **pesos por contexto** (Sugiyama et al. 2007; Pesaran, Pick y Pranovich 2013): peso 0,1 al
  COVID, decaimiento por recencia y peso doble a los contextos raros;
- «aleatorios» = **remuestreo de bloques de 28 días dentro del entrenamiento** (Bergmeir, Hyndman y Benítez 2016);
- la prueba siempre es hacia adelante: un año a ciegas por año de prueba (2023-2026).

El k-fold por bloques con purga de 7 días y embargo de 35 (López de Prado 2018) queda reservado para afinar
hiperparámetros dentro del entrenamiento, nunca para reportar.

**Decisión 3, una desviación registrada: el objetivo de LightGBM pasa a ser el desvío frente al nivel.** La
primera corrida de `validacion_por_capas_multianual` dio una base con BSS de sube −105 % en 2024, acierto del
42 % y cobertura del 80 % del 33 %. La causa: el árbol aprende log(y) con el nivel como entrada, y un árbol no
predice valores que no vio. El nivel de 2024 (226/día) superó todo el entrenamiento, y en 2026 el peso de
Nueva EPS se hundió bajo su mínimo. Con objetivo log(y) − nivel, la base de 2024 pasa a BSS +4,1 %, acierto
66,3 % y cobertura del 73,3 %. Hewamalage, Ackermann y Bergmeir (2023, *DMKD* 37) describen exactamente este
riesgo. **El cambio es de método, no de variables**, y se reportan las dos versiones.

Consecuencia que sigue viva: el LightGBM del motor (`pronostico.py`) tiene el mismo defecto. Con reentrenamiento
semanal se nota poco, pero existe. Las colas del cuaderno 22, ya preregistradas, siguen como están; la corrección
del motor va como experimento aparte.

**Decisión 4: enmienda antes de calcular.** La marca de «contexto raro» de T3 incluía El Niño y La Niña, que
juntos cubren el 67 % de los días de 2020-2026. Salen de la marca y quedan crisis de la red, ola respiratoria y
racha seca (673 días). Se cambió antes de calcular ningún resultado de técnicas.

**Lo que dice la literatura de urgencias, para leer los resultados.**
- Añadir clima casi nunca mejora el error del total:
  - Wargon et al. 2009, revisión de 9 estudios;
  - Marcilio, Hajat y Gouveia 2013, São Paulo: 10,8 % sin temperatura y 11,5 % con ella;
  - Calegari et al. 2016;
  - Vollmer et al. 2021;
  - Tuominen et al. 2022.
- Lo que ayuda es el **estado del sistema**:
  - avisos prehospitalarios, −6 puntos (Asheim et al. 2019);
  - camas de la red (Tuominen et al. 2022);
  - epidemia de influenza (Murtas et al. 2022).
- La calibración se juzga con BSS y fiabilidad, no con el porcentaje de acierto. Para pocos casos, Platt o beta
  y no la isotónica (Niculescu-Mizil y Caruana 2005; Kull et al. 2017).

**Primer resultado (T0, antes de las técnicas).** Con el método corregido, **ninguna capa aporta en 3 de 4 años**.
Salud pública mejora a la base en 2025 y 2026 (+1,1 puntos cada año); el clima solo en 2025. La capa de red
empeora la probabilidad de pico en 2026 (BSS de pico +7,0 → +1,6). Es coherente con la literatura: en el total, lo
externo aporta poco y de forma inestable.

**Resultado de las técnicas (fila `tecnicas_de_entrenamiento`): no se adopta ninguna; T0 se queda.** BSS de sube
con todo H, frente a T0:

| Técnica | Resultado |
|---|---|
| T1, COVID con peso 0,1 | empeora los 4 años, de −2 a −6 puntos |
| T2, recencia | empeora 3 de 4 años |
| T3, peso doble a contextos raros | mejora 2 de 4 años (2023 +3,7; 2025 +0,5); cobertura 72-78 % |
| T4, remuestreo de bloques | empeora 4 de 4 años |
| T5, todo junto | la peor, de −5 a −14 puntos |

Con esto, el equivalente legítimo de «escogidos y aleatorios» **queda probado y descartado con evidencia**.
Platt con el año anterior baja el Brier en 1 de 4 años con T0: no se adopta.

**La confiabilidad honesta y las probabilidades.** Con la base sola y T0, el acierto en sube/baja fue 57, 66, 60 y
66 % en 2023-2026 (media 62 %), con BSS de −9, +4, +2 y +11. Las probabilidades altas están exageradas (T0 con H,
1.349 días):

| El modelo dice | Acierta de verdad |
|---|---|
| > 80 % (289 días) | 68 % |
| 70-80 % | 62 % |
| 60-70 % | 63 % |
| 50-60 % | 52 % |

Hay que presentarlas comprimidas o en bandas: un «70 % o más» vale lo que un 65 % real.

**Demostración con los datos de que mezclar al azar engaña.**
- Hasta 2025, la mezcla infla el acierto de 57-60 % a 66 %.
- En 2026, con el árbol sobre el desvío del nivel, la mezcla dice que H ayuda: 67,0 % contra 66,0 % de la base.
  Hacia adelante perjudica: 61,2 % contra 66,2 %.
- Con el árbol sobre el conteo en 2026, la mezcla esconde el desplome: dice 63,5 % cuando en realidad es 52 %.

**Lo que no se concluye: «lo externo no sirve».** En las partes, los cuadernos 17-21 midieron efectos de hasta 3
veces el del total. **Siguiente, en orden:**
1. corregir el objetivo del motor (fila nueva);
2. un modelo global por bandas de edad (Montero-Manso y Hyndman 2021);
3. la prueba condicional de Giacomini-White, por régimen;
4. vigilancia tal como estaba publicada en el origen.

Referencias de la investigación, completas, en el cuaderno 23, sección 4.

## 2026-10-05 (noche) — Cuaderno 21: jerárquico por edad; el contexto actúa hasta 3 veces más fuerte en las partes

**Particiones posibles** (fila `jerarquico_tipo`):
- por edad (5 bandas), 100 % desde 2020;
- obstétrico frente al resto (12,5 %), 100 %;
- los diagnósticos cubren el 41 %: son ingresos, y **no sirven como partición**;
- **el cruce edad × obstétrico no existe:** haría falta una extracción del propietario.

**Resultados** (2022-03 a 2024-12; 65 pruebas por parte; BH):
- **Estación:** 0-4 años, 87 puntos de amplitud; 5-14, 64; adultos, 15-20; obstétrico, 7; total, 22.
- **Efecto máximo que sobrevive:** 7,7 % en 0-4, 6,9 % en 5-14, 4,6 % en 65+, contra **2,1 % en el total**.
- **Ruido semanal:** 26 % en 0-4 y 23 % en 5-14, contra 6 % en el total.
- **Pruebas que sobreviven:** 15-44, 12; 45-64, 11; 65+, 7; 0-4 y 5-14, 1 cada una; **sumadas, 32 contra 11 del
  total.**
- **Cada parte tiene su contexto:**
  - **mayores, la lluvia reciente**: +4,6 %, q < 0,001;
  - **adultos, las rachas secas, la diarrea de la ciudad y El Niño**: 2-3,5 %;
  - **niños, el clima de la semana y El Niño.**

**Decisión: el cuaderno 22 usa la partición por bandas de edad** (regla preregistrada).

---

## 2026-10-05 (noche) — Cuaderno 20: regímenes como estados; El Niño es la hipótesis prospectiva

**Qué se hizo** (fila `regimenes`).
- Siete estados diarios, conocidos al predecir, en `notebooks/indices.py`:
  - El Niño y La Niña (ONI de 2 meses antes);
  - COVID fuerte y parcial;
  - paro nacional 2021;
  - sismo fuerte (M ≥ 4,5 a menos de 150 km; catálogo USGS en `calendarios/sismos_usgs.csv`, con
    `calendarios/fenomenos/sismos_usgs.py`);
  - desastre activo;
  - crisis de la red.
- **Episodios 2012-2024:** El Niño 4, La Niña 5, sismos 40, desastres 9, crisis de la red 4. COVID y paro, 1 cada
  uno, así que **entran como marcas, no como predictores.**

**Resultados:**
- **La Niña sube la enfermedad de la ciudad:** violencias +0,35, salud mental +0,31 y varicela +0,38
  desviaciones típicas, por encima de BH.
- **Los sismos no mueven ni a la ciudad ni al hospital.** Con 40 episodios es un negativo con muestra.
- **El Niño → triage +3,6 %** (p < 0,001), **pero es un solo episodio en la ventana del hospital** (2023-24), y
  coincide con el año récord y con la entrada de SURA.
  - **Puede explicar la firma del «día soleado» de 2022-2024**, que desapareció en 2025 (cuadernos 12 y 14).

**Decisión: predicción prospectiva escrita hoy**, en la fila `hipotesis_el_nino_2026` de `variables.csv`.
- **El Niño está en curso y es fuerte** (ONI JAS 2026 = +2,16).
- **Predicción:** del 2026-10-04 al 2026-12-26, el triage real superará a la mediana de la combinación congelada
  (que no usa ENSO) en ≥ +2 % de media.
- **Si no lo hace, se rechaza.**
- Se evalúa al re-extraer el triage.

---

## 2026-10-05 (noche) — Cuaderno 19: seis familias de enfermedad; el clima mueve a las transmisibles, el hospital las ve diluidas

**Qué se hizo** (fila `familias_enfermedad`).
- Seis índices semanales de Manizales en el SIVIGILA:
  - respiratoria;
  - digestiva;
  - violencias y agresiones;
  - salud mental e intoxicaciones;
  - materno-perinatal;
  - inmunoprevenibles.
- Cada índice usa anomalías operativas y se define en `notebooks/indices.py`, el módulo compartido de los
  cuadernos 17-22. Ese módulo trae también los índices de clima y las variables de red.
- **Cinco familias tienen dato de 2026 al predecir** (Power BI). **La digestiva no:** solo hay microdatos, con ~8
  meses de retraso.

**Resultados** (2012-2024):
- **Las familias son casi independientes** semana a semana: ninguna correlación pasa de 0,19.
- **Clima → familia** (índices del cuaderno 17, rezagos de 0 a 6 semanas, BH):
  - **digestiva:** 12 de 63 sobreviven; las semanas largas sin lluvia fuerte la suben **+15,7 %**;
  - **respiratoria:** 4; una racha seca la baja **−9,5 %** a 3 semanas;
  - **varicela:** 5;
  - **violencias:** 1;
  - **salud mental y materno-perinatal:** 0.
- **Familia → hospital** (rezagos de 0 a 4 semanas, BH):
  - **triage total:** 4 de 30 sobreviven, con efectos de 1-3 %;
  - **ingresos respiratorios, infecciosos, digestivos y por trauma:** 0;
  - **ingresos por embarazo y por salud mental:** hay asociaciones que pasan BH, pero sin mecanismo y con
    signos que se alternan. **No se toman como hallazgo.**

**Decisión: arquitectura del modelo para los cuadernos 21-22.**

| Capa | Qué mueve |
|---|---|
| Clima | Las familias transmisibles de la ciudad |
| Familias | Su parte del triage |
| Red | El nivel |
| Calendario | El día a día |

En el total, clima y familias llegan diluidos (1-3 %).

---

## 2026-10-05 (noche) — Cuaderno 18: el panel de todas las EPS; la caída de Nueva EPS es sobre todo de acceso

**Privacidad, corregido antes de subir.**
- Los Excel de medidas de la Supersalud traen nombre, documento, correo y teléfono de los interventores.
- Se guardan en `calendarios/capturas/crudo/` (ignorado). Se versiona solo una tabla limpia: entidad, NIT,
  ciudad, medida, resolución y fechas.
- Los commits locales de esta sesión se rehicieron sin esos Excel. No se había subido nada.

**Resultados** (fila `panel_eps`; descriptivo, no elige modelo):
- **El SES depende de dos aseguradoras**, Nueva EPS y SURA (80-90 % del triage).
  - SURA pasó de 8,6 triages por día (2020) a 69,6 (2024) y 62,0 (2026).
  - **El escalón de abril de 2024 fue de SURA** (+40 por día), no de Nueva EPS (−0,2).
- **Sustitución:** cuando Nueva EPS cae, el resto compensa poco en el SES.
  - **Noviembre de 2025:** compensa el 16 % de −70 por día; el total cae un 28 %.
  - **Julio de 2026:** compensa el 11 %; el total cae un 19 %.
- **Afiliados contra uso** (MinSalud, Manizales, julio de 2025 a agosto de 2026):
  - **Nueva EPS:** −19,5 % de afiliados (de 112.573 a 90.585), **−60 % de triage** y **−50 % de uso por
    afiliado**. La caída es sobre todo **barrera de acceso**, no traslado.
  - **SURA:** +14 % de afiliados, +14 % de triage, uso por afiliado igual.
- **Supersalud:** 7 EPS de la región bajo medida.
  - Sobre Nueva EPS hay 7 resoluciones con fecha. **Las del 14 y el 25 de noviembre de 2025 coinciden con el
    escalón del 15 de noviembre.**
  - Marzo y julio de 2026 no tienen resolución cerca. Probablemente son decisiones de **contratación** SES-EPS,
    que no son públicas: es el pendiente #11.

**Decisión: al modelo entran 6 variables de red:**
- peso de Nueva EPS y de SURA en 28 días;
- cambio de Nueva EPS y del resto en 28 días;
- índice de Herfindahl;
- bandera de resolución de la Supersalud sobre Nueva EPS en los últimos 30 días.

**Lo que queda fuera por ahora:** la afiliación mensual y el uso por afiliado, con solo 14 meses de historia.
Se acumulan con la captura semanal.

**Límite:** las variables internas describen la red pero no la anticipan.

---

## 2026-10-05 (noche) — El propietario aprueba las 6 propuestas; captura automática semanal y clima completo (cuaderno 17)

**Decisión del propietario.** Aprueba las seis propuestas del cuaderno 16 y pide desarrollarlas en cuadernos
separados (17-21) y después repetir el entrenamiento y la predicción (22). También pide automatizar las
capturas de las fuentes que no guardan historia, para no depender de correrlas a mano.

**Captura automática.**
- **Pieza:** `calendarios/capturas.py` con su envoltorio `capturas.cmd`. La tarea de Windows es
  **`triage_capturas_semanales`**: los lunes a las 08:00, y al encender el equipo si estaba apagado.
- **Fuentes:**
  - BDUA de Caldas;
  - Power BI del INS;
  - zips de afiliación de MinSalud (se extrae Caldas);
  - Excel de medidas de la Supersalud;
  - ONI.
- **Guardado:** solo si la huella cambió.
- **Primera corrida:**
  - BDUA, corte del 2026-10-02: 473.394 afiliados en el contributivo y 435.507 en el subsidiado;
  - 9 Excel de medidas;
  - **13 meses de afiliación por EPS × municipio** (julio de 2025 a agosto de 2026);
  - ONI.
- **Sin automatizar todavía:** PQRD (la página no expone descargas) y ADRES.
- Detalle en `calendarios/docs/CAPTURAS.md`.

**Clima completo (cuaderno 17, fila `clima_completo`).**
- **Datos:** `calendarios/clima/clima_completo.py`, desde 2010.
- **Validación:**
  - **la lluvia del ERA5 está rota en Manizales:** ~16.000 mm al año, con correlación −0,02 frente al
    pluviómetro. Se descartó;
  - **la de NASA POWER** da ~2.060 mm al año y correlaciona 0,30 por día, 0,52 por semana y 0,80 por mes.
    Solo se usa en ventanas de 7 días o más;
  - temperatura, humedad y radiación del ERA5 concuerdan (0,5-0,77);
  - horas de sol y nubosidad, de forma moderada (0,54 y −0,43).
- **Barrido** (2010-2024; 266 pruebas por desenlace; mes y año fijos; BH q = 0,10):

  | Desenlace | Sobreviven a BH | Lectura |
  |---|---|---|
  | **IRA de Manizales** (2012-2024) | **53** (el azar daría ~13) | Un **mes** lluvioso, nublado, húmedo y con poco sol trae **+6-7 % de IRA a 1-5 semanas**. Horas de sol (−7 %) y déficit de presión de vapor (−6,7 %), que son variables nuevas, están entre las más fuertes |
  | **Triage total** (2022-2024) | 36, con efectos de **1,5-2,4 %** | Diluido. Pesan una semana muy lluviosa reciente, las rachas secas y el calor del último mes |
  | **Ingresos respiratorios del hospital** (2021-2024) | **0** | Son ingresos (un tercio de lo que llega, ~33 por semana), no triage |

- **Índices:** 4 componentes de estado del clima (86 % de la varianza) y 3 de cambio brusco (81 %), ajustados
  con 2010-2024. El primero, «soleado y seco frente a nublado y húmedo», da −4 % de IRA a 1-3 semanas.
- **Decisión:** al modelo entran índices y dos o tres rachas, no 38 variables. **La vía del clima al hospital
  pasa por la IRA de la ciudad.**

---

## 2026-10-05 (tarde) — El propietario cuestiona el entrenamiento: variables pocas, demasiado específicas y poco escalables

**Lo que plantea el propietario.** Aunque la combinación predice bien 2026, las variables le parecen pocas,
demasiado específicas y poco escalables:
1. **EPS:** se mide solo a Nueva EPS, como si fuera la única. Falta el estado de todas las EPS de Manizales.
2. **Clima:** quiere el contexto completo. No solo temperatura o si llovió, sino humedad, precipitación,
   sol, **cuánto tiempo lleva haciendo sol** y las transiciones.
3. **Salud:** no solo IRA. Al menos las **5 enfermedades más comunes**, cruzadas con tiempo, clima,
   fiestas, vacaciones y horario escolar, para una predicción escalable.
4. **Catástrofes y fenómenos:** solo se marcó la COVID. Faltan El Niño y La Niña, terremotos, epidemias y
   enfermedades de vector.
5. **«Parece que se le dieron las respuestas de 2026».** El periodo es corto y el entrenamiento demasiado
   específico.

Pide:
- un cuaderno nuevo (16) que explique la combinación y por qué es compatible y confiable;
- que recoja estas preocupaciones para explorar un mejor entrenamiento;
- revisar a fondo qué se puede sacar del SIVIGILA y de otras fuentes;
- cómo monitorear las EPS;
- cuánto se le puede inyectar al modelo antes de sobreajustar;
- que se le explique el método de rejilla.

**Lo que se midió para responderle:**
- **Lo que entró al modelo.**
  - E2 tenía 49 externas: 12 de clima (temperatura media, mínima y máxima, amplitud, humedad, lluvia, radiación, viento), 9 de salud (IRA total, 0-4 y 60+, consultas, 5 eventos), 4 sociales, 2 de red, desastre y ENSO, y 20 de eventos y días especiales.
  - E3 dejó 8. **Faltan:** duración de rachas secas o soleadas, días desde la última lluvia, transiciones, horas de sol, nubosidad; EDA en 2026; un panel de todas las EPS.
- **EPS:** `triage_entidad` trae **301 entidades**. **SURA EPS pasó de 8 % del triage (2020) a 36 % (2026)**, mientras Nueva EPS bajó de 61 % a 42 %. Los pacientes se movieron de aseguradora, y el modelo solo veía una. El propietario tiene razón.
- **Enfermedades de Manizales** (SIVIGILA 2022-2025):
  - por volumen dominan la IRA (248.277 consultas) y la EDA (82.679 casos);
  - después vienen agresiones por animales (5.900), violencia de género (5.499), intento de suicidio (2.812), intoxicaciones (2.237), morbilidad materna extrema (1.854), varicela (963) y tuberculosis (881);
  - el dengue no aplica por la altitud.
- **Fenómenos en la ventana 2020-2026:** ~4 episodios ENSO (La Niña 2020-21, La Niña 2021-23, El Niño 2023-24, El Niño en curso) y 17 desastres catalogados (9 deslizamientos, 4 sismos). **Con 4 episodios no se puede aprender el efecto de El Niño.** Es un límite de muestra, no de código.
- **Muestra efectiva:** el residuo diario tiene autocorrelación de 0,35. Los 1.399 días de 2022-2025 equivalen a **~670 días independientes**.
- **Complementariedad SARIMAX-LightGBM:** sus errores correlacionan 0,85, pero el 21 % de los días se equivocan en sentido opuesto. Además, LightGBM falla más tras el escalón de julio (12-13 % frente a 8-11 %).
- **La preocupación de las «respuestas de 2026» tiene fundamento, aunque no por fuga de datos.**
  - El origen rodante garantiza que cada predicción solo usó el pasado.
  - **Pero 2026 se usó para elegir:** se compararon ~20 diseños (E0-E3, J, cópula, LazyPredict, afinados, combinaciones) y se quedó el mejor. Eso convierte a 2026 en un conjunto de validación, no de prueba.
  - **Comprobación:** en 2025, con los modelos de E0 (2022-2024), la combinación **no gana**: 57,6 %, BSS −2,8, frente a SARIMAX con 60,1 % y +2,8. Las probabilidades apenas superan la tasa base.
  - Falta separar si es por los años de entrenamiento o porque 2026 favoreció. Se corre la configuración de E1 sobre 2025 (fila `validacion_2025`, `--exp e1_2025`).

**Resultado de `validacion_2025`** (configuración E1 entrenada desde 2020, evaluada en 2025, 365 orígenes):

| Modelo | Acierta | BSS sube | Cobertura 80 % | MAPE |
|---|---|---|---|---|
| Combinación | **59,9 %** | **+5,9** | 78,0 % | 8,6 % |
| SARIMAX | 58,4 % | +4,0 | 84,1 % | 8,8 % |
| LightGBM | 59,7 % | −2,4 | 67,7 % | 9,3 % |

- La combinación frente a LightGBM: Brier −20,4, IC [−29,8, −10,5], significativo.
- La combinación frente a SARIMAX: empate (Brier −4,7, IC [−12,6, +3,3]).

**Lectura:**
- **El orden se repite en otro año:** la combinación no se eligió por suerte.
- **La magnitud de 2026 (69,4 %; +21,1) es propia de ese año**, por sus escalones de Nueva EPS. **Expectativa
  honesta: ~60 % de acierto y una mejora pequeña de la probabilidad (+4 a +6).**
- **Le da la razón al propietario:** con calendario e historia el modelo sigue lo que ya pasó, pero no
  entiende el porqué.

**Decisión:** el cuaderno 16 recoge el diagnóstico y la propuesta de entrenamiento holístico:
- panel externo de todas las EPS;
- clima con rachas, transiciones y pronóstico;
- 5-6 familias de enfermedades como índices;
- regímenes en lugar de fechas;
- jerárquico por tipo de consulta;
- protocolo: afinar en 2020-2024, elegir con 2025, probar una vez en 2026, y la prueba prospectiva.

Queda pendiente que el propietario decida por dónde empezar.

---

## 2026-10-05 — ¿Sesgo hacia SARIMAX? Se prueba con datos, y el líder pasa a ser la combinación SARIMAX + LightGBM

**La pregunta del propietario.** Preguntó si Claude se había «casado» con SARIMAX, porque ve que los otros
modelos dan muy buenos resultados. Se respondió con pruebas de significancia, que hasta hoy no se habían
hecho entre modelos: remuestreo por bloques de 7 orígenes, 2.000 veces, en 2026 con E1.

**Resultado: SARIMAX contra cada modelo.**
- **Acierta sube/baja:** **ninguna diferencia es significativa.** Están empatados.
  - LightGBM: +0,9 puntos, IC [−6,2, +7,7].
  - Chronos: −1,2.
  - Regresión: −1,8.
- **En abril-junio, LightGBM supera a SARIMAX por +10,2 puntos** (IC [−0,5, +21,0]), casi significativo.
- **Lo que SARIMAX sí gana con significancia** es pequeño:
  - el error del número, por 0,5-1 punto de MAPE, frente a todos;
  - el Brier de «sube», frente a la regresión, Chronos y XGBoost afinado. Frente a LightGBM, el Brier no
    es significativo.

**Corrección de Claude.** Llamar a SARIMAX «el mejor» exageró un **empate en la dirección**.
- Su ventaja venía de la jerarquía de criterios que Claude propuso: probabilidad y calibración primero.
  Eso favorece a los modelos con rangos honestos.
- Esa jerarquía tiene sentido para el objetivo, pero no justifica el tono de «ganador claro».
- El propietario tenía razón en dudar.

**La combinación** (fila `combinacion_modelos`, fijada antes de calcularla): promedio de cuantiles, con pesos
iguales, de SARIMAX y LightGBM E1.

| | Acierta | BSS sube | BSS pico | R² del desvío | Cobertura 80 % | MAPE | Abril-junio |
|---|---|---|---|---|---|---|---|
| **Vara de 28 días** | **69,4 %** | **+21,1** | **+16,5** | 27,2 % | **80,3 %** | 8,9 % | 58,6 %; +5,9 |
| **Vara rápida** | 64,1 % | +9,3 | — | — | — | — | — |

Con los cuatro modelos promediados: 68,9 %; +19,3; cobertura del 82,4 %.

**Significancia de la combinación:**
- **frente a SARIMAX:** mejor en todo y **significativa en abril-junio** (+7,8 puntos de acierto, IC
  [+2,5, +13,6]; Brier −13,5, IC [−27,2, −0,5]);
- **frente a LightGBM:** Brier significativamente mejor (−13,0, IC [−26,4, −1,1]) y acierto empatado.

**Lectura.** Los dos modelos se equivocan en días distintos:
- SARIMAX sigue el nivel y da rangos honestos;
- LightGBM capta combinaciones de factores en los meses estables.

Promediar sus distribuciones se queda con lo mejor de ambos. Es el resultado clásico de combinar
pronósticos.

**Decisión: el modelo líder pasa a ser la combinación SARIMAX + LightGBM (E1).**

**Árboles afinados, terminados el 05-10** (acierta; BSS sube; abril-junio; cobertura del 80 %):

| Árbol | Configuración elegida en 2024 | Acierta | BSS sube | Abril-junio | Cobertura 80 % |
|---|---|---|---|---|---|
| LightGBM | 15 hojas, 20 por hoja, 600 árboles | 66,7 % | +13,1 | 61,1 % | 76,7 % |
| XGBoost | profundidad 2, 500 árboles, tasa 0,1 | 65,0 % | +11,6 | 56,8 % | 77,4 % |
| GradientBoosting | profundidad 3, 500 árboles, tasa 0,1 | 64,5 % | +10,3 | 56,7 % | 76,5 % |
| **LightGBM original, sin afinar** | parámetros por defecto | **67,8 %** | **+15,9** | 63,3 % | 71,2 % |

- **Afinar con 2024 no mejoró a ningún árbol en 2026.** Lo que mejor rindió en 2024 no fue lo mejor en 2026,
  que es otro régimen (Nueva EPS).
- **La calibración con los errores de 2025 mejoró la cobertura** (de 71 % a ~77 %), pero se queda corta:
  2026 trajo choques más fuertes que 2025.
- Se conserva LightGBM sin afinar dentro de la combinación.

---

## 2026-10-02 (noche) — El propietario aprueba: vara justa (control rápido) y árboles afinados

**Qué se decidió.** El propietario aprobó las dos propuestas. Quedan preregistradas antes de correr nada
(filas `control_rapido` y `arboles_afinados` de `variables.csv`):
1. **Control rápido**, como segunda vara.
   - Qué es: calendario + nivel de 28 días + desvío de la última semana.
   - **Por qué:** el control de 28 días regala acierto tras cada escalón de Nueva EPS.
   - Cómo se reporta: por separado, «seguir el nivel» y «anticipar el día».
2. **Árboles afinados** (XGBoost, GradientBoosting, LightGBM), en tres etapas que no se mezclan:
   - afinar con 2024;
   - calibrar los rangos con los errores fuera de muestra de 2025;
   - probar en 2026.
   - **Por qué:** LazyPredict mostró que los ensambles de árboles son la única familia con 58-60 % de
     acierto en los meses estables; con parámetros de fábrica se sobreajustan (XGBoost, 62,6 %), y LightGBM
     con cuantiles se sobreconfía (cobertura del 80 % de 71 %).
   - **Calibración:** se toman los cuantiles de errores reales fuera de muestra de 2025, en lugar de
     cuantiles aprendidos por el árbol. Así el rango queda honesto por construcción.

**Resultado de la vara justa** (control rápido; `_umbrales_rapido.parquet`; 2026):
- **El sesgo tras los escalones se reduce a la mitad:**
  - marzo, de +10,9 % a +6,0 %;
  - julio, de −7,8 % a −3,7 %;
  - septiembre, de +11,7 % a +4,5 %.

  No desaparece: el salto de Nueva EPS es de un día para otro.
- **Acierto real en «anticipar el día»** (acierta sube/baja; BSS sube):

  | Modelo | Todo 2026 | Abril-junio |
  |---|---|---|
  | SARIMAX E1 | **60,5 %; +8,1** (R² del desvío 12,7 %) | 54,2 %; +2,2 |
  | SARIMAX E3 | 59,5 %; +5,9 | — |
  | Chronos E1 | 59,3 %; +1,2 | — |
  | Regresión E1 | 58,1 %; +3,2 | — |
  | **LightGBM E1** | 61,1 %; +1,1 | **67,2 %; +11,9** |
  | LightGBM E0 | — | 64,5 %; +11,2 |

- **La cifra honesta que se reporta es ~60 %**, no 65-70 %. LightGBM tiene la señal más clara en los
  meses estables, pero la pierde por mala calibración en el resto del año. Eso justifica afinarlo y
  calibrarlo.

---

## 2026-10-02 (tarde) — LazyPredict: barrido de ~40 regresores, pedido por el propietario

**Qué es.** LazyPredict ajusta de una vez los regresores de scikit-learn, más XGBoost y LightGBM, con sus
parámetros por defecto. Sirve para **explorar qué técnicas merecen afinarse**, no para elegir el modelo
final: sin afinar, da solo un pronóstico puntual y no tiene origen rodante.

**Diseño, fijado antes de correrlo:**
- **Partición temporal, nunca aleatoria:** entrena hasta el 2025-12-31 (desde 2020, con la COVID marcada)
  y prueba en 2026.
- **El modelo queda congelado el 31-12** y no se reentrena. Eso lo pone en desventaja frente a
  SARIMAX y los demás, que se reentrenan cada 7 días, y se declara así.
- **Entradas:**
  - las de E1: calendario, estación, nivel y memoria, a 1 día;
  - las de E3: E1 más las 8 externas.
- **Objetivo:** log del triage.
- **Métricas:**
  - las de LazyPredict (R², RMSE);
  - las del cuaderno 15: MAPE y acierto en si sube o baja frente al control de E0;
  - todas en 2026 completo **y en abril-junio** (meses sin escalones de Nueva EPS).

Instalados `lazypredict 0.3.0` (sin tocar las demás librerías) y `xgboost 3.2.0`.

**Resultado** (42 modelos por juego de entradas, 263 días de 2026; `salidas/pronostico/lazypredict_e1|e3.csv`):

| | Acierta sube/baja | Acierta abril-junio | MAPE |
|---|---|---|---|
| **E1, mejor: GradientBoosting** | **67,3 %** | **60,4 %** | 9,3 % |
| E1, LightGBM | 66,9 % | 58,2 % | 9,2 % |
| E1, familia lineal (Ridge, Lasso, ElasticNet…) | 66,2 % | 53,9 % | 8,7 % |
| E1, RandomForest | 63,8 % | 60,4 % | — |
| E1, XGBoost (parámetros por defecto, se sobreajusta) | 62,6 % | 50,5 % | 9,8 % |
| E3 (+8 externas), mejor: ElasticNetCV | 63,0 % | 55,0 % | — |
| E3, boosting | 57-60 % | — | — |
| Últimos (GaussianProcess, KernelRidge, KNN, MLP) | ≈ 50 % | — | 15-99 % |

Lo que se lee:
- **Congelados el 31-12, los mejores empatan con SARIMAX reentrenado** (65,8 %, 52,7 % en abril-junio a 1
  día, con la misma vara).
- **En E3 todos empeoran:** el contexto externo vuelve a restar.
- **Señal que se repite:** en los meses estables, los **ensambles de árboles** (GradientBoosting,
  LightGBM, RandomForest, HistGradientBoosting) dan **58-60 %**, contra 53-54 % de los lineales y de
  SARIMAX. Son implementaciones distintas que coinciden, así que es candidata a señal real: interacciones
  que lo lineal no ve.
- **Límite:** con 91 días en abril-junio, la incertidumbre del acierto es de ±5 puntos. Es una pista,
  no una prueba.
- **Referencia, misma vara a 1 día:** SARIMAX E3, reentrenado, da 60,4 % en abril-junio, contra 52,7 % de
  SARIMAX E1. También una pista, con la misma reserva.

---

## 2026-10-02 (tarde) — El 65-70 % de acierto es casi todo seguir el nivel de Nueva EPS; en meses estables, nadie le gana al calendario

**SARIMAX E3 (8 externas) terminó:** 65,0 %; BSS +16,3; R² del desvío 25,3 %. Frente a SARIMAX E1 (66,8 %;
+18,8) es **peor**, y la diferencia en la probabilidad es significativa:
- Brier de «sube», E3 − E1 = +0,0063, Diebold-Mariano con HAC, p = 0,002;
- en la pérdida de cuantiles, p = 0,19.

**Ninguna familia mejora con contexto externo sobre el total.** Ni con 8 variables ni con 49.

**El hallazgo de método, medido al revisar el acierto por mes** (SARIMAX E1, 2026):

| | ene | feb | mar | abr | may | jun | jul | ago | sep |
|---|---|---|---|---|---|---|---|---|---|
| % de días que «suben» | 24 | 40 | **90** | 40 | 59 | 47 | **16** | 37 | **91** |
| Sesgo del control (real / anunciado − 1) | −6,7 | −3,6 | **+12,6** | −2,0 | +2,3 | −1,4 | **−10,5** | −7,1 | **+12,0** |
| Acierto de SARIMAX | 67 | 62 | 83 | 57 | 47 | 47 | 79 | 78 | 91 |
| Acierto de «decir siempre lo más frecuente» | 76 | 60 | 90 | 60 | 59 | 53 | 84 | 63 | 91 |

- **Por qué pasa:** el control de calendario usa el nivel de los últimos 28 días. Cuando Nueva EPS salta
  (marzo, julio, septiembre), el control queda corrido un 10-13 % durante semanas. Casi todos los días
  «suben» o «bajan», y cualquier modelo que se adapte más rápido «acierta».
- **El acierto global de 65-70 % mide sobre todo eso:** seguir el nivel de la red más rápido que el
  control. No mide anticipar el día.
- **En los meses estables (abril-junio, 637 predicciones), nadie le gana al calendario:**
  - SARIMAX E1, 50,2 % de acierto y BSS +0,1;
  - regresión, 50 %;
  - Chronos, 52-56 % con BSS negativo;
  - **solo LightGBM** (E0/E1) da 63-64 % y BSS +7,4 a +7,7, aunque su R² del desvío y su BSS de pico son
    negativos. Es una señal débil, a confirmar.

**Qué cambia:**
1. **Hay que separar dos habilidades al reportar.**
   - **(a) Seguir el nivel:** la red de salud y los escalones. Ahí SARIMAX es claramente mejor que el
     control.
   - **(b) Anticipar el día dentro de un nivel estable:** los picos. Ahí hoy nadie lo logra.

   El propietario pidió revisar que el criterio de medición fuera el correcto. Este es el defecto que
   tenía.
2. **El control de referencia debe seguir el nivel tan rápido como sea legítimo,** por ejemplo con 7
   días. Si no, el contexto y los modelos se llevan el crédito de los escalones. Propuesta pendiente de
   preregistrar.
3. **Coincide con el cuaderno 14:** a nivel día, ninguna fuente externa anticipa los estados en periodos
   estables. Coincide también con la literatura: efectos de 2-10 %, dentro de un ruido del 10 %.

---

## 2026-10-02 — Depuración del contexto (E3) y modelo jerárquico (J): reglas, selección y arranque

**Qué se decidió.** Hay dos experimentos más, con la regla escrita en `variables.csv` (filas
`contexto_depurado` y `jerarquico`) antes de aplicarla:
- **E3, contexto depurado.**
  - **Por qué:** en E2, las 49 variables externas sobreajustaban a la regresión (de +14,5 a +6,3).
  - **Cómo se eligen:** con un LightGBM entrenado **solo hasta el 2025-12-31**. El ranking de ayer
    venía de un modelo entrenado hasta septiembre de 2026, y elegir con él para evaluar 2026 habría
    sido una fuga de información.
  - **Qué sale:** 8 variables.

    | Familia | Variables |
    |---|---|
    | Salud | IRA total, consultas por toda causa |
    | Clima | cambio de la radiación, temperatura de 28 días |
    | Social | lesiones personales, violencia intrafamiliar |
    | Red | peso y cambio de Nueva EPS |

  - **Qué queda fuera:** catástrofes (0 % de la ganancia), ENSO (1,4 %) y eventos (0,5 %).
  - **Coincide con lo explorado antes** (cuadernos 07, 11, 12 y 13), sin haberlo forzado.
- **J, jerárquico.**
  - Nueva EPS y el resto se predicen por separado, con las entradas de E1, y se suman los cuantiles.
  - **Dato que lo motiva**, medido hoy: entre 2025 y 2026 Nueva EPS baja de 115,8 a 72,2 triages al
    día y **el resto sube de 83,8 a 100,4**. Parte de los pacientes se movió de aseguradora. Un
    modelo del total solo ve la suma.

**Resultados parciales del 02-10, en 2026 con 257 orígenes** (acierta sube/baja; BSS sube):

| Modelo | E0 | E1 | E3 |
|---|---|---|---|
| SARIMAX | 65,7 %; +17,2 | **66,8 %; +18,8** (R² del desvío 27,1 %, cobertura del 80 %: 85,4 %) | corriendo |
| Chronos-2 + calendario | 62,6 %; +9,6 | 65,6 %; +12,1 | 65,4 %; +13,3 |
| Regresión | 64,3 %; +9,1 | 65,0 %; +14,5 | 62,5 %; +11,0 |

**Corrección de Claude, el mismo día.** Le había dicho al propietario que las variables externas mejoraban
a Chronos un 40 % (de +9,6 a +13,3). Con E1 a la vista, **casi todo es por tener más años** (+2,5). Las 8
externas suman +1,2, que no se distingue del ruido. El patrón vale para todos los modelos medidos hasta
hoy:
- **la historia larga (2020-2025) es lo que más mejora;**
- **el contexto externo aporta poco al total, o estorba si entra completo.**

Falta ver SARIMAX y LightGBM con contexto, y el jerárquico.

**Más resultados del 02-10 (2026, 257 orígenes):**
- **LightGBM:** E1 67,8 %; +15,9. **E3 (8 externas): 64,9 %; +8,5.** El contexto lo empeora, como a la
  regresión: sobreajuste.
- **Jerárquico** (Nueva EPS + resto, entradas de E1):

  | Modelo | Combinación | Acierta | BSS sube | R² desvío | Cobertura 80 % | MAPE | Frente al total |
  |---|---|---|---|---|---|---|---|
  | SARIMAX | suma de cuantiles | 67,9 % | +17,1 | 27,3 % | 92,9 % | 8,9 % | 66,8 %; +18,8 |
  | SARIMAX | cópula | 67,6 % | +18,1 | 27,9 % | 88,8 % | 8,9 % | 66,8 %; +18,8 |
  | Regresión | cópula | 66,6 % | +14,0 | — | — | — | 65,0 %; +14,5 |

  - La cópula usa ρ = 0,33-0,35, medido en enero de 2026 (fila `jerarquico_correlado`).
  - **Lectura:** separar las aseguradoras mejora la dirección y el número en menos de 1 punto, y ensancha
    el rango. **SARIMAX jerárquico y SARIMAX sobre el total quedan empatados**, porque la incertidumbre de
    un acierto con 257 días es de ±3 puntos.
  - El valor del jerárquico es **explicativo**: separa cuánto de la predicción es Nueva EPS.
- **Nueva EPS en 2026 salta a escalones:**
  - ~55 por día en enero y febrero;
  - **~92 de marzo a junio**;
  - ~52 en julio y agosto;
  - 68 en septiembre.

  SARIMAX los sigue en pocos días, pero no los anticipa. Es la variable institucional que falta
  (pendiente #11).

- **LightGBM E2 (49 externas): 62,6 %; +6,4**, peor que E3 (+8,5) y que E1 (+15,9). En LightGBM, cuantas más
  externas, peor.
- **Decisión: SARIMAX E2 queda fuera de esta ronda.**
  - **Coste:** su primer reentrenamiento con 61 exógenas tardó 35 min. Con 37 reentrenamientos serían
    ~21 h.
  - **Evidencia:** las tres familias que ya probaron las 49 variables (regresión, LightGBM, Prophet)
    empeoran o no mejoran con ellas.
  - **Sustituto:** la prueba justa del contexto en SARIMAX es E3.
  - Se puede correr de noche o en el equipo de casa con `--exp e2 --modelos sarimax` si hace falta.

**Trampa operativa:** con cuatro colas, Chronos (PyTorch) y SARIMAX (álgebra lineal) acaparan los
núcleos, y LightGBM queda con 0,1-0,2 núcleos. Al primer reentrenamiento le tomó 49 min. Las corridas
nuevas deben limitar los hilos: `OMP_NUM_THREADS`, `MKL_NUM_THREADS` y `torch.set_num_threads`.

**Estado.** Corren cuatro colas independientes:
- **E2:** LightGBM y SARIMAX;
- **E1:** SARIMAX y Chronos;
- **E3:** regresión, Chronos, LightGBM y SARIMAX;
- **J:** regresión y SARIMAX, en Nueva EPS y en el resto.

---

## 2026-10-01 (noche) — Cuaderno 15, predicciones tempranas: resultados preliminares y corte de la sesión

`notebooks/15_predicciones_tempranas.ipynb`, 38 celdas, 0 errores. Se generó con
`notebooks/construir/15_predicciones_tempranas.py` y las lecturas de `15_lecturas.json`. **Es
preliminar:** el propietario cortó la sesión con 4 corridas sin terminar, que se detuvieron sin
pérdida. Cada modelo escribe su archivo al terminar.

**Resultados en 2026, a 1-7 días** (acierto en si sube o baja / mejora de la probabilidad / cobertura
del 80 %):

| Modelo | E0 (2022-24) | E1 (2020-25) | E2 (E1 + contexto) |
|---|---|---|---|
| SARIMAX | **65,7 % / +17,2 % / 80 %** | sin terminar | sin terminar |
| LightGBM | 60 % / +1,6 % / 71 % | **68 % / +15,9 % / 71 %** | sin terminar |
| Regresión binomial negativa | 64 % / +9,1 % / 79 % | 65 % / +14,5 % / 84 % | 60 % / +6,3 % / 78 % |
| Chronos-2 + calendario | 63 % / +9,6 % / 82 % | sin terminar | 70 % / +15,9 % / 79 % (37 orígenes) |
| Prophet | 41 % / −38,7 % | 43 % / −35,1 % | 57 % / −17,1 % |

**Lo que se concluye por ahora:**
1. **Más años ayudan** a los modelos que aprenden de ejemplos: LightGBM de +1,6 a +15,9; la regresión
   de +9,1 a +14,5.
2. **Todo el contexto de golpe sobreajusta a la regresión** (de +14,5 a +6,3). Chronos-2 lo aprovecha
   sin daño. Con LightGBM, el contexto pesa un 26 % de la ganancia. Las externas que más usa:
   - peso y cambio de Nueva EPS;
   - lesiones personales;
   - IRA de Manizales;
   - intento de suicidio.
3. **Los buenos quedan en 60-70 % de acierto**, lo que esperaba el propietario.
4. **Año a ciegas** (predicho el 31-12-2025): error medio del mes del 8,9 % para Chronos-2 (E1) y del
   9,8 % para SARIMAX (E1).
   - Los errores siguen los escalones de Nueva EPS (marzo y julio).
   - Ahí el contexto no ayuda: SARIMAX E2, 14,0 %.
5. **Hora:** hora pico con ±1 hora en el 62 % de los días; error por hora del 35 %, casi todo ruido de
   conteos pequeños.
6. **MedGemma** (servidor, `medgemma:latest`, 19 consultas): error del 19,7 %, el peor de todos.
   Responde con escaleras y números consecutivos: **rellena números, no pronostica**. Se descarta para
   esto.

**Errores de método encontrados y corregidos en la sesión:**
- **Año a ciegas:** se puso en cero todo el contexto pasado como «año típico». Eso incluía variables de
  nivel (peso de Nueva EPS, ENSO), y equivalía a decir «Nueva EPS desaparece». Ahora esas se congelan
  en el valor del origen (`NIVELES` en `pronostico.py`). SARIMAX E2 pasó de 25 % a 17 % de error
  diario.
- **Empalme del SIVIGILA:** el tablero de Power BI trae una SE53 parcial en años de 52 semanas. Se suma
  a la SE1 siguiente.
- **Chronos-2 con 61 covariables** en CPU tarda horas por origen diario. Se corrió con un origen cada 7
  días, y todos los modelos se comparan en esos mismos orígenes.
- **No se corrió MedGemma local:** la del servidor responde la pregunta, y en CPU habría frenado las
  colas.

**Depuración provisional:**
- **Se quedan:** SARIMAX y Chronos-2 + contexto (candidatos principales); la regresión (complemento,
  con pocas variables); LightGBM (a prueba, hay que calibrarlo).
- **Salen:** Prophet (a corto plazo), Chronos-2 sin calendario y MedGemma.

---

## 2026-10-01 — Cuaderno 00, versión 2: en primera persona y con una prueba por etapa

**Lo que pidió el propietario.** Los textos de la versión 1 sonaban a IA y estaban en tercera
persona. Tiene que leerse **como si lo hubiera escrito él**. Y cada una de las 4 etapas tiene que
mostrar **una prueba concreta**, desglosada de forma sencilla.

**Estructura de la versión 2** (`notebooks/00_la_trayectoria.ipynb`, 0 errores; generador en el
scratchpad, `c00/hacer_nb.py`):
- **Línea de tiempo** de las 4 etapas.
- **Etapa 1.** Tabla de los calendarios manuales iniciales:
  - vigilancia a mano, 321 filas, y el **67 %** de las ventanas con las mismas fechas cada año;
  - eventos, 99 filas; desastres, 17.
  - Gráfica de barras semanal, «los lunes llega más gente»: **lo único que se podía decir**.
- **Etapa 2.**
  - Tabla de ejemplos de frases difíciles y de alucinaciones.
  - Figura de calidad del texto y tabla de intentos.
  - El mapa viejo del agrupamiento (`clustering/salidas/mapa.png`, 15-sep, `bge-m3`), con una
    gráfica de barras: los temas 2 y 10 agrupaban **textos largos** (mediana de 28 y 25 palabras,
    contra 4 a 9 en los demás). Agrupaban por longitud, no por motivo.
  - Validación a ciegas: **2 de 16** notas difíciles bien, **5 de 40** estropeadas.
- **Etapa 3.** Tabla de fuentes y tres hipótesis (abajo).
- **Etapa 4.** Tabla de los 8 modelos con la técnica en lenguaje sencillo, una gráfica pequeña por
  modelo con las predicciones a 1 día de junio a septiembre de 2026, tabla de métricas y barras.

**Privacidad: los ejemplos de notas no salen de pacientes.** Regla 1 de `CLAUDE.md`: `HCTMOTCON`
nunca se imprime en crudo. Las frases vienen de:
- `NLP/tests/test_fidelidad.py`: frases escritas a mano con la forma de las notas reales. Una,
  «ME INDICAN CONSULTAR POR URGENCIAS», está marcada ahí como caso real del banco. Es una frase de
  trámite, sin identidad.
- Frases ya documentadas en este archivo y en `NLP/docs/`: «no me baja el azúcar», «oídos tapados»,
  «entumida» → «entubada».

**Hipótesis que se mantienen para la exposición, con sus cifras:**
1. **Feria → SOAT en el SES.** Los 5 primeros días: **+36,9 % ± 5,5**, contra +12,5 % ± 8,5 en otros
   52 regresos de vacaciones. Cada una de las 5 Ferias (2020, 2023, 2024, 2025, 2026) queda entre
   **+27 % y +45 %**, más o menos. Mismo método que el cuaderno 07.
   - **Se quitó el panel de la ciudad (Policía).** Su promedio de Feria, +62,7 % ± 50,8, lo arrastra
     **solo 2020** (+163 %). Los demás años parecen un regreso normal.
   - Por eso **no está probado** que «llegan aquí porque son tantos». Haría falta el dato de
     remisiones del CRUE.
2. **IRA 0-4 de Manizales (SIVIGILA 995) contra triage 0-4 del SES**, semanal, 2020-2025, 312 semanas:
   **r = 0,70** en conteos y **0,81** con cada año contra su propia media. La ciudad va a la par o un
   poco adelante (r 0,69 a una semana de adelanto, 0,70 a cero).
3. **Nueva EPS.** Las mismas cifras de la entrada de abajo.

**Hipótesis que se dejó fuera de la exposición, y por qué.**
- Una prueba sencilla de «semana más fría de lo normal → más niños en el SES» **no mostró efecto**:
  anomalía de temperatura contra la misma semana del año, residuo contra año × mes, rezagos de 0 a
  4 semanas, terciles. Diferencias entre **−3 % y +2 %**, sin patrón.
- Clima → IRA de la ciudad, con agrupación simple, tampoco dio un efecto monótono limpio.
- El cuaderno 11 encontró **+8 a +10 %** con una regresión. O sea, **el efecto depende del método**.
- No se graficó para no mostrar una prueba débil. **Es un matiz medido, no la conclusión de que el
  clima no importa.** El propietario no comparte ese tipo de conclusión (ver la entrada de abajo).

**Corrección de la lectura de una métrica.** «Acierta si sube o baja» se compara contra el **55 %**,
no contra el 50 %:
- solo el **45 %** de los días sube por encima del calendario, así que decir siempre «no sube» ya
  acierta el 55 %;
- el control de calendario saca **54,8 %**;
- SARIMAX saca **62,4 %**: **7 puntos** por encima de la regla trivial, sin datos externos.

La entrada de abajo dice «dentro del 60-70 %» sin esta base. Sigue siendo cierto, pero **siempre se
dice junto a la referencia del 55 %**.

---

## 2026-10-01 — La trayectoria contada por el propietario, y el cuaderno 00

**Por qué esta entrada.** El propietario presenta avances el 2026-10-02. Al proponerle un guion,
Claude contó el recorrido de una forma que no es la suya. Él corrigió la lectura, y esta es **su
versión**, que manda sobre cualquier resumen anterior:

1. **Etapa 1, registros y calendario básico.** Con el conteo y los festivos no había forma de
   comprobar ninguna hipótesis: por ejemplo, que una temporada de frío trae problemas respiratorios
   que llegan al triage. Tampoco había un conocimiento real de qué casos llegan más.
2. **Etapa 2, el motivo de triage.** Por eso se buscó el motivo. Al desarrollarlo se vio que el
   texto es **demasiado natural, inexacto o irrelevante**, que gran parte de la base es así, y que ni
   las reglas ni los modelos pudieron interpretarlo, por esa misma razón. Hablado con los datos y con
   el superior: **aunque se lograra limpiarlo, seguirían siendo datos poco confiables**, y las
   predicciones se harían sobre invenciones o inexactitudes. **Por eso nunca se predijo con el
   motivo**: la conclusión salió de los resultados de la limpieza, no de un pronóstico fallido.
3. **Etapa 3, el contexto externo** (SIVIGILA, calendario de Colombia, epidemias y enfermedades a lo
   largo de la historia, el perfil y la identidad del hospital). Con eso aparecen los patrones, y las
   hipótesis **coinciden con los datos**: aumentos de triage o de enfermedad con clima, fiestas y
   demás.
4. **Etapa 4, la predicción.** Hoy se usa **un solo dato** a propósito, porque lo que se está
   decidiendo es **cómo predecir**: qué técnicas y qué modelos son los más adecuados. Las demás
   variables entran después. Aun así, ya se ven tendencias de qué técnica sirve.

**Desacuerdo registrado.** El propietario **no comparte** la conclusión de los cuadernos 12, 13 y 14
(«nada externo anticipa el total de forma estable»). Ya lo había dicho en otra sesión: le parece mal
medida, con situaciones demasiado específicas que no determinan nada, cuando hay que tomar el
panorama completo. Pidió corregirlos, y **no se corrigieron**. Siguen pendientes.

**Qué se hizo: `notebooks/00_la_trayectoria.ipynb`**, la puerta de entrada del proyecto, con esta
historia y sus pruebas (27 celdas, 10 figuras, 0 errores). Generador en el scratchpad de la sesión
(`c00/hacer_nb.py`); si se pierde, se edita el `.ipynb`. Cifras que se midieron aquí y no estaban
escritas:
- **Calidad del texto**, sobre las 95.424 notas sin identidad y sin imprimir ninguna:
  - mediana de **5 palabras** por nota; el 25,9 % tiene 3 o menos, y el 57,0 % tiene 6 o menos;
  - el 87,9 % está toda en mayúsculas;
  - el **40,2 %** trae al menos una sigla, errata o coloquialismo de los diccionarios de
    `NLP/recursos/`. Es un piso, porque los diccionarios son incompletos.
- **Cobertura:** 94.952 de 433.258 triages hasta el 2026-09-20 (21,9 %) tienen texto.
- **Por asegurador** (triages por día de 2024, 2025 y 2026):
  - Nueva EPS: 125,6 → 115,8 → 72,2;
  - el resto: 101,3 → 83,8 → 100,4.
  - **Matiz a «la caída del volumen es de Nueva EPS»:** vale para 2025-2026. **El pico de 2024 y su
    bajada a 2025 son del resto de aseguradores**, y su causa no se conoce.
- **Estacionalidad por edad, 2021-2025** (mes más alto / mes más bajo − 1): 0-4 años **+122 %**,
  5-14 años +66 %, 15 años y más +15 %. El método es distinto del 72,5 % de antes (amplitud
  estacional), así que no se comparan.
- **Fase A, recalculada desde los archivos:** coincide con la entrada de abajo. Dato nuevo:
  **SARIMAX acierta si el día sube o baja frente al calendario el 62,4 % de las veces** (control
  54,8 %), dentro del 60-70 % que el propietario fijó como confiabilidad creíble.

---

## 2026-10-01 — Contexto completo, todos los años y prueba sobre 2026: decisiones del propietario

**Lo que dijo el propietario.** Los resultados de la fase A le parecen razonables, pero predecir solo
con la serie del triage es proyección con un modelo. Pide:
1. **Meter todo el contexto** que se exploró y tiene historia: salud (SIVIGILA), clima, social
   (seguridad), eventos, catástrofes, EPS, temporadas.
2. **Ampliar el entrenamiento a todos los años con registro**, para que el modelo vea situaciones de
   todo tipo: COVID, EPS, catástrofes.
3. **Enfrentarlo contra 2026**, que es lo reciente y controlado.
4. **Seguir con todos los modelos y técnicas.** Con las variables nuevas el ganador puede cambiar.
   Depurar e ir contando qué técnica y qué modelo dan resultados más correctos.
5. Juntar esto con su visión anterior:
   - la prueba del **año a ciegas** («en julio habrá X triages al día»);
   - la **hora de saturación**;
   - la confiabilidad esperada de **60-70 %**. Más que eso le haría desconfiar de sobreajuste.
6. **Cuaderno 15 = predicciones tempranas.** Lo que salga, bueno o malo, para saber qué falta.
7. **Curiosidad:** probar `medgemma:latest` del servidor de su superior (`NLP/modelo.py`), sin
   cargarlo mucho.

**Qué cambia frente a lo decidido antes.** La fase B preregistrada (5 variables, por parsimonia, 30-09)
**queda sustituida** por decisión del propietario: entran todas las familias. Para que «más
variables» no se convierta en sobreajuste:
- se mide por separado **qué aporta tener más años** y **qué aporta el contexto**;
- la cobertura de los intervalos queda como alarma de exceso de confianza.

**Diseño:**
- **E0:** fase A recortada a los orígenes de 2026. Entrena desde 2022-03, sin externas.
- **E1:** entrena desde 2020-01, con la COVID como variable (fuerte: 2020-03-15 a 2020-08-31; parcial:
  hasta 2022-02-28), sin externas.
- **E2:** E1 más todo el contexto externo (fila `contexto_completo` de `variables.csv`).
- **Prueba 1, corto plazo:** origen rodante del 2025-12-31 al 2026-09-13, de 1 a 7 días. 257
  orígenes.
- **Prueba 2, año a ciegas:** desde el 2025-12-31 se predice todo 2026 hasta el 20-09. Solo con lo
  que se conoce por adelantado (calendario, eventos programados, estación). El clima y el SIVIGILA
  futuros no se conocen y van como «año típico».
- **Prueba 3, la hora:** la predicción del día × el perfil horario por día de la semana del último
  año.
- **Fuentes de 2026:** SIVIGILA por la instantánea de Power BI del 2026-09-28.
  - Riesgo: las semanas tempranas pudieron revisarse después (notificación tardía). Se declara.
  - Sin SIVIGILA 2026: EDA, IRA de Caldas e IRAG hospitalizada. La IRAG solo viene de otra tabla,
    sin solape para verificar el empalme. Esas tres quedan fuera.

---

## 2026-10-01 — Fase A, 7 de 8 modelos: resultados, y el criterio de «el mejor» estaba mal puesto

**Estado.** La corrida del 30-09 se cortó con el cierre de sesión durante SARIMAX. No fue un error del
código. Los otros 7 modelos quedaron completos (4.354 predicciones fuera de muestra cada uno).
SARIMAX se relanzó el 01-10.

**Corrección de Claude sobre su propio criterio.** Durante la corrida se ordenó a los modelos por la
pérdida de cuantiles y el MAPE. **Eso premia acertar el calendario, que es proyección.** El
propietario preguntó si se estaba midiendo bien, y no del todo:
- el control solo ya tiene un MAPE del 9,9 %, y el mejor modelo, 9,5 %;
- casi todo el error que queda es lo que no se puede anticipar, así que el MAPE apenas distingue
  modelos y no contesta «¿va a subir?».

**Métricas alineadas con el objetivo.** Se calcularon después de ver la fase A y se declaran como
tales.

| Modelo | R² del desvío | BSS sube | BSS pico | AUC pico | Cobertura 80 % | MAPE |
|---|---|---|---|---|---|---|
| Regresión binomial negativa | **9,3 %** (h1: 15,6) | **+4,0** | **+4,2** | 0,66 | 77,7 | **9,51** |
| Chronos-2 + calendario | 8,6 % (h1: 14,9) | **+4,1** | +2,6 | **0,71** | 78,5 | 9,57 |
| Control | 0 | −0,9 | −0,2 | — | 72,8 | 9,94 |
| Chronos-2 | −11,7 | −1,3 | −7,6 | 0,68 | 79,0 | 10,47 |
| LightGBM | −13,0 | −9,1 | −9,0 | 0,66 | 64,9 | 10,87 |
| Prophet | −30,2 | −22,5 | −19,7 | 0,41 | 64,2 | 11,18 |
| Ingenuo | −83,4 | −13,4 | −31,4 | 0,64 | 77,1 | 13,07 |

Cómo se lee cada columna:
- **R² del desvío:** de lo que el calendario NO explica (log real / lo que anunciaba el control),
  cuánto anticipó el modelo. Un valor negativo es peor que decir «lo que diga el calendario».
- **BSS** (*Brier skill score*): mejora de la probabilidad frente a decir siempre la tasa base
  (sube 45 %, pico 15 %). Positivo = la probabilidad sirve.

**Lo que se concluye:**
- **Solo dos modelos anticipan algo de lo que el calendario no explica:** la regresión y Chronos-2 +
  calendario.
  - Anticipan el 9 % del desvío (el 15 % a 1 día) y mejoran la probabilidad un 4 % sobre la tasa
    base.
  - Es una señal real y modesta.
- Los demás dan probabilidades **peores que no tener modelo**.
- **Por año:** el R² del desvío de los dos mejores es del 2-5 % en 2025 y del 14-16 % en 2026.
- **Semana contra semana** (¿la próxima semana tendrá más que esta?): todos están cerca del azar,
  entre 52 y 61 % frente a una base de 52 %.
- **Señal sobre el control:** la tasa de «sube» es del 45 %, no del 50 %. El nivel de 28 días va por
  detrás de una serie que cae, y el control sobreestima.

**SARIMAX, terminado el 01-10, gana en casi todo:**
- **R² del desvío: 17,1 %** (21,8 % a 1 día);
- **BSS sube: +9,0**; **BSS pico: +5,0**; AUC de pico 0,70;
- cobertura del 80 %: 78,0 %;
- **MAPE: 9,12 %**; pérdida de cuantiles: 2,24.

Le saca el doble a la regresión y a Chronos-2 + calendario en lo que el calendario no explica. Lectura
probable: es el único que **actualiza su estado cada día** con la memoria corta del residuo
(autocorrelación +0,26 a 1 día, cuaderno 14).

Nota de método: la corrida se relanzó arrancando cada ajuste desde los parámetros del anterior
(`start_params`). La especificación del modelo no cambia, solo el punto de partida del optimizador.
Antes no convergía en 100 iteraciones y tardaba más de 45 min.

**Propuesta de jerarquía de criterios** (espera confirmación del propietario):
1. **Decide:** BSS de sube y de pico, más la calibración.
2. R² del desvío.
3. Pérdida de cuantiles.
4. MAPE, solo para comunicar.
5. Requisito: cobertura del 80 % entre 75 y 85 %.

---

## 2026-09-30 — Arranca el modelo de predicción: decisiones del propietario y protocolo fijado antes de mirar

**Aclaración del propietario (corrige una lectura de Claude).** No hay dos proyectos. El proyecto
es **uno: predecir la tendencia del registro de triage**. La exploración (cuadernos 01-14) sirvió
para saber **con qué entrenar** y **cómo comprobar la fiabilidad**, y ahora empieza la fase de
modelado. Claude había planteado «predecir contra explicar» como una disyuntiva; no lo es. Las
razones de cada predicción son parte de la salida, no otro proyecto.

**Decisiones (propietario, 2026-09-30):**
- **D1. «Aumentar»** se mide contra lo que anuncia el calendario. Pico = z > +1 del residuo del
  control, como en el cuaderno 14. Además se da un umbral operativo.
- **D2.** Ventana diaria, horizonte de 1 a 7 días, y la suma semanal.
- **D3. La salida es una distribución** (cuantiles), y de ahí salen la probabilidad de pico y el
  intervalo. **La clasificación no aplica.** La regresión entra como **complemento**, para
  identificar patrones y como modelo explicable, no como método principal.
- **D4. Primero series de tiempo, y en competencia con otras familias**, cada una usada como le
  corresponde. El propietario pregunta si puede probar **MedGemma 4B**.
- **D5-D8, como los recomendó Claude:**
  - desde 2022-03, con régimen, y **solo lo disponible el día de la predicción**;
  - origen rodante y después una prueba prospectiva congelada;
  - mejora sobre el control y calibración;
  - razones descompuestas por capa.
- **Formato: un cuaderno con todas las fases de la predicción**, para revisar el paso a paso, lo que
  se tuvo en cuenta y la interpretación de cada resultado.

**Protocolo, fijado antes de ver ningún resultado:**
- **Desenlace:** triage diario del 2022-03-01 al 2026-09-20. La caída de registro de marzo de 2024 va
  como nula.
- **Evaluación de origen rodante:**
  - un origen por día del 2025-01-01 al 2026-09-13, prediciendo t+1 a t+7;
  - el entrenamiento arranca en 2022-03-01 y crece;
  - **todos los modelos se reentrenan cada 7 orígenes, con la misma regla.** Entre reentrenamientos
    usan los datos nuevos solo si su estructura lo permite (estado o rezagos).
- **Entradas por capas**, todas conocidas en el origen:
  1. calendario;
  2. estación;
  3. nivel reciente (28 días) en lugar de fechas de escalones, porque un escalón futuro no se
     conoce;
  4. memoria (rezagos del conteo);
  5. externas.
- **Fase A:** capas 1-4 en todos los modelos. **Fase B:** la capa 5 se suma a los mejores y se mide
  cuánto aporta. **Lo externo solo entra con información anterior al origen**: no hay pronóstico
  histórico del clima, así que se usa el clima observado hasta el origen.
- **Métricas:**
  - MAPE de la mediana, y mejora sobre el control de calendario (1 − error / error del control);
  - CRPS aproximado por pérdida de cuantiles;
  - cobertura de los intervalos del 50, 80 y 90 %;
  - probabilidad de pico con Brier, AUC y diagrama de fiabilidad.
  - Todo por horizonte.
- **Bases obligatorias:** el mismo día de la semana anterior, y el control de calendario (MAPE
  10,13 % en la medición de 2026-09-17).
- **Nada del periodo de evaluación se usa para elegir hiperparámetros.** Si hace falta afinar, se
  afina dentro de 2022-2024.

**Los modelos, especificados a priori** (`notebooks/pronostico.py`). Salida: 9 cuantiles, de 0,02 a
0,98.

| Modelo | Familia | Especificación |
|---|---|---|
| Ingenuo | base | Mismo día de la semana anterior × cuantiles históricos del salto semanal |
| Control | base | Log-lineal: día de semana + calendario + nivel de 28 días. Residuo empírico |
| GLM binomial negativa | regresión (complemento, con razones) | Las 4 capas. Un modelo por horizonte |
| LightGBM | árboles con refuerzo | Las 4 capas. Un modelo por cuantil y horizonte. 300 árboles, 15 hojas, tasa 0,03. Sin afinar |
| SARIMAX | serie de tiempo | (1,0,1)(0,1,1)₇ sobre log. Exógenas: calendario + Fourier anual de 3 armónicos |
| Prophet | serie de tiempo | Tendencia con cambios (`changepoint_range` 0,95), semana, año y calendario como regresores |
| Chronos-2 | modelo fundacional de series (IA preentrenada) | Sin entrenar. Contexto: toda la historia hasta el origen |
| Chronos-2 + calendario | igual | Con el calendario como covariable conocida a futuro |

**Sobre MedGemma 4B (pregunta del propietario).** Es un modelo de lenguaje médico: lee y escribe
texto. No está hecho para series numéricas: para él una serie es una cadena de dígitos. La
literatura (LLMTime, 2023, y sus réplicas) muestra que un modelo de lenguaje puede pronosticar sin
entrenamiento, pero peor que los modelos hechos para eso, y que el conocimiento médico no aporta
nada a ese pronóstico. **La «IA» diseñada para esto es un modelo fundacional de series de tiempo
(Chronos-2)**, y por eso entra en la competencia. MedGemma se prueba igual, a pedido del
propietario, como experimento pequeño y marcado como tal.

---

## 2026-09-30 — Resultado del cuaderno 14 (primera vuelta): a nivel día, ninguna fuente externa anticipa los estados de forma estable

`notebooks/14_los_estados_del_triage.ipynb`, 24 celdas, sin errores. Método de la fila
`estados_diarios`, sin cambiarlo después de mirar.

**Evidencia:**
- **El calendario explica el 72 % de la variación diaria** (el día de la semana solo, el 57 %). De
  264 picos del conteo, solo 116 (44 %) siguen siendo pico sin el calendario. Lo que queda se
  reparte parejo en la semana.
- **Estados:** pico +17,3 % (15 % de los días), bajo −15,5 %. Racha media de 1,4 días.
  P(pico mañana | pico hoy) = 29 %, contra una base del 15 %.
- **Estación:** mayo, 30 % de días pico y 4,5 % de bajos. Febrero y octubre, 7 % de picos. Diciembre,
  24 % de bajos.
- **Un pico es de toda la demanda:** todas las bandas de edad suben entre +16 y +27 %, y la
  composición del día no cambia (15-44 años: 53 % en pico, normal y bajo). Apunta a acceso y red, no
  a epidemia.
- **Agitación** (desviación típica de 14 días, tercil alto): diciembre 65 %, enero 47 %; trimestres
  2025-T4 63 % y 2026-T1 50 %. Es festiva o institucional.
- **326 pruebas, 55 con p < 0,05 (el azar daría 16), 36 sobreviven a BH y 3 se confirman.**
  - Vigilancia, días especiales, eventos, fiestas y desastres: 0 sobreviven.
  - Las 3 confirmadas (temperatura mínima, temperatura media y viento a 15-28 días) **no aguantan
    año por año**: están cerca de cero en cada año, salvo el viento en 2026. **No se toman como
    hallazgo.**
- **El clima del mismo día cambia en 2025:** la temperatura máxima en el pico da +0,26 / +0,26 /
  +0,32 en 2022-2024 y −0,18 / −0,09 en 2025-2026. La radiación aguanta mejor (+0,28 en 2026).
  Lectura: era una firma de **acceso** que el cambio de la red de 2025 alteró. **Sin verificar.**
- **Transición «mes cálido y seco → semana fresca y húmeda»**, a posteriori y declarada: +0,28
  (p = 0,02) en 2025-2026 y −0,10 en 2022-2024. **Es hipótesis, no hallazgo.**

**Qué se decide.** A nivel día, lo que sostiene un primer modelo es calendario, estación, nivel de la
red y memoria corta. Lo externo queda pendiente de la conversación con el propietario (preguntas
A-C de la sección 7 del cuaderno).

---

## 2026-09-30 — Cuaderno 14: los estados del triage a nivel día contra todas las fuentes externas

**Qué pide el propietario.** Enfrentar **todos** los datos externos contra el triage para ver qué
pasa en cada estado: picos, bajas y normalidad o estabilidad. A nivel **año-mes-día, sin hora**,
para no empezar demasiado fino. Y hacerlo en conversación, sacando conclusiones entre los dos para
saber qué hay para empezar el modelo de predicción.

**Qué se decidió (método, fila `estados_diarios` de `variables.csv`, escrito antes de mirar):**
- **El estado se define sobre lo que el calendario no explica**, no sobre el conteo crudo. Sobre el
  crudo, los picos son lunes y las bajas domingos, y eso es proyección. El control es el
  calendario completo más el nivel de la red. **La estación se conserva**, porque el clima y la
  vigilancia pueden explicarla.
- **Estados:** pico z > +1, bajo z < −1, normal |z| ≤ 0,5. La **estabilidad** es un tramo: la
  desviación típica móvil de 14 días del residuo.
- **Confrontación:** cada exposición contra los estados, con y sin mes fijo. Se descubre en 2022-2024
  y se confirma en 2025-2026. Cuenta solo lo confirmado con el mes fijo.

**Por qué el día y no la semana.** Los cuadernos 12 y 13 barrieron a nivel semana, y la semana
promedia los picos, que son de uno o dos días (cuaderno 08). El día es la escala a la que el
propietario quiere ver los estados.

---

## 2026-09-30 — Resultado de los barridos (cuadernos 12 y 13): el entorno general no predice el triage total; el camino es el desenlace respiratorio

**Qué se decidió.** No entra al modelo del total ninguna variable de clima ni de vigilancia como
predictor firme.
- **Entra a prueba** una sola: el cambio de radiación solar a 2 semanas, de la misma semana.
  Se retira si no mejora el control de calendario con origen rodante.
- **Candidato principal para el desenlace respiratorio:** la presión respiratoria de la ciudad
  (PC1 del SIVIGILA, en su mayor parte la IRA de Manizales por edad), con el resto de Caldas como
  adelanto de una semana.

**Por qué.** Se aplicó el método preregistrado (entrada siguiente y filas `barrido_*` de
`variables.csv`), sin cambiarlo después de mirar.

**Evidencia del clima (cuaderno 12)**
- **693 pruebas:** 11 variables base, 77 derivadas y 9 rezagos.
- **Descubrir:**
  - 84 pruebas con p < 0,05, cuando el azar daría unas 35; 34 sobreviven a BH q = 0,10.
  - Casi todas son un solo patrón a rezago 0: la semana soleada, seca y cálida trae +1-2 %.
- **Confirmar:**
  - 18 repiten el signo, **1 se confirma** (el azar daría 0,85) y 0 pasan BH dentro de la
    confirmación.
  - El efecto en confirmar es, en mediana, el 4 % del de descubrir.
  - Tiene más pluviómetro válido que descubrir (53,2 % frente a 35,8 %): la falta de confirmación
    no es por peor medida.
- **La que se confirma:** el cambio de radiación a 2 semanas, +1,4 % → +1,2 %, y +1,0 % con el mes
  fijo (p = 0,001). Por ser de la misma semana, se lee como acceso al hospital, no como contagio.
- **Estados del clima** (PCA ajustada en descubrir, 90 % de la varianza):
  - soleado y seco (51,6 %);
  - bochorno húmedo (24,6 %);
  - racha seca en calma (7,6 %);
  - ventoso (6,2 %).

  Contra el total no se confirma ninguno, y contra respiratorio, infecciosas y trauma sobreviven
  0 de 216 pruebas.
- **Sequía de 2026:**
  - real frente a lo normal del mes: abril −35 %, mayo −45 %, julio −52 %;
  - **gira en agosto a +44 %**, y la semana del 2026-08-16 cumple la regla de fin de sequía;
  - 4 episodios parecidos con triage: las 4-8 semanas siguientes quedaron en −0,6 % (sd 4,7) en el
    total y −2,1 % en respiratorio.

**Evidencia de la vigilancia (cuaderno 13)**
- **Inventario:** 88 series semanales.
  - El SES aporta entre el 0 % y el 0,22 % de la IRA de Manizales, así que la IRA de la ciudad no
    contiene al hospital.
  - **La SE53 de 2025 del 998 es un error de la fuente** (EDA de Manizales 2.495, unas 7 veces lo
    normal). Se anuló solo en memoria.
- **531 pruebas:** 13 sobreviven a BH, 10 con rezago ≥ 1 (5 series).
  - 3 se confirman en 2025, todas de una sola serie: EDA hospitalizada de Caldas a 4-6 semanas,
    +1,6 a +2,0 %.
  - **Al quitar la estación del desenlace cae a −0,3 / −0,5 %**, y el triage la «predice» igual de
    bien 2 semanas antes (p = 0,031). **Acompaña a la estación, no la anticipa**: se descarta.
- **Presión epidemiológica** (4 componentes, 44 % de la varianza):
  - PC1, respiratorio;
  - PC2, gastro;
  - PC3, salud mental e intoxicaciones;
  - PC4, violencia y lesiones.

  PC3 y PC4 son inestables entre periodos.
- **Contra los desenlaces:**
  - Contra el total, ningún componente pasa de ±1,7 %.
  - **PC1 → respiratorio del hospital:**
    - a rezago 0: +11,5 % en descubrir y +14,4 % en 2025;
    - **a 1 semana: +8,7 % → +10,6 %, con p = 0,055 en 2025.** No pasa el criterio y no se ajusta
      nada para que pase.
  - **La dilución está medida:** la misma ola da +11-14 % en el respiratorio del hospital y menos
    de +2 % en el total.
  - PC3 → respiratorio a 5 semanas se «confirma», pero sin mecanismo ni sostén en descubrir: se
    trata como azar.
- **Adelantos:**
  - el resto de Caldas se adelanta una semana a la IRA de Manizales (p = 0,009, sin corrección
    múltiple; con Bonferroni sobre 8 pruebas, ~0,07);
  - Colombia no se adelanta;
  - ninguna geografía se adelanta al triage total.
- **Operación:** los microdatos llegan ~8 meses tarde. La IRA de Manizales de Power BI se puede
  calcular a tiempo, y su anomalía correlaciona 0,989 con la de los microdatos. Pero la anomalía
  operativa (sin la media del año entero, que en operación no se conoce) correlaciona 0,806 con la
  del cuaderno, así que **todo resultado se re-mide con la anomalía operativa**.

**Qué cambia en el método desde hoy (añadido tras mirar, se declara como tal).** Antes de dar algo
por confirmado se exigen dos pruebas más:
- que el efecto sobreviva con el desenlace **sin estación**;
- que el triage **no «prediga» la variable** a rezagos negativos.

Motivo: la EDA hospitalizada cumplía el criterio preregistrado y era estacionalidad compartida. Se
aplica a ambos cuadernos. La radiación del cuaderno 12 la resiste: con el mes fijo sigue en
+1,0 %.

**Lectura.** La pregunta del proyecto sigue en pie, pero la evidencia desplaza dónde buscar:
- El **nivel** lo mueve la red (Nueva EPS), y ya está medido.
- Los **picos del total** los mueven el calendario y los mecanismos puntuales de 07 y 08.
- El **entorno general** actúa sobre la **fracción respiratoria**, donde el efecto es del 10-14 %,
  y se diluye en el total.

Esto confirma con datos el argumento de dilución de `CLAUDE.md`, ahora con los diagnósticos del
cuaderno 10, que existen desde 2020 sin NLP.

**Calidad de datos encontrada:**
- **Horas de lluvia de Open-Meteo:** inservibles (mediana de 24 h al día; r = 0,18 con el
  pluviómetro).
- **Consenso de lluvia:** llueve el 66 % de los días donde el pluviómetro dice 43 %. Por eso las
  rachas secas dependen de la fuente del día.
- **Radiación del consenso:** es solo NASA POWER.

Anotado en `calendarios/docs/CLIMA.md`.

**Pendiente de decisión del propietario:**
1. Corregir la SE53-2025 del 998 en `sivigila.py`.
2. Programar una instantánea semanal de Power BI, que es lo único que permite confirmar PC1 en 2026
   y operarlo.

---

## 2026-09-30 — Cambio de enfoque: variables generales y exploración ancha con método, no casos puntuales

**Lo que dijo el propietario tras el resumen.** Siente que el trabajo se fue a **casos demasiado
específicos** (colegios, Feria, accidentes), mientras **el clima completo y el SIVIGILA completo
casi no se han explotado**: «no hemos usado ni el 10 %». Pide mirar **las variables generales que
afectan a toda Manizales**:
- los estados climáticos completos: precipitación, calor, humedad, ambiente, y sus cambios;
- las épocas del año, por ejemplo **la sequía que está terminando ahora**, con lo que eso puede
  traer;
- toda la vigilancia.

También pide **pensar en predicción a más largo plazo**. Los casos puntuales llevan a predicciones
condicionadas a situaciones concretas, y eso es sobreajuste. Excepción clara: la red de salud (EPS),
que sí es general.

**Lectura honesta de la sesión.** El propietario tiene razón en el diagnóstico:
- se midieron muchos mecanismos puntuales (07, 08, 11) y se barrió poco;
- de las ~40 columnas de clima y de las 3 fuentes crudas se usaron 4-5 variables de nivel;
- de los 84 eventos del SIVIGILA se integraron 14 y se usaron 2-3.

**Decisión de método**, que responde a la vez a la amplitud y al sobreajuste:
1. **Barrido ancho por familia de fuente.** Cada variable se prueba en nivel, anomalía contra la
   climatología del mes, cambio brusco (1, 2 y 4 semanas) y extremos, con rezagos de 0 a 8 semanas.
   **Se controla la tasa de falsos descubrimientos con Benjamini-Hochberg** sobre todas las pruebas
   de la familia.
2. **Reducción a pocos índices generales.** Componentes principales del clima («estados del clima»)
   y de la vigilancia («presión epidemiológica»). **Al modelo entran índices, no cientos de
   variables.**
3. **Descubrir y confirmar en periodos distintos.** Se descubre en 2022-03 a 2024-12 y se confirma
   en 2025-01 a 2026-08. **Lo que no se confirma no entra.** Es la defensa directa contra el
   sobreajuste que preocupa al propietario.
4. **Desenlace:** triage total semanal (log), sin calendario y **sin los cortes de nivel de la red**
   (efecto por año y escalones de Nueva EPS en 2024-04, 2025-11 y 2026-07), **conservando la
   estacionalidad**, porque el clima y la vigilancia pueden explicarla. Como desenlaces
   secundarios, las series de diagnóstico del cuaderno 10: respiratorio, infecciosas, trauma.
5. **Horizonte largo:** además de 0-8 semanas, índices de temporada. Por ejemplo, el **fin de la
   sequía**: lluvia acumulada de 4-8 semanas contra la climatología, y su giro.

**Cuadernos:**
- 12, «El clima completo»;
- 13, «La vigilancia completa».

Método preregistrado en `patrones/datos/variables.csv` (filas `barrido_*` del 2026-09-30).

---

## 2026-09-30 — Cuaderno 11: más cruces del entorno, y lo que entra al repertorio

Archivo: `notebooks/11_cruces_del_entorno.ipynb`, 21 celdas, sin errores, sin datos del hospital.
Las preguntas son las preregistradas en `variables.csv` el mismo día.

**Resultados:**
1. **Frío y humedad → IRA de la ciudad**, media de las 5 semanas previas, 2022-2025, HAC:
   **+7,6 a +9,9 % (frío) y +6,8 a +9,7 % (humedad) por desviación típica**, significativo. **La
   interacción con colegio abierto no aparece** (p = 0,57 y 0,45).
   - **Corrección dentro del cuaderno:** la primera versión daba +33 % porque medía por grado y no
     por desviación típica (sd = 0,33 °C).
2. **Tras la Feria, la IRA de la ciudad sube** +19 / +37 / +20 % a 1-3 semanas; sin 2022, +26 / +57
   / +34 %. **No se atribuye a la Feria**: cae siempre en las mismas semanas, y el año de
   referencia incluye 2015-2019, cuando los eventos no están marcados. Lo que sí queda es que
   **en los años recientes enero trae una ola respiratoria** tras la temporada festiva, que el
   cuaderno 10 ve también en el hospital (respiratorio en enero, 1,26).
3. **Puentes → IRA:** +3 a +9 %, sin forma. **Semana Santa → IRA registrada −14 a −35 %**: menos
   consulta.
4. **El receso escolar, medido desde su inicio, no baja la IRA**, cuando el cuaderno 09 (por semanas
   de receso) sí lo veía. **Resultado no robusto al método.**
5. **Lluvia → lesiones personales −5,7 %** [−10,1; −1,1] con el calendario descontado. La violencia
   intrafamiliar y el tránsito no responden al clima.
6. **Salud mental:** el intento de suicidio baja en enero-febrero (0,77-0,83) y sube en
   agosto-octubre (1,11-1,14). Festivos y quincena no mueven de forma clara ni el intento de
   suicidio ni las intoxicaciones.
7. **ENSO:** a IRA −0,10 a −0,13 y a EDA +0,15 a +0,18 a 2-4 meses. Nada pasa el umbral (~0,32):
   es contexto de fondo.
8. **Policía frente a SIVIGILA:** la violencia de género y la violencia intrafamiliar van juntas año
   a año (0,79) y algo por semana (0,23). **Trampa:** el intento de suicidio y la violencia
   intrafamiliar dan 0,86 anual por tendencia compartida de notificación, pero 0,03 semanal.

**Decisión, por parsimonia: qué entra al repertorio del modelo.**
- **Frío y humedad del último mes.**
- **Enero como periodo respiratorio.**
- **Calendario festivo y lluvia para la calle.**

**Queda de contexto, sin entrar:** ENSO, salud mental, puentes, las series de la Policía como
predictor.

---

## 2026-09-30 — Parsimonia: no explorar de más, y más cruces del entorno antes de volver al hospital

**Decisiones del propietario:**
1. **Las preguntas para el superior se descartan por ahora** (código 9, «no habilitación», alza
   obstétrica). No hay forma de consultarlas hoy. No bloquean nada.
2. **No profundizar innecesariamente.** Una exploración demasiado fina da al modelo demasiado
   contexto. El riesgo es el **sobreajuste**: predicciones con probabilidades demasiado altas que
   no se sostienen fuera de muestra.
   - **Principio que queda:** pocas variables, cada una con un mecanismo plausible y respaldo en
     la literatura o en la medición, preregistradas.
   - No se añade una variable porque «podría explicar algo».
3. **El perfil del hospital (cuaderno 10) se va completando** a medida que aparezcan limitaciones,
   sin abrir otra exploración a fondo.
4. **Siguiente: más cruces entre contextos externos**, para entender mejor la ciudad y tener un
   repertorio más amplio antes de volver a enfrentarlo contra el hospital. Después, un resumen de
   todo lo encontrado y la conversación sobre cómo hacer las predicciones.

**Por qué importa el punto 2 para la tesis.** Con ~236 semanas útiles (2022-2026) y un residuo
semanal con autocorrelación de +0,62, el número efectivo de semanas independientes es del orden
de 75. **Un modelo con decenas de variables externas se ajusta al ruido.** La literatura de
pronóstico de urgencias muestra ganancias pequeñas por variables externas (revisión en
`calendarios/docs/LITERATURA_ENTORNO.md`). Un modelo que prometa mucho más es sospechoso por
construcción.

**Alcance de los cruces nuevos (cuaderno 11)**, a propósito acotado a preguntas con mecanismo y
literatura detrás:
- ¿Las fuentes de la ciudad cuentan lo mismo? Policía frente a SIVIGILA.
- ¿Las aglomeraciones siembran contagio? Feria, puentes y Semana Santa → IRA a 1-3 semanas.
- ¿El frío pesa más con los colegios abiertos? Es la «suma de factores» dentro de la ciudad.
- ¿El clima mueve la violencia?
- Salud mental e intoxicaciones frente al calendario.
- ¿El ENSO precede a la IRA o a la EDA?

---

## 2026-09-30 — Cuaderno 10: el perfil del hospital, con datos enmascarados

**Decisiones del propietario:**
- **No existe diccionario de códigos de la base.** La causa de ingreso se rotula solo donde hay
  evidencia: 3 = enfermedad general (probable), 6 = tránsito, 10 = laboral. El resto queda como
  «código N (sin catálogo)».
- **Solo interesa qué pasa y en qué estado**, nunca quién. Enmascarar lo mejor posible.
- Commit y push para no perder el progreso.

**Cómo se enmascara** (`python -m extraccion --perfil`, en `extraccion/__main__.py`):
- **Solo conteos** por mes, semana o año y por categoría de catálogo. Los ingresos, folios y
  diagnósticos se unen dentro de la consulta.
- **Toda casilla con menos de 5 casos se oculta**; la columna `suprimido` la marca.
- **Cruces elegidos gruesos a propósito.** Con mes × motivo × servicio se ocultaba el 81 % de las
  casillas, y con semana × capítulo × edad el 53 %. Con cruces de dos dimensiones se oculta el
  7-36 %.
- **Los diagnósticos se agrupan en los 22 capítulos de la CIE-10** (`extraccion/cie10.py`). El
  código de 3 caracteres solo sale **por mes y con ≥ 5**, rotulado con la subcategoría más usada
  del hospital, porque el catálogo de la base no trae el nombre de la categoría.
- **Se versionan** las 9 tablas con supresión. **No se versiona** `perfil_dx_diario` (día ×
  capítulo, sin supresión), que se queda en este equipo para el análisis de mecanismos.
- El texto libre (`MotivoRemision`, notas) **no se consulta nunca**. `MOTIVO` solo se extrae si
  sigue siendo un catálogo de ≤ 10 valores y ≤ 60 caracteres; se comprueba en cada corrida.

**Resultados** (`notebooks/10_perfil_del_hospital.ipynb`, 19 celdas, sin errores):
1. **Fracción de triages que pasan a ingreso:** 51,6 % (2020), 49,5 % (2023), **35,2 % (2024),
   30,0 % (2025)**, 34,3 % (2026). **El hospital sigue recibiendo, pero se queda con menos.**
2. **Por edad**, se ingresan más los mayores y mucho menos los niños (estabilizar y remitir). **El
   nivel de triage es la decisión**: I, II y IIIU 92-95 %; IV 14 %; V 0 %.
3. **La unidad obstétrica crece** (2.349 → 5.554 ingresos entre 2020 y 2024) mientras Urgencias cae
   desde 2023.
4. **El código 9 de causa de ingreso, sin catálogo, pasa del 18 % al 31 %** de los ingresos
   (2020-2026). Accidentes de tránsito: 600-1.000 al año, estable. Laborales: de 238 a 6 (2025).
5. **Diagnósticos por edad:**
   - 0-4: respiratorio 26 %, trauma 22 %, perinatal 21 %;
   - 5-14: trauma 33 %;
   - 15-44: embarazo 24 %;
   - 65+: circulatorio 13 % y respiratorio 10 %.
6. **Perfil anual por capítulo** (2022-2025, 1 = media del año):
   - **respiratorio: junio 1,36, enero 1,26, mayo 1,19**; febrero 0,75;
   - **diarrea: marzo-abril 1,30-1,33**;
   - **trauma: diciembre 1,21**, agosto 1,10;
   - el embarazo casi no varía.

   **Cada mecanismo del entorno tiene su huella en lo que se atiende, y en su época.**
7. **Remisiones**, 2023-2026:
   - falta de especialidad: 1.913;
   - **no hay convenio con la EPS: 1.209**;
   - camas: 444;
   - **«no habilitación» aparece de golpe (0 → 21 → 110 en 2024-2026)**.

**Hallazgo de método.** Hay **series de desenlace específico diarias desde 2020, con diagnóstico
médico y sin NLP**: respiratorio (J), diarrea (A09), trauma (S) y embarazo (O). Es lo que
`CLAUDE.md` esperaba del NLP, con 6 años en vez de 20 meses. **Límite:** solo cubren al grupo que
se ingresa (30-50 % del triage).

**Rareza sin interpretar:** «perinatal» aparece en el 17 % de los ingresos de 5-14 años.
Probablemente viene de cómo se registra la edad cuando un ingreso agrupa a madre y recién nacido.

**Preguntas para el propietario y su superior:**
- qué es el código 9;
- qué servicio dejó de estar habilitado en 2025-2026;
- si el alza de obstetricia es de la ciudad o del cierre de otra maternidad.

---

## 2026-09-29 — Exploración de la base para el perfil del hospital: primeros resultados

Se siguió el protocolo:
- esquema primero;
- **las columnas sensibles de 14 tablas añadidas a `extraccion/__init__.py` antes de consultar
  nada**;
- solo agregados por año. Las casillas con menos de 5 casos van a «otros».

**Ningún texto libre salió.** Los scripts de exploración están en el scratchpad
(`esquema_perfil.py`, `cobertura_perfil.py`, `repartos_perfil.py`) y todavía no se versionan.

**Cómo se enlaza:**
- triage → `DIM_INGRESO` (`ADNINGRESO`);
- ingreso → `DIM_FOLIO` → `CONTROL_DIAGNOSTICO` (`HCPDIAPRIN` = principal) → `DIM_DIAGNOSTICO` (CIE-10);
- ingreso → `AREA_SERVICIO` (con marca de urgencias).
- **Cobertura: el 98-99 % de los ingresos tiene diagnóstico principal CIE-10.** Es el diagnóstico
  estructurado que `GENDIAGNO1` no traía.

**1. Qué fracción del triage se atiende en el SES** (triage con ingreso):
- ~50 % en 2020-2023, **35 % en 2024, 30 % en 2025 y 34 % en 2026**.
- Por nivel: I 87 %, II 94 %, IIIU 93 %, III-G 64 %, **III 30 %, IV 14 %, V 0,1 %**. El nivel es,
  en la práctica, la decisión de tomar o redirigir.
- **Por edad: 65+ 55 %, 45-64 43 %, 15-44 39 %, 5-14 15 %, 0-4 13 %.** Confirma lo dicho por el
  superior: los niños se estabilizan y se remiten.

**2. Dónde se atiende:**
- Urgencias: 122.136 ingresos, 2020-2026.
- **Unidad obstétrica: 27.841, y creciendo** (2.349 en 2020, 5.554 en 2024, 4.851 en 2026 a
  septiembre).
- Recién nacidos: 596.

**3. Qué tienen** (diagnóstico principal del primer folio, primera letra CIE-10, 2020-2026):

| Grupo | Ingresos |
|---|---|
| R, síntomas (dolor abdominal R10: 15.171) | 25.459 |
| **S, traumatismos** | **22.128** |
| O, obstetricia | 21.840 |
| N, genitourinario | 13.157 |
| **J, respiratorio** (EPOC exacerbado J44, rinofaringitis J00) | **11.523** |
| M, osteomuscular | 11.037 |
| G, neurológico (cefalea, migraña) | 10.767 |
| I, circulatorio | 10.120 |
| K, digestivo | 8.713 |
| **A, infecciosas (diarrea A09: 4.944)** | 5.917 |
| U07, COVID | 4.601 |

- **Llega mucho trauma (S, el segundo grupo), pero no por SOAT.** Son contusiones de dedos,
  rodilla y cabeza: caídas y golpes, no accidentes de tránsito.
- **Aviso para la tesis.** Hay series con **mecanismo externo conocido**, codificadas desde 2020,
  **sin NLP**: respiratorio (J), diarrea (A09), trauma (S) y obstetricia (O). Son los «desenlaces
  específicos» que el `CLAUDE.md` pedía al NLP, **pero solo del subconjunto que se ingresa**.

**Advertencia:** los nombres de los códigos de 3 caracteres salieron de `MIN(DIANOMBRE)`, que es el
nombre de una subcategoría y no de la categoría. Por ejemplo, N39 salió como «incontinencia»
cuando N39.0 es infección urinaria, y R07 como «dolor de garganta» cuando R07 es sobre todo dolor
torácico. **Hay que rotularlos con la categoría CIE-10 oficial.**

**4. Causa de ingreso** (`AINCAUING`, códigos sin catálogo en la base). Descifrados en parte cruzando
con el asegurador:
- **código 6 = accidente de tránsito** (74 % SOAT);
- **código 10 = accidente laboral** (74 % ARL);
- **código 3 = enfermedad general** (casi todo);
- el **código 9** tiene 34.197 casos de todos los aseguradores y no se sabe qué es;
- 4, 2, 1 y 8 tampoco se saben.
- **Hace falta el diccionario de la base** (pregunta al superior).

**5. Remisiones** (`SEGUIMIENTO_REMISIONES_DW`, 2023-2026, ~1.200-1.600 por año). `MOTIVO` resultó
ser un catálogo de 6 valores (≤ 36 caracteres). `MotivoRemision` es texto libre de ~550 caracteres
y **no se consulta**.

| Motivo | Remisiones |
|---|---|
| **No disponibilidad de la especialidad** | 1.913 |
| **No convenio con la EPS** | 1.209 |
| No disponibilidad de camas | 453 |
| No habilitación (sube: 0 → 111) | 152 |
| Menor complejidad | 103 |
| No disponibilidad de equipos | 71 |

El 60 % de las remisiones sale de Urgencias (2.975). Coincide con el superior: se recibe todo y se
remite por especialidad y por convenio con la EPS.

**Pendiente de decidir con el propietario:**
- **qué granularidad se persiste**. Un diagnóstico por día con cifras pequeñas es información de
  salud: se propone capítulo CIE-10 por día, capítulo × banda de edad por semana y código de 3
  caracteres solo mensual con supresión < 5;
- **si se versiona**, porque el repositorio está en GitHub. La propuesta es **no** versionarlo
  mientras no lo autorice.

---

## 2026-09-29 — Qué hospital es el SES, según el superior del propietario; se abre la exploración de la base

**Contexto institucional** (el superior, vía el propietario). Responde la decisión #13 en su parte
cualitativa:
- **El SES recibe de todo.** Una urgencia se atiende por razones legales y morales. Otra cosa es
  que pueda **resolverla** allí.
- **Donde faltan especialistas, se recibe, se estabiliza y se remite.**
  - **Niños:** no hay especialistas pediátricos. La urgencia infantil se estabiliza y se envía al
    Hospital Infantil, que no tiene urgencias propias de puerta.
  - **Cardiovascular:** se remite a una clínica cardiovascular de Manizales. El propietario cree
    que es Avidanti, sin confirmar.
- **Accidentes de tránsito:** no hay un destino fijo; la ambulancia va al hospital más cercano.
  - Hipótesis del propietario: el SES está en una zona de avenidas bien señalizadas, con pocos
    accidentes cerca, y por eso le llegan pocos.
  - Sin SOAT, el paciente no llega por esa vía, sino por su EPS a donde haya convenio.
- **Remitir no es no atender**: «es mejor remitirlo que tratarlo con limitaciones».

**Cómo cambia la lectura de lo ya medido:**
- El **SOAT bajo** del SES (4 %) y su falta de relación con el tránsito de la ciudad (r = 0,01) son
  **geografía y logística de ambulancias**, no falta de demanda.
- La **estacionalidad pediátrica** del SES mide a los niños que **pasan por aquí para ser
  estabilizados**, no a toda la demanda infantil.
- El **51 % «no urgente»** (cuaderno 02) y el «60 % que se remite a la EPS» son la puerta de un
  hospital que **recibe todo y resuelve según su capacidad**.

**Decisión:** explorar la base para el perfil del hospital (cuaderno 10) **con el protocolo de la
regla 1, y con cautela reforzada por petición expresa del propietario**:
1. Solo esquema.
2. Clasificar cada columna nueva y añadir las sensibles a `extraccion/__init__.py` **antes** de
   consultar nada.
3. Solo conteos agregados de columnas codificadas.

**Ningún texto libre sale de la base**, ni siquiera como «valores más frecuentes». El precedente
del 28-09 fue que un agente imprimió valores de una columna con forma de cédula.

---

## 2026-09-29 — Cuaderno 09: el entorno conectado consigo mismo

Archivo: `notebooks/09_el_entorno.ipynb`, 21 celdas, sin errores. **Ningún dato del hospital.**
25 contextos por semana, y análisis conjunto en 2022-2025, unas 209 semanas.

**Datos nuevos integrados:**
- **ENSO:** `calendarios/clima/enso.py` → `calendarios/enso_oni.csv` (ONI de la NOAA, 1950-2026).
  Un episodio abierto al final de la serie se marca «en curso»: **El Niño de 2026, ONI +1,80 en
  junio-agosto**.
- **Recesos escolares oficiales:** `calendarios/calendario_escolar_manizales.csv`, 2021-2026, cada
  uno con su resolución y su URL. Sustituye las 122 fechas fijas del calendario.

**Hallazgos:**
1. **El calendario mueve la violencia de la ciudad** (Policía, Poisson, 2015-2026 sin cuarentenas).
   - Lesiones personales: domingo ×1,78, festivo ×1,32, **noche festiva ×1,96**.
   - Homicidios: domingo ×2,11 y noche festiva ×2,02.
   - **La violencia intrafamiliar tiene otro calendario:** quincena ×1,20 y receso escolar ×0,83.
   - El tránsito baja en festivo (×0,72).
2. **Cadenas con rezago** (anomalías sin estacionalidad):
   - **Temperatura media → IRA ciudad: r = −0,37 a 4 semanas.** Frío → más IRA.
   - Temperatura mínima: −0,31 a 1 semana.
   - Humedad: +0,31 a 5 semanas.
   - Lluvia: +0,23 a 5 semanas.
   - **Receso escolar → IRA −0,20 y varicela −0,18 en la misma semana.**
   - **ENSO → temperatura +0,49.** El Niño calienta Manizales.
   - Al revés de lo esperado: **lluvia → EDA −0,19**.
   - La ceniza no se puede medir: solo 4 episodios.
   - **Es la cadena clima → contagio → consulta que describía el propietario**, vista en la ciudad
     sin el hospital. Las barras en *k < 0* indican que parte es persistencia compartida: no es
     prueba de causa.
3. **Estados del entorno** (k-medias):
   - **Con calendario, 5 estados:** calma (45 % de las semanas; febrero-mayo y
     septiembre-noviembre), seco y cálido (julio-septiembre, El Niño), fiestas de los pueblos,
     temporada decembrina (100 % de diciembre) y Feria.
   - **Sin calendario, 3:** frío y húmedo (marzo-junio y octubre-diciembre), intermedio, y seco y
     cálido (julio-septiembre).
   - La IRA no define ningún estado. **El estado visible es el gatillo** (frío y húmedo), que
     precede a la IRA.
   - Siluetas bajas (0,13-0,17): son regiones de un continuo, no cajas.
4. **La «suma de factores» puesta en fechas:**
   - **marzo a mayo** junta colegios abiertos, frío y humedad, y lluvias. Es donde el cuaderno 08
     vio las semanas altas sostenidas;
   - **diciembre** junta receso, fiestas y violencia. Son los picos puntuales de noche.

**Trampas documentadas:**
- **La IRA como porcentaje sube en receso por el denominador** (cae la consulta programada). Para
  el contagio se usa el conteo.
- **La ceniza, la pólvora y el alumbrado parecen relacionados solo porque caen en el mismo
  diciembre** (2023).

**Sección 6 hecha el mismo día.** Revisión de literatura en `calendarios/docs/LITERATURA_ENTORNO.md`:
11 relaciones y 86 referencias verificadas, escrita **antes** de comparar.
- **Casi todo lo esperado aparece en la dirección publicada:** lluvia y humedad → IRA a ~1 mes,
  frío → IRA, cierre de colegios → menos transmisión, El Niño → calor, fin de semana y fiesta →
  violencia, pólvora en diciembre-enero. Eso da confianza en que las series externas miden lo que
  dicen.
- **No coincide:** la lluvia no sube los siniestros viales. La literatura avisa que el efecto es
  por hora y que el dato diario lo diluye.
- **Aportes posibles de la tesis, sin estudio publicado:**
  - quincena → violencia intrafamiliar ×1,20;
  - **la interacción frío × virus × población mayor.**
- **Vacíos de datos:** la ceniza (hace falta el PM10 del CDIAC, #10a), el tránsito por hora y la
  transición seco → lluvioso sobre la EDA.

**Decisión: el siguiente paso es enfrentar los estados y sus interacciones contra el hospital**,
preregistradas antes de mirar. La primera es la del propietario: frío anómalo × IRA circulando ×
mayores de 65.

---

## 2026-09-29 — Primero el entorno entre sí, después el hospital; el perfil del hospital espera

**Decisión del propietario.** Antes de volver a enfrentar nada contra el triage, se **conectan
los contextos externos entre sí**:
- clima, calendario (fines de semana, festivos, vacaciones);
- fiestas y eventos;
- vigilancia en salud;
- violencia y lesiones;
- volcán, ENSO y desastres.

**Qué se busca:**
- qué se mueve junto y con qué rezago;
- qué caracteriza la **«calma»** o flujo normal;
- qué **estados del entorno** se repiten, por ejemplo «temporada respiratoria activa»,
  «temporada festiva» o «calma».

Cada relación observada se **contrasta con la investigación publicada**. Ejemplo del
propietario: estudios de cómo la ceniza volcánica afecta la calidad del aire y la salud
respiratoria. **Solo después** se enfrentan esos estados, y sus **interacciones**, contra el
hospital.

**Por qué.** Enfrentar cada factor por separado contra el triage no ve **la suma de factores**. El
ejemplo del propietario: población frágil, más frío, más virus circulando da un riesgo mayor que
cada uno solo. Para medir esa interacción, primero hay que saber cuándo coinciden los factores
en el entorno.

**Diseño:**
1. **Revisión de literatura primero**, por un agente. Relaciones esperadas entre contextos, con
   dirección, tamaño y rezago publicados. Así lo esperado queda escrito antes de mirar lo
   observado, que es el espíritu del preregistro.
2. **Cuaderno 09, «El entorno».** Solo datos externos, ningún dato del hospital:
   - perfiles estacionales compartidos;
   - correlaciones cruzadas con rezago entre anomalías;
   - efecto del calendario sobre las otras series externas;
   - **estados del entorno** por agrupamiento de semanas;
   - comparación de lo observado con lo publicado.
3. **Datos que faltan y se integran para esto:** el índice ENSO (ONI de la NOAA) y el calendario
   oficial de vacaciones escolares, con las fechas de las resoluciones.

**El perfil del hospital (cuaderno 09 propuesto el mismo día) queda EN ESPERA.** El propietario
va a hablar con su superior para conseguir documentación e información de base antes de
construirlo desde cero. Pasa a ser el cuaderno 10. Ya se identificaron en el esquema, sin bajar
datos, tres tablas candidatas:
- `DIM_INGRESO`: causa de ingreso, servicio, cama;
- `CONTROL_DIAGNOSTICO` → `DIM_DIAGNOSTICO`: CIE-10;
- `SEGUIMIENTO_REMISIONES_DW`: remisiones. **Trae cédula, nombres y texto clínico: solo
  agregados.**

---

## 2026-09-29 — Cuaderno 08: los picos tienen tres relojes, y se corrige lo dicho sobre la mitad de año

Archivo: `notebooks/08_los_picos.ipynb`, 21 celdas, sin errores. Las pruebas son las
preregistradas el mismo día.

**1. Revierte el «matiz» de la entrada «Los cuadernos cuentan la historia completa»**, que decía
que el alto de mitad de año cae en mayo, antes de las vacaciones, y que junio-julio bajan.
**Era un artefacto del control.** Ese cálculo descontaba las «vacaciones escolares» del
calendario, que son 122 fechas fijas cada año.
- **Sin ese descuento** (control con día de la semana, festivo y año), **las semanas de
  vacaciones escolares oficiales están por encima del nivel del año los cinco años**: +3,5 a
  +9,3 %, media **+6,5 %**. Marzo-mayo está en +4,3 %.
- **El propietario tenía razón:** la mitad del año es la parte alta, de marzo a julio.
- Lección: un control que incluye la variable que se quiere estudiar la hace desaparecer.

**2. Las noches festivas**, frente a los demás domingos y festivos:
- **La ciudad es violenta esas noches.** Las lesiones personales de la Policía suben +161 % en
  velitas, +120 % el 8 de diciembre, +54 % el 25 y **+201 % el 1 de enero**.
- **En el SES el día completo baja**: −24 % en velitas, −35 % el 24, −40 % el 31.
- **Pero la madrugada sube**: +44 % la del 8 de diciembre, +31 % la del 31 y +35 % la del 1 de
  enero.
- **El 31 llegan +74 % de particulares.**
- La pólvora es el 80 % de sus casos anuales en diciembre-enero (SIVIGILA 452: 1,3 por semana),
  pero pesa poco en el conteo.

**3. El pico llega el día después.** En las 4 temporadas limpias: **3 de enero +14,0 %**, 2 de
enero y 26 de diciembre +6,7 %, 4 de enero +5,6 %.
- Del 2 al 4 de enero se juntan el día siguiente a Año Nuevo, el regreso de vacaciones, la Feria
  y el Carnaval de Riosucio.
- **Corrección dentro del mismo cuaderno:** la temporada 2021-22, dentro de la ventana COVID que
  el modelo no ajusta, fabricaba un pico de +11 a +17 % el 8-10 de diciembre. Sin ella, el 8 de
  diciembre queda en +2,7 %.

**4. Fiestas de los pueblos** (107 fiestas realizadas con fecha):
- Durante la fiesta y los 3 días siguientes, el total sube **+1,9 % [+0,5; +3,4] con las lejanas
  (≥ 60 km)** y +0,2 % con las cercanas. En 15-44 años, +2,1 % con las lejanas.
- **La huella del asegurador no acompaña:** particulares −7,5 %; IPS remitente −6 %, −10 % con
  las cercanas.
- Son 18 pruebas. El patrón «lejos > cerca» encaja con la hipótesis de remisión, pero el efecto
  es pequeño. **La prueba directa es la serie del CRUE** (#12).

**5. Para el modelo, decidido aquí:**
- **El indicador de festivo se parte en dos**: la noche de fiesta, que baja de día y sube de
  madrugada, y el día siguiente, que sube.
- **Las vacaciones escolares se toman con las fechas oficiales de cada año**, no con las fijas
  del calendario.
- **Las fiestas de los pueblos entran separadas por distancia**, con peso bajo.
- **Conviene un modelo por hora, o al menos día y madrugada por separado.**

---

## 2026-09-29 — El pluviómetro de La Nubia reporta cero cuando llueve: el clima vuelve a fabricar sequías

**Hallazgo**, del agente del cuaderno 03 y verificado aquí sobre `calendarios/clima_unificado.csv.gz`:

| Mes | Pluviómetro (mm, días con dato) | NASA POWER (mm) |
|---|---|---|
| 2025-02 | 1,2 (7) | 202,8 |
| 2025-10 | 4,2 (31) | 202,6 |
| 2026-01 | 8,8 (30) | 240,3 |
| 2026-02 | 1,6 (28) | 200,4 |
| **2026-03 a 2026-06** | **0,0 cada mes, con dato los 30-31 días** | 103-159 |

**El pluviómetro no está ausente: reporta cero todos los días.** Como `precip_con_estacion` lo da
por medido y el consenso toma el pluviómetro de referencia, **marzo-junio de 2026 aparecen como
los meses más secos de la serie**, cuando la fuente satelital dice que llovió lo normal. Es el
mismo tipo de defecto que el arreglo del 23-09 corrigió en otra dirección: allí la falta de dato
fabricaba tormentas; aquí un **dato falso** fabrica sequías. El propietario sospechaba que el clima
tenía cálculos mal hechos, y en esto tenía razón.

**Además:** en 2021 no hay ninguna medida de lluvia en tierra (0 días con pluviómetro). Todo ese
año es reanálisis, y sale como el más seco del consenso (664 mm).

**Qué queda en duda:**
- las variables de lluvia de octubre de 2025 a junio de 2026;
- **los episodios «seco → lluvioso» del cuaderno 07 de ese periodo**, porque un falso seco
  seguido de la vuelta del pluviómetro fabrica una «ruptura»;
- las variables de lluvia del periodo de prueba del cuaderno 05.

El +22 % de los 0-4 años tras un paso de seco a lluvioso **se vuelve a medir con el clima arreglado
antes de citarlo**.

**Decisión:** `clima_unificado.py` debe detectar la falla y tratarla como ausencia de pluviómetro.
El criterio es el cero sostenido de la estación mientras el satélite registra lluvia, a escala
de mes y no de día: un día seco aislado es real. La corrección y su evidencia van en
`calendarios/docs/CLIMA.md`.

**Hecho el mismo día.** `pluviometro_fallido()` usa 31 días centrados: pluviómetro < 10 % de NASA
y NASA ≥ 60 mm.
- **Por qué el 10 %:** en los 34 meses sanos la razón va de 0,27 a 1,42; en los fallidos es
  < 0,04.
- Marca 199 días y se aplica **antes** de calcular los factores de escala.
- La lluvia anual queda en 1.297 mm y los días con pluviómetro válido bajan al 34,7 %.

**Resultados que cambian:**
- **Seco → lluvioso, 0-4 años: de +22,0 ± 17,8 % (13 episodios) a +13,4 ± 15,0 % (17
  episodios).** La forma es la misma, pero **ya no se distingue de cero**.
- Lluvia fuerte y madrugada: de −7,8 % a −4,3 %, no significativo.
- En el cuaderno 06, la lluvia en quintiles pasa de −3,6 a −2,5 puntos.

**No cambian:** Feria, eventos sociales, Nueva EPS, enfriamiento y calentamiento, picos y el mapa
de correlaciones (las mismas 15 casillas marcadas).

**Cuadernos:**
- 06 y 07 re-ejecutados, con recuadros «clima corregido».
- 01, 02, 03 y 05 en manos de un agente.

**Lección, la segunda sobre el mismo archivo:** una fuente que **reporta** también puede estar
rota. La completitud no mide la verdad del dato. Toda referencia en tierra se contrasta con una
fuente independiente mes a mes antes de usarla.

---

## 2026-09-29 — Los cuadernos cuentan la historia completa, y los picos pasan al centro

**Decisión del propietario: los cuadernos 01 a 07 se corrigen para contar todo el camino.**
Cada uno debe mostrar:
- las premisas, los datos y las figuras;
- las fuentes de donde sale cada dato;
- la lectura y sus límites;
- **y lo que se supo después**.

**Cómo se corrige** (criterio fijado aquí): una afirmación que resultó falsa **no se borra en
silencio**. Queda visible con un recuadro «Corrección del 2026-09-29» que dice qué cambió y por
qué, igual que este archivo, que solo crece. El valor del recorrido está en poder ver por qué se
cambió de idea.

**Correcciones de fondo ya identificadas:**
1. **El 01 dice que la caída del 23,9 % es «en parte artefacto» del cambio de criterio de
   triage.** Es un error de razonamiento: reetiquetar un triage de IV a III **no cambia el
   conteo**. La caída del volumen es de **Nueva EPS** (cuaderno 07: 115,8 → 72,2 triages por día
   entre 2025 y 2026). La reclasificación es un fenómeno aparte, de la institución.
2. **El 01 dice «no hay huecos de registro».** El 19 y el 20 de marzo de 2024 no tienen filas,
   y el 21 tiene 40.
3. **El 01 y el 02 presentan la gripa y los niños como la hipótesis del proyecto.** Era un
   ejemplo (aclaración del 28-09).
4. **El 02 remite a un «cuaderno 03» de control de calendario que no existe.**
5. **El `05_validacion_sin_motivo.py` no es un cuaderno.** Se convierte, y su conclusión («las
   externas no mejoran el pronóstico») se matiza con el 07.

**Estructura nueva:**
- **03, nuevo**: las fuentes externas, con de dónde sale cada una, su cobertura y sus escalones.
  Hoy esa información solo está en `calendarios/docs/`.
- **08, nuevo**: los picos.
- **`notebooks/README.md`**: el hilo que une los cuadernos. El 04 (ciclo horario con Fourier)
  sigue pendiente.

**Los picos pasan al centro. Hipótesis del propietario**, que se preregistran antes de medir en
el 08:
- **Diciembre**: alcohol, riñas, fiesta, **pólvora**, quemados por velitas (7 de diciembre) y por
  el muñeco del 31. Es festivo y peligroso.
- **Año Nuevo y enero**: además de la Feria, **las fiestas de los pueblos cercanos**. Lo que el
  hospital del pueblo no puede atender termina en Manizales.
- **Mitad de año**: el propietario ve **más picos a mitad de año que a final**, lo que hay que
  medir.
- El contexto debe salir de **fuentes oficiales del gobierno de Caldas y de Manizales**.

**Lo que se deja:** accidentes de tránsito y lluvia como vía de los picos. Ya se midió que al SES
llega poco tránsito (r = 0,01 con la ciudad, salva la Feria) y que la lluvia no lo sube. El
propietario considera que seguir por ahí es sobrepensar.

**Medido el mismo día: hay dos tipos de pico** (descriptivo, residuo contra el calendario y el
nivel del año, 2022-03 a 2026-09; `scratchpad/picos_por_mes.py`, que pasará al cuaderno 08):
1. **Días puntuales**: más de 1,5 desviaciones sobre el nivel local.
   - **Enero 14,5 y diciembre 12,1 por cada 100 días**; el resto de meses, 1-6,5.
   - Ejemplos: 25 de diciembre de 2022; 1 y 8 de diciembre de 2024 (la noche de velitas); 26-27 de
     diciembre de 2025; 2-5 de enero de 2025; 3-4 de enero de 2026.
   - **El nivel medio de esos meses es bajo** (−2,6 % y −2,9 %). Son noches, no temporadas.
2. **Semanas altas sostenidas**: más de +8,4 % sobre el nivel del año.
   - **Mayo 45 %** de sus semanas, marzo-abril 23-25 %, **octubre-noviembre 0 %**.
   - Mayo tiene el nivel medio más alto del año (+8,1 %).

**Lectura.** El propietario ve más picos a mitad de año, y es cierto **si «pico» es una semana alta
sostenida**. Si es un día puntual, dominan diciembre y enero. Parecen dos mecanismos distintos:
lo festivo y rápido en diciembre-enero, y algo lento y sostenido en marzo-mayo.

**Matiz.** El alto de mitad de año cae en **mayo, antes de las vacaciones escolares**; junio y
julio, ya en vacaciones, bajan al 14 %. La variable preregistrada `mitad_de_anio` (semanas de
vacaciones) apunta a la ventana equivocada. **No se redefine**: se deja escrito y se añade como
exploratoria la ventana marzo-mayo, declarando que se miró después.

### Mismo día: el contexto oficial de los picos

Informe completo en `calendarios/docs/CONTEXTO_PICOS.md`.

**1. Calendario de fiestas municipales:** `calendarios/fiestas_caldas_2020_2026.csv`.
- **Primera versión incompleta**: 75 filas de 22 municipios, de las que 48 citan la fuente como
  texto y no como URL. Hay otro agente completándolo.
- Lo que ya se ve: **en enero solo está el Carnaval de Riosucio** (años impares).
- **El grueso de las fiestas cae entre finales de junio y comienzos de julio**, y en
  octubre-noviembre.
- Es decir, **no coinciden con los meses de más picos** (enero puntual, mayo sostenido). Hay que
  medirlo, no suponerlo.

**2. Pólvora (DTSC, Gobernación, Alcaldía).**
- En Caldas, de 24 a 47 quemados por temporada; en Manizales, de 8 a 16.
- **Son uno o dos triages por día pico, frente a ~177 de media.** La pólvora es parte de la
  noche festiva, pero no la explica sola.
- En la serie de MinDefensa, las **lesiones personales se multiplican por 2 a 5 el 1-ene y el
  25-dic**. Diciembre es el mes más alto (71,6 al mes) y junio el más bajo (48,0).

**3. Hechos de la red de salud que afectan al conteo.** Son causas de **oferta**, no de demanda.
- **28-feb-2024: el SES deja de atender en urgencias a Salud Total y Sanitas.** En los datos:
  172 y 194 triages en febrero y marzo de 2024, 120 en abril. Es un corte real, pero de solo
  4-6 triages por día.
- **Marzo de 2025: el SES al 200 %** («todos los pacientes del departamento llegan al SES»).
- **Julio de 2025: alerta hospitalaria en Manizales**, con urgencias al 200 % en días punta; en
  abril de 2026 seguía vigente por Nueva EPS.
- **La saturación puede recortar el conteo en los días de más demanda.** Si el servicio está
  lleno, se desvía o no se registra. **El conteo mide lo que el hospital recibe, no lo que la
  ciudad necesita.** Hay que tenerlo presente al interpretar cualquier pico.

**4. Remisiones.** La DTSC publica **119 informes mensuales del CRUE** («Referencia y
contrarreferencia Caldas», 2015-01 a 2026-08), pero cada descarga pide un reCAPTCHA. **Solo los
puede bajar el propietario a mano.** Además hay un derecho de petición propuesto en
`CONTEXTO_PICOS.md` §4.3.

**5. Vacaciones escolares de mitad de año**, por resolución de la Secretaría de Educación de
Manizales, 2021-2026. Ejemplo: 2025, del 16-jun al 6-jul.

**6. Calendario de fiestas completado**: `calendarios/fiestas_caldas_2020_2026.csv`.
- **177 ediciones de 26 municipios**, 167 con URL. Hay 119 fechas confirmadas y 58 estimadas;
  130 filas verificadas abriendo la página (V), 8 vistas solo en el buscador (B) y 39 inferidas
  (I).
- Valores de `estado` válidos: realizado, cancelado, virtual, programado y aplazado.
- **Las fiestas realizadas empiezan en octubre (39), junio (33) y agosto (20); en enero, 2.**
  Octubre y noviembre son justo los meses **sin** semanas altas de triage (0 %).
- No hay fiestas de San Pedro y San Pablo como fiesta principal. El puente de finales de junio lo
  ocupan otras fiestas (Colación, Ceiba, Samán y Horticultura).
- El terremoto del 10-ago-2026 canceló o aplazó varias.

### Mismo día: cuadernos 01 y 02 corregidos, y tres correcciones a `CLAUDE.md`

**Cuadernos.** El 01 tiene 38 celdas y el 02, 36; corren sin errores. Llevan 22 y 24 recuadros
«Corrección del 2026-09-29».
- **El markdown de los dos estaba roto**: sin saltos de línea y con las tablas en una sola línea.
  Se rehízo.

**Hallazgos nuevos:**
- **Caída del volumen de 2024 a 2026:** el total pierde 54,2 triages por día y Nueva EPS 53,4.
  **Pero de 2024 a 2025 la caída es sobre todo del resto** (−17,4; Sura baja de 69,6 a 53,9 tras
  su salto de abril de 2024). De 2025 a 2026 es de Nueva EPS (−43,6), mientras el resto sube 16,6.
- **La reclasificación del nivel y la cuota de Nueva EPS** van en sentido contrario de enero a
  octubre de 2025 (r = −0,80), así que la deriva de criterio es independiente. Desde noviembre
  de 2025 van juntas (r = +0,63). Queda como hipótesis; comprobarla exige un agregado nuevo día ×
  nivel × entidad.
- **Composición por edad de 2024 a 2026:** los 15-44 bajan de 122,1 a 88,1 por día y los 0-4 no
  suben (6,8 a 6,9). Los extremos ganan peso porque cae el centro, no porque vengan más niños.

**Cifras antiguas corregidas:**
- Emergencias: 1.591 casos, no 1.463.
- Obstétrico: 12,5 %.
- Triages por mes, octubre-diciembre de 2025: 6.434 → 5.165 → 4.581.
- Estancia, régimen 2: 324.046 registros.
- Clima del 02 (anterior al arreglo): temperatura media 16,6 °C; lluvia ~1.081 mm por año con
  máximo en marzo. **El «rezago de un mes» entre lluvia y pico pediátrico deja de sostenerse.**

**Corregido en `CLAUDE.md`, verificado aquí contra `triage_horario`, 2022-2026:**
1. **La segunda joroba del día es a las 14-15 h, no a las 18-19 h.** Pico a las 10 h (15,8
   triages por hora), valle a las 12-13 h (10,9), segundo pico a las 14-15 h (13,0); a las 18-19 h
   ya se baja a 8,6.
2. **Los «2 huecos» se nombran:** 19 y 20 de marzo de 2024, y el 21 con 40 triages.
3. **«Por qué cae no se sabe»** queda tachado y resuelto: es Nueva EPS.

**Hueco de reproducibilidad sin arreglar:** `python -m extraccion --series` **no** regenera
`triage_diario.parquet` ni `triage_horario.parquet`. Ningún script del repositorio los produce.
Sí se comprobó que el horario coincide casilla a casilla con `triage_nivel` sumado (0 diferencias
en 55.833 casillas).

---

## 2026-09-28 — Dos capas: el nivel lo mueve la red, los picos los mueven otras cosas

**Contexto que aporta el propietario**, con el respaldo de su superior y de las noticias:
- **Nueva EPS fue intervenida por corrupción y quedó al borde de la quiebra.** No puede pagar
  los tratamientos.
- **Sus afiliados dejaron de venir** porque saben que no los van a atender.
- Es lo que el cuaderno 07 vio en los datos del hospital: de 116 a 72 triages por día de Nueva EPS
  entre 2025 y 2026, con escalones en noviembre de 2025 y julio de 2026.

**Decisión de diseño.** El desenlace se separa en dos capas con causas distintas:
1. **El nivel**, lo que el hospital recibe «en una semana normal». Lo mueve la **red de salud**:
   la situación de la EPS dominante, los cierres y las intervenciones. Cambia en escalones y
   dura meses.
2. **Los picos**, lo que se sale del nivel reciente. Los mueven eventos sociales, cambios
   bruscos de clima, epidemias y catástrofes, cada uno con su reloj.

**Por qué importa.** Si los picos se miden contra la media del año, un desplome de nivel como el
de noviembre de 2025 fabrica «días bajos» y esconde «días altos» dentro de un año partido en dos.
**Los picos se definen desde ahora contra el nivel reciente**: los días previos, no la media del
año. Eso además coincide con la pregunta del proyecto, «¿va a incrementar?», que siempre es
respecto de lo que se venía viendo.

**Sobre el tránsito, según el propietario.** Los accidentados probablemente van a la Clínica La
Presentación o a Santa Sofía, y al SES solo llegan en momentos concretos, como la Feria. No lo
puede asegurar. El SIVIGILA no trae accidentes de tránsito como evento. La serie diaria de lesiones
de tránsito de MinDefensa en datos.gov.co (`FUENTES_EXTERNAS.md`) permite comparar la ciudad con el
SOAT del SES.

**Medido el mismo día** (`calendarios/seguridad/mindefensa.py` → `seguridad_mindefensa.csv.gz`,
solo sumas por día; cuaderno 07, sección 3.3):
- Correlación entre el **tránsito de la ciudad** (Policía, 3,1 casos por día) y el **SOAT del SES**
  (7,2 por día): **r = +0,01** por día y por semana. No se mueven juntos, como sostenía el
  propietario.
- En la Feria sí suben los dos: ciudad +63 % (±51) y SES +37 % (±6), frente a +26 % y +12 % de otros
  regresos.
- La lluvia fuerte no sube el tránsito ni en la ciudad (−8,5 % ±16) ni en el SES.

**Decisión derivada:** el tránsito de la ciudad **no** entra como predictor del triage del SES; la
Feria sí.

**Picos redefinidos contra el nivel local** (mediana de ±14 días, solo para describir): hay **30**,
frente a 22 contra la media del año. Los preceden la Feria (5,3 veces la tasa base) y los eventos
sociales (2,0 veces; 18 de 30). 18 caen en fin de semana, 9 en enero y 6 en diciembre. **Un nivel
que solo mira hacia atrás confunde la recuperación de Nueva EPS (mar-2026) con un pico.** Por
eso el pronóstico tendrá que llevar el estado de Nueva EPS como variable explícita.

---

## 2026-09-28 — Cambio de método: mecanismos con su propio reloj, no correlaciones globales

**Qué se decide.** El análisis de patrones deja de ser «correlacionar el residuo semanal con
todo». Pasa a buscar **mecanismos**. Cada familia de factores tiene:
- **su reloj**: los eventos sociales actúan en 0-5 días (trasnocho, trago, aglomeración,
  trauma, visitantes sin EPS a mano); lo infeccioso y lo climático, en 1-4 semanas
  (incubación, contagio);
- **su gatillo**: el cambio brusco, no el nivel;
- **su condición**: en día laboral la gente va a urgencias por la incapacidad, porque la cita de
  la EPS tarda una semana;
- **su subgrupo**: edad, hora, asegurador.

Y se ve en **picos puntuales**, no a lo largo del año.

**Por qué.** El propietario leyó el cuaderno 06 y vio en las gráficas lo contrario de lo que
decían sus lecturas. Tenía razón en lo esencial. Las lecturas concluían «no afecta» a partir de
un residuo al que **ya se le había quitado la estacionalidad**: eso borra precisamente los
efectos que se repiten cada año en las mismas fechas. Es un **sesgo de supervivencia**: se
concluyó sobre lo que sobrevivió al filtro. Además:
- una sola ventana semanal diluye los efectos de días;
- las variables de nivel no ven los cambios bruscos;
- el total entierra las firmas de subgrupo.

**Lo que ya estaba bien y se conserva:**
- Coincidir en el tiempo no identifica la causa. La Feria cae siempre al regreso de vacaciones,
  y el pico de mayo-junio coincide con lluvia, IRA y vacaciones escolares a la vez.
- Para eso sirven los años y fechas que **varían**, usados como experimentos naturales.

**Cómo se hace:**
1. Ventanas **preregistradas** en `patrones/datos/variables.csv` (filas del 2026-09-28), antes de
   mirar. Cada fila declara lo que ya se había visto.
2. Anatomía de los picos: composición y lo que pasó antes.
3. Efectos rápidos en días, con comparadores. Por ejemplo, la Feria contra otros regresos de
   vacaciones.
4. Efectos lentos por transiciones, separando día laboral de fin de semana.

**Dato nuevo que lo hace posible sin el motivo: la entidad administradora.**
`DIM_TRIAGE.GEENENTADM` → `DIM_ENTIDAD` cruza en el 100 % de 2020-2024 y el 99 % de 2025-2026.
Se extrae como `salidas/triage_entidad.parquet` (`python -m extraccion --entidad`; día × hora ×
entidad, 434.726 triages) y se agrupa con `extraccion/entidades.py`. Reparto:

| Grupo | % |
|---|---|
| Nueva EPS | **58,2** |
| EPS Sura | 22,2 |
| Otras EPS | 6,1 |
| **SOAT (accidente de tránsito)** | **4,0** |
| Régimen especial | 2,5 |
| Prepagada | 1,8 |
| **Particulares** | 1,3 |
| **ARL (accidente laboral)** | 1,0 |

La clasificación es un borrador que revisa el propietario (`salidas/entidades_clasificadas.csv`).
**El SOAT mide los accidentes de tránsito que llegan al SES**, que era la pregunta abierta del
propietario. La residencia del paciente **no** se usa, por decisión suya.

**Primer dato, aún sin analizar.** Nueva EPS pasa de 42.270 triages en 2025 a 19.532 en lo que va
de 2026 (~26 mil anualizados, −38 %). EPS Sura se mantiene (19.691 → 16.858, ~22 mil
anualizados).

### Mismo día: resultados del cuaderno 07 con el método nuevo

Archivo: `notebooks/07_mecanismos.ipynb`, 27 celdas, sin errores. Las pruebas son las
preregistradas en `variables.csv`.

1. **Red de salud (el efecto más grande).** Nueva EPS pasa de 115,8 a 72,2 triages por día entre
   2025 y 2026 (−38 %), mientras Sura sube; su cuota baja del 58 % al 42 %.
   - A mediados de **noviembre de 2025** se desploma de ~130 a ~55 por día. Empieza **antes** del
     cierre de Santa Sofía del 1-dic, así que apunta a algo entre el **SES y Nueva EPS**.
   - Se recupera en marzo de 2026 y vuelve a caer en **julio de 2026**.
   - Tras el cierre de Avidanti, Nueva EPS sube frente a Sura (+15,5 %).
   - **Estos escalones explican las semanas más bajas del cuaderno 06.**
2. **Feria contra 52 otros regresos de vacaciones**, media de los días 0-4:
   - **SOAT +36,9 ± 5,5 % contra +12,5 ± 8,5 %.** Sigue separado con t de 4 grados de libertad.
   - Particulares +61 contra +29 %, con intervalo ancho.
   - 15-44 +9 contra +4 %; total +7,3 contra +2,7 %, que se solapan.
   - Parte de la subida empieza el 1-2 de enero (Año Nuevo).
3. **Picos.** 22 días (más de +27 %), 13 de ellos en fin de semana y concentrados en enero y mayo.
   Su composición es casi la de un día normal. Los preceden la Feria (4,2 veces la tasa base) y
   los eventos sociales (1,8 veces). La mirada hacia atrás no sirve para lo lento: su ventana
   cubre al 65 % de los días.
4. **Transiciones de clima**, del cambio hacia adelante:
   - **Seco → lluvioso: 0-4 años +22,0 ± 17,8 % a los 7-13 días** (13 episodios), que se apaga a
     los 21-28.
   - Enfriamiento: + en mayores y en adultos en día laboral (+2 a +4 %). Calentamiento: −2 a −3 %.
     Los signos son coherentes, pero cada intervalo cruza el cero.
   - Son 36 comparaciones, así que el resultado de los niños hay que confirmarlo fuera de muestra.
5. **Lluvia fuerte:** −7,8 % de madrugada y ningún aumento del SOAT en el SES.
6. **Subidas de la IRA de la ciudad:** nada en el SES, ni en día laboral ni en fin de semana.

**Corrección del cuaderno 06.** Sus lecturas decían «no afecta». Ahora dicen qué no podía ver el
método (estacionalidad quitada, ventana semanal, nivel en vez de cambio, total en vez de
subgrupo) y remiten al 07.

**Lo que solo tiene el propietario:** las fechas de suspensión y reanudación de servicios entre
el SES y Nueva EPS. Con ellas, la variable de mayor efecto pasa a ser un predictor conocido **por
adelantado**.

---

## 2026-09-28 — Calendario de vigilancia cerrado: 14 eventos, marcadores y 2026 por Power BI

Detalle y evidencia en `calendarios/docs/VIGILANCIA.md`, sección final; estado por evento en
`calendarios/docs/INVENTARIO.md`.

**Decisiones de construcción** (las tomó el agente de integración; se asientan aquí):
1. **Archivo aparte para los eventos individuales**, `calendarios/vigilancia_sivigila_eventos.csv.gz`
   (`calendarios/vigilancia/eventos.py`). `sivigila.py` reescribe su archivo entero y dos
   escritores sobre el mismo se pisarían. Tiene la misma estructura larga. El censo de casos por
   año y evento está en `vigilancia_sivigila_eventos_censo.csv`.
2. **La semana principal es la de la columna `SEMANA`**, porque es la única que empalma con 2026
   (Power BI). **Contra ella:** no sigue la misma fecha todos los años. Por ejemplo, el 875 pasa
   a fecha de consulta en 2020 y el 549 en 2023. Por eso se conserva también
   `casos_ocurrencia_semana_consulta`, que es homogénea pero no existe para 2026. Según el
   evento, las dos correlacionan de ≥ 0,9 a 0,07-0,45.
3. **Las instantáneas de Power BI se versionan** (`calendarios/vigilancia/powerbi/AAAA-MM-DD/`).
   Son agregados sin persona y no se pueden rehacer: el tablero se sobrescribe cada semana. Hoy
   hay una sola, la del 28-09. **Falta una tarea que congele una cada semana.**

**Integrados** como serie semanal de Manizales (2015-2025, más 2026 por Power BI donde hay):
- 300 (agresiones por animales), 875 (violencias), 356 (intento de suicidio).
- 365 (intoxicaciones, suma de 360 a 414), 549 (morbilidad materna extrema), 831 (varicela).
- 155 (cáncer de mama y cuello), 850 (VIH), 813 (tuberculosis), 346 (COVID).
- 113 (desnutrición < 5 años), 620 (parotiditis).

Como **marcadores**: 452 (pólvora), 349 (brotes de ETA) y 348 (IRAG inusitado). En el límite
de volumen: 414, 735 y 750. Otros 53 eventos tienen volumen insuficiente, y 11 dejaron de
publicarse.

**Empalme de Power BI contra los microdatos:**
- Totales anuales de 2025 dentro del ±2 %.
- Excepción: el 300 de 2024, −8,3 %, sin explicar.
- El 995 del tablero va +3 a +8 % por encima, con r = 0,999: es un nivel, no un desfase.
- **Los tableros no usan una sola definición de semana**: 356 y 875 van por `SEMANA`; 300 y 831
  por la de notificación.

**Escalones** (antes de usar cualquiera, mirar su serie):
- 414 cae un 93 % entre 2016 y 2021 y arrastra al 365.
- 549 se triplica en 2020-2021.
- 831 cae de 1.316 a 110 entre 2015 y 2020.
- 348 absorbió COVID en 2022-2023.
- 113 salta ×2,9 en 2023.
- 155 no tiene 2022.

**Error encontrado y corregido.** `sivigila.fecha()` cortaba el texto a 10 caracteres y perdía
las fechas con día o mes de un dígito («5/1/2021 00:00:00»). En las fichas individuales perdía
8.718 de 29.557 filas del 831; `eventos.py` usa un lector propio. **Se midió que no afectaba al
995 ni al 998:**
- 995: 0 fechas nulas de 2015 a 2025.
- 998: 2016, 2020, 2021, 2023 y 2025 sin pérdidas; todo llega como fecha de Excel o como texto
  que se lee bien.

La función se arregló igual, cortando antes del espacio. Al rehacer `vigilancia_sivigila.csv.gz`
se obtienen 203.772 filas y **0 valores distintos**.

---

## 2026-09-28 — El hospital es el SES, el alcance se fija y empieza la búsqueda de patrones

**1. Identidad del hospital (resuelve la decisión #9).** El propietario confirma que es el
**SES Hospital Universitario de Caldas**, en Manizales. En el SIVIGILA 995 es la institución
**`170010010301` «SERVICIOS ESPECIALES DE SALUD»**, presente de 2019 a 2025. Lo medido:
- Sus consultas por todas las causas contra el triage semanal del proyecto dan **r = 0,758**
  en 313 semanas.
- **Reporta ~0 consultas por IRA**: 0 en 2022 y 2025, con 87 y 146 mil consultas. La
  correlación r = 0,703 entre la IRA de la ciudad y el triage 0-4 **no es mecánica**: el
  hospital no aporta a ese numerador.
- **Sí aporta al denominador** de la ciudad. Cuando se use «consultas de la ciudad» como
  variable externa, se **excluye el SES**.
- Dato sin interpretar: sus consultas del SIVIGILA suben de 2024 a 2025 (126 → 146 mil),
  mientras el triage baja (82 → 72 mil).

**2. Alcance, decidido por el propietario:**
- **Eventos sociales**: interesan los **grandes**, como la Feria de Manizales. Los partidos del
  Once Caldas quedan fuera por ahora.
- **Catástrofes**: de las bases abiertas colombianas (UNGRD en datos.gov.co).
- **Calidad del aire**: **descartada**. No hace falta.
- **Clima**: basta con `clima_unificado.csv.gz`.
- **Con esto hay datos suficientes para empezar a buscar patrones.** Se abre un cuaderno
  exploratorio de correlaciones y gráficas.

**3. Cómo se leen esos patrones.** Son **exploratorios**: sirven para generar hipótesis, no para
confirmarlas. Toda variable que se quiera contrastar después se preregistra en
`patrones/datos/variables.csv` antes de mirar su resultado confirmatorio.

### Mismo día: cuaderno 06, los primeros patrones

Archivo: `notebooks/06_patrones_exploratorios.ipynb`. Tiene 25 celdas y 7 figuras, cada una con
su lectura, y corre sin errores.

**Corrección de datos que vale para todo el proyecto.** Un día **sin filas** en el triage total
es una **caída del registro**, no cero pacientes. El 19 y el 20 de marzo de 2024 no tienen ni un
registro, y el 21 tiene 40. Rellenados con cero fabricaban una semana de −42 %. **Regla:** en el
total, un día sin filas es nulo, y un día con menos del 40 % de lo esperado fuera de COVID se
excluye como caída parcial. Rellenar con cero sigue siendo lo correcto para **subconjuntos**
(una banda de edad sí puede tener cero).

**Lo que se vio:**
- **Residuo semanal: 8,0 %, con autocorrelación de +0,62.** Lo que falta por explicar se mueve
  lento y en bloques.
- **Semanas extremas.** De las 10 más bajas, 7 caen entre noviembre de 2025 y febrero de 2026,
  y otra es la del terremoto. **Los calendarios actuales no tienen nada que decir de casi
  ninguna.**
- **Mapa de correlaciones:** 23 variables, rezagos de −1 a +4, 138 pruebas por panel.
  - Hay **15 celdas marcadas y el azar daría ~7**.
  - Solo es robusta la del propio SES en el SIVIGILA (+0,32 a +0,46), que es el control.
  - Ciudad sin el SES: +0,08 a +0,18.
  - Clima: ninguna de nivel pasa de ±0,15.
  - Feria y eventos: desaparecen al quitar la estacionalidad.
- **Consultas de la ciudad contra el hospital:** r = 0,17 en nivel y 0,00 con rezago. El total
  del SIVIGILA mezcla consulta externa (programada, que se hunde en festivos) con urgencias:
  **no mide demanda urgente**.
- **Feria:** +6,3 % de media, pero de −7,7 % a +27,3 % según el año. No se separa del regreso
  de vacaciones de enero.
- **Clima en quintiles:** la diferencia entre extremos queda dentro de ±3,6 puntos, sin
  pendiente.
- **Deslizamientos:** nada.
- **Terremoto:** −50 % el día del sismo, −26 % la primera semana, −7 % los días 8 a 21.

**Hipótesis que salen de aquí.** Sección 8 del cuaderno; ninguna probada.
- **H1:** la red de salud mueve el triage total más que cualquier otra familia.
- **H2:** la persistencia es la base contra la que se mide todo.
- **H3:** una catástrofe grande baja el triage registrado.
- **H4:** la lluvia de la semana lo baja un poco.
- **H5:** varicela y desnutrición comparten algo con el triage, quizá el calendario escolar.

**Siguiente paso propuesto:** el calendario del sistema de salud (H1).

---

## 2026-09-28 — Corrección del propietario: el ejemplo de la gripa no es el objetivo, y ahora toca recolectar

**Qué se corrige.** Las entradas anteriores del mismo día se estrecharon hacia lo respiratorio y
lo pediátrico: IRA 0-4, su correlación con el triage 0-4 y el pico de marzo a junio. **El
propietario aclara que la gripa era una ilustración del tipo de razonamiento, no la hipótesis
a perseguir.** El desenlace sigue siendo uno solo: **cuándo sube o no la tendencia del triage
total**. Y la etapa actual no es de conclusiones.

**Decisión.** Esta etapa es de **recolección e inventario**:
- Reunir el mayor número de variables externas candidatas, de fuentes oficiales y
  comprobables: clima, salud pública, sistema de salud, sociales, catástrofes, calendario.
- De cada una, documentar qué es, de dónde sale, qué cobertura tiene, con qué granularidad y
  rezago, y qué calidad.
- Las hipótesis y las correlaciones contra el triage total vienen **después**, con el
  inventario completo y preregistrando las variables en `patrones/datos/variables.csv`.

**Qué pasa con lo ya hecho.** Los hallazgos respiratorios y pediátricos de hoy (r = 0,703, el
pico de marzo a junio, etc.) **no se retiran, pero tampoco guían el trabajo**. Quedan como
auditoría de calidad de la fuente: demuestran que la serie SIVIGILA es coherente con el
hospital. No son un resultado del proyecto.

**Entregable central nuevo: `calendarios/docs/INVENTARIO.md`.** Es el catálogo de variables
candidatas, una fila por variable, con fuente, estado y limitaciones.

### Mismo día: inventario de fuentes fuera de vigilancia

Informe completo en `calendarios/docs/FUENTES_EXTERNAS.md`: 6 familias, cada fuente marcada como
verificada [V] o inferida [I].

**Lo más aprovechable.** Tienen historia desde 2020 o antes y se pueden automatizar:
- **Delitos de MinDefensa y la Policía** en datos.gov.co: lesiones, violencia intrafamiliar,
  homicidio, lesiones y muertes en tránsito. Por **día** y municipio, desde 2003, con 2-6
  semanas de rezago.
- **NOAA ONI**, el índice ENSO, 1950 →.
- **Pronóstico archivado de Open-Meteo**: temperatura desde 2021-03, lluvia desde 2024-01.
- **Partidos del Once Caldas** de local, con asistencia (API de ESPN, no documentada).
- **DANE**: población anual y desempleo por trimestre móvil.
- **UNGRD**: 80 emergencias en Manizales entre 2019 y 2025.
- **Sismos del USGS.**
- **Aerocivil** y la **terminal de buses**.
- **Aire del IDEAM**, hasta 2024-12.

**Escalones en fuentes externas.** Lesiones en tránsito sube de 279 a 1.013 entre 2019 y 2022;
lesiones personales cae un 62 % entre 2018 y 2025. Parecen cambios de registro, no de
realidad. Es la misma disciplina que con el triage: mirar la serie antes de usarla.

**Lo que no existe como serie y hay que pedirlo o construirlo:**
- Alertas hospitalarias.
- Cierres de servicios por fecha.
- Histórico de afiliados por EPS.
- Medidas de la Supersalud ya levantadas.

Lista de acciones del propietario en `HANDOFF.md`.

**Urgente por construcción.** La foto mensual de afiliados por EPS (BDUA) no guarda historia:
cada mes que no se descarga se pierde.

**Segundo incidente de privacidad del día.** Una consulta de prueba al REPS (`c36g-9fc2`)
imprimió en la terminal del agente una fila con nombre, cédula y correo de un profesional
independiente. No se guardó en ningún archivo. **Regla que sale de aquí:** en datos.gov.co,
la primera consulta a un dataset nuevo pide **solo el esquema** (`$select` con conteo, o los
metadatos), nunca `$limit=1` sobre todas las columnas.

---

## 2026-09-28 — Se aparta el NLP y se rehacen los calendarios externos con fuentes reales

**Decisión del propietario.** Las notas de triage quedan en pausa. El trabajo pasa a sustituir
los calendarios hechos a mano por **series obtenidas por API, descarga o raspado de fuentes
públicas**, con historia real, empezando por uno solo a la vez.

**Por qué.** La validación del mismo día (entrada siguiente) mostró que los calendarios
actuales no aportan señal fuera de muestra. El 67 % de la vigilancia son ventanas con fechas
fijas y los eventos son recurrentes anuales. El cuello de botella es la calidad de las
variables externas, no el modelo ni el texto.

**Orden** (fijado aquí; el propietario puede cambiarlo):
1. **Vigilancia en salud → microdatos SIVIGILA** (84 eventos, 2007-2025). Es la fuente con más
   valor y la única ya confirmada.
2. **Clima.** Auditoría de lo que el propietario sospecha mal calculado, más pronóstico
   archivado (Open-Meteo).
3. **Desastres y emergencias**, incluida la pandemia como periodo.
4. **Eventos sociales.**

**Arquitectura de vigilancia**:
- Código en `calendarios/vigilancia/`.
- Descarga cruda en `calendarios/vigilancia/crudo/`, **ignorada por git**. Los archivos del
  SIVIGILA traen nombre, teléfono y correo de quien notifica.
- Salida agregada a municipio × semana epidemiológica, **sin una sola columna de persona**,
  versionada como `calendarios/vigilancia_sivigila.csv.gz`.
- El porqué de la construcción va en `calendarios/docs/VIGILANCIA.md`.
- El CSV manual `vigilancia_salud_manizales_caldas.csv` **no se borra**: queda como registro de
  lo que había y de dónde salió cada fecha.

**Límite conocido desde el inicio.** Los microdatos se publican con ~8 meses de rezago (2025
salió el 25-ago-2026; 2026 no existe). Sirven para entrenar y medir. Para operar en tiempo
real hará falta otra vía (boletines semanales), que se investiga en paralelo.

### Mismo día, más tarde: la vía para 2026 y el orden de eventos

Fuente: `calendarios/docs/FUENTES_VIGILANCIA.md`.

**1. La vía para 2026 es Power BI, no los boletines.** El tablero público del INS «006
Vigilancia Rutinaria» da conteos por evento × semana × municipio, se actualiza cada semana y
va ~7 días por detrás.
- Se consulta por la API pública de Power BI, sin token. Su clave se lee cada vez de la lista
  SharePoint `MenuReporteNivel2`.
- Los tableros por evento traen historia y **cuadran con los microdatos**: 356 de 2016 da 368
  contra 368; 831 de 2024, 214 contra 211-214.
- Se descartaron:
  - El BES: solo baja a departamento.
  - La DTSC: reCAPTCHA en cada descarga.
  - datos.gov.co: congelado en 2022.
  - La Secretaría de Salud de Manizales: PDF mensual, casi todo gráficos.
- **Límites:** la API no está documentada y las 2 o 3 últimas semanas se revisan por
  notificación tardía. Cada descarga se guarda congelada con su fecha, para poder evaluar con
  lo que se habría sabido en su momento.

**2. Regla de privacidad nueva, y no negociable.** Los modelos públicos de los tableros por
evento **exponen en su esquema columnas identificables**: nombre, documento, dirección,
teléfono, coordenadas. Por eso:
- El proyecto solo pide **medidas agregadas** (`Casos`, `SUM(conteo)`) o la tabla ya agregada
  del 006.
- **Nunca pide una columna cruda de esos modelos.**
- Si se avisa o no al INS lo decide el propietario.

**3. Orden de integración después del 995:**
1. 998 (EDA), con el denominador del 995.
2. 356 (intento de suicidio).
3. 875 (violencia de género e intrafamiliar).
4. 300 (agresiones por animales).
5. 365 (intoxicaciones, suma de los códigos 360-414).
6. 831 (varicela) + 620 (parotiditis).
7. 549 (morbilidad materna extrema), solo si el triage cubre obstetricia; cubre el 12,6 %.

Los vectores quedan fuera: tienen 0-7 casos al año en Manizales. El 345 también: Manizales no
es sitio centinela. Pólvora (452), brotes de ETA (349) e IRAG inusitado (348) entran como
**marcadores de evento**, no como series.

**4. Aviso de fuga.** 356, 875, 300 y 365 son **parte del propio desenlace**: esas personas
consultan en urgencias, quizá en este mismo hospital. Solo pueden entrar al pronóstico con
rezago, o como desenlaces específicos. En la misma semana serían fuga de información.

**5. Calendario epidemiológico.** Semana de domingo a sábado; la SE1 es la que contiene el 4 de
enero. Tienen 53 semanas 2008, 2014, 2020 y 2025. **2021 no**, aunque algún calendario
interno del INS le asigne una.

### Mismo día: 995 y 998 integrados, y cuatro decisiones de construcción

Evidencia en `calendarios/docs/VIGILANCIA.md`. La corrida se repitió aquí desde el caché
(`--sin-descargar`, 16 s): 203.772 filas, **ninguna columna de persona** y el crudo ignorado
por git.

1. **La serie usable del 995 empieza en 2015.**
   - 2011 es otra ficha: trae casos, sin denominador.
   - 2012-2014 tienen semanas con 2 instituciones, duplicados y más IRA que consultas.
2. **La proporción IRA / todas las causas solo se compara dentro de cada año.** El
   denominador sube +60 % en 2021 y +35 % en 2024 por instituciones nuevas. La caída del
   16 % al 3,6 % es del denominador, no de la IRA. Para comparar entre años se usa el
   **conteo** de IRA, o una proporción sobre un **panel fijo de instituciones** (pendiente).
3. **El municipio se toma del código de la institución** (`cod_pre[:5]`), porque `cod_mun`
   cambia de formato entre años. Se midió: en Manizales es idéntico desde 2016, y en
   2012-2015 la correlación es ≥ 0,995.
4. **Semana epidemiológica asignada por regla, no por la columna.** Las 39 filas de «SE53 de
   2021» son la SE53 de 2020 y se descartan; ninguna es de Manizales.

**Hallazgos que cambian cosas.**
- **Correlación con el hospital: r = 0,703** entre la IRA 0-4 de Manizales y el triage 0-4,
  en 312 semanas de 2020-2025; 0,808 normalizando por año. El 0,685 de antes perdía los 124
  días con cero triages pediátricos, porque el `GROUP BY` no emite ceros. **Esa trampa vale
  para toda serie de conteo del proyecto.**
- **Límite:** en diferencias semanales la correlación baja a 0,18. Explica el nivel, no el
  cambio de una semana a la siguiente.
- **El segundo pico de lluvias (octubre-noviembre) no tiene pico de IRA en 0-4 años**, como ya
  pasaba en el hospital. Octubre es el mes más bajo.
- **Avidanti −39 % tras cerrar a Nueva EPS.** Pesa el 0,3 % del volumen de la ciudad y no se
  ve desplazamiento agregado.
- **La EDA de Manizales cae a la mitad desde 2020, sin explicación.** No se sabe si es real o
  de notificación.

**Sin verificar.**
- **Si el hospital del proyecto es una de las instituciones del 995.** Si lo es, parte de la
  correlación es mecánica: son las mismas consultas. El propietario lo sabe.
- El significado de los códigos de ajuste 4 y 6. Se asumió que 6 es descartado.

**Incidente de privacidad.** En la exploración inicial, el agente de integración imprimió en su
salida de sesión los 5 valores más frecuentes de `num_con`, que tienen forma de cédula. No
quedaron en ningún archivo del repositorio. A partir de ahí `num_con` va en la lista de
columnas descartadas al leer.

---

## 2026-09-28 — Validación: ¿se puede predecir el conteo sin el motivo de triage?

**Origen.** El superior del propietario sostiene que el motivo de la nota no hace falta para el
objetivo: las notas las escriben enfermeras, están sujetas a interpretación, y bastaría con
conteo + fecha enfrentados a factores externos (clima, salud, eventos, desastres). Se pidió
validarlo con los datos. **No es una decisión todavía: es la medición que la va a sostener.**
Script: `notebooks/05_validacion_sin_motivo.py` (solo parquet agregados y calendarios).
Ventana 2022-03-01 a 2026-09-20; control = día de semana, festivos, puentes, quincena,
vacaciones, Semana Santa, Navidad + nivel por año + escalón 2025-11. Las dos variables de
transición se definieron en el docstring **antes** de correr (no se preregistraron en
`variables.csv`: lo encontrado aquí es exploratorio).

**1. Los calendarios, tal como están, son en su mayoría calendario disfrazado.**
- `vigilancia_salud`: 216 de 321 filas (67 %) son «ventana_estacional», **las mismas fechas
  cada año**. El mes del año explica el **92,6 %** de la bandera IRA y el **100 %** de VSR e
  influenza. Usarlas es proyección, no predicción — exactamente lo que `CLAUDE.md` descarta.
  Solo 28 filas traen número de casos; de Manizales, 6.
- `eventos`: 99 filas, casi todas recurrentes anuales. **Efecto medido nulo**: días de evento
  +0,0 % [−0,4; +0,4]; días de Feria +0,2 % [−0,8; +1,1] por día.
- `desastres`: 17 filas, 4 pendientes de verificar.

**2. El presupuesto de ruido: sí hay algo que explicar, sobre todo a escala semanal.**

| | Diario | Semanal |
|---|---|---|
| sd del residuo tras control + estacionalidad | 11,8 % | 6,4 % |
| piso de Poisson (irreducible) | 7,3 % | 2,7 % |
| varianza residual potencialmente explicable | 62 % | 82 % |
| autocorrelación del residuo | +0,26 | +0,52 |

De la varianza diaria total: calendario 55,1 %, nivel por año +16,5 %, estacionalidad anual
**+2,5 %**, queda 25,9 % (≈10 puntos son Poisson).

**3. Las externas no explican el conteo TOTAL más allá del azar; sí explican el pediátrico.**
R² incremental de 19 variables externas sobre el residuo semanal: **total 0,112** (azar en
bloques de 8 semanas, p95 = 0,167: indistinguible) · adultos 0,112 (p95 0,175) · **0-14 años
0,260** (p95 0,197: por encima del azar).

Efectos por desviación típica (IC95 HAC, control + estacionalidad):

| | total | 0-14 años |
|---|---|---|
| temperatura, rezago 1-2 sem | −0,2 / −1,2 % | **−9,9 / −10,8 %** (frío → más niños) |
| humedad, rezago 1-2 sem | −0,5 / +0,3 % | **+6,2 / +7,4 %** |
| lluvia, misma semana | **−1,4 %** (llueve → menos consultas) | +1,1 % |
| enfriamiento brusco, misma semana | **−3,6 %** | −1,7 % |
| ruptura seca→lluvia | nulo, IC ±8 % | nulo, IC ±17 % |
| La Niña / El Niño | +1,8 % / −0,8 % | **+21,8 % / −27,2 %** (confundido con año) |
| terremoto 2026-08-10 (2 sem.) | **−21,5 %** | −29,5 % |

**El mecanismo respiratorio existe y se ve sin motivo, en la edad, con 6,7 años de historia.**
En el total se diluye: la correlación del residuo pediátrico con el de adultos es +0,08, y el
residuo pediátrico de la semana anterior no anticipa a los adultos (t = −1,75).

**4. Pronóstico semanal, origen rodante, 136 semanas (2024-01 a 2026-08), h = 1 semana.**

| Modelo | MAPE | acierto «¿sube?» | Brier |
|---|---|---|---|
| ingenuo (= semana actual) | 5,24 % | — | — |
| nivel + calendario | 6,07 % | 64,0 % | 0,240 |
| + estacionalidad (proyección) | **5,23 %** | 58,1 % | 0,237 |
| + externas conocidas en t | 5,64 % | 63,2 % | 0,252 |
| oráculo: + clima observado t+1 | 5,61 % | 55,9 % | 0,255 |

(Base: 47,1 % de semanas suben; Brier de una moneda 0,250.) **Ninguna variable externa mejora
el pronóstico del total, ni siquiera con el clima de la semana siguiente conocido.** Para la
serie pediátrica tampoco: el clima empeora de 15,0 % a 15,9 % de MAPE — la asociación existe,
pero no alcanza para predecir una semana adelante.

**5. Potencia.** Solo **7 semanas de ruptura seca→lluvia** en 237 (3 %). Efecto mínimo
detectable ~5,5 % sin corregir autocorrelación y ~7 % corrigiéndola, contra 2-10 % publicado.
La hipótesis de transición sobre el total **no se puede contrastar con este diseño, con o sin
motivo**.

**6. Lo que mueve de verdad el conteo es institucional.** Las semanas más extremas: 2025-11-02
y 11-09 (+21,7 %, +18,9 %) seguidas de 11-30 y 12-07 (−17,1 %, −13,2 %); la del terremoto
(−26,4 %); un bloque alto en marzo-abril de 2026. Ninguna coincide con una anomalía de clima.
Y el volumen anual (105,7 → 226,4 → 172,6) lo movieron COVID y la reclasificación.

**Lectura.**
1. **El superior tiene razón en que el motivo no hace falta para predecir** — `CLAUDE.md` ya lo
   decía: el motivo nunca podía ser entrada. Y para **probar el mecanismo**, la edad lo sustituye
   con más historia y sin interpretación de nadie.
2. **No tiene razón, con estos datos, en que las externas mejoren la predicción del total.** Los
   calendarios actuales no aportan señal fuera de muestra. No es que la idea sea falsa: es que
   las variables disponibles son calendario disfrazado, o demasiado raras para tener potencia.
3. El motivo solo añadiría lo que la edad no ve: la vía respiratoria **adulta** (la de la
   incapacidad). Es explicación, no pronóstico.

**Límites.** El periodo de prueba (2024-2026) es justo el de la deriva administrativa; ridge
con λ fijo sin ajustar; ENSO confundido con el año; solo horizonte semanal.

**Complemento del mismo día: lo que hay fuera** (investigación web; [V] = página leída por el
agente, no re-verificado en esta sesión).
- **La literatura coincide con el resultado.** Wargon et al. 2009, una revisión de 9 estudios
  [V]: *«adding meteorological data failed to improve model performance»*. Marcilio et al.
  2013 en São Paulo [V]: con temperatura el MAPE fue de 11,5 %, sin ella de 10,8 %. En
  Colombia el efecto grande aparece en lo **respiratorio o pediátrico** (Rodríguez-Villamizar
  2018; Medellín 2024; Bogotá 2015), no en el total.
- **La dilución es mayor de lo que suponía `CLAUDE.md`.** En los microdatos SIVIGILA 995 de
  2025, la IRA es ~5 % de las consultas de Manizales, no el 10 % supuesto.
- **Existe una serie de vigilancia real.** Son los microdatos SIVIGILA del evento 995 (IRA
  colectiva), en `portalsivigila.ins.gov.co/Microdatos`, **2011-2025**. Traen una fila por
  institución × semana con código de municipio, consultas por IRA en 7 grupos de edad y
  `tot_exturg`, que es el total de consultas de todas las causas. Tienen dos límites:
  - Publican con ~8 meses de rezago, así que sirven para entrenar, no para operar.
  - Traen nombre, teléfono y correo de quien notifica: esas columnas se descartan al cargar.
- **Hay eventos institucionales que coinciden con las semanas extremas** [V]:
  - Avidanti suspende todos los servicios a Nueva EPS el 21-ago-2025. Es ~30 % de la capacidad
    de la ciudad y ~1.600 triages al mes.
  - Santa Sofía cierra a Nueva EPS el 1-dic-2025.
  - Diagnostimed suspende en diciembre de 2025.
  - La Resolución 373 de 2026 obliga a reportar los tiempos de triage desde el 1-ene-2026.

  Esto es compatible con que el hospital recibiera primero la demanda desplazada (el pico de
  noviembre) y después cambiara su registro o se viera afectado por el cierre. **No está
  comprobado.** Se comprueba con `tot_exturg` por institución.

---

## 2026-09-24 — Se reabre la competencia de modelos EN CPU: Llama 3 y otros ligeros

**Decisión del propietario**: antes de dar por cerrado que el problema necesita GPU, medir
si **Llama 3 o alguna de sus variantes** —u otro modelo ligero— resuelve lo que qwen3:8b no
pudo, con menos recursos. No contradice el cierre de la fase de CPU: aquel era **no iterar
más el prompt**; esto es cambiar de **modelo** con el prompt fijo.

**Cómo se mide, y por qué así:**
- **La misma sonda de 32 notas** (17 fallos verificados + 15 guardas) y **el mismo prompt
  v1.7**, para que la única variable sea el modelo (regla 7).
- **Dos modos**: `solo` (sin filtros ni segunda pasada, como `NLP.duelo`: mide al modelo)
  y `cadena` (lo que iría a producción). Primero `solo` para todos; `cadena` para los
  mejores. Con filtros dos modelos salen parecidos porque se mide a los filtros.
- **qwen3:8b se vuelve a correr en la misma tanda**, no se compara solo contra sondas
  viejas: el 8B no es determinista cuando duda (entrada del duelo 8B-14B).
- **Las notas duras se repiten 3 veces** para medir la inestabilidad, que es el fallo que
  hoy no tiene arreglo (descartes falsos que salen o no según la corrida).
- **Se juzga leyendo, no contando**: la sonda cuenta mal (entrada «Conclusión: el 14B…»).
- **Una sola corrida contra Ollama a la vez**; los agentes solo investigan y leen.

Script de la comparación, fuera del repo (no cambia código del proyecto): el `comparar.py`
del scratchpad de la sesión, que usa `NLP.banco`, `NLP.cadena` y `NLP.fidelidad` sin tocarlos.

**Corrección del propietario, el mismo día: igualdad de condiciones.** Un modelo solo se
compara con qwen3:8b si es **de su mismo peso** (~8B, Q4_K_M, ~5 GB). `llama3.2:3b` se midió
primero por ser rápido, pero es un **piso**, no un rival: leído, 6/32 bien contra ~14/32 de
qwen3:8b sin filtros. No dice nada de la familia Llama. La comparación de familia es
`llama3.1:8b` contra `qwen3:8b`, más los **reentrenados de Llama 3.1 8B** por terceros
(Tulu 3.1, Hermes 3, SuperNova-Lite), que tienen el mismo tamaño. Llama 3.3 (solo 70B) y
Llama 4 (109B y 400B) no caben en 16 GB.

**Sesgo que queda a favor de qwen, y cómo se compensa**: el prompt v1.7 se afinó durante días
sobre qwen3:8b (ya le costó notas al 14B, que se abstenía de más). El mejor rival recibe
**una vuelta de ajuste del prompt**, como la tuvo el 14B (`v1_7_14b.py`), antes de decidir.

**Diseño final, fijado por el propietario y PREREGISTRADO antes de ver ningún resultado**
(escrito cuando solo se habían leído 2 salidas de llama3.1:8b):

- **Muestra de 63 notas** = la sonda (32) + una muestra **nueva** de los bancos que el prompt
  no vio al afinarse: 16 de `fallos.csv` (2 por cada bandera fuerte, empezando por la más
  rara) y 15 de `aciertos.csv` (2 por estrato; de `descarte_correcto` solo quedaba 1),
  semilla 11, sin OID de la sonda. La nueva existe porque la sonda favorece a qwen: v1.7 se
  afinó mirándola.
- **Contendientes, mismo prompt v1.7, modo solo, Q4, temperatura 0**: qwen3:8b ·
  llama3.1:8b · tulu3:8b (sin su mensaje de sistema) · Llama-3.1-Storm-8B · gemma3:12b ·
  gemma4:12b-it-qat. Los dos gemma son **un escalón más pesados** (~7 GB) y se reportan
  aparte de los 8B.
- **Veredicto por nota, leído** (bien / parcial / mal) contra una lista de lo que la
  respuesta correcta **debe** y **no debe** contener, escrita antes de juzgar a los modelos.
- **Puntaje — un daño pesa el doble que un arreglo** (la regla del propietario: no vale
  arreglar una nota y dañar otra que estaba bien):
  - nota de `fallo`: bien **+1**, parcial **+0,5**, mal **0**
  - nota de `acierto`: bien **0**, parcial **−1**, mal **−2**
  - el **descarte falso** se cuenta además aparte, en cualquier banco: es el peor error.
- **Dos lecturas**: la **estricta** (la línea que guardaría producción, `modelo.limpiar`),
  que es la que decide; y la de **comprensión** (la respuesta final del texto completo),
  que dice si un arreglo de formato cambiaría el orden. Motivo: llama3.1:8b razona en voz
  alta antes de responder y la primera línea sale inservible aunque la respuesta sea buena.
- **Sin repeticiones**: llama3.1:8b dio salidas idénticas en dos corridas; a temperatura 0
  es determinista, y el tiempo rinde más en notas y modelos.
- **La velocidad se mide aparte**, con la máquina quieta: esta tanda coincidió con descargas.

**Primer resultado medido (sonda, 32 notas, banco corregido: 18 fallos · 14 aciertos)**. El
revisor corrigió el banco de 13 de las 63 notas antes de juzgar: 9 «aciertos» de v1.6 estaban
mal por las reglas de v1.7 (duda, embarazo o negación perdidos) y 4 «fallos» eran falsos
positivos de un detector.

| Modo solo, prompt v1.7 | Fallos | Aciertos | Puntaje | Descartes falsos |
|---|---|---|---|---|
| qwen3:8b | +5,5 | −9 | **−3,5** | 2 |
| llama3.1:8b, lectura estricta | +5,0 | −16 | **−11** | 2 |
| llama3.1:8b, lectura de comprensión | +6,0 | −15 | **−9** | 5 |
| llama3.2:3b (piso) | | | −16 | 3 |

Lectura: **en arreglar fallos empatan; Llama daña el doble de aciertos.** Inventa el sufijo de
la regla 6 («en gestante de N semanas») en 6 notas, una de un varón; descarta «amarillo» y
«control prenatal»; en el 44 % de las notas su primera línea no es la respuesta (razona en voz
alta). Parte del daño lo induce la redacción de la regla 6, afinada para qwen, pero la lectura
de comprensión, que ignora el formato, lo deja igual de abajo.

**Estabilidad, medida por primera vez** (16 notas duras × 3 corridas): qwen3:8b cambia la
salida en 5/16 y el **veredicto en 1/16** (la hernia discal: descarte falso en 2 de 3);
llama3.1:8b cambia en 2/16 y 1/16. La inestabilidad de qwen es real pero estrecha: una nota,
no una familia.

**Resultado sobre las 63 notas: qwen3:8b le gana a llama3.1:8b** (medido y leído el mismo día).

| Modo solo, v1.7 | Sonda | Nueva | **Total 63** | Descartes falsos |
|---|---|---|---|---|
| qwen3:8b | −3,5 | **+10,5** | **+7** | 2 (0 en la nueva) |
| llama3.1:8b, comprensión | −9 | +7 | **−2** | 5 (0 en la nueva) |
| llama3.1:8b, estricta | −11 | −8,5 | **−19,5** | 2 |

Qué decide: **aun en su mejor lectura (la que ignora el formato), Llama queda 9 puntos
abajo**, así que la salida estructurada no lo rescataría y no se le corre esa segunda ronda.
En la muestra nueva qwen no daña ninguno de sus 11 aciertos; Llama inventa embarazos (3),
cambia síntomas («prurito» → «dolor mamario», «ardor al orinar» → «arritmia») y deja una
nota sin respuesta. **Llama gana solo en 3 trámites**, donde qwen copia el trámite en vez de
«sin motivo clinico» (parcial: no inventa). Los dos fallan igual en parte del cuerpo
inventada, «desde ayer» y negaciones: errores de la tarea, no de la familia.

**Muestra nueva contra sonda**: qwen pasa de −3,5 a +10,5. La sonda son sus peores notas a
propósito; la nueva se parece más al corpus. Las dos cifras se reportan siempre juntas.

**Velocidad**: la única medición limpia hasta ahora es qwen3:8b en la nueva, 16,4 s/nota de
mediana; llama3.1:8b es más lenta por construcción (razona en voz alta: ~100 tokens por
nota contra ~10).

**Tulu 3 8B (Llama 3.1 reentrenado por AllenAI, sin su mensaje de sistema)**: −8 solo (sonda
−13,5, nueva +5,5), 3 descartes falsos, **0 % de fallos de formato** y el más rápido de los
8B (15,5 s/nota de mediana, limpio). Resuelve cosas que qwen no: no descarta la hernia discal,
descarta los 3 trámites que qwen copia, no inventa lado ni «desde ayer». Su defecto dominante
es **inventar el sufijo de la regla 6 en 15 notas** (varón incluido): el reentrenamiento
arregla el formato de Llama y empeora la invención.

**Con los filtros de producción** (`posprocesar` de v1.7 aplicado a las salidas guardadas, sin
segunda pasada; deterministas, no llaman al modelo): **qwen3:8b +15,5 · tulu3:8b +2,5 ·
llama3.1:8b −9,5**. El orden no cambia. El filtro quita los 15 embarazos de Tulu, pero en 11
queda otro error debajo; 7 de los 10 puntos que gana Llama son del filtro de trámites
escribiendo «sin motivo clinico» sobre su relleno, no mérito del modelo.

**Defectos de los filtros de producción que salieron de aquí** (valen solos, pendientes):
1. `quitar_embarazo_inventado` **borra un embarazo real**: en una nota de «prueba positiva de
   embarazo» quita las semanas inventadas y con ellas el embarazo; la salida queda vacía.
2. El filtro de trámites deja restos: «derivada de la eps» → «la eps» (qwen, una nota de la
   muestra nueva).
3. `descarte_falso` → segunda pasada **se dispara en 2 trámites puros bien descartados** de la
   muestra: falsos positivos del disparador; si la segunda pasada inventa, un acierto se
   vuelve fallo. (Los OID de cada caso están en el material de la competencia, fuera del repo.)

**Los dos ~12B (un escalón más pesados: ~8 GB en RAM, cabe en esta máquina con ~2 GB de
margen, sin paginar).** Velocidad limpia, un solo modelo en memoria.

| Modo solo, v1.7 | Sonda | Nueva | **Total 63** | Con filtros | Desc. falsos | RAM | s/nota |
|---|---|---|---|---|---|---|---|
| **gemma4:12b-it-qat** | +7,5 | +17,5 | **+25** | **+26** | 5 | 8,49 GB | 23,8 |
| qwen3:8b | −3,5 | +10,5 | +7 | +15,5 | 2 | ~5,9 GB | 16,4 |
| gemma3:12b | −3,5 | +10 | +6,5 | +7,5 | **0** | 8,06 GB | 21,8 |

- **gemma4:12b resuelve casi todo lo que ningún 8B pudo**: oídos tapados e hipo completos;
  duda → certeza 4/4; negaciones 4/4; la agresión de la pareja; «antier»; no inventa lado,
  parte del cuerpo ni embarazo. En la muestra nueva no daña ningún acierto. **Su único error
  sistemático es el descarte falso (5, todos en la sonda)**: «congestionado», la hernia
  discal, la turbinoplastia, «amarillo», el control prenatal. Es el patrón del qwen3:14b con
  v1.7: el bloque de abstención, endurecido para el 8B, un modelo más capaz lo cumple de más.
  Si la segunda pasada los recuperara, el techo es +33.
- **gemma3:12b empata con qwen solo y pierde con filtros**, pero es **el único con cero
  descartes falsos**. Sus errores son omisiones y cambios de sentido, que ningún filtro ve;
  los de qwen son mecánicos (lado, parte, «antier», institución), que los filtros sí ven.
- **Ningún modelo resolvió «no me baja el azúcar»** (todos: «hipoglucemia»): es de glosario.

**Pendiente antes de tomarlo como decisión**: (1) verificación por un segundo juez **ciego**
de qwen3:8b contra gemma4:12b en las 43 notas donde difieren —el +25 lo juzgó un solo
revisor—; (2) la segunda pasada real de gemma4 sobre sus descartes; (3) la vuelta de ajuste
del prompt (abstención suavizada) que el diseño reserva al mejor rival.

**Verificación ciega: confirmada.** Un segundo agente, sin acceso a la clave ni a los archivos
de la competencia, juzgó las **43 notas donde qwen3:8b y gemma4:12b difieren**, con el orden
A/B barajado por fila. Destapada la clave: **gemma4 es mejor en 31, qwen en 3, empate en 9**;
veredictos gemma4 33 bien · 6 parcial · 4 mal, qwen 7 · 23 · 13. Descartes falsos: gemma4 3,
qwen 0 en esas 43 (los dos de qwen, «congestionado» y la hernia, **gemma4 también los hace
con la misma salida**, por eso no entraron). Dos jueces independientes, uno ciego, dan el
mismo orden. Lección de método: el juez resumió «A es mejor que B» como si A y B fueran
sistemas fijos, cuando el orden estaba barajado; **lo que vale del juez ciego son sus
veredictos fila a fila, no su resumen**.

**Preregistro de la vuelta de ajuste para gemma4** (escrito antes de correrla): se usa
`NLP/prompts/v1_7_14b.py` **tal como está** —escrito el 2026-09-24 para qwen3:14b, que tenía
el mismo problema—, sin ningún retoque mirando a gemma4. Solo cambia el bloque de abstención.
Mismas 63 notas, mismo juicio, mismo puntaje; se reporta **al lado** de v1.7, no en su lugar.
Criterio: si baja los descartes falsos **sin** dañar aciertos, es el prompt de gemma4.

**REVERTIDO el mismo día, antes de correrlo, por decisión del propietario** (entrada siguiente):
la vuelta con `v1_7_14b.py` se cancela y la reemplaza un prompt propio por modelo.

---

## 2026-09-24 — Cada modelo con su propio prompt: gana el primero que cruce la barrera

**Decisión del propietario.** Un prompt afinado para un modelo no es igualdad de condiciones.
Ya se conocen las fuerzas y debilidades de cada uno; ahora **cada modelo recibe su propio
prompt optimizado** y compiten por cruzar la barrera que qwen3:8b no cruzó. **El primero que
la cruce es el que se queda.**

**El riesgo que hay que cerrar, y cómo**: afinar prompts mirando las mismas 63 notas con que
se mide los hace **memorizar** esas notas («no me baja el azúcar = hiperglucemia» escrito en
el prompt) y el puntaje sube sin que el modelo mejore. Tres defensas:
1. **Conjunto de validación nuevo**, de las mismas familias difíciles, que ningún agente de
   prompt ve. Su lista de verificación se escribe antes de correr ningún modelo.
2. **Los prompts solo llevan reglas generales**, nunca frases, palabras raras o casos de
   notas concretas de la muestra. El revisor lo audita en cada ronda.
3. **Mismo presupuesto para todos**: máximo 3 rondas por modelo, todos parten de v1.7, mismos
   filtros (`posprocesar` de v1.7 sin cambios) y misma cadena con segunda pasada.

**PREREGISTRO — la barrera** (modo cadena, que es lo que iría a producción; juicio leído
contra la lista, banco real):
- **B1, lo que qwen no pudo**: de las 16 notas duras (`oids_duros.txt`), **≥ 12 bien**.
- **B2, no dañar**: en los aciertos del banco real, **0 mal**.
- **B3, no sacar pacientes de la cuenta**: **0 descartes falsos** sin marca; uno marcado
  `revisar` por la segunda pasada se tolera, porque lo ve una persona.
- **Confirmación**: quien cruce B1-B3 en las 63 se corre en la validación; ahí debe dar
  0 aciertos dañados, 0 descartes falsos sin marca y **puntaje por nota mayor que el de
  qwen3:8b con v1.7 y cadena** en esa misma validación.

**Quién se queda**: el primero que cruce la barrera y la confirmación, **contando por rondas**
(todos corren la ronda 1, luego la 2…). Si cruzan varios en la misma ronda: el de mejor
puntaje en validación; si empatan, el más ligero. Si nadie cruza en 3 rondas, **no hay
ganador por esta vía** y se le dice al propietario que el problema no se resuelve con
modelos ligeros en esta máquina.

**Participantes**: gemma4:12b-it-qat, qwen3:8b, gemma3:12b, tulu3:8b, llama3.1:8b (la familia
que el propietario pidió explorar). Storm 8B entra si en su corrida con v1.7 supera a Tulu.

**Storm 8B, medido: no entra.** −8 solo (igual que Tulu), +1,5 con filtros (Tulu +2,5) y **8
descartes falsos**, el peor número de la competencia; inventa el embarazo en 12 notas.

**Cuarto defecto de los filtros**: `quitar_parte_inventada` borró una parte del cuerpo **real**
de una respuesta fiel de Storm porque la nota la escribe con errata y el detector compara
letra por letra. Primer caso medido de un filtro que convierte un bien en mal.

**Aclaración del reglamento, a mitad de la ronda 1, para todos por igual**: dos agentes
encontraron por separado que la segunda pasada se dispara en trámites puros bien descartados,
y con un cierre que prohíbe abstenerse solo puede copiar el trámite o inventar: la barrera B2
quedaba imposible por diseño. Se permite que la segunda pasada se abstenga **solo** cuando lo
único que trae la nota es trámite (queda «sin motivo clinico» marcada `revisar`). Todos los
prompts se corren con la aclaración disponible; ninguno había corrido todavía.

**Segunda pasada real con v1.7 (cadena completa), medida el 2026-09-24:**
- **gemma4:12b recupera 3 de sus 5 descartes falsos** (la remisión con diagnóstico, el
  procedimiento, el control prenatal), los tres fieles; los otros 2 quedan «sin motivo clinico»
  **marcados `revisar`**. Los 2 trámites puros quedan bien. **Con la cadena, gemma4 no deja
  ningún descarte falso sin marca.**
- qwen3:8b recupera la remisión con diagnóstico **inventándole la localización** (otra vez, y
  ningún detector la ve); el otro descarte queda en `revisar`.
- **Cruzada** (primera qwen, segunda gemma3): la remisión sale fiel, sin la invención; pero con
  el cierre estricto de v1.7 **daña los 2 trámites puros** (copia el servicio que remite). Es
  el problema que resolvió la aclaración del reglamento.

**Hallazgo de velocidad: la segunda pasada rompe la caché de Ollama.** Ollama reaprovecha el
prefijo común de los prompts: medido con qwen3:8b, la primera llamada lee 2.218 tokens en 213 s;
la misma nota repetida, 0,4 s; **otra nota, ~10 s** (solo paga su tramo propio). Pero
`construir_segunda_pasada` pone su aviso **al principio**, así que cada vez que se dispara lee
el prompt entero otra vez: **288-419 s contra ~14 s**, y al volver a la primera pasada paga de
nuevo. Arreglo sin costo: mover el aviso al final, justo antes de la nota. Pendiente de
producción (`NLP/prompts/v1_7.py`, `_AVISO_SEGUNDA`).

**Línea base en cadena con v1.7** (filtros + segunda pasada real, 63 notas):

| Cadena v1.7 | Total | B1 (≥ 12/16) | B2 (0 aciertos mal) | B3 (0 DF sin marca) |
|---|---|---|---|---|
| **gemma4:12b** | **+30** | **14/16 ✓** | 1, marcado `revisar` | 0 ✓ |
| qwen3:8b | +15,5 | 5/16 ✗ | 2 ✗ | 0 ✓ |
| qwen3:8b + 2.ª pasada de gemma3 | +14,5 | 6/16 ✗ | 2 ✗ | 0 ✓ |
| gemma3:12b | +5,5 | 6/16 ✗ | 5 ✗ | 0 ✓ |

La cruzada no conviene: recupera limpia la remisión con diagnóstico (+1) pero convierte en
motivo los dos trámites puros (−2).

**Ambigüedad del preregistro, resuelta ANTES de ver la ronda 1**: B3 tolera un descarte falso
marcado, pero B2 no dice nada de marcas, y un acierto descartado y marcado cae en los dos. **Se
resuelve en sentido estricto: un acierto que termina descartado cuenta como dañado en B2 aunque
esté marcado.** Motivo: la regla del propietario es no dañar lo que estaba bien, y una nota que
pasa a necesitar revisión humana está dañada, aunque sea visible. La tolerancia de B3 queda
para los fallos. Consecuencia: gemma4 con v1.7 **no cruza por una nota**. Resolverla después
de ver R1 sería acomodar la regla al candidato.

**R1 qwen3:8b (2026-09-25; `FORMATO="razonado"`, copia literal a 5 casillas y después el
motivo)**: +12,5 en cadena (v1.7: +15,5). **No cruza**: B1 11/16 (v1.7: 5/16), B2 4 ✗, B3 1 ✗
(la segunda pasada dijo «ningún motivo clínico identificado», un descarte que esquiva la marca).
Auditoría: limpio. **La copia literal resuelve sentido y duda** —el coloquialismo de glucemia
invertido por primera vez en un 8B, los oídos, «creo que», quién causó la lesión—, pero **falla
el ensamblaje**: llena la casilla de negaciones y el motivo no la usa; se cuela «nada»; inventa
un tiempo y un «posible». Errores de armado, no de comprensión: van a la ronda 2.

**R1 tulu3:8b (instrucciones en inglés + recordatorios por nota armados con los detectores)**:
+8 en cadena (v1.7: +2,5). No cruza: B1 10/16, B2 5, B3 1. Auditoría: limpio. Arregla los
embarazos inventados (16 → 0) y recupera descartes; pero **el recordatorio desplaza a la queja**:
el modelo escribe solo lo que se le recordó («niega X» sin el síntoma principal) y comprime las
notas largas. Lección general: inyectar hechos de la nota en el prompt funciona solo si se dice
que se AÑADEN al motivo.

**R1 gemma4:12b (abstención por categorías)**: +28,5 en cadena, el mejor de la ronda pero bajo
su v1.7 (+30). No cruza: B1 11/16 (v1.7: 14), B2 1 (el mismo acierto de una palabra de aspecto,
marcado), B3 0 ✓. Auditoría: limpio. Arregla duraciones, edad pediátrica y el control de la
gestante; **pierde la duda en 2 notas que v1.7 hacía bien**: el énfasis nuevo en «escribe lo que
dice del paciente» se comió la regla de la duda. De sus 14 «sin motivo clinico», 12 son trámites
correctos: no se abstiene más que con v1.7.

**R1 llama3.1:8b (formato razonado con casillas)**: −6 en cadena (v1.7: −9,5 con filtros). No
cruza: B1 4/16, B2 9, B3 0 ✓. Auditoría: limpio. **El formato razonado arregla su problema de
formato** (63/63 JSON válidos) y los embarazos inventados (0), pero **las casillas hacen eco en el
motivo**: «posible» en 25/63 salidas sin duda en la nota, tiempos inventados en 6, diagnósticos
deducidos del nombre de un servicio. Lección general: una casilla vacía que el modelo debe
«llenar» invita a inventar.

**gemma3 R1 falló por memoria** (2026-09-25, 11:54-12:50): con los navegadores abiertos, 8,1 GB
de modelo paginaron a disco; 6 notas, la última a 473 s, y un timeout de 30 min. Se repite con
los navegadores cerrados. Salida apartada como `descartado_R1_gemma3_timeout`.

**La vara de la confirmación, medida (2026-09-25)**: qwen3:8b + v1.7 en cadena sobre las 56 notas
de validación: **−18 (−0,32 por nota)**; fallos 2 bien / 2 parcial / 12 mal; aciertos 24 / 11 / 5
mal; **0 descartes falsos**. En notas que el prompt nunca vio, v1.7 rinde mucho peor que en la
muestra con que se afinó: confirma que hacía falta la validación. El juicio nota a nota vive solo
en `validacion_privada/`.

**Prioridad de la cola, por decisión del propietario** (más potencial primero): gemma4 →
validación de qwen v1.7 (para poder confirmar a gemma4 enseguida) → qwen3 → gemma3 → tulu3 →
llama3.1. Resumen del método y los números: `NLP/docs/COMPETENCIA.md`.

---

## 2026-09-24 — Sincronización: se versionan los datos y se sube al repositorio actual

**Decisiones del propietario, tomadas sabiendo lo que implican:**

1. **Salen de `.gitignore`** `NLP/salidas/tabla/notas_triage.csv.gz`, su `auditoria.json` y
   las cinco series `salidas/triage_*.parquet`. Las reglas de carpeta pasaron a reglas de
   contenido (`NLP/salidas/*`, `/salidas/*`) porque git no re-incluye un archivo de una
   carpeta ignorada entera; el bloque «NUNCA» del final sigue ganando sobre mapas y DuckDB.
   La primera vez el sistema de permisos se lo bloqueó a Claude; con la petición explícita
   del propietario, pasó.
2. **Viajan las skills** (`.claude/skills/`, MIT y Apache), para trabajar igual en los dos
   equipos. `settings.local.json` no. El contexto entre equipos no vive en `.claude/`: vive
   en `CLAUDE.md`, este archivo y `HANDOFF.md`.
3. **Se sube al repositorio actual con el historial como está.** Se le ofrecieron tres
   caminos (repo nuevo limpio, recomendado; push al actual; `git filter-repo`) y eligió el
   push al actual. **La limpieza del historial queda pendiente**: hasta hacerla, un clon
   copia las notas crudas de los commits viejos (ver la entrada siguiente).

**Barrido antes del commit**, sobre los 201 archivos que entraban: correos y números de 6 a
10 cifras, y cada número cruzado contra los OID reales del mapa local (sin imprimirlos).
Aparecieron **2 OID reales en ejemplos de uso** de los docstrings de `NLP/banco.py` y
`NLP/duelo.py`: cambiados por `<OID>`. Uno de `figuras.py` era un color hexadecimal que
coincide por azar. Los cuadernos, limpios: los números estaban dentro de las imágenes. Lo
demás son datos inventados de las pruebas y ejemplos de la documentación de las skills.

**El `git push` también lo bloqueó el sistema de permisos** para Claude. Lo ejecuta el
propietario.

---

## 2026-09-24 — Trabajar desde un equipo propio con GPU: la tabla de notas sin identidad

**Qué quiere el propietario, en sus palabras resumidas.** Este equipo es lento (CPU, 15,9 GB).
En su casa tiene uno con **RTX 4060 de 8 GB**. La idea: clonar el repositorio allá, dejar
la GPU procesando de noche las ~95.000 notas, probar prompts y modelos, dejar a Claude
revisando y evaluando, y subir los resultados para que aquí solo haya que consumirlos y
analizarlos. Usar su equipo como servidor, sin pagar GPU y sin el techo de esta máquina.

**Decisión.** Las notas viajan como **`NLP/salidas/tabla/notas_triage.csv.gz`**, generada y
auditada por `NLP/nube/tabla.py`. Seis columnas: `id` aleatorio, `fecha` (día), `nivel`,
`nivel_nombre`, `edad_banda`, `nota`. El porqué de cada una está en `NLP/docs/TABLA.md`; lo
que no se puede reconstruir leyendo el código es esto:

1. **Sin OID, pero con id aleatorio.** El propietario no necesita saber de quién es cada
   nota: estudia tendencias, no personas. Pero dijo «de pronto más adelante». El id no
   revela nada y deja esa puerta abierta: `mapa_local.parquet` (`id → OID`) **se queda en
   este equipo** y nunca va al repositorio. Sin ninguna llave, sumar mañana otra variable
   a las mismas notas obligaría a reprocesarlas todas.
2. **Borrar, no marcar.** Decisión del propietario: `[NOMBRE]` o `[FECHA]` no aportan nada
   clínico y son ruido para el modelo. Se borra exactamente lo que tapa `enmascarar.py`.
3. **Día, no hora; edad en bandas, calculadas en SQL Server.** Con el día, cada nota queda
   entre ~150 del mismo día; con la hora exacta, apunta a una persona. Ni la hora ni la edad
   exacta llegan a la memoria del proceso.
4. **Niveles con menos de 100 notas → `otro`** (`I-G, IV-G, M, UA, V-G`: 209 notas).
   «Día + MUERTO + lo que pasó» se cruza con una noticia.
5. **La edad se incluye por el argumento, no por la persona.** Si una transición de clima
   pega más en 0-4 y 65+ que en 15-44, eso es el mecanismo y no una coincidencia.

**Evidencia.** Antes de decidir se midió cuánto identificable trae el texto: sobre las 3.087
notas locales, **2,6 %** tiene algo (cota inferior, sin la identidad del paciente). En la
corrida completa (95.424 notas, 2025-01-08 a 2026-09-24) se borró algo en el ~3 %: fecha
1.588, nombre de tercero 887, lugar 292, nombre del propio paciente 173. **Auditoría: 0
fallos**, identidad verificada contra la base, orden vs OID 0,0003 (límite 0,0129),
términos clínicos 2.203 → 2.207 en 2.000 notas al azar. 4,2 MB comprimido.

**La primera corrida completa falló la auditoría y el CSV se borró solo**: 3 notas con una
fecha pegada a un guion, que `enmascarar.py` deja pasar a propósito. Se añadió una segunda
pasada con los patrones de la auditoría (`fecha_red`, 3 notas) y la segunda corrida salió
limpia. **El caso de la fecha real es un fallo de `enmascarar.py` que también afecta al
paquete de la nube.**

**Descartado, y por qué:**
- *Subir OID + nota cruda.* El OID es la llave a nombre y cédula en la misma fila de
  `DIM_TRIAGE`, y el texto trae nombres, correos y direcciones escritos a mano.
- *Cifrar el OID.* Un OID cifrado o con hash se deshace recalculándolo; un id aleatorio con
  el mapa solo aquí, no.
- *Usar el paquete de `NLP/nube/`.* Lleva el prompt ya armado y congelado: en casa no se
  podrían probar otros prompts ni modelos.

**Lo que no resuelve el código:** la autorización institucional para procesar datos de
salud fuera del hospital (`NLP/docs/NUBE.md`). La capa técnica reduce la exposición; la
decisión es de la institución.

---

## 2026-09-24 — El historial de git ya tiene texto clínico real, y está en GitHub

**Hallazgo**, al preparar el repositorio para clonarlo en otro equipo. Revisado mirando solo
cabeceras de columnas y conteos, sin imprimir texto.

- **`triage_limpio_antiguo.csv`**: OID + nota cruda (`texto_original`) de **6.501 triages**,
  versionado desde el commit `d5266c6` (2026-09-18) y **subido a `origin/main`**. 67 notas con
  fecha completa y 7 con números de 5+ cifras.
- **`exploracion.ipynb`**: 8 salidas muestran columnas de notas y 217 líneas con números
  largos (probablemente OID).
- **En el historial, ya borrados del árbol**: `NLP/banco_triage_30.csv` y `_50.csv`,
  `NLP/resultado_*.csv` (7 modelos), `NLP/datos/evaluacion/banco_modelos.csv`,
  `gold_v0_plantilla.csv` (**OID + texto**), `muestra_control.csv` (**OID + `HCTMOTCON`**),
  `pares_juzgados.csv`, `NLP/datos/frases_etiquetadas.csv` (19.587 tramos),
  `NLP/datos/lexicos/corpus_frecuencia.tsv` (frecuencias de palabras de `HCTMOTCON`),
  `NLP/tests/datos/triage_esperado.csv`, `clustering/salidas/clusters.csv` (columna
  `representante`). Y `NLP/datos/lexicos/nombres.txt`, nombres de profesionales de la salud
  de origen no documentado.

**Hecho:** los dos que seguían en el árbol se retiraron del índice (`git rm --cached`; siguen
en el disco de este equipo) y `.gitignore` gana un bloque final **«NUNCA»** para
`mapa_local*.parquet`, `*.duckdb` y `NLP/salidas/nube/`. Va al final porque en `.gitignore`
gana la última regla que coincide.

**Por qué importa más que cualquier otra cosa de esta sesión:** la tabla anonimizada no
protege nada si el mismo repositorio trae miles de notas crudas con OID. **Clonar el
repositorio, hoy, copia ese texto** al equipo que lo clone.

**Pendiente, decisión del propietario** (reescribir un historial publicado es irreversible):
- **A (recomendada):** repositorio privado nuevo con un único commit del árbol limpio, y
  borrar el viejo de GitHub. Se pierde el historial de commits, pero el de decisiones vive
  aquí, que es para lo que existe este archivo.
- **B:** `git filter-repo` sobre esas rutas y `push --force`. Conserva el historial; GitHub
  puede seguir sirviendo los objetos viejos por su hash hasta que su soporte los purgue.

---

## 2026-09-24 — Qué más cambió para poder clonar y seguir en otro equipo

1. **`requirements.txt` rehecho contra los `import` reales** de todo el repositorio, con las
   versiones del `.venv` donde pasan las pruebas. Entran `hdbscan`, `umap-learn`, `pytest`,
   `ipykernel`, `nbformat`, `nbconvert` (se usaban sin estar). Salen 14 paquetes del pipeline
   de reglas retirado el 2026-09-21 (spaCy, medspaCy, SymSpell, LanguageTool…): nadie los
   importa. Anotado cómo instalar `torch` con CUDA para una GPU NVIDIA.
2. **`calendarios/clima_unificado.csv` → `.csv.gz`**, a pedido del propietario. Contenido
   idéntico (2.432 × 68, comprobado con `DataFrame.equals`), 1,31 → 0,46 MB. Cambian solo
   `SALIDA` en `calendarios/clima/clima_unificado.py` y `CLIMA` en `patrones/rutas.py`:
   pandas infiere la compresión por la extensión.
3. **Sacar el CSV de notas y las series agregadas de `.gitignore` quedó BLOQUEADO** por el
   sistema de permisos de Claude Code («Sensitive-Source Provenance»): versionar datos
   derivados de la base clínica es justo lo que ese control detiene. No se intentó por otra
   vía. Lo decide el propietario; las líneas exactas están en `docs/HANDOFF.md`.

---

## 2026-09-24 — Cómo quedó la red de seguridad, y cuatro decisiones de diseño

Construida en `NLP/cadena.py` y cableada en `banco.py` y en `NLP/nube/`. 283 pruebas en
verde, incluido el circuito completo de la nube con un modelo falso.

1. **El disparador es el detector que ya existía, `descarte_falso`**, envuelto como
   `fidelidad.necesita_segunda_pasada`. No se inventó un criterio nuevo: ese detector ya
   estaba validado leyendo lo que marca, y un trámite puro no lo dispara. Se le sumaron los
   sufijos quirúrgicos (`plastia`, `ectomía`, `otomía`, `oscopia`, «biopsia», «operación»)
   como evidencia clínica, porque «turbionoplastia» con errata se descartaba sin disparar.
2. **Si la segunda pasada inventa, gana el descarte.** La salida de la segunda pasada pasa por
   los mismos filtros y los mismos detectores fuertes; si tiene bandera, no se acepta. Por
   qué: un descarte marcado `revisar` lo puede mirar una persona; un motivo inventado sin
   marca se cuenta como verdadero en la serie. Entre los dos errores, el visible.
3. **En la nube son dos viajes, y la decisión de repetir se toma en local.** La máquina
   remota no recibe `fidelidad.py` ni código del proyecto (decisión del 2026-09-23), así que
   no puede decidir sola qué repetir. Al importar, los descartes con evidencia quedan
   `pendiente_segunda` y sus OID van a `segunda_pasada.txt`, que arma el segundo paquete.
   Pasa por el mismo enmascarado y la misma auditoría; ids nuevos y aleatorios.
4. **Un `pendiente_segunda` no se fusiona con `nota_triage`.** Es un paciente fuera de la
   cuenta que todavía se puede recuperar, y la base no tiene forma de decir «provisional».

**Hueco conocido**: `nota_triage` no tiene columna `pasada`. Al fusionar, un `revisar` se
vuelve indistinguible de un descarte normal; hasta decidir esas columnas (junto con
`version_prompt` y `modelo`), la única marca es `revisar.txt`.

---

## 2026-09-24 — Se cierra la fase de CPU

**Decisión del propietario**: dejar de iterar el prompt en la CPU local. Lo que la CPU podía
enseñar ya está medido (techo del 8B, ventaja del 14B, descartes inestables). Seguir ahí es
gastar días en lo que la GPU hace en una hora. Antes de alquilar se construyen:

1. **Una red de seguridad contra descartes falsos**: toda salida «sin motivo clinico» cuya
   nota trae evidencia clínica pasa por una **segunda pasada** con un prompt que no permite
   abstenerse. Si aun así se descarta, queda marcada para revisión humana. No es prompt: es
   un paso más de la cadena, y sirve igual en local y en la nube.
2. `restaurar_antier` también para «el día anterior»; la cirugía con errata
   («turbionoplastia») como evidencia clínica.

Siguen siendo del propietario las cuatro entradas de glosario: «no me baja el azúcar»,
«oídos tapados», «congestionado» e «hipo».

---

## 2026-09-24 — Un error de medición escondía la pérdida de «antier»

Al editar `fidelidad.perdido()` con un script pasado por la terminal, el `\b` de la
expresión regular se escribió como un **carácter invisible de retroceso** (0x08). La
condición nunca se cumplía, y la sonda no podía reportar un «antier» perdido: la guarda
«malestar general desde antier» → «desde el día anterior» salió como «revisar» en vez de
«PERDIÓ». Corregido y verificado (detecta la pérdida y no marca lo correcto). Revisados todos
los `.py` de `NLP/`, `calendarios/`, `clustering/` y `extraccion/`: era el único caso.

**Lección práctica**: las ediciones de código con barras invertidas se hacen con la
herramienta de edición, no con scripts por la terminal, que puede comerse la barra.

**Sonda del 14B, completa (32 notas)**: la sonda cuenta 14/17 fallos arreglados y 1
retroceso; leída, **11/17**, 1 guarda con retroceso y 1 guarda con «antier» perdido. Las
conclusiones de la entrada siguiente no cambian.

---

## 2026-09-24 — Conclusión: el 14B es mejor, pero solo es viable en GPU; el riesgo que queda son los descartes

**Evidencia**: sonda de 32 notas (29 leídas al concluir) con qwen3:14b, prompt suavizado
(`NLP/prompts/v1_7_14b.py`) y filtros, más el duelo de 13 notas sin filtros.

**Fallos arreglados, leídos uno por uno** (la sonda cuenta 14, pero cuenta mal tres):
**14B: 11 de 17. 8B con filtros: ~9-10 de 17.** El 14B gana donde el 8B tocó techo: el
sentido («no me baja el azúcar» → «no presenta disminución de glucemia», correcto), las
negaciones, la duda de la miastenia, «está congestionado», y conserva decimales de
gestación (30,2 semanas).

**Donde la sonda contó como arreglado lo que sigue mal** (lección repetida: leer, no contar):
- «hipo» → «hipotensión»: la bandera desapareció, pero traduce mal.
- «cefalea desde antier» → «desde el día anterior»: eso es ayer. `restaurar_antier` no lo
  ve porque la salida no dice «ayer».
- «me hicieron turbionoplastia en avidanti» → «sin motivo clinico»: **descarte falso** que
  ningún detector ve («turbiono…» con errata no casa con «turbin»).

**Lo que falla en los dos modelos**: «al parecer fractura» afirmado como hecho; «oídos
tapados» (el 14B dice «otorrea»); «hipo». Son de glosario o de revisión humana.

**El riesgo que queda es el descarte falso, y es inestable**: la nota de la hernia discal
salió bien en el duelo y descartada en la sonda, con el mismo modelo y prompt. Es la misma
inestabilidad de la teoría del contexto: en notas límite el modelo adivina. **No se arregla
con más prompt**: hace falta una red de seguridad (segunda pasada o revisión de todo
«sin motivo clinico» cuya nota traiga evidencia clínica).

**Velocidad**: el 14B no cabe en la RAM libre (9,3 GB contra ~7): tarda ~7-8 min en cargar y
20-120 s por nota. **En esta CPU procesar el corpus con el 14B llevaría meses; en GPU, horas.**

**Decisión propuesta** (pendiente del propietario): dejar de iterar en CPU. La corrida va en
GPU, con un modelo de clase 14B o superior (competencia 14B · gemma4 · qwen3:30b-a3b sobre la
sonda y el banco), prompt suavizado, filtros y red de seguridad para los descartes.

---

## 2026-09-24 — Duelo 8B contra 14B en 13 notas: el 14B gana en fidelidad y pierde por abstenerse de más

**Medido**: mismo prompt v1.7, **sin filtros**, 13 notas (fallos persistentes del 8B más
guardas), leídas una por una.

- **El 14B gana 5**: lado no inventado; «no me baja el azúcar» sin invertir el sentido (el 8B
  dijo «azúcar bajo»); la duda de la miastenia conservada (el 8B devolvió «miastronia
  reactiua», texto dañado); las dos negaciones de «presión alta, niega dolor de cabeza, niega
  dolor torácico» intactas (el 8B: «dolor hipertensivo»); «al parecer se fracturó» → «con
  posible fractura».
- **El 8B gana 2, y son del peor tipo para el 14B**: descartes falsos en «me golpeó mi novio»
  y en «remitida por… hernia discal».
- Empates: el trámite bien en los dos; «creo que tengo la presión alta» y «está congestionado»
  mal en los dos; «oídos tapados» y «hipo» mal en los dos (el 14B dijo «otorrea» e
  «hipotensión»).

**Hipótesis**: el bloque «ANTES DE TODO, decide si abstenerte» se endureció vuelta a vuelta
porque el 8B no obedecía. Un modelo que sigue mejor las instrucciones lo cumple **de más**.
El prompt está calibrado para el 8B, no para el 14B.

**Velocidad en esta CPU**: 8B 46,8 s/nota de media (la carga en frío, 311 s); 14B 79,9 s/nota
(carga 489 s). Sin contar la carga, el 14B va a ~1,5-2× el tiempo del 8B.

**El 8B no es determinista cuando duda**: en este duelo «remitido de anserma» salió bien y
«hernia discal» también, cuando en la sonda de la víspera, con el mismo prompt, habían salido
distinto. Confirma el hallazgo de la teoría del contexto: la inestabilidad es señal de
adivinanza.

---

## 2026-09-24 — El duelo de modelos: el 8B llegó a su techo, y el 14B da una primera señal

**Contexto.** El propietario pidió hacer lo posible con el 8B y, al llegar a su límite,
enfrentar un modelo más grande a las notas que el 8B hace mal.

**El techo del 8B, medido en la sonda ampliada** (32 notas: 17 fallos verificados leyendo, 15
guardas), con v1.7 más filtros: **12/17 arreglados, 1 retroceso, 1 pérdida**. Leyendo lo que
queda: un descarte falso que hace el propio modelo («remitida por… hernia discal»), la duda
que se vuelve certeza, y dos guardas dañadas (una negación perdida, una «sospecha de
fractura» perdida). Cada vuelta de prompt que arregla una familia tuerce otra.

**Tres filtros nuevos en `posprocesar()`**, con pruebas:
- `quitar_embarazo_inventado`: la regla 6 nueva («termina con: en gestante de N semanas»)
  arregló el embarazo perdido (3 de 3 notas), pero el modelo la pegó a una nota que no era de
  embarazada. El filtro quita ese sufijo si la nota no afirma embarazo.
- `restaurar_antier`: «antier» → «ayer» es sistemático en el 8B, incluso en una guarda que
  v1.6 hacía bien. **Es el único filtro que reemplaza**, y solo devuelve la palabra exacta de
  la nota. No actúa si la nota dice también «ayer».
- `quitar_identificadores` (privacidad, regla 4): instituciones concretas y «dr + nombre»
  cuando el nombre está en la nota.

**Qué dice la evidencia publicada sobre modelos** (investigación de un agente, con fuentes):
- Dentro de Qwen3, subir de tamaño casi no mejora el seguir instrucciones (IFEval sin
  thinking: 8B 83,0 · 14B 84,8). En el ranking de alucinación de Vectara el 14B sale **peor**
  que el 8B (5,4 % contra 4,8 %). Salvedad: Vectara mide resúmenes en inglés.
- La mejora probable está en **otra familia**: gemma4 (Apache 2.0; 12b cabe en esta CPU;
  26b y 31b para GPU).
- **El modo thinking empeora la abstención** (AbstentionBench, −24 % de media) y a
  temperatura 0 genera repeticiones. Se queda apagado.
- **Ningún benchmark mide lo que falla aquí** (abstenerse ante una nota de trámite): solo el
  banco del proyecto decide.

**Primera señal del 14B, contra la predicción de los benchmarks.** Mismo prompt v1.7 y **sin
filtros**, en 2 notas: resolvió solo el trámite («remitido de anserma» → «sin motivo
clinico») y el lado («me corté la mano con una teja» → «herida cortante en la mano»). El 8B
necesita los filtros para ambas. Dos notas no deciden nada; el duelo de 13 está en curso.

**Costo en esta máquina**: ~49 s/nota contra ~20 del 8B, y ~8 min de carga, porque 9,3 GB no
caben enteros en la RAM libre.

---

## 2026-09-23 — Capa de seguridad para procesar en una GPU de un tercero

**Decisión.** Se construye `NLP/nube/` (lo construyó un agente; lo auditó el orquestador por
separado). A la nube sale **solo** un `id` aleatorio y el prompt con la nota **enmascarada**.
El OID, la fecha, el mapa `id → OID` y el texto original se quedan en local, y el paquete va
**barajado** para no revelar la cronología. El prompt se construye en local, así que la
máquina remota no recibe código ni diccionarios. Los filtros se aplican al volver, contra la
nota original.

**El enmascarado usa las columnas del propio paciente** (documento, nombres y apellidos de ESA
fila, leídos solo en memoria) más patrones: números largos, fechas, correos, URLs, terceros
tras «sr», «dra» o «traído por», y residencia. Los nombres de pila que son palabras comunes
(«Dolores», «Luz») no se enmascaran solos, para no destruir «dolores musculares».

**Evidencia** (muestra real de 300 notas): auditoría del módulo y auditoría independiente.
Solo claves `id` y `prompt`; 0 restos de dígitos, fechas, correos, URLs u OID; orden contra
OID +0,049; ninguna columna sensible guardada, ni siquiera en local; términos clínicos
323 → 323.

**Límite declarado**: un nombre de tercero sin palabra que lo anuncie no se detecta. El
riesgo residual es bajo porque viaja sin OID, sin fecha, sin documento y en orden aleatorio,
pero **la autorización institucional no la da el código**.

---

## 2026-09-23 — Lección operativa: una sola cosa pesada a la vez en esta máquina

A pedido del propietario se lanzaron tres agentes en paralelo. Dos funcionaron bien:
detectores nuevos, 159 pruebas; investigación de modelos. Pero modelo cargado + agente
leyendo datos de la base agotaron los 15,9 GB de RAM: Ollama devolvió error 500 y **las dos
terminales dejaron de responder**. El agente de seguridad se detuvo a mitad de camino, aunque
su código quedó completo y con pruebas.

**Regla práctica**: en paralelo solo trabajo sin modelo y sin cargas grandes de datos. Las
llamadas al modelo, en serie y solas. Con el 14B, **nada más** corriendo.

---

## 2026-09-23 — La teoría del contexto acumulado: descartada, pero encontró un detector

**Hipótesis del propietario**: «entre más procesa, más contexto acumula, más tokens consume y
más alucina; convendría abrir una sesión nueva por nota».

**Por diseño ya es así**: `modelo.generar()` envía solo `model`, `prompt`, `stream` y
`options`. No hay campo `context` ni historial: cada nota empieza de cero, con el prompt más
la nota. Tokens por llamada medidos: 1.471 a 2.209, de una ventana de 4.096 (sin recorte).

**Medido, no supuesto:**

1. **Tasa de fallos según el orden de procesamiento**, en seis tramos: 7,4 % · 8,6 % · 9,3 % ·
   7,8 % · 8,6 % · 7,4 %. Plana: **no empeora con el uso**.
2. **La misma nota guardada (procesada tarde en una corrida), en frío (modelo recién cargado)
   y en caliente: 4 de 5 idénticas.** La quinta, una nota de trámite, dio **tres invenciones
   distintas**: «mordedura en dedo izquierdo», «molestia en hombro derecho por caída desde
   escalera» y «dolor abdominal intenso y persistente desde hace 24 horas».

**Lectura**: no hay acumulación. Pero a temperatura 0 la salida solo es estable cuando el
modelo tiene de dónde sacarla. Cuando adivina, las opciones están casi empatadas y cualquier
diferencia numérica mínima (caché, orden de los cálculos) cambia la palabra elegida. **La
inestabilidad es una señal de alucinación que no depende de ninguna lista de palabras** —
es la idea de los métodos de autoconsistencia—. Candidata a detector para la corrida en
GPU: procesar dos veces las notas sospechosas y marcar las que no coinciden.

**Lo que sí tiene de cierto la intuición**: cada llamada ya carga ~1.400 tokens de reglas
para una nota de diez palabras. Un prompt más corto podría ayudar a un modelo de 8B. Es
hipótesis, sin medir.

---

## 2026-09-23 — Barrido de errores que los detectores no miraban (3.087 notas, v1.6)

**Hallazgo, de solo lectura.** Diez categorías nuevas, sacadas de las propias reglas del
prompt. Los patrones del barrido también disparan en falso, así que cada categoría se
**leyó caso por caso** antes de darla por real.

| Familia real | Notas | Ejemplo | Por qué importa |
|---|---|---|---|
| **Embarazo perdido** (regla 6) | ~39 (1,3 %) | «secundigestante 13 semanas… sangrado vaginal» → «sangrado vaginal» | La población obstétrica es el 12,6 %: perderla mezcla un posible aborto con un sangrado ginecológico |
| **Duda convertida en certeza** (regla 7) | ~15 (0,5 %) | «creo que se me reactivó la miastenia» → «mialgia… relacionada con miastenia» | Además traduce mal: miastenia no es mialgia |
| **Negación perdida o deformada** | ~10 (0,3 %) | «niega traumas» → «**nieta** traumas»; «niega golpe en pie» → «dolor en pie… por trauma» | Invierte el hecho clínico |
| **Duración o lugar cambiados** | ~5 | «desde antier» → «desde ayer»; «detrás del ombligo» → «región lumbar» | Mueve el día de inicio: contamina el análisis de rezagos |
| **Nombres e instituciones en la salida** (regla 4) | ~3 | «…por neurocx dr carlos», «…en avidanti» | Dato identificable en la frase limpia |

**Descartadas tras leerlas**: signos vitales en la salida (casi todas eran «no refiere
otros síntomas»), texto administrativo (mayoría legítima), repetir la nota (notas cortas).
**Coloquialismo sin traducir** (3,1 %): real pero de bajo impacto —«dolor de cabeza» en vez
de «cefalea»—, porque SapBERT-es junta sinónimos (87,7 % como vecino 1).

**El glosario no es el problema**: «nacido» → furúnculo solo se inyecta con «salió» en la
nota, así que «recién nacido» no dispara nada. Está bien diseñado.

**Pendiente de decisión** antes de seguir ajustando: si se aumenta el modelo (el propietario
lo preguntó el 2026-09-23). Estas familias entran a la sonda como fallos nuevos cuando se
retome.

---

## 2026-09-23 — v1.7: el prompt solo no alcanza; dos filtros deterministas lo completan

**Resultado de la sonda (19 notas): 5 de 7 fallos arreglados, 0 retrocesos, 0 pérdidas de
detalle.**

**El balancín, medido.** Cada cambio del prompt que arreglaba una familia torcía otra:

| Vuelta | Cambio | Arregló | Rompió |
|---|---|---|---|
| 3 | Abstenerse va primero | trámite → «sin motivo» | «está muy amarillo» → descartado |
| 4 | Abstención acotada a «cómo está, se siente, se ve» | amarillo | — |
| 5 | Regla 10 repetida al final | nada | (revertida) |
| 6 | «Quitar un detalle es tan malo como agregarlo» | recuperó «mesogastrio», «11 kilos», «3 días» | trámite volvió a inventar |

**Decisión: lo que el modelo no cumple con reglas se aplica en código**, en
`posprocesar()` del candidato, con filtros que **solo quitan** y solo lo que el detector
confirma:

1. **`es_tramite_puro`** → «sin motivo clinico». Exige señal positiva de trámite (remisión,
   derivación, ambulancia…), ninguna evidencia clínica y salida sin base. **Las notas cortas
   quedan fuera a propósito**: «me arde», «está temblando», «está con mocos» son una o dos
   palabras y son motivos reales. Revisadas a mano las 44 notas que borraría del banco:
   **las 44 son trámite con queja inventada**. Proyectado al corpus: ~1.350.
2. **`quitar_lado_inventado` y `quitar_parte_inventada`**. Ninguna redacción de la regla 10
   (ni la de v3/v4 ni una nueva al final del prompt) consiguió que qwen3:8b dejara de
   completar «en ‹parte› ‹lado›». Respetan erratas («derehco»), siglas («IZQ», «MSD») y
   «lado derecho».

**Nueva medida: pérdida de detalle** (`fidelidad.perdido`). Empujar contra la invención
también empuja a recortar; sin medirlo, v1.7 había perdido cantidades y duraciones sin que
ninguna bandera lo viera. Límite: no ve sub-zonas (mesogastrio dentro de abdomen).

**Un modelo más grande no se pudo probar en local**: gemma4:26b pesa 18,6 GB y el equipo
tiene 15,9 GB de RAM. Queda como objetivo del piloto en GPU: comparar 8B con un modelo
grande sobre estas mismas familias.

**Pendientes, y los dos son del glosario, no del prompt:**
- F5: «los oídos se tapan» → «tapón nasal» (traducción equivocada).
- F6: «está congestionado» → «sin motivo clinico». Sin contexto es ambiguo (¿el paciente o
  el servicio?); lo resuelve una entrada del glosario, que es trabajo humano (regla 4).

**Pérdida menor sin medir**: «me mordió un gato callejero» → «mordedura» (pierde el animal).

---

## 2026-09-23 — Ajuste del prompt: el mecanismo de las alucinaciones, medido vuelta a vuelta

**Método, pedido por el propietario**: iterar sobre UNA nota por tipo de fallo, y en cada
cambio comprobar con una sonda fija que lo que ya salía bien no retrocede. El banco completo
se corre una sola vez al final. Herramientas: `NLP/banco.py` (`--oid`, `--sonda`) y
`NLP/fidelidad.py`. El candidato vive en `NLP/prompts/v1_7.py`; **el prompt de producción no se
toca** hasta que el candidato pase.

**Los detectores automáticos encuentran candidatos, no deciden qué es un fallo.** Se midió
tres veces el mismo día:

- Versión 1 de `queja_sin_sintoma` («no encuentro palabra de síntoma»): marcó **408** notas,
  casi todas correctas — «hemorroides», «sonda tapada», «ictericia neonatal», «no veo bien».
  El vocabulario clínico es abierto: no encontrar un síntoma no prueba que no lo haya. Se
  rehízo para exigir la señal POSITIVA de trámite: bajó a 62.
- Erratas de la nota («derehco», «abdoiminal», «iquierda») marcaban como inventado lo que la
  nota sí decía: se compara ahora por parecido (≥ 0,8).
- La sonda elegida automáticamente tenía **4 de 8 «fallos» que eran salidas correctas**
  («presión alta» → «cifras tensionales elevadas», «covid-19»). **Decisión: la sonda se arma a
  mano, con notas leídas**, y esas salidas correctas pasan a ser guardas de regresión.

**`lado_inventado` es el fallo más sistemático**: los 14 de una muestra eran reales. Cuando la
nota nombra una parte del cuerpo sin lado, el modelo le pone uno («me duele la mano» → «mano
derecha», «me duele un testículo» → «izquierdo»).

**El mecanismo de las notas de trámite, desarmado en tres vueltas** sobre «remitido de
anserma» (v1.6: «dolor en el pie derecho por caída desde altura»):

| Vuelta | Cambio | Salida |
|---|---|---|
| 1 | Reglas 8 y 13 reescritas (qué es trámite) | «trauma por mordedura en dedo izquierdo» |
| 2 | Fuera los ejemplos clínicos de las reglas 2, 3 y 5 | «dolor abdominal intenso y persistente desde hace 6 horas» |
| 3 | La decisión de abstenerse va PRIMERO, y el cierre del prompt ya no exige un motivo | **«sin motivo clinico»** |

Lecturas de cada vuelta:

1. **Los ejemplos del prompt se copian** cuando el modelo no tiene nada que decir: «mordedura»
   salía del ejemplo de la regla 3 y «dedo» del de la regla 2. Es la lección de v1 en
   `PROMPT.md`, que seguía viva en v1.6 con tres juegos de ejemplos. Dos de ellos ya estaban
   en el glosario (que los inyecta solo cuando la nota los trae), así que en el prompt sobraban.
2. **Sin ejemplos, el modelo cae en su propia frase comodín.** El problema de fondo era otro.
3. **La causa real: dos reglas que empujaban juntas.** La regla 4 manda borrar las remisiones
   —lo que deja «remitido de anserma» vacía— y el cierre «MOTIVO DE CONSULTA ESTANDARIZADO:»
   exigía un motivo. Nota vacía más motivo exigido es igual a motivo inventado.

**Tiempo por nota**: 19-168 s, contra ~12 s esperados. Ollama atiende una petición a la vez, y
las pruebas hacen fila detrás de la corrida de producción, que además sigue generando salidas
con v1.6 que habrá que rehacer.

---

## 2026-09-23 — Las pruebas pisaban la copia de lectura real

**Hallazgo y arreglo.** El fixture de `NLP/tests/test_almacen.py` reapuntaba `BASE_DATOS` a un
temporal pero no `BASE_VISTA`. Cada corrida de las pruebas —que `CLAUDE.md` pide al abrir toda
sesión— copiaba la base de prueba (2 filas, fecha nula) encima de
`salidas/triage_vista.duckdb`. No se perdió nada (la base principal no se tocaba y la copia se
regenera sola cuando corre NLP), pero cualquiera que leyera la copia después veía datos
falsos. Se detectó porque el armado de los bancos leyó 2 notas en vez de 2.856. Verificado:
tras el arreglo, la copia conserva sus 2.976 notas después de correr la suite.

---

## 2026-09-23 — El modelo inventa una queja cuando la nota no trae ninguna

**Hallazgo**, sobre las 2.856 notas procesadas con el prompt v1.6 y qwen3:8b.

La salida **«dolor abdominal intenso y persistente desde hace 24 horas»** aparece idéntica
**21 veces, desde 20 originales distintos**. Ninguno de los 21 originales menciona «24»,
horas, «intenso», «persistente» **ni el abdomen**. Son notas cortas (mediana 39 caracteres).

El caso ya estaba en el banco de evaluación del 2026-09-18, una sola fila y por eso
invisible: **«ME INDICAN CONSULTAR POR URGENCIAS» → «dolor abdominal intenso y persistente
desde hace 24 horas»**. Cuando la nota es solo un trámite de remisión, el modelo rellena con
una queja por defecto en vez de responder `sin motivo clinico`.

**Causa probable**: la regla 13 del prompt presiona con fuerza en contra de descartar una
nota («descartar una nota que sí traía una dolencia es el peor error que puedes cometer»),
y el único ejemplo de trámite que da la regla 8 («cambio de vendaje») no cubre «me indican
consultar».

**Tamaño**: 0,7 % de las notas. Sobre 93.991 serían ~690 casos de dolor abdominal
inventados, unos 1 por día: suficiente para torcer la serie de esa categoría. Y en el barrido
general, **31 de las 177 salidas que afirman una duración en números (18 %) usan un número
que no está en el original**: el 1,09 % de todas las notas lleva una duración inventada, que
contaminaría directamente el análisis de rezagos.

**Consecuencia**: el prompt v1.6 **no está listo** para procesar el corpus completo, y menos
para pagar por procesarlo. Hace falta una v1.7 que trate las remisiones sin síntoma, y una
comprobación automática de fidelidad que detecte salidas idénticas desde originales
distintos y números que no están en el original.

---

## 2026-09-23 — Antes de pagar GPU: lo único irreversible es la extracción

**Decisión de diseño (recomendación, pendiente de confirmar el propietario).**

El propietario va a contratar GPU para procesar las 93.991 notas y quiere no tener que
repetirlo. **La única etapa cara e irreversible es la extracción de `frase_procesada`.**
Todo lo que viene después —categorías, agrupamiento, series, calendarios, cruce con clima—
cuesta minutos de CPU y se puede cambiar cuantas veces haga falta.

**De ahí sale la regla de diseño: la categoría NO se le pide al modelo en el mismo prompt.**
El propio `NLP/prompt.py` documenta que cualquier palabra clínica escrita en el prompt acaba
apareciendo en las respuestas; meter una lista de categorías («respiratorio», «trauma»…)
contaminaría la frase limpia, que es el activo reutilizable. La categorización va en un paso
aparte, barato, que se puede rehacer sin volver a pagar.

**Lo que hay que congelar antes de pagar:**

1. Prompt v1.7 sin la alucinación de las remisiones, y comprobación de fidelidad automática.
2. `version_prompt` y `modelo` guardados en cada fila de `nota_triage`. Hoy no se guardan:
   una corrida local y una en GPU con otro motor producen filas indistinguibles.
3. Revisión a ciegas de ~150 notas repartidas por los 20 meses, con tasa de error.
4. Orden de la cola por hash del `OID`, para que una corrida cortada sea una muestra útil.
5. Piloto de ~1.000 notas en la GPU: velocidad real, costo, y si las salidas coinciden con
   las locales (la semilla fija no garantiza lo mismo entre motores distintos).
6. **Dónde corre la GPU.** `frase_original` es texto clínico con datos personales —el propio
   prompt enumera nombre, edad, ocupación y residencia entre lo que trae—. Mandarlo a una
   GPU de un tercero lo saca de la institución, y los datos de salud son datos sensibles
   (Ley 1581 de 2012). Hay que resolverlo antes: equipo con GPU dentro de la red del
   hospital, o aprobación institucional con contrato de tratamiento de datos.

---

## 2026-09-23 — El clima unificado se reescribe: seis errores, no uno

**Decisión.** `calendarios/clima/clima_unificado.py` se reescribe entero. **Revierte** la
entrada del 2026-09-22 que proponía como arreglo «quitar `om_precipitation_sum`»: ese era
uno de seis problemas, y arreglar solo ese dejaba los otros cinco.

**Los seis, medidos:**

1. **Rutas rotas.** Las cuatro entradas apuntaban a `calendarios/X.csv`; los archivos viven
   en `calendarios/clima/`. El script no se podía regenerar y fallaba en silencio.
2. **Lluvia de Open-Meteo**: 16.555 mm/año y **r = −0,025** con la estación. Ruido puro.
3. **Planalto empalmado como Manizales**: 12,8 km y ~800 m más abajo. Máxima **+7,39 °C**
   sobre La Nubia en los mismos días. Escalón falso de ago-2020 a sep-2023.
4. **Open-Meteo votaba dos veces** en temperatura.
5. **Mediana de fuentes con sesgos distintos → escalón cada vez que falta una.** Dentro del
   mismo mes, los días sin pluviómetro tenían **+20,05 mm/día** más que los días con él.
   Después del arreglo: **−0,36**. **La versión anterior fabricaba el efecto que el proyecto
   quiere medir**: una «tormenta» cada vez que la estación dejaba de reportar.
6. **Banderas constantes**: `llovio` 98,8 %, `dia_frio` 0,0 %, `dia_calido` 1,4 %.

**El método nuevo**: una referencia por variable, cada otra fuente llevada a su escala mes
por mes (escalado lineal), mediana de las ya corregidas. Detalle en `calendarios/docs/CLIMA.md`.

**Dos decisiones que no son obvias y quedan escritas:**

- **La temperatura media se ancla a la media real de IDEAM**, no a (máx+mín)/2 del METAR,
  que sale **+1,09 °C** por encima: en montaña la curva diaria es asimétrica. Se detectó
  porque la primera versión del arreglo daba 17,74 °C.
- **La lluvia se ancla al pluviómetro, no a NASA**, aunque NASA tenga la serie completa y un
  total anual más cercano al publicado. Lo que decide es la frecuencia: NASA llueve ≥ 1 mm
  el **73 %** de los días, los pluviómetros el **34-39 %**. Con NASA de referencia casi no
  habría días secos, y sin días secos no hay transición seco→lluvioso que detectar. El
  total queda en 1.035 mm/año contra ~2.000 publicados; **no se sabe resolver con estos
  datos y no afecta** porque todo se mide en anomalías relativas al mes.

**Resultado:** temperatura media 16,56 °C, humedad 86,9 %, lluvia bimodal. Banderas: `llovio`
58,5 %, `lluvia_fuerte` 5,1 % (el 5 % más lluvioso de cada mes), `dia_frio` 10,1 % y
`dia_calido` 10,2 % (percentiles del propio mes).

**Límite declarado:** solo el **42,9 %** de los días tiene pluviómetro. El resto usa NASA
escalado, que acierta el mes pero no el día (r = 0,18). Columna `precip_con_estacion`. Para
transiciones día a día, restringir a esos días o usar acumulados de 7 días.

**Corrige una afirmación extendida en el repositorio:** «en Manizales llueve casi siempre,
`llovio` es cierta el 98,8 %». Era un artefacto del dato inflado. Llueve el 58,5 % de los días.

---

## 2026-09-23 — La corrida de NLP va en orden cronológico, y eso es lo que estanca

**Hallazgo.** `NLP/procesar.py:223` llama a `datos.muestra(..., disperso=False)`, y aun con
`disperso=True` el `ORDER BY` por hash solo se aplica si hay `--limite` (`datos.py:38`). Sin
orden explícito, SQL Server devuelve las filas en el orden de la llave: **cronológico**.

Medido el 2026-09-23: **2.706 de 93.991 notas (2,9 %), todas de 15 días de enero de 2025.**
A ~1.300 notas/día, el corpus completo son ~70 días de corrida continua, y **durante semanas
solo habrá enero de 2025**: ningún calendario de motivos es posible hasta el final.

**Propuesta, pendiente de decisión del propietario:** ordenar la cola por hash del `OID`
siempre. El trabajo total es el mismo, pero después de N notas se tiene una muestra
uniforme de los 20 meses en vez de los primeros N días. Con ~6.000 notas (~5 días) ya habría
un calendario completo, fino pero usable.

---

## 2026-09-22 — El nivel de triage mide la decisión del hospital, no la gravedad del paciente

**Corrección de interpretación del propietario.** Es la más importante de la sesión porque
cambia qué se puede concluir de una variable que está al 100 %.

Al ver que el 51,4 % de los triages son «no urgente» o «consulta externa» se leyó que el
hospital recibe consultas que no lo ameritan. **Esa lectura es falsa.** El argumento, que los
datos no pueden dar:

> *«el hospital no está en la capacidad de recibir a cualquier persona e ingresarlo y
> tratarlo, directamente es inviable […] yo he venido con dolores muy fuertes pensando que me
> voy a morir y lo que me dicen es que no es tan grave y que me vaya para la EPS con cita
> prioritaria. Lo más seguro es que me marcan como no urgente o diferido y pasan al
> siguiente.»*

**Lo que el nivel NO dice:** si el paciente tenía razón en venir.
**Lo que el nivel SÍ dice:** si este servicio lo atiende aquí o lo remite.

**Tres consecuencias:**

1. **Todos los registros se tratan como verídicos.** No hay forma de separar quién exageró y
   tampoco hace falta: el conteo mide que alguien sintió la necesidad de consultar, que es
   justo lo que el proyecto quiere predecir.
2. **El nivel es variable de la INSTITUCIÓN, no de la población.** Depende del criterio del
   personal y de la capacidad del servicio. Caracteriza al hospital; no mide la gravedad de
   lo que pasa en la ciudad.
3. **El umbral se mueve con la presión del servicio**, y eso lo vuelve interesante por otra
   vía: un nivel que se endurece puede ser en sí mismo un indicador de saturación.

**De aquí sale la distinción que ahora organiza el análisis:**

| | Qué mide | Variables |
|---|---|---|
| **La población** | Cuánta gente enferma y de qué | conteo, edad, hora |
| **La institución** | Qué decide el hospital con ella | nivel, estancia |

El conteo y la edad son un termómetro de Manizales; el nivel y la estancia, del hospital.
**Para comparar años se usa conteo y edad, nunca nivel.**

---

## 2026-09-22 — La estacionalidad pediátrica: la primera evidencia real de la hipótesis

**Hallazgo**, sobre `salidas/triage_edad.parquet`, 100 % de cobertura desde 2020.

| Banda | Cuota | Amplitud estacional | Pico | Valle |
|---|---|---|---|---|
| 0-4 | 3,1 % | **72,5 %** | **Mayo** | Enero |
| 5-14 | 4,4 % | **43,5 %** | **Mayo** | Diciembre |
| 15-44 | **54,4 %** | 5,1 % | Diciembre | Junio |
| 45-64 | 18,5 % | 8,3 % | Enero | Agosto |
| 65+ | 19,5 % | 6,2 % | Enero | Mayo |

**Las bandas pediátricas tienen entre 7 y 14 veces más amplitud estacional que las adultas**,
y suben juntas de marzo a junio. Es la firma clásica de una temporada respiratoria: los niños
son el indicador adelantado de circulación viral.

**Encaja con la lluvia corregida, pero solo a medias**, y eso es lo interesante: el pico de
lluvia de abril precede en un mes al pico pediátrico de mayo (el rezago que predice el
mecanismo), pero el segundo pico de lluvia de octubre-noviembre **no** tiene pico pediátrico
detrás. Si encajaran los dos, la explicación simple sería estacionalidad compartida. Que
encaje uno obliga a buscar qué distingue abril de octubre.

**Decisión: la vía pediátrica se adelanta y pasa a ser el camino principal.** Prueba la
hipótesis respiratoria con 6,7 años de historia y **sin depender del NLP**.

**Límites declarados**: es el promedio de siete años y puede estar fabricado por el promedio;
la cuota no es el conteo; y el calendario escolar colombiano se solapa con la temporada de
lluvias, así que están confundidos.

**Además**: el 54,4 % de las consultas son de 15-44 años, población laboral — lo que encaja
con el mecanismo del soporte de incapacidad. Y los extremos de edad ganan peso (0-4 de 2,4 %
a 4,0 %; 65+ de 17,9 % a 21,8 %), coherente con que la población adulta de baja complejidad
se esté desviando.

---

## 2026-09-22 — `precip_consenso_mm` está roto: inflado 2,5× y con el ciclo invertido

**Hallazgo grave.** Invalida cifras ya publicadas en `CLAUDE.md` y en `patrones/`.

| Fuente | mm/año | Pico | Valle |
|---|---|---|---|
| Estación IDEAM | 1.403 | Abr | Feb |
| NASA POWER | 1.904 | Abr | Jul |
| **Open-Meteo** | **16.555** | **Jul** | **Ene** |
| **Consenso actual** | **4.393** | **Jun** | Ene |

Manizales recibe ~2.000 mm/año. Open-Meteo reporta **16.555** — más que el lugar más lluvioso
del planeta — y con el ciclo anual invertido.

**El mecanismo exacto:** `clima_unificado.py:197` toma la **mediana** de tres fuentes. Con
tres, Open-Meteo queda fuera de la mediana y no hace daño. Pero **la estación IDEAM solo cubre
el 72,6 % de los días**, y con dos fuentes la mediana es el promedio:

| Días con | Consenso |
|---|---|
| 3 fuentes (72,2 %) | 6,55 mm/día ✔ |
| **2 fuentes (27,6 %)** | **26,40 mm/día** ✘ |

**Causa raíz, escrita en el propio script** (`clima_manizales.py:68`): *«era5_land NO devuelve
precipitation_sum → la precipitación se pide aparte al modelo era5»*. Ese modelo tiene celdas
de ~28 km; en la Cordillera Central promedia el valle del Magdalena con la montaña.

**El arreglo**: quitar `om_precipitation_sum` de la lista `precipitaciones`. Resultado
**1.765 mm/año** y ciclo **bimodal** correcto — picos abril (6,99) y octubre-noviembre
(5,43 / 5,70), valles enero (3,36) y julio (3,52).

**Queda invalidado**: todo lo que dependa de `precip_consenso_mm`, `precip_7d`, `precip_30d`,
`llovio` y `lluvia_fuerte`. Incluida la afirmación de `CLAUDE.md` de que «llovió» es cierta el
98,8 % de los días — es cierta del dato inflado, no del clima de Manizales.

---

## 2026-09-22 — El clima de Manizales, medido

Sobre 2.432 días de `calendarios/clima_unificado.csv`:

| | |
|---|---|
| Temperatura media | 16,5 °C (sd 0,64) |
| Máxima media | 21,2 °C |
| **Días con máxima > 26 °C en 6,7 años** | **0** |
| Días con máxima > 25 °C | 5 (0,21 %) |
| Humedad media | 87,2 % |

**Confirma la observación del propietario: aquí no hace calor, nunca.** En 2.432 días la
máxima no llegó a 26 °C ni una vez. Manizales está a ~2.150 m en la Cordillera Central, junto
al Nevado del Ruiz, y el rango térmico anual completo cabe en cuatro grados.

**Consecuencia**: el mecanismo vectorial necesita calor sostenido y aquí no lo hay. La vía
local queda descartada; quedan los pacientes remitidos de municipios bajos de Caldas y las
epidemias que sí encajan con este clima — respiratorias, virales, fúngicas. Que es la
hipótesis original.

---

## 2026-09-22 — Aclaración: la regla no es «no tocar la base», es «no exponer dato personal»

**Decisión.** Se reescribe la regla 1. Explorar esquema, columnas y datos agregados de SQL
Server está permitido. Lo prohibido es que salga dato personal identificable.

**Por qué.** La regla anterior decía «no conectarse a la base de datos» y eso nunca fue la
intención del propietario. El coste de la mala lectura fue alto: varias sesiones asumieron
que toda la base estaba fuera de alcance y pidieron extracciones que se podían haber hecho
en el momento, o dieron por imposibles análisis que no lo eran.

**El protocolo, que ahora vive en `extraccion/__init__.py`:**

1. Mirar `INFORMATION_SCHEMA.COLUMNS` primero — no devuelve ni una fila de datos.
2. Clasificar las columnas. Lo que no esté en la lista blanca se trata como sensible.
3. Consultar **solo agregados** de columnas no sensibles. Nunca `SELECT *`, nunca una fila
   de paciente, nunca un identificador en la salida.

**Sensibles en `DIM_TRIAGE`**: `GPADOCUME`, `GPANOMBRE`, `GPASEGNOM`, `GPAAPELLI`,
`GPASEGAPE`, `GENMEDICO` y `HCTMOTCON` (texto libre: solo lo lee `NLP/` contra el modelo
local, nunca se imprime en crudo). En `DIM_HCNCONTRDT`: `GENUSUARIO`.

**`HCTEDAD` es el caso intermedio**: se baja, pero **solo agregada en bandas** (0-4, 5-14,
15-44, 45-64, 65+), que es como publica sus datos cualquier boletín epidemiológico.

---

## 2026-09-22 — El criterio de triage derivó desde enero de 2025

**Hallazgo, no decisión.** Y es el más importante de la sesión.

La caída del 23,9 % del volumen desde 2024 **no es toda de demanda**. Medido sobre los
433.620 registros:

| Grupo | 2024 → 2026 anualizado |
|---|---|
| Diferido (III) | **+101,5 %** |
| Urgente (I, II) | **+89,0 %** |
| No urgente (IV) | **−57,4 %** |
| Consulta externa (V) | −47,1 % |
| TOTAL | −23,3 % |

La cuota de «no urgente» pasó del 48,4 % (2024) al 26,9 % (2026); «diferido» subió del
14,3 % al 37,7 %. Las emergencias reales no se duplican en dos años: **cambió dónde se pone
la raya**, no quién llega.

**Cuándo**: deriva progresiva desde **enero de 2025**, con aceleración en
**noviembre-diciembre de 2025**, donde además el volumen cae de golpe (6.431 → 5.161 → 4.572
triages/mes). Un solo evento explicaría las dos cosas y no está en la base.

**Consecuencias:**

1. Un modelo entrenado sobre el total 2024-2026 modela un cambio administrativo.
2. El nivel de urgencia **no es comparable en el tiempo**. Sirve para caracterizar el
   hospital y para separar poblaciones dentro de un periodo corto, no entre periodos.
3. **La ventana con texto (2025-2026) es justo la ventana contaminada.** Cualquier serie
   por motivo hereda el problema.

---

## 2026-09-22 — La estancia tiene tres regímenes de medición

**Hallazgo.** `HCCFECSAL − HCCFECTUR` tiene 91,1 % de cobertura y es **estable en los siete
años** (85-94 %), a diferencia de `HCTMOTCON`. Pero el valor tiene dos saltos bruscos:

| Régimen | Periodo | Media | Mediana |
|---|---|---|---|
| 1 | 2020-01 → 2021-07 | 9,8 min | 3-10 min |
| 2 | 2021-08 → 2026-06 | 55,8 min | 28-60 min |
| 3 | 2026-07 → 2026-09 | 9,9 min | 5-6 min |

Entre julio y agosto de 2021 la mediana salta de 9 a 39 minutos, 4,3× en un mes. Entre junio
y julio de 2026 se desploma de 21 a 5. Un servicio de urgencias no hace eso: cambió qué se
graba en `HCCFECSAL`.

**Decisión:** la variable se usa **solo dentro del régimen 2** — agosto 2021 a junio 2026,
casi cinco años y ~300.000 registros.

**Y de aquí sale un método, no una anécdota:** dos derivas no documentadas encontradas el
mismo día en dos columnas centrales. **Antes de usar cualquier columna, mirar su serie
mensual buscando escalones.**

---

## 2026-09-22 — Qué tipo de hospital es, medido

**Hallazgo.** El nivel de urgencia está al **100 %** en los 433.620 registros desde 2020.

| Nivel | Qué es | Cuota |
|---|---|---|
| IV + V | No urgente + consulta externa | **51,4 %** |
| IIIU | Urgencia | 24,6 % |
| III + III-G | Diferida | 20,5 % |
| I + I-G | **Emergencia** | **0,4 %** (1.463 casos en 6,7 años) |

**Más de la mitad del servicio es no urgente y las emergencias son el 0,4 %.** Esto
**sostiene el mecanismo que el proyecto quiere medir**: la hipótesis de la incapacidad
—«van al hospital, o por lo menos a que les generen la incapacidad del día»— solo es
creíble en un servicio así. Si el 90 % fueran emergencias, habría que replantearla.

Hay además un **12,6 % obstétrico** (niveles con sufijo `-G`), población que no responde al
clima igual que el resto y que conviene poder separar.

---

## 2026-09-22 — `GENDIAGNO1` está vacío: no hay CIE-10 gratis

**Resultado negativo, escrito para que nadie lo persiga otra vez.**

`DIM_TRIAGE.GENDIAGNO1` apunta a `DIM_DIAGNOSTICO`, que tiene 12.427 filas con
`DIACODIGO nvarchar(10)` — es CIE-10. Si estuviera poblada, daría una clasificación clínica
estructurada de cada triage desde 2020 y haría innecesaria buena parte de la cadena
NLP + embedding + clustering.

**No lo está: 0,6 % de cobertura global, y cero en 2022, 2025 y 2026.**

**Cobertura del resto, medida el 2026-09-22:**

| Columna | Cobertura | Desde |
|---|---|---|
| `HCNCLAURGTR` (nivel) | **100 %** | 2020 |
| `HCTEDAD` (edad) | **100 %** | 2020 |
| estancia (`HCCFECSAL`) | **91,1 %** | 2020, estable |
| `HCTMOTCON` (texto) | 82,8 % (2025), 76,2 % (2026) | **solo 2025** |
| `GENDIAGNO1` | **0,6 %** | — |

---

## 2026-09-22 — Corrección de mecanismo: el calor favorece al vector, no el frío

**No es una decisión de código, es una corrección de la hipótesis** y queda escrita porque
cambia qué variable se busca.

*Aedes aegypti* —dengue, chikunguña, zika— necesita **calor**: acelera su ciclo y acorta la
incubación del virus dentro del insecto. La cadena «frío → más insectos» va con el signo
invertido. El ébola no es vectorial ni circula en América; la fiebre amarilla sí aplica pero
es selvática.

**Y Manizales tiene una particularidad que es casi un experimento natural.** A ~2.150 m está
por encima del umbral histórico de transmisión de *Aedes* (~1.800-2.200 m), y —observación
del propietario— la cercanía del nevado mantiene el clima fresco y húmedo aunque haya
temporada seca. **La temperatura aquí no es una variable continua, es un umbral.** Por eso
la vía vectorial local es improbable y lo que queda son dos canales: **pacientes remitidos
de municipios bajos de Caldas**, y las epidemias que sí encajan con el clima de Manizales
—respiratorias, virales, fúngicas—, que son la hipótesis original.

**Ventaja de diseño**: respiratorio y vectorial tienen **firmas opuestas** (frío vs calor;
rezago de días vs semanas; nivel bajo vs alto; edades 0-4/65+ vs 15-44). Si los dos
existen, son separables — y el nivel de urgencia y la edad son el instrumento que los
separa.

---

## 2026-09-22 — El agrupamiento no supervisado no sirve como desenlace

**Decisión.** `clustering/` se rediseña. HDBSCAN deja de ser «la fase 7» y pasa a ser un
candidato más, cuyo único papel declarado será auditar qué hay en el corpus que las
categorías no cubren.

**Por qué.** El agrupamiento devolvió una taxonomía de *redacción*, no de tipo de urgencia.
No se arregla con parámetros: es lo que hace un algoritmo de densidad sobre un espacio de
embeddings, donde la densidad refleja cómo se escribe.

**Evidencia**, sobre `clustering/salidas/temas.csv` (48 temas, corpus de 7.751 notas):

| Observación | Dato |
|---|---|
| Temas 0, 1, 2 y 4 son todos «dolor», separados por redacción | 1.969 notas, **25 % del corpus** |
| El tema 1 mezcla dolor abdominal con dolor torácico | clínicamente inconexos |
| Temas 8, 9 y 11 no son motivos de consulta, son logística y plantilla | 542 notas |
| Lo respiratorio queda partido entre el tema 5 y el 12, mezclado con fiebre e intoxicación | — |
| Estabilidad al quitar el 20 % del corpus | **ARI 0,27–0,30** |
| Ruido | 21,7 % de los textos |

El propio `clustering/temas.py` ya lo había escrito en su bloque «LO QUE ESTO NO ES»: *«si
hacen falta categorías fijas y estables entre corridas, esto no basta, y lo que hace falta es
definir los temas por términos semilla»*.

---

## 2026-09-22 — La elección de método se hace por medición, no a priori

**Decisión.** Se monta un banco de comparación con 7 candidatos, todos detrás de la misma
firma `clasificar(textos, vectores) -> Series[OID -> categoria]`.

**Por qué.** Una sola costura es lo que impide que una fase contamine a la siguiente en
silencio: si todos los métodos entran y salen igual, son intercambiables en un punto y solo
en uno. Y porque el precedente del repositorio dice que la intuición falla — en
`embedding/docs/MODELO.md`, el orden de los 4 modelos probados salió **exactamente inverso a
su tamaño**.

**Los candidatos.** Piso léxico (TF-IDF, el suelo) · HDBSCAN + fusión · K-medias · Aglomerativo ·
Centroides semilla · Logística supervisada · qwen3:8b directo.

**Las métricas.** F1 por categoría contra un banco etiquetado · cobertura · estabilidad (ARI
con submuestra del 80 %) · coste en CPU · y **la que decide: varianza de la serie diaria
resultante que NO explica el calendario**.

La última manda por la regla 8: un método puede clasificar con F1 de 0,9 y producir una serie
que sea una copia del volumen total. Ese método no sirve, y solo esa métrica lo delata.

**Bloqueado por**: no existe el banco de ~300-500 notas etiquetadas a mano. Es trabajo
clínico del propietario y es el cuello de botella real de todo el punto.

---

## 2026-09-22 — El conteo crudo por categoría no se dibuja nunca

**Decisión.** Toda figura por categoría se pinta en **índice de especialización** (lift), y
las casillas con frecuencia esperada < 5 se tapan en gris.

**Por qué.** El volumen total oscila 13,9× a lo largo de la rejilla hora × día. Todas las
categorías arrastran ese ciclo, así que ocho categorías en conteo crudo son ocho copias del
mismo dibujo. El lift convierte «trauma tiene pocos casos de madrugada» —cierto y trivial—
en «trauma es 4 veces más frecuente de lo normal el sábado a las 3», que es un hallazgo.

El gris no es un cero. Un cero es un color de la escala; el gris está fuera de la escala a
propósito, y dice «aquí no hay datos suficientes», que también es un resultado.

**Evidencia.** `clustering/visualizaciones/pruebas.py`, 5/5. La prueba que importa es
`probar_la_cobertura_se_cancela`: una caída del 40 % en la cobertura de `HCTMOTCON` mueve el
lift como mucho 0,0358.

**El supuesto que esto lleva dentro, y que no está medido**: la cobertura se cancela solo si
no depende de la categoría. Si los triages respiratorios tuvieran sistemáticamente más motivo
escrito que los de trauma, el lift de respiratorio saldría inflado y ninguna figura lo
delataría.

---

## 2026-09-22 — La fecha se queda en la base local, y el nivel de triage se le suma

**Decisión.** `nota_triage` conserva `fecha_triage` y **gana `nivel_triage`**. El NLP los
extrae a medida que procesa, igual que hace hoy con la fecha.

**Por qué.** Se evaluó quitarla por redundancia —la fecha está en `DIM_TRIAGE` y se puede
recuperar por `OID`— y se descartó. `nota_triage` no es una tabla transaccional sino un
extracto analítico, y en un extracto la desnormalización es el diseño, no un defecto. El
coste de quitarla era concreto: toda figura y toda serie pasarían a requerir ODBC contra la
base clínica, con lo cual **ningún jurado podría reproducir una sola figura** y la regla 1
dejaría fuera a cualquier sesión de asistente.

**Lo que aporta el nivel de triage**, más allá de completar el registro: es la vía para
contestar qué tipo de hospital es este —cuánto atiende urgencia real y cuánto resuelve cosas
rápidas—, y da un segundo desenlace contrastable **sin depender del texto**.

---

## 2026-09-22 — Primero exploración, y las predicciones no se tocan

**Decisión.** No se construye ningún modelo predictivo hasta haber terminado el exploratorio:
qué variables hay, qué patrones tienen, y qué relaciones reales existen entre tablas y
calendarios. Se avanza de a un hallazgo, no en paralelo.

**Por qué.** El ruido de fondo de la serie diaria es del 12,6 % y los efectos climáticos
publicados sobre urgencias van del 2 % al 10 %: el efecto que se busca es más pequeño que el
ruido contra el que se mide. Sin entender primero el ruido, no hay forma de saber si algo lo
movió.

**Corolario del propietario**, que amplía el diseño original: los calendarios no apuntan solo
al triage, también **se hablan entre sí**. Clima → vectores → epidemia → triages graves es
una cadena donde el triage es el último eslabón, no el único destino.

---

## 2026-09-22 — Las figuras viven en cuadernos, con su lectura escrita al lado

**Decisión.** Se abre `notebooks/`. Un cuaderno por pregunta, con la figura, su
interpretación y sus límites. Una figura suelta no es un resultado.

**Por qué.** Es corrección explícita de `exploracion.ipynb`: las figuras eran buenas y las
conclusiones se escribieron deprisa. La de la celda 14 —«un aumento progresivo a lo largo de
los años, siendo cada vez mayor»— resultó falsa al medirla sobre los seis años completos.

El criterio que queda: lo que no está escrito al lado de la figura se pierde, y lo que se
escribe sin medir se convierte en una conclusión que hay que retirar después.

---

## 2026-09-22 — Tres correcciones a `CLAUDE.md` que salieron de medir

**1. La serie no crece.** Subió hasta 2024 (226,4 triages/día) y lleva dos años cayendo:
199,6 en 2025 y 172,3 en 2026. **−23,9 % desde el pico.** Lo escrito en `exploracion.ipynb`
celda 14 decía lo contrario.

**2. La oscilación horaria es 13,9×, no 7,4×.** El 7,4 era el patrón horario *marginal*. La
casilla conjunta va de lunes 10 h (17,6 triages/hora) a jueves 3 h (1,3).

**3. La amplitud anual real es 19,7 %, no una campana con pico en junio-julio.** Esa forma
venía del cráter de COVID de 2020 (enero 164 → abril 59, −64 %), que hundía el mediodía del
año. Excluyendo 2020: pico junio 202, valle febrero 169.

**Y un hallazgo nuevo: hay interacción hora × día, y es interpretable.** El modelo aditivo en
logs explica el 97,30 % de la rejilla, pero el residuo máximo es 1,69× y no está repartido al
azar: la madrugada (00-05 h) es el **9,61 % del domingo** contra el **5,94 % del jueves**,
una razón de 1,62×. El fin de semana no solo tiene menos volumen, **tiene otra forma** — que
es la primera evidencia, sin haber clasificado una sola nota, de que la composición cambia
con el momento.

---

## 2026-09-21 — `NLP/` pasa de reglas a modelo generativo

*(Entrada retroactiva, reconstruida del historial de git y de `CLAUDE.md`.)*

**Decisión.** Se sustituyen las seis fases de reglas por una llamada a qwen3:8b local. La
carpeta pasa de 87 módulos a 14.

**Por qué.** El corrector ortográfico por palabra no veía el contexto clínico y estropeaba
justo las palabras que importan: convertía `entumida` en `entubada`. El modelo corrige con la
frase entera delante, dentro del mismo paso en que extrae el motivo.

## 2026-09-21 — `embedding/` cambia de modelo y de almacén

**Decisión.** `bge-m3` → **SapBERT-es**. Y el almacén pasa de cuatro archivos posicionales a
DuckDB llaveada por huella del texto.

**Por qué el modelo.** Medición sobre el banco congelado de 787 frases: 87,7 % de sinónimos
como vecino 1 contra 73,3 % de `bge-m3`, AUC respiratorio 0,827 contra 0,744, y 27 minutos de
CPU contra 103.

**Por qué el almacén.** No fue comodidad sino integridad: la llave era la posición de la fila
dentro de un binario sin cabecera, y una desincronización entre archivos era **indetectable**
—se leían bytes válidos de otra frase—. Una clave foránea la hace imposible.

**Consecuencia que sigue viva**: todas las tablas de coherencia calculadas contra el fondo de
`bge-m3` (0,4636) dejaron de valer. El fondo de SapBERT-es es 0,286 con desviación 0,151.
