# Plan — la operación con un solo entrenamiento, un centinela y un horizonte medido

**Escrito el 2026-10-19 y reescrito el mismo día con más detalle**, después de una conversación larga con el
propietario. El porqué de cada decisión está en `docs/CONTEXTO.md`, entradas «2026-10-19 (rediseño de la operación)» y
«2026-10-19 (rediseño, respuestas y frontera)».

---

## 0. Cómo se usa este documento

El propietario abrirá cada sesión con una frase corta, del tipo **«comienza con el plan de desarrollo, fase N»**. Esa
sesión no conoce la conversación que dio origen a este plan. Todo lo que necesita está aquí, y **si algo no está
aquí, se pregunta al propietario; no se interpreta.**

Al recibir «fase N», en este orden:

1. Leer `CLAUDE.md`, `docs/HANDOFF.md` y **este archivo entero**, no solo la fase. Las secciones 1 a 5 son las que
   evitan interpretar mal.
2. Ver la tabla de estado (sección 8). Si una fase de la que depende N no está **Hecha**, no empezar: decírselo al
   propietario.
3. `git status`. El cambio en `NLP/modelo.py` es ajeno (apunta a MedGemma) y no se toca ni se incluye.
4. Hacer la fase siguiendo sus pasos.
5. **Durante la sesión**, no al final:
   - cada decisión va a `CONTEXTO.md` (el archivo solo crece, la entrada nueva va arriba);
   - cada cambio de estado va a `HANDOFF.md`;
   - el estado de la fase va a la tabla de la sección 8.
6. **No se da una fase por terminada** hasta que pasen todas sus pruebas de aceptación, con la salida de cada
   prueba a la vista. Si una prueba no pasa, se le cuenta al propietario con el número. **Nunca se ajusta la prueba
   para que pase.**

La regla de oro: las decisiones de la sección 4 **no se vuelven a discutir**. Si una medición las contradice, la
sesión lleva el número al propietario y él decide. Lo mismo vale para cualquier cosa que no esté escrita.

---

## 1. Qué es el producto (contexto mínimo)

- **El desenlace** es el número total de solicitudes de triage por día en urgencias del hospital (SES). No el motivo
  de consulta.
- **El producto** es un pronóstico para los jefes de urgencias:
  - cuántos pacientes llegarán cada día, con un rango;
  - cómo se reparten en madrugada, mañana, tarde y noche, y a qué horas está el pico;
  - de qué aseguradora vienen.

  Urgencias decide el personal con esa información. Se muestra en Power BI (`prediccion.pbip`) y en un tablero de
  Streamlit (`operacion/tablero.py`).
- **Dos modelos corren lado a lado, siempre con los mismos datos y en los mismos momentos:**
  - **M3s**, el principal: es C0r más los mecanismos externos (Feria de Manizales, fiestas de los pueblos, noches del
    7, 24 y 31 de diciembre, terremotos, olas de salud pública, red de urgencias, seguridad). Es el que contesta «por
    qué».
  - **C0r**, la comparación: solo calendario, estación, nivel y memoria. Es la vara de `CLAUDE.md` («toda métrica se
    reporta contra el control de calendario»).
  - Cada uno es una combinación (promedio de cuantiles) de **SARIMAX** y **LightGBM**.
- **Quien lo construye es un practicante.** El producto tiene que sobrevivirle y caber en un servidor compartido del
  hospital, que hoy está casi saturado. No se sabe cuánto tiempo lo van a usar: **nada de ingeniería de
  escalabilidad que no se haya pedido.**

## 2. Cómo funciona hoy la operación (antes del plan)

`python -m operacion` (`operacion/__init__.py`, función `correr` → `predecir`), hecho para correr cada lunes:

1. Toma el último día completo de triage como **origen** (`ultimo_dia_completo()`).
2. Fija el **horizonte** con `horizonte(o)`: hasta el 31 de diciembre, con un mínimo de 28 días (`VALIDADO`) y un
   máximo de 120 (`HORIZONTE_MAX`).
3. **Reentrena desde cero**: `sm.Ajuste(y, cal, sm.COMBOS[modelo])` seguido de `aj.ajustar(o, hs)`, y predice con
   `aj.predecir(o, hs)`. Lo hace para M3s y para C0r.
   - Coste medido el 15-10, con 78 días de horizonte: M3s 373 s y C0r 229 s.
   - LightGBM es **un modelo por cada día de adelanto y por cada uno de los 9 cuantiles** (`QL` = .02 … .98). Con
     120 días son 1.080 modelos por combo. Por eso tarda.
4. Con los cuantiles del total, `_dias()` arma, día por día:
   - el reparto por hora (`rp.Perfiles`, perfil `P52`);
   - por aseguradora (`ag.Proporciones`, ventana `T4`);
   - la corrección por la red de urgencias (`rd.EfectoV2`);
   - el ensanchamiento del rango tras un quiebre (`rs.Quiebre`).
5. Guarda la corrida, sin rehacerla nunca, en `salidas/operacion/corridas/<origen>_<modelo>/` (`resumen.json`,
   `dias.parquet` y demás).
6. `verificar()` cruza todas las corridas guardadas con lo real y escribe `salidas/operacion/verificacion.parquet`,
   con `en_rango` = el real entre q10 y q90 (inclusive), y `error_pct`.
7. `semaforo()` escribe `salidas/operacion/estado.json`. Las señales:
   - antigüedad del dato: verde ≤ 8 días, rojo ≥ 21;
   - error del día en los **últimos 28 días** verificados: verde ≤ 12 %, rojo ≥ 18 %;
   - días dentro del rango: verde ≥ 65 %, rojo ≤ 50 %;
   - cambio de Nueva EPS;
   - salud pública;
   - comparación M3s frente a C0r: regla de vuelta atrás a los 84 días comunes.

   **El semáforo solo pinta colores: no dispara nada.**
8. `python -m operacion.powerbi` exporta 11 CSV a `salidas/powerbi/`, que lee Power BI. Hoy no está en ninguna tarea
   programada.

Aparte:
- `python -m contexto` pone al día las fuentes externas, cada una a su ritmo, más la extracción del hospital
  (`python -m extraccion --series`). Duraciones medidas el 15-10: todas las fuentes 143 s; solo lo que toca 17 s; la
  extracción 16 s.
- `python -m operacion --ajustar` reaplica a la última corrida, **sin reentrenar**, el registro manual de cierres y
  reaperturas de la red (`datos/eventos_red.csv`).

## 3. Glosario: estas palabras tienen un único significado en este plan

| Término | Significa | **No** significa |
|---|---|---|
| **Entrenar** | Estimar parámetros: ajustar los modelos de LightGBM, los parámetros de SARIMAX, el control o los coeficientes de `EfectoV2`. Cualquier `fit` o `lstsq` | Leer datos nuevos |
| **Reentrenar** | Volver a entrenar con datos más recientes. **Solo lo hace un profesional, a mano** (D2) | Recalcular una predicción |
| **Artefacto** | Lo que deja el entrenamiento, guardado en disco: modelos, parámetros, columnas usadas y metadatos | Una corrida (que es una predicción) |
| **Modelo congelado** | Usar el artefacto sin cambiarle ni un parámetro | Usar datos viejos |
| **Datos frescos** | Las entradas actualizadas hasta el día del origen: triage, aseguradoras, red, contexto externo y los promedios recientes de la sección 5 | Entrenar |
| **Predecir / recalcular** | Correr el modelo congelado con datos frescos desde un origen y guardar la corrida. Dura segundos o pocos minutos (se mide en la fase 1) | Reentrenar |
| **Origen** | El último día completo con datos cuando se predice | — |
| **Adelanto** | Días entre el origen y el día predicho (1, 2, …) | — |
| **Horizonte confiable `h*`** | El mayor adelanto en que la predicción cumple el criterio de D12. Se **mide** en la fase 2 | Los 120 días ni los «4 meses» de la conversación, que son intuición |
| **`W`** | Los días mínimos que urgencias necesita ver por delante para organizar turnos: **28** (D11) | — |
| **Vigencia `V`** | Cuántos días sirve una predicción antes de reemplazarla: `V = h* − W`. Así siempre quedan al menos `W` días confiables por delante | El horizonte |
| **Predicción vigente** | La última corrida guardada del modelo principal y su compañera de C0r con el mismo origen | — |
| **Centinela** | La regla que vigila la predicción vigente contra lo real: **5 de los últimos 7 días fuera del rango** (D5) | El semáforo actual, que solo pinta colores |
| **Rango del 80 %** | De q10 a q90. «Dentro» = q10 ≤ real ≤ q90 | — |
| **Cobertura** | La parte de días (u horas) reales que cayó dentro del rango. Es lo que muestra hoy el «X % de probabilidad» del tablero | La probabilidad de que la predicción sea correcta |
| **Lo habitual** | La media del mismo día de la semana en las 8 semanas que terminan en el origen (columna `habitual`). Es la vara de «sube» desde el 2026-10-08 | El control de calendario |

## 4. Decisiones del propietario (2026-10-19) — no se rediscuten

Cada decisión va con lo que **no** significa, que es donde una sesión nueva se equivocaría.

- **D1. Un solo entrenamiento más, hecho aquí y en local**, con todo lo disponible hasta ahora: 2026 y las dos
  caídas de Nueva EPS (mediados de noviembre de 2025 y julio de 2026), más el sismo de 2026. Así el entrenamiento
  contiene cómo se ven el hospital y el contexto cuando una EPS colapsa. Es **el último entrenamiento del modelo
  actual**.
  - *No significa* cambiar la receta (variables, hiperparámetros, combinación). La receta de M3s y C0r está congelada
    desde el 16-10.
- **D2. Cero reentrenamientos automáticos.** Ningún script, tarea programada ni centinela entrena. Reentrenar lo
  decide en el futuro la persona de BI, y solo si algo institucional o del país cambia lo que el modelo debería
  saber.
  - *No significa* construir herramientas, alertas ni calendarios de reentrenamiento. **No se invierte tiempo ahí**,
    más allá de una página que diga cómo se hizo el entrenamiento (fase 3).
- **D3. Modelo congelado + datos frescos.** La predicción usa el artefacto fijo y las entradas actuales del hospital
  y del contexto externo. Eso es «ver la actualidad» sin entrenar.
  - *No significa* que el modelo «aprenda» de los datos nuevos: los usa como entrada, como hoy usa el nivel de los
    últimos 28 días.
- **D4. Horizonte y vigencia medidos.** Se mide `h*` y se fija `V = h* − W`. Se acaba el «hasta el 31 de diciembre».
  - *No significa* aceptar 120 días porque se mencionaron: puede salir más o menos.
- **D5. El centinela.** Con 5 de los últimos 7 días fuera del rango de la predicción vigente, la predicción falla.
  Urgencias varía mucho, así que 3 o 4 días fuera se toleran. Reaccionar en una o dos semanas es aceptable; casi un
  mes (los 28 días del semáforo actual) no.
- **D6. Cuando el centinela salta, se recalcula solo**: una predicción nueva desde ese día, con datos frescos y el
  artefacto fijo, sin esperar a que se acabe la vigencia. Queda registrado con su motivo, y no hace falta que una
  persona lo apruebe.
  - *No significa* reentrenar.
- **D7. La predicción no se rehace cada semana.** Se rehace solo al acabarse la vigencia o al saltar el centinela.
  Los **datos** sí se actualizan con regularidad (D14).
- **D8. Rangos útiles con probabilidad honesta.** Mejor un rango más concreto con su probabilidad real (por ejemplo,
  60 %) que uno enorme con 89 %. Es el ejemplo del dado: «seguro que sale entre 1 y 6» no informa nada.
- **D9. n8n descartado.** El modelo necesita Python y la extracción, SQL Server dentro de la red. El despliegue
  (servidor actual o máquina nueva) se decide al final, con los recursos medidos del diseño nuevo.
- **D10. No se compara contra el reentrenamiento semanal.** El propietario ya vio su efecto. El régimen congelado se
  mide contra criterios absolutos (D12), contra «lo habitual» y contra C0r.
- **D11. `W` = 28 días.**
- **D12. Criterio de «confiable» para `h*`**, a la vez y en los dos años de la retroprueba (2025 y 2026):
  - error medio del día ≤ 12 %;
  - cobertura del rango del 80 % entre 70 y 90 %;
  - error menor que el de «lo habitual» en el mismo adelanto.

  Se aplica a M3s; C0r se reporta al lado.
- **D13. Recálculo que no arregla.** Si el centinela vuelve a saltar en los 14 días siguientes a un recálculo por
  centinela, se recalcula igual y el semáforo marca **«requiere revisión de un profesional»**. Nada más: ni
  reentrenamiento ni aviso externo.
- **D14. Cadencia de los datos.**
  - El dato real del hospital (extracción, unos 16 s) se baja **a diario**, para que el centinela reaccione en días
    y no en semanas.
  - El contexto externo, al menos **semanal**, y dos veces por semana si sale barato.
  - La fase 6 confirma con mediciones que esto no carga el servidor. Si no se cumple, se le lleva el número al
    propietario.

*Nota honesta:* D11 a D14 salieron de propuestas de Claude que el propietario aceptó. Si una medición las pone en
duda, eso se le dice.

## 5. La frontera: qué se congela y qué es dato fresco

Además de SARIMAX y LightGBM, cada corrida de hoy **estima** otras piezas con datos recientes. Para D2 y D3 la regla
es: **lo que sale de un ajuste (`fit`, `lstsq`, máxima verosimilitud) se congela en el artefacto; lo que es una
proporción o un promedio de una ventana reciente es dato fresco.**

| Pieza | Dónde | Qué hace | Clase |
|---|---|---|---|
| SARIMAX | `pronostico.SARIMAX.ajustar` / `.predecir` | Parámetros por máxima verosimilitud. `predecir(o)` ya filtra los datos hasta `o` con `self.params` fijos | **Congelar** `params` y `cols` |
| LightGBM (`lightgbm_rel`, `lightgbm_rel_mec`) | `pronostico._Directo.ajustar`, `LightGBMRel` | Un modelo por adelanto y por cuantil. Aprende `log(y) − nivel` | **Congelar** `m[h]` y `cols[h]` |
| Control | `pronostico.Control` (`_Directo`) | Da «lo normal» en `Ajuste.predecir` | **Congelar** |
| Nivel y memoria | `pronostico.rasgos()` | `nivel` = media de 28 días de `log(y)`; `mem_semana`, `mem_mismo_dia` | **Dato fresco**: son entradas |
| Contexto externo y mecanismos | `contexto_diario.csv`, `mecanismos.columnas` | Las 35 columnas de mecanismo | **Dato fresco** |
| Perfil horario P52 | `reparto.Perfiles` | Proporción del día por hora en las últimas semanas | **Dato fresco** (promedio de ventana) |
| Reparto por aseguradora T4 | `aseguradoras.Proporciones` | Proporción por grupo en las últimas semanas | **Dato fresco** |
| Quiebre | `resiliencia.Quiebre` | Compara los últimos 7 días con los últimos 28, frente a 52 semanas | **Dato fresco** (regla fija sobre promedios) |
| Efecto de la red | `red.EfectoV2.estimar` | Coeficientes por `np.linalg.lstsq` sobre semanas desde 2024-01-08 | **Congelar** los coeficientes (es un ajuste). El registro `eventos_red.csv` y el estado abierto o cerrado de cada episodio son dato fresco |

Si aparece una pieza que no está en esta tabla, se clasifica con la misma regla y se escribe en `CONTEXTO.md`. Si la
regla no la resuelve, se pregunta al propietario.

---

## 6. Las fases

**El orden es secuencial: 1 → 2 → 3 → 4 → 5 → 6 → 7.** El porqué está en la sección 7.

### Fase 1 — Separar entrenar de predecir, sin cambiar ni un número

**El problema concreto.** En `operacion.predecir()`, entrenar y predecir van en el mismo paso (`aj.ajustar` y luego
`aj.predecir`), y lo ajustado se pierde al terminar el proceso. No hay forma de «usar el modelo de ayer con los datos
de hoy». Sin eso, nada del resto del plan existe.

**Lo que NO es esta fase.** No cambia la operación: `python -m operacion` sigue igual al terminar. No cambia la
receta, ni el horizonte, ni el centinela. No entrena el modelo definitivo (eso es la fase 3).

**Pasos.**
1. Leer `notebooks/semana.py` (`Ajuste`), `notebooks/pronostico.py` (`Modelo`, `_Directo`, `LightGBM`,
   `LightGBMRel`, `SARIMAX`, `_ConExogenas`, `Control`), `notebooks/mecanismos.py` (`construir`,
   `LightGBMRelMec`, `SARIMAX` de mecanismos) y `notebooks/red.py` (`EfectoV2`).
   - Confirmar que M3s sigue el mismo patrón que la tabla de la sección 5. Si no lo sigue, escribirlo.
   - Ojo con lo global: `pr.H` decide cuántos adelantos se construyen en `_Directo.__init__`, y `_preparar()` fija
     `pr.FIN`, `pr.H` e `ix.FIN_RED`.
2. Crear un módulo nuevo en `operacion/` (por ejemplo `operacion/modelo.py`) con:
   - `entrenar(corte, combo, H) -> carpeta`: construye `sm.Ajuste` con los datos hasta `corte`, ajusta y guarda el
     artefacto. Se usa solo a mano.
   - `predecir_congelado(origen, combo, carpeta) -> (Q, normal)`: carga el artefacto, construye las entradas con los
     datos hasta `origen` y predice **sin llamar a ningún ajuste**.
   - Para los coeficientes de `EfectoV2`: guardarlos en el artefacto y permitir que `_dias()` los use en vez de
     llamar a `estimar`. Hacerlo con el menor cambio posible y sin alterar los cuadernos.
3. El artefacto, en una carpeta propia, `salidas/modelo/<corte>_<combo>/`:
   - LightGBM: `booster_.save_model` en texto, por adelanto y cuantil, o `joblib` si es más simple; justificar la
     elección en `CONTEXTO.md`;
   - SARIMAX: `params` y `cols`;
   - el control;
   - los coeficientes de `EfectoV2`;
   - `meta.json`: corte, combo, H, commit, versiones (Python, lightgbm, statsmodels, numpy, pandas), sha256 de la
     serie de entrenamiento y la fecha.
4. Decidir dónde vive el artefacto en git. Puede pesar decenas o cientos de MB. Lo más probable es dejarlo fuera de
   git, con una línea comentada en `.gitignore` según la regla 2 de `CLAUDE.md`, y su huella en `CONTEXTO.md`. Si
   pesa poco, versionarlo. Escribir la decisión.
5. **No tocar** `notebooks/pronostico.py` ni `notebooks/semana.py` de forma que cambien los resultados publicados.
   Si hay que añadirles algo (por ejemplo, un método para guardar), que sea aditivo, y comprobarlo con la prueba 1.

**Entregable.**
- El módulo nuevo.
- Un artefacto de prueba (no el definitivo).
- Una entrada en `CONTEXTO.md` con los tiempos y la RAM medidos.
- La sección «Artefacto» en `operacion/docs/OPERACION.md`.

**Pruebas de aceptación.**
1. **Equivalencia.** Para M3s y para C0r, en 3 orígenes (al menos uno de 2025 y uno de 2026, y uno con red y
   quiebre activos si los hay), `entrenar(corte=o)` + `predecir_congelado(o)` da cuantiles **idénticos** a los del
   camino actual (`Ajuste.ajustar(o)` + `Ajuste.predecir(o)`), con diferencia relativa < 1e-9. Lo mismo para la salida
   de `_dias()` con los coeficientes de `EfectoV2` congelados en el origen.
2. **No se ajusta nada.** Durante `predecir_congelado`, `lightgbm.LGBMRegressor.fit`, el `fit` de SARIMAX de
   statsmodels y `np.linalg.lstsq` dentro de `EfectoV2` se sustituyen por funciones que lanzan error, y la predicción
   sale igual.
3. **Ve los datos frescos.** Con un origen 8 semanas posterior al corte, el `nivel` de la fila de adelanto 1 es igual
   a la media de 28 días de `log(y)` calculada aparte, con los datos nuevos. Las columnas externas de esa fila son las
   del `contexto_diario` a esa fecha.
4. **Proceso limpio.** Un proceso de Python nuevo, que solo carga el artefacto, reproduce la prueba 1.
5. **Coste.** Tiempo y RAM máxima (`psutil`) de `entrenar` y de `predecir_congelado`, en este equipo y con 3
   repeticiones, escritos en `CONTEXTO.md`.

**Parar y preguntar si:** la equivalencia no se logra; M3s guarda estado global que no se puede serializar; o el
artefacto pesa más de 1 GB.

### Fase 2 — Retroprueba del régimen congelado: una corrida, cuatro lecturas

**Depende de:** la fase 1.

**El problema concreto.** Todo lo que se supone del diseño nuevo está sin medir:
- hasta dónde llega una predicción confiable;
- cuánto debe durar;
- si la regla de 5 de 7 salta cuando debe y calla cuando debe;
- qué tan anchos son de verdad los rangos.

La validación existente reajustaba cada 4 semanas y solo llegaba a 28 días, así que no responde nada de esto.

**Lo que NO es esta fase.** No compara contra el reentrenamiento semanal (D10). No prueba variantes del modelo. No
toca la operación.

**Antes de calcular** (regla de evidencia de `CLAUDE.md`):
1. Añadir una fila a `patrones/datos/variables.csv` (columnas `variable,ventana_dias,familia,primaria,motivo`), con
   `variable = retroprueba_congelada`, que describa los cortes, el criterio D12, la regla D5, D13 y `W`.
2. Escribir en `CONTEXTO.md` una entrada razonada: qué se espera y qué haría cambiar de opinión.

Las dos cosas, con fecha anterior a los resultados.

**Diseño.** Debe reproducir la operación futura.
- **Dos cortes**, cada uno con M3s y C0r:
  - artefacto entrenado con datos hasta **2024-12-31** y congelado durante todo 2025;
  - artefacto entrenado con datos hasta **2025-12-31** y congelado en 2026, hasta el último día completo de la
    extracción.
- **H = 180 días.** Coste estimado: unos 15 minutos por entrenamiento (el de 78 días tardó 373 s); 4 entrenamientos
  en local, de uno en uno. Medirlo.
- **2025 contiene** la caída de Nueva EPS de noviembre; **2026**, la de julio y el sismo. Son las pruebas de estrés
  del centinela.
- **El total del día sin la corrección de la red** es la lectura principal: es el modelo puro. La corrección con la
  red va como lectura secundaria, y solo con lo que se sabía en cada origen. Si el registro no permite saberlo,
  escribirlo como límite y no inventarlo.
- **Límite que hay que escribir, no resolver:** algunas fuentes externas se publican con retraso (SIVIGILA,
  MinDefensa), y la retroprueba ve valores que en su día no estaban. La operación ya mitiga lo de salud con la semana
  epidemiológica completa (`ix.salud_semana_completa`); usarla igual.

**Las cuatro lecturas.**
- **a. Horizonte confiable `h*`.** Orígenes semanales. Desde cada uno, predecir de 1 a 180 días con
  `predecir_congelado`. Por adelanto, calcular:
  - el error medio del día;
  - la cobertura del rango del 80 %;
  - el error de «lo habitual».

  `h*` es el mayor adelanto en que se cumple D12 **en los dos años**. Si el criterio se rompe y luego vuelve a
  cumplirse a adelantos mayores, `h*` es el primer adelanto en que se rompe. Reportar también la curva completa.
- **b. Envejecimiento.** El error a adelanto fijo (7, 28 y `h*`) según los meses transcurridos desde el corte. Dice
  si un solo entrenamiento aguanta un año. Es información para el profesional de D2, **no un disparador**.
- **c. Centinela.** Simular la operación día a día, en cada año por separado:
  - empezar con una predicción desde el corte;
  - cada día con dato real, contar cuántos de los últimos 7 días **de la predicción vigente** cayeron fuera del
    rango. Hacen falta al menos 7 días verificados de esa predicción;
  - con 5 o más, predicción nueva desde ese día (D6). Aplicar también la vigencia `V` y D13.

  Medir:
  - cuántas veces salta y cuándo;
  - falsas alarmas: saltos sin choque conocido;
  - demora, en días, en los choques conocidos;
  - cuánto tarda el error en volver a lo normal tras cada recálculo;
  - cuántas veces se marcaría «requiere revisión».
- **d. Rangos.** Cobertura y ancho por nivel (día, semana, franja y hora, Nueva EPS, Sura y otras) y por adelanto.
  - Si correr `_dias()` en todos los orígenes con 180 días es muy lento, usar un subconjunto de orígenes y decirlo.
  - Comparar el rango por hora con el piso de Poisson: con media `μ`, el rango del 80 % de un modelo perfecto.

**Vigencia.** `V = h* − 28`.
- Si `h* ≤ 28`, el diseño no funciona tal cual: **parar y llevarlo al propietario.**
- Si `V` sale muy corta (menos de 7 días), también.

**Entregable.**
- Un cuaderno nuevo en `notebooks/` (siguiente número libre), con la lectura escrita al lado de cada figura y voz de
  tesis impersonal («se encontró que»). Sin «propietario», sin pasos siguientes y sin tono de chat.
- Las tablas en `salidas/pronostico/congelado/`.
- Una entrada en `CONTEXTO.md` con `h*`, `V`, la tabla del centinela, el envejecimiento y los rangos.

**Pruebas de aceptación.**
1. El preregistro y la entrada razonada tienen fecha anterior a los resultados (`git log` lo muestra).
2. Las cuatro lecturas existen para los dos años y los dos modelos.
3. La simulación del centinela está en una función reutilizable: la fase 4 la usa como referencia.
4. **El propietario aprueba `h*` y `V`.** Se le presenta la curva de la lectura a y la tabla de la c.

**Parar y preguntar si:**
- `h* ≤ 28`;
- el centinela no salta en ninguno de los choques conocidos;
- el centinela salta más de una vez al mes sin choque;
- el envejecimiento muestra que el artefacto se degrada fuerte en pocos meses. Eso pondría en duda D1-D2, y lo decide
  el propietario.

### Fase 3 — El entrenamiento único definitivo

**Depende de:** las fases 1 y 2 (`H = h*`).

**El problema concreto.** Hace falta el artefacto con el que va a operar el producto, entrenado una sola vez y con
todo lo que se sabe, incluidas las caídas de Nueva EPS (D1).

**Lo que NO es esta fase.** No cambia la receta. No construye herramientas de reentrenamiento (D2).

**Pasos.**
1. **Comprobación honesta antes de congelar:**
   - entrenar M3s y C0r con corte 8 semanas antes del último día completo;
   - predecir esas 8 semanas con `predecir_congelado` y datos frescos, con orígenes semanales;
   - comprobar que el error y la cobertura caen dentro de lo que dio la fase 2 para 2026.
2. Si la comprobación pasa: entrenar M3s y C0r con corte en el último día completo y `H = h*`. Es **el**
   artefacto.
3. Escribir en `operacion/docs/ENTRENAMIENTO.md`, en una página:
   - cómo se hizo: datos, corte, comando, tiempos y huellas;
   - qué tendría que comprobar un profesional si algún día decide reentrenar: las pruebas 1 a 4 de la fase 1 y la
     comprobación de 8 semanas;
   - la advertencia de abajo.

   Sin automatizar nada.

**Advertencia que debe quedar escrita en `ENTRENAMIENTO.md`.** Con solo dos episodios de Nueva EPS, el modelo aprende
cómo se ve el hospital **después** de una caída, no a anticiparla.
- Las señales que podrían anticiparla (medidas de la Supersalud y afiliación BDUA, en `calendarios/capturas.py`) se
  guardan desde octubre de 2026 y no tienen historia.
- La defensa ante una caída es otra: el nivel fresco, el centinela y el registro de la red (`datos/eventos_red.csv`
  + `--ajustar`).

**Entregable.**
- Los dos artefactos definitivos (M3s y C0r).
- `ENTRENAMIENTO.md`.
- Una entrada en `CONTEXTO.md` con la comprobación de 8 semanas y las huellas.

**Pruebas de aceptación.**
1. Las pruebas 1 a 4 de la fase 1 pasan sobre los artefactos definitivos.
2. La comprobación de 8 semanas queda dentro de lo esperado según la fase 2, con los números escritos.

**Parar y preguntar si:** la comprobación de 8 semanas da clarísimamente peor que la fase 2 (por ejemplo, un error
más de 3 puntos por encima o una cobertura por debajo del 60 %).

### Fase 4 — La operación nueva: datos frescos, centinela y recálculo sin reentrenar

**Depende de:** la fase 3.

**El problema concreto.** Hoy `python -m operacion`:
- reentrena cada vez;
- tiene el horizonte atado a diciembre;
- tiene un semáforo de 28 días que no dispara nada.

Hay que cambiarlo por el ciclo de D3 a D7 y de D13 a D14.

**Lo que NO es esta fase.** No cambia los rangos ni su presentación (fase 5). No decide el servidor (fase 7).

**El ciclo nuevo** (`operacion/__init__.py`, `operacion/__main__.py`):
1. **Datos.** La extracción del hospital (diaria) y `contexto` (cada fuente a su ritmo) siguen como están. La
   operación solo lee.
2. **Verificar.** `verificar()` como hoy.
3. **Centinela.** Sobre la predicción vigente del modelo principal (`MODELO`): contar cuántos de sus últimos 7 días
   verificados cayeron fuera de su rango, en `verificacion.parquet`, con el mismo rango que se le mostró a urgencias.
   Hacen falta al menos 7 días verificados de esa predicción. La ventana **se reinicia** con cada predicción nueva.
4. **¿Predecir?** Solo si:
   - no hay predicción vigente (motivo `inicial`);
   - a la vigente le quedan menos de `W = 28` días dentro de `h*` (motivo `vigencia`);
   - o el centinela cuenta 5 o más (motivo `centinela`).

   Se predicen **los dos modelos** con el mismo origen y `predecir_congelado`, hasta `h*`. Si nada de eso se cumple,
   no se predice nada.
5. **D13.** Si el motivo es `centinela` y la predicción anterior también se hizo por centinela hace 14 días o menos,
   `estado.json` lleva `revision_profesional: true` y el semáforo lo muestra en rojo con ese texto.
6. **Guardar** la corrida como hoy, sin rehacerla nunca, con `motivo`, `artefacto` (carpeta y huella), `h_conf` y
   `vigente_hasta` en `resumen.json`.
7. **Semáforo** (`estado.json`):
   - señales nuevas: predicción vigente (origen, motivo, días que le quedan) y centinela (k de 7 y fechas de los días
     fallidos);
   - la señal de acierto pasa de 28 días a los días de la predicción vigente;
   - se mantienen la antigüedad del dato, Nueva EPS, salud y la comparación M3s/C0r a los 84 días.
8. **Exportar a Power BI** (`python -m operacion.powerbi`) al final de cada ciclo en que haya cambios. Los CSV llevan
   la vigencia, el motivo y el estado del centinela.

**Lo que se quita o cambia:**
- `horizonte()` y `HORIZONTE_MAX` dejan de existir, y `h*` sale del artefacto;
- `predecir()` ya no llama a `Ajuste.ajustar`;
- el camino que entrena queda solo en `python -m operacion --entrenar`, documentado como «solo un profesional»
  (fase 3) y fuera de cualquier tarea programada;
- `--ajustar` (red) se mantiene;
- los mensajes «Reentrenando…» desaparecen.

**Archivos que toca:**
- `operacion/__init__.py`, `operacion/__main__.py`;
- `operacion/powerbi.py`, solo para añadir campos; la presentación es de la fase 5;
- `operacion/tablero.py`, para mostrar la vigencia y el centinela;
- `contexto/operacion_semanal.cmd` y su `.xml`, que pasan de «semanal» a «diario: verificar + centinela + predecir
  si toca»;
- `operacion/docs/OPERACION.md`, reescrito.

**Pruebas de aceptación.**
1. **Ningún ajuste.** Con los `fit` de lightgbm y statsmodels y `np.linalg.lstsq` de `EfectoV2` sustituidos por
   funciones que fallan, un ciclo completo de la operación corre sin error.
2. **Repetición del pasado.** Un modo de prueba con fecha simulada (por ejemplo `--hoy AAAA-MM-DD`) recorre 2025 y
   2026 con los artefactos de la fase 2. El centinela salta en las **mismas fechas** que la simulación de la fase 2
   (lectura c), y los motivos coinciden.
3. **Idempotencia.** Correr el ciclo dos veces el mismo día, o cada día dentro de la vigencia sin fallos, no crea
   predicciones nuevas.
4. **Visible.** `estado.json`, el tablero de Streamlit y los CSV de Power BI muestran la vigencia, los días que le
   quedan, el motivo de la última predicción y el estado del centinela.
5. **Bitácora.** `CONTEXTO.md` tiene la entrada de la fase y `OPERACION.md` está reescrito.

**Parar y preguntar si:** la prueba 2 no coincide con la fase 2 y la diferencia no se explica por un error de la
simulación.

### Fase 5 — Rangos útiles y probabilidades honestas en el tablero

**Depende de:** la fase 2 (lectura d) y la fase 4 (los campos nuevos del exportador).

**El problema concreto.** El propietario vio en Power BI un «89 %» y rangos tan anchos que no informan (D8). Medido
el 2026-10-19 en `salidas/powerbi/verificacion_hora.csv` (1.008 horas):
- **El 89 % es la medida `P acierto hora`**: el 88,6 % de las horas cayó dentro del rango q10-q90 por hora. Su ancho
  mediano es de 7 pacientes, con una media real de 7,5 por hora.
- **En la hora, el ancho no es culpa del modelo.** Las llegadas individuales son azar (Poisson). Con media 7,5:
  - un modelo **perfecto** daría un rango del 80 % de unos 4 a 11 pacientes;
  - un rango de 6 a 9 acertaría el 54 %.

  Ese rango no se estrecha mejorando el modelo. Hay tres caminos:
  - anunciar una probabilidad menor: un «rango más probable» del 50 %, de q25 a q75. Hoy `_dias()` solo guarda q10,
    q50 y q90 por hora, así que hay que añadir q25 y q75;
  - agrupar horas en franjas, donde el azar pesa menos;
  - quitar la sobrecobertura que meten los límites enteros inclusivos: 88,6 % frente al 80 % nominal.
- **En el día es distinto.** El rango mide el 25-30 % del valor central y la cobertura medida es del 76 % (M3s, 620
  días; `CONTEXTO.md` «2026-10-19 (Power BI, rangos)»). Ahí no sobra ancho: estrecharlo exige menos error, no
  recalibrar.
- **El rótulo engaña.** La píldora «X % de probabilidad» (`D píldora`, `P acierto día`, `P acierto hora` y
  `P acierto aseguradora`, en `prediccion.SemanticModel/definition/tables/Medidas.tmdl`) muestra la **cobertura
  pasada**, no la probabilidad de que la predicción sea correcta.

**Lo que NO es esta fase.** No toca el modelo ni los artefactos.

**Pasos.**
1. Con la lectura d de la fase 2, calcular para cada nivel (día, semana, franja, hora y aseguradora) dos cosas:
   - qué probabilidad real tiene el rango que se muestra hoy;
   - qué ancho tendría un rango con el 50 % y otro con el 80 % **reales** (calibrados con la retroprueba, por nivel
     y por tramo de adelanto).
2. Presentar al propietario, con números, dos o tres formatos posibles por nivel. Por ejemplo: «día: 165-195 (50 %)
   y 150-210 (80 %); hora: 6-9 (50 %)». **El propietario elige.**
3. Implementar lo elegido en `_dias()` (cuantiles nuevos si hacen falta), en `operacion/powerbi.py` y en el modelo
   de Power BI. Rotular la probabilidad como lo que es: «acierta X de cada 10 días».
4. El modelo de Power BI se edita con el flujo ya establecido:
   - abrir Desktop;
   - cambiar el modelo con el MCP;
   - `ExportToTmdlFolder` a una carpeta temporal;
   - cerrar Desktop **sin guardar**;
   - copiar el TMDL y las páginas PBIR, que se regeneran con `python -m operacion.powerbi_pagina`, con Desktop
     cerrado;
   - reabrir.

   Detalle en `operacion/docs/POWERBI.md`.

**Pruebas de aceptación.**
1. Para cada nivel, la cobertura medida en la retroprueba está a ±5 puntos de la probabilidad que se anuncia.
2. Cada rango se muestra con su probabilidad, y la probabilidad está rotulada como tasa de acierto.
3. El propietario ve el tablero y lo aprueba.

### Fase 6 — Cadencia de los datos y recursos medidos

**Depende de:** la fase 4, porque se mide el diseño nuevo, no el viejo.

**El problema concreto.** Para decidir entre el servidor actual (casi saturado) y una máquina nueva de BI hace falta
saber cuánto consume cada pieza. Hoy solo hay tiempos sueltos, y **nunca se ha medido la RAM**.

**Pasos.**
1. Un envoltorio de medición que lance cada pieza como subproceso y muestree con `psutil`: tiempo, CPU (porcentaje y
   núcleos usados) y RAM máxima, de cada proceso y de sus hijos.
2. Medir, con 3 repeticiones en este equipo:
   - cada fuente de `python -m contexto`;
   - la extracción del hospital;
   - el ciclo diario sin predicción (verificar + centinela);
   - el ciclo con predicción (`predecir_congelado` de los dos modelos + `_dias()`);
   - el exportador de Power BI.

   El entrenamiento, una sola vez y como referencia: no se automatiza.
3. Confirmar D14: la extracción diaria y el contexto semanal o dos veces por semana. Si algo cuesta más de lo
   esperado, llevarlo al propietario.
4. Ajustar las tareas `contexto/*.xml` a la cadencia. **Registrarlas en el Programador de tareas requiere
   autorización del propietario**: preguntar.

**Entregable.** `operacion/docs/RECURSOS.md`: una tabla pensada para TI, con el pico de RAM, la CPU, la duración y
la frecuencia de cada pieza, y el total por semana.

**Pruebas de aceptación.**
1. La tabla tiene las 3 repeticiones por pieza, con la mediana y el máximo.
2. La cadencia queda escrita en `CONTEXTO.md`.

### Fase 7 — Dónde se monta

**Depende de:** la fase 6.

No es desarrollo: es la conversación con TI, con `RECURSOS.md` en la mano. Las dos opciones:
- el servidor existente (habló con Leandra: hoy se satura);
- una máquina nueva para BI (Mateo).

Lo que ya se sabe que hace falta, sea cual sea:
- autorización institucional antes de mover datos reales;
- una cuenta con lectura en la base `DWSES` para la extracción;
- Python con las versiones del artefacto;
- una ruta para los CSV que lea Power BI.

El documento para el superior en Claude Docs (enlazado en `HANDOFF.md`) se actualiza con el diseño nuevo.

---

## 7. ¿Se pueden trabajar fases en paralelo? No: es secuencial

Recomendación de Claude, aceptada como regla del plan:
1. **Cada fase usa lo que produce la anterior.** La 2 necesita la separación de la 1; la 3 necesita el `h*` de la 2;
   la 4 necesita el artefacto de la 3; la 5 necesita la lectura d de la 2 y los campos de la 4; la 6 mide lo que deja
   la 4.
2. **Comparten archivos.** Las fases 1, 4 y 5 tocan `operacion/` y `operacion/powerbi.py`, y todas escriben
   `CONTEXTO.md`, `HANDOFF.md` y la tabla de estado. Dos sesiones a la vez sobre el mismo árbol de trabajo se pisan.
3. **El equipo no lo aguanta.** Tiene 15,9 GB de RAM, no tiene GPU y aguanta una sola cosa pesada a la vez (regla 6
   de `CLAUDE.md`). Las fases 2 y 3 entrenan modelos de 180 días; dos a la vez se estorban o tumban el equipo.

Lo único que se puede adelantar sin riesgo es **pensar**: mientras corre el cálculo largo de la fase 2, la misma
sesión puede ir escribiendo el cuaderno. Abrir otra sesión para otra fase, no.

## 8. Fuera de este plan

- Reentrenamientos automáticos, variantes de la receta y experimentos con el modelo. La prueba aislada `M3s-cf`
  (catástrofe por fecha) de `HANDOFF.md` sigue aislada y no entra en la operación.
- n8n.
- Fuentes nuevas, otros hospitales y otras fases del hospital (consulta, hospitalización), salvo pedido expreso.

## 9. Estado

Cada sesión actualiza esta tabla **en cuanto** cambia algo, con la fecha y una línea.

| Fase | Qué | Depende de | Estado |
|---|---|---|---|
| 1 | Separar entrenar de predecir | — | Pendiente |
| 2 | Retroprueba congelada: `h*`, `V`, centinela y rangos | 1 | Pendiente |
| 3 | Entrenamiento único definitivo | 1, 2 | Pendiente |
| 4 | Operación nueva con centinela | 3 | Pendiente |
| 5 | Rangos y probabilidades en el tablero | 2, 4 | Pendiente |
| 6 | Cadencia y recursos | 4 | Pendiente |
| 7 | Dónde se monta | 6 | Pendiente |
