# Handoff — dónde está todo ahora

**Este archivo se reescribe.** Describe el presente, no la historia. La historia —qué se
decidió, cuándo y por qué— está en `docs/CONTEXTO.md` y esa solo crece.

Regla 10 de `CLAUDE.md`. Se actualiza **durante** la sesión, cada vez que algo cambia de
estado: una sesión que se corta a la mitad tiene que dejar esto utilizable igual.

**Última actualización: 2026-10-16.**

---

## HECHO (2026-10-16): dos correcciones de M3s (red fuera, salud con rezago) — NO PASAN — versionado en `main`

**Encargo:** entrada «Dos correcciones de M3s» de `CONTEXTO.md` (16-10). Resultado en «(correcciones)» y «(rezago)».
- **Rezago de la salud medido: 1 semana.**
- **Preregistro** `m3s_correcciones_red_salud`, escrito antes de calcular.
- **Veredicto: ninguna variante mejora a M3s en 2025** (M3s-r +0,015 puntos, M3s-rs +0,087; hacía falta −0,1). En 2026
  ninguna empeora. **No se cambia nada en la operación.**
- **Código** (no cambia nada de lo publicado; M3s y C0r reproducen exactamente las corridas del 14-10):
  - experimentos `m3s_r` y `m3s_rs` (`pronostico.py`);
  - combos `M3s-r` y `M3s-rs` (`semana.py`, en `DIAGNOSTICO`);
  - `indices.REZAGO_SALUD` y `salud_con_rezago`, por defecto 0;
  - `mecanismos.columnas(dias, rezago_salud)`.
- **Validación:** `notebooks/validacion_anual.py` (`--resumir` rehace las tablas en segundos) →
  `salidas/pronostico/correcciones_red_salud/`. Sin procesos corriendo.
- **`operacion/` no se tocó.** La corrida del lunes 19-10 sigue siendo M3s + C0r.
- **Sigue abierto:** el lunes M3s lee una semana epidemiológica a medias. Corregirlo como dato de la operación exige
  una fila propia.

---

## Lo demás del 16-10: lunes y pendientes del propietario

**Qué se probó:** M3s-r (sin las columnas `ext_g_m_red_*`, endógenas) y M3s-rs (M3s-r con la salud leída con 1 semana
más de rezago). El porqué está en `CONTEXTO.md`, entrada «2026-10-16 — Dos correcciones de M3s»; el resultado, en la
sección de arriba: **ninguna pasa** y `operacion/` no cambia.

**Lo que sigue son dos propuestas, cada una con su propia fila antes de medir:**
1. la semana epidemiológica a medias como dato de la operación (por ejemplo, no usar en el origen una semana con menos
   del 90 % de su valor esperado), sin cambiar el modelo;
2. la catástrofe por fecha del evento (propuesta 1 de «(reacción)»), que es donde M3s-r pierde (sismo +0,41 puntos).

**Versionado (16-10):** todo lo del 16-10 está en `main` (validaciones de 2026 y anual, experimentos m3cal, m3s_r y
m3s_rs, las dos filas de `variables.csv`, `CONTEXTO.md`, este archivo y los datos de las tareas programadas).
`NLP/modelo.py` **sigue fuera, a propósito**: apunta Ollama al servidor de MedGemma y es un cambio ajeno.

**Hecho el 16-10:**
- **Validación de 2026 de la operación semanal** (entrada del 16-10 de `CONTEXTO.md`): M3s **se mantiene** frente a
  C0r. A 1-7 días, como se entrega: MAPE 8,57 % frente a 8,51 %, y cobertura 80,4 % frente a 82,5 %; DM p = 0,60.
  - Con la extracción diaria, el error de la semana siguiente (8,5 %) es menor que el de 15-21 días que se usaba antes
    (10,5 %).
  - Lo que resta viene de la red (julio) y del sismo (agosto) dentro de M3s; el calendario suma.
- **Tareas programadas funcionando:** la diaria corrió sola el 16-10 a las 07:42 (el equipo estaba apagado a las
  06:30), con resultado 0. La semanal corre por primera vez el **lunes 19-10 a las 07:00**: revisar su resultado
  (`Get-ScheduledTaskInfo triage_operacion_semanal`) y la corrida nueva en `salidas/operacion/corridas/`.

**Pendientes del propietario, sin cambios:**
- las fiestas con el estado vacío (Belalcázar el 26-oct y la Noche del Fuego el 7-dic);
- la lista por confirmar;
- las revisiones del pasado que solo se aplican con `--rehacer`;
- las fichas por factor desde `calendarios/docs/LITERATURA_ENTORNO.md`, propuestas el 15-10 para que cada cambio
  de modelo parta de la literatura. El propietario cuestionó el método («prueba y error»); ver la respuesta en la
  sesión del 15-10 y la entrada «(reacción)».

---

## HECHO (2026-10-15): el contexto externo se actualiza solo y la operación usa M3s — SIN COMMIT

**Decisión del propietario.** Entradas del 2026-10-15 de `CONTEXTO.md`, empezando por la de abajo. Power BI queda
para después.

**Qué hay ahora:**
- **`python -m contexto`** (manual en `contexto/docs/CONTEXTO_EXTERNO.md`):
  - 16 pasos, cada uno con su frecuencia, que actualizan todas las fuentes externas y el hospital;
  - deja `salidas/contexto/contexto_diario.csv` (2020-2028, 45 columnas: lo mismo que ve M3s) y `frescura.csv`;
  - `--todo` tarda unos 130 s sin el hospital; la extracción, unos 16 s.
- **Todos los scripts de `calendarios/` son incrementales** (`calendarios/actualizacion.py`): no reescriben el
  pasado. Las revisiones del pasado solo se aplican con `--rehacer`, y eso lo decide el propietario.
- **Actualizadores nuevos** (reglas y acierto en `calendarios/docs/ACTUALIZADORES.md`):
  - eventos y Feria, fiestas y calendario escolar. Proyectan 2027-2028 como `estimada_auto`; nunca tocan filas
    existentes;
  - desastres: terremoto desde el USGS, con criterio preregistrado;
  - pluviómetro IDEAM (`clima/clima_ideam.py`).
- **La operación usa M3s** como principal y C0r como vara (preregistro `operacion_m3s_contexto_automatico`).
  - Regla de vuelta atrás a los 84 días comunes; la primera evaluación, hacia mediados de enero de 2027.
  - Corridas `2026-10-14_M3s` y `2026-10-14_C0r`. Semáforo con «Contexto externo» y «Comparación».
- **Arreglado al integrar** (entrada «(cierre)»): la red de M3s congelada en el 20-sep (`indices.FIN_RED`) y las filas
  incoherentes del clima unificado.

**Esperando al propietario:**
1. ~~Registrar las tareas de Windows~~ **Hecho por el propietario el 15-10.**
   - `triage_contexto_diario` (06:30) y `triage_operacion_semanal` (lunes 07:00) están registradas;
     `triage_capturas_semanales` está deshabilitada.
   - Lanzada a mano desde el Programador, la diaria terminó con resultado 0, sin ventana.
   - Corrió sola el 16-10 a las 07:42 (el equipo estaba apagado a las 06:30), con resultado 0, en 112 s.
   - **Validación de 2026, hecha** (`CONTEXTO.md`, entrada del 2026-10-16; `notebooks/validacion_2026.py`;
     `salidas/pronostico/validacion_2026/`). Veredicto preregistrado: M3s **se mantiene** frente a C0r.
     - A 1-7 días, como se entrega: MAPE 8,57 % frente a 8,51 %, y cobertura 80,4 % frente a 82,5 %.
     - Diebold-Mariano: p = 0,60.
     - Lo poco que pierde viene de las columnas de red (julio) y de catástrofe (sismo de agosto) dentro de M3s.
   - **Pendiente detectado:** la corrida del lunes lee la semana epidemiológica a medias, lo que hunde el índice de
     salud unas 5 desviaciones. Hay que leer la última semana completa. (16-10: leerla como variante del modelo,
     M3s-rs, no pasó la regla; ver arriba.)
2. **8 filas de fiestas escritas a mano tienen el estado vacío y el modelo las ignora.** Entre ellas, Belalcázar
   (26-oct a 2-nov) y la Noche del Fuego de Salamina (7-8 dic 2026). Ponerles `programado` es una decisión del
   propietario.
3. **Lista por confirmar** (`salidas/contexto/por_confirmar_*.csv`): 7 fechas en los próximos 60 días. El calendario
   escolar oficial de 2027 sale a finales de octubre.
4. **Revisiones del pasado sin aplicar:**
   - NASA, de mayo a agosto de 2026;
   - el desplazamiento de Open-Meteo y ERA5;
   - la magnitud del sismo del 29-sep;
   - los 4 días de agosto inflados ×5/3 en el clima unificado.

   Se aplican con `--rehacer`, que mueve el pasado.
5. **Autorizar el commit**, y decidir qué hacer con `NLP/modelo.py`, que trae un cambio ajeno.

6. **Prueba de reacción** (`CONTEXTO.md`, «(reacción)»): el calendario funciona; salud, red, catástrofe y social no
   se comportan como mecanismos. Decidir cuáles de las cinco propuestas se preregistran y validan.

**Límites:**
- El umbral del terremoto se fijó conociendo el único caso real.
- La red v2 y el rango W están validados sobre C0r, no sobre M3s.
- MinDefensa publica más tarde de lo que M3s lee: la columna social queda vacía en el origen.
- El SARIMAX de M3s avisa de que no converge.

---

## HECHO (2026-10-14): la red de urgencias corrige sin reentrenar (v2, en operación)

**Pedido del propietario.** Integrar como variables del momento, sin reentrenar, el estado de la red de urgencias de
Manizales: cierres y reaperturas a una aseguradora, en el SES y fuera. Probar si mejora la precisión de 2026 y verlo
en el tablero, por aseguradora y por hora. Revierte la exclusión del convenio del 13-10.

**Cómo quedó** (`CONTEXTO.md`, entradas del 14-10, de la primera a la (5)):
- **v1** (solo el registro de prensa): no pasó su regla. El fin mal fechado del cierre del SES (E25) dañó abril de 2026.
- **v2** (preregistro `red_de_urgencias_v2`):
  - el estado del convenio SES–Nueva EPS se **mide** con los ingresos no urgentes de la base
    (`salidas/ingresos_entidad.parquet`, `python -m extraccion --ingresos`, también dentro de `--series`);
  - el registro `datos/eventos_red.csv` solo aporta lo **anunciado** que todavía no se ve en los datos;
  - los otros hospitales cuentan solo si el SES atiende a Nueva EPS.
- **v2 pasó la regla.** A 15 días, 2026: error del día de 11,6 % a 10,2 %, rango del 71 % al 77 % y Nueva EPS de
  25,6 % a 20,3 %. 2025 también mejora (10,3 % → 10,0 %). Julio de 2026 pasa de 15,2 % a 6,8 % y abril ya no se daña.
- `operacion.USAR_RED = True` (v2). `python -m operacion --ajustar` reaplica el registro y el estado medido a la última
  corrida, sin reentrenar, y guarda `ajustes/<fecha_hora>.parquet`. Último: `2026-10-14_1501`. Para los días que
  vienen, el factor es 1: el SES atiende a Nueva EPS según los datos y no hay episodios anunciados.
- Tablero:
  - «Cómo ha predicho» compara el modelo solo con la v2A (2026: 11,1 % → 9,9 %);
  - el detalle del día muestra los episodios en curso y un mapa de calor de aseguradora × hora.

  Probado con AppTest, sin excepciones.

**Límites:**
- es una segunda mirada a 2025-2026: la confirmación es prospectiva;
- el coeficiente sale atenuado: julio bajó un 26 % y la caída real fue del 45 %;
- una reapertura sin anuncio solo se ve con el rezago de los datos;
- diciembre de 2025 sigue en ~20 %.

**Versionado en el commit 7d1b434 (rama modelos-afinados).** Pendiente: la revisión del tablero con el propietario.

**Esperando al propietario:**
- revisar el tablero (http://localhost:8502 o `operacion\tablero.cmd`);
- digiturno: nombre de la base y permiso (no está en `DWSES`; las otras 15 bases dan «sin acceso»);
- mantener `datos/eventos_red.csv` al día (guía en `operacion/docs/OPERACION.md`).

**Resiliencia (14-10, `CONTEXTO.md` (8)).** Se mide en semanas de recuperación tras cada golpe: 32 sin red, 28 con
la v2. Julio pasa de 3 semanas a 0.
- El reanclaje tras un quiebre **no entró**: el sismo lo engañó.
- El rango más ancho tras un quiebre **sí entró** (`operacion.RANGO_QUIEBRE`).
- Último ajuste guardado: `ajustes/2026-10-14_1639`.

**Digiturno = `DIM_HCNCONTRDT` (14-10, `CONTEXTO.md` (7)).** Hay 5-7 % de solicitudes de triage no atendidas.
- Extracción: `python -m extraccion --turnos` → `salidas/turnos_triage.parquet`.
- Patrones descriptivos: la espera duplica el abandono; pico a las 13 h; madrugada alta con espera corta.
- **Pendiente:** el análisis formal de por qué se van, la predicción de no atendidos por hora y que urgencias o
  sistemas confirme el significado de `HCCESTADO`.

**Foco fijado por el propietario (14-10):** solo la precisión del total del día y del reparto por aseguradora del SES.
Las indicaciones son:
- **no** estudiar otros hospitales;
- **no** abrir fuentes nuevas, como `RECEPCIONES_DW`, mencionada en `CONTEXTO.md` (5) y descartada por ahora;
- el registro de la red se mantiene como está, sin ampliarlo.
---

## HECHO (2026-10-13): lo que pidió urgencias — operación autónoma, aseguradoras y tablero

**El producto** (reunión del propietario con urgencias):
- la herramienta **informa** y **urgencias decide** el personal;
- muestra el total del día, el reparto en madrugada, mañana, tarde y noche, las horas de más demanda y **de qué
  aseguradora llegan**;
- debe seguir funcionando cuando el propietario (practicante) se vaya;
- **la fase siguiente** es cuántos pasan a consulta, de esos cuántos a hospitalización y en qué especialidad
  (por ejemplo, obstetricia).

**Hecho, medido y escrito** (`CONTEXTO.md`, entradas (1) a (5) del 13-10). Todo **SIN COMMIT**.
1. **Reparto del día** (`notebooks/reparto.py`). Gana P52; el reparto queda en el piso de ruido; el rango de las
   franjas pasa al 71-83 %. Ya está en `semana.py`.
2. **Recalibrar el rango con los errores recientes no sirve.** Queda sin cambio.
3. **`DIM_TRIAGE.ASEGURADORA`** (añadida por el superior el 08-10) es una copia de `DIM_ENTIDAD.ENTNOMBRE`: no aporta.
   La base llega al 13-10. La semana prospectiva del 5 al 11 de octubre acertó: 178 anunciados contra 177,4 reales,
   con 7 de 7 días dentro del rango.
4. **Reparto por aseguradora** (`notebooks/aseguradoras.py`, fila `reparto_por_aseguradora`). Gana T4 (las últimas 4
   semanas).
   - Sura se informa bien: rango del 79-80 %.
   - **Nueva EPS falla en sus cambios de convenio:** rango del 54 % en 2026 y del 5 % en los meses de cambio.
5. **Calendario de festivos hasta 2030.** El festivo de Chiquinquirá de 2027 está por confirmar.
6. **Operación** (`operacion/`, guía en `operacion/docs/OPERACION.md`):
   - `python -m operacion [--extraer] [--estado] [--modelo M3s]`: C0r con receta fija, 28 días, corrida guardada y
     versionada, verificación y semáforo;
   - tablero: `streamlit run operacion/tablero.py` (o `operacion\tablero.cmd`);
   - primera corrida guardada: `salidas/operacion/corridas/2026-09-20_C0r/`; semáforo rojo porque los datos tienen 23
     días.
7. En `.venv` se instalaron streamlit 1.65.0, altair 6.3.0 y vl-convert 1.9.0. Están en `requirements.txt`, con
   holidays 0.105.

**Pendiente:**
- **Cuaderno 27 hecho** (`notebooks/27_el_dia_por_jornada_y_aseguradora.ipynb`, 0 errores, 6 figuras; constructor en `construir/`).
- Fila 27 de `notebooks/README.md` añadida.

**Actualizado el 13-10 por la tarde** (`CONTEXTO.md`, entrada (6)):
- `salidas/` llega al **12-10** (se reextrajo; `--series` ahora escribe también el diario y el horario);
- corrida `2026-10-12_C0r`, que predice hasta el 31-dic;
- historial de 638 días;
- tablero con tres pestañas: próximos días, cómo ha predicho y confiabilidad.

Precisión: 10-11 % de error a 15-21 días en 2025-2026. En el 21-sep a 12-oct, 5,9 % con el 95 % de los días dentro
del rango.

**Cómo verlo:** `operacion\tablero.cmd` (o `.venv\Scripts\python.exe -m streamlit run operacion	ablero.py`).

**Decidido por el propietario:**
- **no** programar la ejecución automática todavía;
- el estado del convenio hospital-EPS queda **fuera del alcance**;
- el festivo de Chiquinquirá se mantiene (Ley 2578 de 2026).

**Siguiente:**
- mostrar el calendario a urgencias y recoger qué tan cerca lo ven de la realidad;
- cada semana: `python -m operacion --extraer` a mano (unos 5 minutos) para seguir midiendo;
- la fase de consulta, hospitalización y especialidad, cuando el propietario la abra.

---

## HECHO (2026-10-08): cuaderno 26, ¿está madura la predicción? — leer esto primero

**Todo está terminado, sin procesos corriendo y SIN COMMIT** (rama `modelos-afinados`). `NLP/modelo.py` sigue con su
cambio local ajeno (MedGemma): no se toca ni se incluye.

**Qué hay.** `notebooks/26_madurez_de_la_prediccion.ipynb`, ejecutado con 0 errores (37 celdas, 5 figuras).
- Constructor: `notebooks/construir/26_madurez_de_la_prediccion.py`.
- Cálculo: `notebooks/madurez.py`. El cuaderno solo lee `salidas/pronostico/madurez/`.
- Preregistro: filas `madurez_de_la_prediccion` y `_enmienda`.
- Resultado y porqué: `CONTEXTO.md`, entradas del 08-10.

**Veredicto (criterio preregistrado): ningún uso está maduro.**
- **A (1-7 días):** casi madura; falla en el rango de la media semanal de 2026 (61 %) y en 1 alarma aislada.
- **B (15-21 días, el adelanto real):** el número sirve (10-11 % de error, por delante del control); el rango no
  (2026: 71 % de días dentro, fallos en racha).
- **C (el día alto en un nivel estable):** no le gana al calendario.
- **D (un mes desde diciembre):** empata con el calendario.
- **SPA:** en 2025 la ventaja sobre el control no se separa de la selección (p = 0,124); en 2026, sí (p = 0,027).
  M3 no se separa de C0r.

**Cómo se rehace:**
- `python notebooks/madurez.py --curva`: ~1 h con el equipo libre; esta vez tardó 3 h con dos pausas del equipo;
- `python notebooks/madurez.py`: segundos; no repite SPA;
- `--spa`: rehace SPA y MCS en ~1 min;
- después, el constructor y `nbconvert --execute`.

**Pendiente del propietario:**
1. Decir qué quiere hacer después, para leer el veredicto contra eso. La conclusión del cuaderno distingue base
   operativa (sí) de instrumento de picos (no).
2. Autorizar el commit.

Cambios de código fuera del cuaderno:
- `semana.validar` acepta `adelantos` y `archivo`; por defecto hace lo mismo;
- `arch` 8.0.0 en `.venv` y en `requirements.txt`;
- fila 26 en `notebooks/README.md`.

**Cuando el superior actualice la base:** `python notebooks/madurez.py` recalcula la tabla de prospectivas. Las de
octubre son la única prueba que nadie ha mirado.

---

## ESTADO AL CIERRE (2026-10-06, 17:00)

**Todo está detenido y guardado.** No hay procesos corriendo ni agentes vivos. Todo está en git, en la rama
`modelos-afinados`, sin subir. `NLP/modelo.py` tiene un cambio local que no es de esta sesión (apunta a MedGemma):
no se toca ni se incluye en los commits.

### 1. Modelos vigentes
| Uso | Modelo | Qué es | Cómo se corre |
|---|---|---|---|
| **De 1 a 7 días** | **M3** | C0r + mecanismos medidos (Feria días 0-4, noches festivas, fiestas a ≥ 60 km, terremoto, paro, salud pública y red con compuerta, transiciones de clima, MinDefensa con 42 días de rezago), sin la fase fuerte de la COVID | `python notebooks/mecanismos.py --exp m3_2025 --modelos sarimax_mec lightgbm_rel_mec` (`--rejilla` y `--humo` también) |
| **Respuesta semanal** | **M3s** | M3 sin las 7 variables de clima, válido con cualquier adelanto | `python notebooks/semana.py --semana <lunes> --combo M3s --hmax 28` |
| Referencia | C0r | SARIMAX + LightGBM, solo calendario, estación, nivel y memoria | `--combo C0r` |

Resultados y porqué: `CONTEXTO.md`, entradas del 2026-10-06 «Mecanismos, etapa 2» y «(cierre) M3s gana…».
- **M3:** 2025 63,2 % de acierto, contra 61,9 % de C0r. 2026, empate. Rejilla 2023-2025: Brier −4,7 [−7,7; −2,0].
- **M3s:** 2025 criterio 5,98 contra 4,46.

### 2. Lo primero que hay que hacer mañana
1. **Contarle al propietario el resultado de la prueba ciega**, en el formato que pidió (memoria
   `formato-verificacion-semanal`). Semana del 14 al 20 de septiembre, predicha con datos hasta el 31 de agosto:
   - real: media de 182,4/día; la de los 3 meses previos, 165,7;
   - **M3s, 155: falló.** Subestimó los días laborables un 17-19 %, y solo 3 de 7 días cayeron en el rango;
   - **C0r, 166: mejor.** Error del 8,9 % y 7 de 7 días en el rango.
   - Los dos acertaron la forma de la semana y la subida frente a las 4 semanas anteriores.
   - Hipótesis: el contexto congelado en un origen deprimido por el terremoto y Nueva EPS arrastra el bache.
   - Mañana y tarde, real: lunes 83/68, martes 58/66, miércoles 79/64, jueves 70/69, viernes 58/55, sábado 48/55,
     domingo 41/47. El modelo no predice la franja: reparte el día con la proporción de las 8 semanas previas.
   - Los archivos están en `salidas/pronostico/prueba_ciega/` (M3s y C0r, .md / .csv / .json).
2. **Rehacer la referencia C0r de la semana del 12 de octubre**, que se cortó al cerrar:
   `python notebooks/semana.py --semana 2026-10-12 --combo C0r --hmax 28`. Tarda unos 6 minutos.
3. **Decidir con el propietario** qué se publica cada semana: M3s solo, o M3s con C0r al lado mientras se acumulan
   semanas verificadas. Proponer, preregistrado, probar el contexto con las anomalías a cero en lugar de congelarlo
   en el origen.
4. **Cuando el superior actualice la base:** `python notebooks/semana.py --verificar 2026-10-05` (y 2026-10-12).
   Reportarlo en el formato del propietario.

### 3. Servidor con Python (en trámite)
- El equipo del servidor recibió `notebooks/servidor/modelos_pronostico.ipynb`: el código mínimo de SARIMAX
  (`statsmodels`), LightGBM cuantil (`lightgbm`) y su combinación, sin datos.
- **Prueba de instalación:** con origen 2026-09-13, el lunes 14 debe dar 220 (186-254). Versiones: Python 3.11.9,
  statsmodels 0.15.0, lightgbm 4.7.0, numpy 1.26.4, pandas 2.2.3.
- **La GPU no acelera estos modelos.** Sirven los núcleos de CPU, para paralelizar los reentrenamientos.
- Tiempos de referencia en este equipo: un ajuste de LightGBM tarda ~59 s y uno de SARIMAX ~138 s. La validación de
  2025 tarda ~48 y ~38 min.
- **Antes de enviarle datos reales al servidor, se necesita la autorización institucional.**

### 4. Cuadernos
Los 22 (00-03, 05-21 y 23) están revisados, son coherentes entre sí y tienen voz de analista. El 00 cuenta además
la historia de la predicción hasta M3, en primera persona.
- Del 00 al 13 se editan en el `.ipynb`; del 14 al 23, en `construir/` y `*_lecturas.json`.
- Qué cambió de conclusión: `CONTEXTO.md`, «Revisión de los 22 cuadernos».
- Pueden añadirse al 00 los resultados de M3s y de la prueba ciega cuando el propietario decida el punto 2.3.
- **24 (2026-10-07): de la base a un mes predicho a ciegas.** Constructor
  `notebooks/construir/24_de_la_base_al_mes_a_ciegas.py`; kernel `.venv`. Conexión a la base por defecto
  (`TRIAGE_FUENTE=base`), o el parquet con `TRIAGE_FUENTE=archivo`. **Lo guardado se ejecutó sin conexión.**
  M3s sin terremoto, entrenado hasta el 31-dic-2025, predice el 1-30 de septiembre de 2026:
  - 6,0 % de error en los 20 días con dato, frente a 12,5 % del control;
  - validación en los septiembres de 2023-2025: empata con el control (11,3 % frente a 11,2 %).
  Lee `salidas/pronostico/mes_a_ciegas/<año>.parquet`, que genera `python notebooks/mes_a_ciegas.py` (unos 15 min los
  cuatro años). **La semana del 21 al 27 de septiembre ya se verificó**, con un reporte (imagen) del propietario: 4,2 % de error y 7
  de 7 días en el rango (`CONTEXTO.md`, 07-10 noche). Esos conteos no están en `salidas/`. **Faltan el 28, el 29 y el 30.** Se completa al correr el cuaderno con la base o
  cuando el superior actualice `salidas/`. Fila `mes_a_ciegas` y `CONTEXTO.md`, 07-10 (tarde).
- **25 (2026-10-07): revisión de predicciones.** Constructor `notebooks/construir/25_revision_de_predicciones.py`.
  Marzo, julio y agosto, desde el 31-dic-2025, dan 13,1 %, 11,9 % y 20,0 % de error; septiembre, 5,6 %. Media de
  12,7 %: el 6 % de septiembre fue suerte de un mes fácil.
  **Octubre está guardado como prospectivo** en `salidas/pronostico/revision/2026-10_desde_2026-09-20.*`, más una
  tabla legible `_tabla.csv` con los umbrales «sube si más de» y «baja si menos de». No se rehace nunca: `revisar()`
  se niega.
  - **El propietario verifica octubre con una fuente externa.** Cada conteo que pase va a `datos/triage_reportado.csv`
    (fecha, triages, fuente); después se reconstruye el 25 y se ejecuta. No entra al entrenamiento.
  - **Versionado el 2026-10-07** (commit 1e85341, integrado en `main` y subido a GitHub), con las salidas de `revision/`
    forzadas con `git add -f`.

### 5. Pendientes del propietario o de fuentes
- **Defectos de fuente:**
  - la SE53-2025 del evento 998 sigue en `vigilancia_sivigila.csv.gz` (`indices.py` la anula en memoria);
  - la lluvia NASA de agosto de 2026 en `clima_completo` parece provisional.
- **Datos que faltan:** CRUE (bloqueado por reCAPTCHA), el calendario de contratación SES-EPS y los partidos del
  Once Caldas (hay 2; la fuente propuesta es la API de ESPN).
- **Hipótesis abiertas, cada una con su fila antes de probarse:**
  - el solapamiento entre la Feria y el día siguiente del 2 al 4 de enero;
  - la Feria por asegurador en j_ne / j_resto.

### 6. Cómo se trabajó hoy (por si se repite)
Un orquestador y agentes en paralelo, uno por cuaderno más uno de entrenamiento. Las reglas comunes estaban en el
scratchpad de la sesión (`REGLAS_AGENTES.md`, `TAREA_CUADERNO.md`, `COHERENCIA.md`), y el turnero (`turno.py`) dejaba
como máximo 3 procesos pesados a la vez. El scratchpad se pierde con la sesión: lo que importa ya está aquí y en
`CONTEXTO.md`.
- El agente de entrenamiento se colgó 3 veces por esperar con comandos largos. Hay que pedir siempre comandos cortos
  para vigilar.
- Las corridas largas van con `Start-Process` y log.

---

## EN CURSO (2026-10-01): presentación de avances del 2026-10-02

**El propietario quiere contar la historia a su manera.** Su versión manda (`CONTEXTO.md`, entrada
«La trayectoria contada por el propietario»): 4 etapas, de los registros a la predicción.

**HECHO: `notebooks/00_la_trayectoria.ipynb`, versión 2.** En primera persona, una prueba por etapa,
0 errores. Generador en el scratchpad de la sesión (`c00/hacer_nb.py`). Qué tiene y por qué:
`CONTEXTO.md`, entrada «Cuaderno 00, versión 2».

**Falta:**
- que el propietario lo revise, y después **armar con él el monólogo** de la exposición;
- ~~corregir los cuadernos 12, 13 y 14~~: hecho el 06-10 (rehechos por mecanismo y con el azar calibrado);
- el mecanismo Feria → «llegan porque son tantos» **no está probado**: necesita los datos del CRUE
  (pendiente #12 de este archivo).

---

## EN CURSO (2026-10-05, noche): las 6 propuestas del cuaderno 16, una por cuaderno (17-21), y después volver a entrenar (22)

**El propietario aprobó las 6 propuestas** y pidió automatizar las capturas. Estado:

| # | Pieza | Estado |
|---|---|---|
| — | **Captura automática semanal** (`calendarios/capturas.py`; tarea de Windows `triage_capturas_semanales`, lunes 08:00) | **HECHO**. Detalle en `calendarios/docs/CAPTURAS.md` |
| 17 | **Clima completo** (`calendarios/clima_completo.csv.gz`) | **HECHO** |
| 18 | **Panel de todas las EPS** | **HECHO** |
| 19 | Familias de enfermedad como índices (`notebooks/indices.py`) | **HECHO** |
| 20 | Regímenes y fenómenos como estados; **hipótesis prospectiva de El Niño** (fila `hipotesis_el_nino_2026`) | **HECHO** |
| 21 | Jerárquico por tipo de consulta: se eligen las **bandas de edad** | **HECHO** |
| 22 | Volver a entrenar y predecir con el protocolo limpio (fila `reentrenamiento_holistico`) | **EN CURSO** |

**Cuaderno 22, estado (05-10, noche).**
- **Diseños:**
  - **C0:** combinación sin contexto (ya corrida en 2025 y 2026);
  - **C1:** combinación con las 24 variables de H, experimentos `h_2025` y `h`;
  - **C2:** LightGBM con H por banda de edad (`hb<banda>_2025` y `hb<banda>`), sumados por cópula.
- **Corriendo la validación en 2025:** tres colas `Start-Process` con logs `c14/v22_q1|q2|q3.log`:
  - q1: `h_2025 sarimax`;
  - q2: `h_2025 lightgbm` y las bandas 04 y 514;
  - q3: las bandas 1544, 4564 y 65.
- **Después:**
  1. elegir con la regla preregistrada (promedio del BSS de «sube» con las dos varas, cobertura del 80 % entre
     75 y 88 %);
  2. correr **solo el elegido** en 2026;
  3. comparar contra C0.
- Si las colas se cortan, se relanza lo que falte en `salidas/pronostico/<exp>/`.

**Protocolo de los cuadernos 22 en adelante:** afinar con 2020-2024, elegir con 2025, probar una sola vez en
2026, y la prueba prospectiva.

**EN CURSO (05-10, tarde-noche): arreglos pedidos por el propietario y la respuesta semanal.**
El propietario **no puede ni debe actualizar la base**: lo hace su superior al final de la semana. **No correr
`python -m extraccion`.** Se predice con lo que hay (datos hasta el 2026-09-20) y se guarda la predicción para
verificarla después.

- **Motor:** `LightGBMRel` (`lightgbm_rel`) en `pronostico.py`, fila `motor_objetivo_relativo`. Corriendo `e1_2025` y
  `e1` (logs `c14/rel_e1*.log`). Al terminar se aplica la regla: C0r = sarimax + lightgbm_rel reemplaza a C0 si gana
  en 2025.
- **`rasgos()`** ahora admite adelantos de más de 7 días (`mem_mismo_dia`); con h ≤ 7 da lo mismo que antes.
- **Respuesta semanal:** `notebooks/semana.py`, fila `pronostico_semanal`.
  - `--validar` está corriendo (log `c14/semanal_val.log`, unas 2 h): domingos de 2025 y 2026, adelantos 1 y 15.
  - Después: `--semana 2026-10-05` **guarda** la predicción del 5 al 11 de octubre en `salidas/pronostico/semanal/`
    (versionada por excepción en `.gitignore`; no se rehace).
  - Cuando el superior actualice los datos: `--verificar 2026-10-05`.
- **Entrenamiento con fechas escogidas (pedido del propietario: no descartar el contexto):**
  - marcas en `notebooks/marcas.py`; diseños S0-S2 y G1-G2 en `notebooks/anual.py`; resultados en
    `salidas/pronostico/anual_curado.parquet`;
  - **pasa la regla G1 + salud pública en compuerta**: la capa se enciende solo con ola.
  - Confirmación con origen rodante corriendo: `g_2025` y `g` (`lightgbm_rel`; logs `c14/g_g*.log`). Cg = sarimax
    de e1 + lightgbm_rel de g; regla en la fila `contexto_con_compuerta_confirmacion`.
  - **Pendiente:** si Cg gana en 2025, `semana.py` necesita un combo con contexto. Guardar dos predicciones de la
    semana (C0r y Cg).
- **Cuaderno 22:**
  - **Error de C2:** las bandas 0-4 y 5-14 tienen días en 0 y log(0) dio infinitos. Se corrige con log(y + 1),
    opción `desplazar`, fila `reentrenamiento_holistico_enmienda`. Hay que rehacer los 5 `hb*_2025`: se lanzan al
    terminar `lightgbm_rel`.
  - **C0 contra C1 en 2025:** C0 4,2 y C1 1,1 en el criterio (promedio del BSS de las dos varas); los dos con
    cobertura válida.

**Cuaderno 23, HECHO y ampliado (05-10, noche): catálogo, validación en 4 años, técnicas, motor C0r (sec. 9), fechas escogidas (sec. 10), compuerta (sec. 11). Las secciones 12 (confirmación de Cg) y 13 (respuesta semanal) dicen «en curso»: volver a ejecutar el cuaderno cuando terminen las corridas y actualizar sus lecturas.**
- **Ejecutado, sin errores.** Lecturas en `notebooks/construir/23_lecturas.json`. Resultados en `CONTEXTO.md`, entrada «Cuaderno 23».
- Resultados:
  - no se mezclan días al azar (se demostró que engaña);
  - T0, objetivo relativo al nivel, se queda;
  - ninguna técnica T1-T5 ni Platt se adopta;
  - ninguna capa aporta al total en 3 de 4 años; salud pública aporta en 2 de 4;
  - confiabilidad honesta de alrededor del 62 %;
  - «más de 80 %» acierta el 68 %.
- **Siguiente:** fila nueva para corregir el objetivo de LightGBM en `pronostico.py` y rehacer la combinación. Después, el modelo global por bandas y Giacomini-White por régimen.

Detalle de cómo se construyó:
- Generador `notebooks/construir/23_catalogo_y_validacion_multianual.py`; módulo `notebooks/anual.py`.
- El cálculo pesado se hace con `python notebooks/anual.py` (unos 30 min) y produce
  `salidas/pronostico/anual_tecnicas.parquet` y `anual_capas.parquet`. El cuaderno solo los lee.
- Filas preregistradas: `validacion_por_capas_multianual` y `tecnicas_de_entrenamiento` (con una enmienda
  hecha antes de calcular).
- **Hallazgo de método:** el LightGBM del motor aprende log(y) y no extrapola un nivel no visto. En 2024, con
  el modelo congelado, da BSS −105 %. Con objetivo log(y) − nivel (T0) la base de 2024 pasa a +4,1 %.
  **`pronostico.py` sigue con el defecto.** Las colas del 22 no se tocan porque están preregistradas.
  Corregir el motor es el siguiente experimento.
- Con T0, **ninguna capa externa aporta en 3 de 4 años**. Salud pública aporta en 2 de 4.
- La investigación bibliográfica, con las referencias, está en `CONTEXTO.md`, entrada «Cuaderno 23».

**Lo que dejaron los cuadernos 17 y 18:**
- **Clima:** el clima mueve la IRA de la ciudad (+6-7 % con un mes húmedo y nublado) y llega diluido al triage
  total (1,5-2,4 %). Al modelo entran 4 + 3 índices, no 38 variables.
- **EPS:** la caída de Nueva EPS es sobre todo de acceso (−20 % de afiliados, −60 % de triage). Al modelo entran
  6 variables de red.

**Rama `modelos-afinados`, sin subir** (main está en `73d9dbd`).

**Pendientes del propietario:**
1. el **calendario de contratación SES-EPS** (#11), que es lo que más error explicaría;
2. la discrepancia de Sanitas en FENIX;
3. el usuario de SISPRO;
4. la API de Google Trends;
5. las quejas (PQRD) y los giros de ADRES, a mano.

**Qué hay.** El motor es `notebooks/pronostico.py`:
- experimentos `--exp e0|e1|e2`, año a ciegas `--anio` y orígenes espaciados `--cada N`;
- e0 = 2022-24 sin contexto, e1 = 2020-25 con la COVID marcada, e2 = e1 + 49 variables externas.

Los resultados están en `salidas/pronostico/`, que **no se versiona**: está solo en este equipo.

| | Hecho | Falta |
|---|---|---|
| E0 (2025-2026) | los 8 modelos | — |
| E1 (2026) | regresión, Prophet, LightGBM | **SARIMAX, Chronos-2 + calendario** |
| E2 (2026) | regresión, Prophet, Chronos-2 (`_cada7`), MedGemma servidor | **LightGBM, SARIMAX** |
| Año a ciegas | todo, en e1 y e2 | — |

**Para retomar**, en este orden. Son procesos largos: lanzarlos con `Start-Process` y seguir el
log, porque las tareas de fondo de la herramienta se cortan antes de una hora.

```
python notebooks/pronostico.py --exp e2 --modelos lightgbm sarimax       (~2,5 h; SARIMAX E2 ~2 min por reentrenamiento)
python notebooks/pronostico.py --exp e1 --modelos sarimax chronos2_cal   (~1,5 h; se puede correr en paralelo con el anterior)
python notebooks/construir/15_predicciones_tempranas.py                   (rehace el .ipynb)
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/15_predicciones_tempranas.ipynb
```

Después hay que actualizar las lecturas en `notebooks/construir/15_lecturas.json`. El ganador puede
cambiar.

**Siguiente, ya decidido con el propietario:**
1. **Depurar el contexto:** pocas variables por familia en lugar de 49. Las que más usa LightGBM:
   - peso y cambio de Nueva EPS;
   - lesiones personales;
   - IRA de Manizales;
   - intento de suicidio;
   - violencia intrafamiliar.
2. **Probar el jerárquico:** Nueva EPS y el resto, cada uno con su modelo, y sumarlos.
3. Calibrar LightGBM: su cobertura del 80 % es del 71 %.
4. Repetir la prueba de la hora con el ganador.
5. Congelar el ganador y hacer la prueba prospectiva con datos nuevos (re-extraer el triage).

**Lo que hay que saber:**
- **Criterio de «mejor»**: decide si acierta que sube o baja frente al calendario (meta 60-70 %), junto
  con la mejora de la probabilidad (BSS) y la cobertura del 80 % entre 75 y 85 %. El MAPE solo sirve
  para comunicar. El propietario lo aceptó.
- **MedGemma** (servidor `medgemma:latest` en `172.16.121.14:8080`, también en `NLP/modelo.py`):
  - probada con 19 consultas; **no sirve para pronosticar**;
  - el propietario pidió no cargar ese servidor.
  - La MedGemma local no se corrió, a propósito.
- **Chronos-2 con contexto completo en CPU** tarda ~60 s por origen. Se usa `--cada 7`.
- Librerías nuevas en `requirements.txt`: `lightgbm`, `prophet`, `chronos-forecasting`.

---

## EN CURSO (2026-09-30, tarde): cuaderno 14, los estados del triage contra todo el entorno

**Qué pidió el propietario.** Enfrentar todos los datos externos a los estados del triage (picos,
bajos, normalidad y estabilidad), por día y sin hora, conversando y concluyendo entre los dos para
saber con qué se empieza el modelo.

**Estado: primera vuelta HECHA**, en `notebooks/14_los_estados_del_triage.ipynb` (24 celdas, sin
errores). Método en la fila `estados_diarios` de `variables.csv`. Resultado en `CONTEXTO.md`, entrada
«Resultado del cuaderno 14».
- En corto: el calendario es el 72 % del día. Un pico es de toda la demanda, no de un grupo.
  Ninguna fuente externa anticipa los estados de forma estable.
- La firma de «día soleado» se rompe en 2025.
- Hay una hipótesis de transición (mes cálido → semana fresca) que solo aparece en 2025-2026.

**Esperando al propietario** (sección 7 del cuaderno):
- **A.** ¿Se mide el clima dentro de cada asegurador (`triage_entidad.parquet`) para ver si el cambio
  de 2025 es Nueva EPS?
- **B.** ¿El primer modelo se arma con calendario, estación, red y memoria corta como base, y lo
  externo entra solo si mejora fuera de muestra?
- **C.** ¿Se repite el enfoque de estados sobre la serie respiratoria?

La sección 7 se completa con lo que se concluya. El generador del cuaderno está en el scratchpad de
la sesión (`c14/hacer_nb.py`). Si se pierde, se edita el `.ipynb` directamente.

---

## EN CURSO (2026-09-30): barrido ancho de clima y vigilancia — cuadernos 12 y 13

**Cambio de enfoque del propietario:** el resumen anterior le pareció «relleno». Pide:
- aprovechar **todo** el clima y **todo** el SIVIGILA;
- quedarse con **variables generales de la ciudad**, no con casos puntuales como los colegios.

El método está fijado antes de mirar:
- decisión en `CONTEXTO.md`, entrada «Cambio de enfoque»;
- filas `barrido_clima`, `barrido_vigilancia`, `indices_generales` y `fin_de_sequia` de `variables.csv`.

Cómo se trabaja:
- **Desenlace común:** `notebooks/desenlace.py`. Es el triage semanal sin calendario ni escalones de la red, con estacionalidad, más las series respiratoria, infecciosa y de trauma.
- **Periodos:** descubrir de 2022-03 a 2024-12 y confirmar de 2025-01 a 2026-08 (el SIVIGILA solo hasta 2025-12).
- **Control:** BH con q = 0,10. **Solo cuenta lo que se confirma.**

**Estado: HECHOS, los dos, y ejecutados con 0 errores.** El resultado está en `CONTEXTO.md`, en
la entrada «Resultado de los barridos».

**Clima (cuaderno 12)**
- 693 pruebas, 34 sobreviven a BH y **se confirma 1**: el cambio de radiación a 2 semanas, a la
  misma semana.
- La sequía de 2026 termina en agosto. Los precedentes no anuncian ola.

**Vigilancia (cuaderno 13)**
- 531 pruebas y **0 predictores válidos del total**. La EDA hospitalizada se confirmaba, pero era
  estación compartida.
- La presión respiratoria de la ciudad da **+10,6 % en el respiratorio del hospital a 1 semana**,
  con p = 0,055. Es el mejor candidato.

**Regla de método nueva, desde el 2026-09-30:** antes de dar algo por confirmado, el efecto tiene
que sobrevivir sin estación y sin causalidad inversa (el triage no puede «predecir» la variable
hacia atrás).

**Lectura:** el entorno general actúa sobre la **fracción respiratoria** y se diluye en el total.

**Esperando al propietario:**
1. ¿Se corrige la SE53-2025 del 998 en `sivigila.py`? Hoy solo se anula en memoria.
2. ¿Se programa una instantánea semanal de Power BI?
3. **Cómo se predice:** si se pronostica el total directamente, o el total más la fracción
   respiratoria.

**Siguiente paso:** la discusión de predicción.

---

## En una frase

Se está en **exploración**, no en modelado. El objetivo de esta etapa es saber qué variables
existen, cómo se comportan y qué relaciones reales hay entre las tablas y los calendarios.
**Nada de predicción hasta terminarla.**

---

## EN CURSO (2026-09-28): calendarios externos con fuentes reales — 1/4: vigilancia

**El NLP está en pausa por decisión del propietario.** El orden y el porqué están en
`CONTEXTO.md` («Se aparta el NLP…»): **vigilancia → clima → desastres → eventos**, de uno en uno.

**Encuadre (propietario, 28-09):** esta etapa es de **recolección e inventario**. El desenlace
es el **triage total**; lo respiratorio era solo un ejemplo. El entregable central es
`calendarios/docs/INVENTARIO.md`. Alcance fijado:
- Eventos grandes (Feria) sí; partidos no.
- Catástrofes, de la UNGRD.
- **Sin** calidad del aire.
- El clima actual basta.

**Estado al cierre del 28-09:**
- **Calendario 1 (vigilancia) CERRADO.**
  - 995 y 998: `vigilancia_sivigila.csv.gz`.
  - 14 eventos individuales y 3 marcadores: `vigilancia_sivigila_eventos.csv.gz`, con el script
    `eventos.py`.
  - 2026 por Power BI (`powerbi.py`), con una instantánea en `powerbi/2026-09-28/`.
  - Decisiones y escalones: `CONTEXTO.md`, entrada «Calendario de vigilancia cerrado».
- **Cuaderno `notebooks/06_patrones_exploratorios.ipynb`**, con los primeros patrones contra el
  triage total. Lo más fuerte es institucional; clima, Feria y vigilancias no se distinguen del
  azar. Cinco hipótesis (H1-H5) en `CONTEXTO.md`.
- **Inventario de fuentes de las demás familias** en `calendarios/docs/FUENTES_EXTERNAS.md`.
  Las acciones del propietario están en la decisión #10.
- **Regla nueva:** en el total, un día sin filas es una caída del registro, no cero pacientes.

**HECHO (30-09): `notebooks/11_cruces_del_entorno.ipynb`**, con más cruces de la ciudad.
- **Principio de parsimonia** (propietario): no explorar de más, porque sobreajusta.
- Entra al repertorio: frío y humedad del último mes (+8-10 % de IRA por desviación típica), enero
  como periodo respiratorio, y calendario festivo y lluvia para la calle.
- El resto queda de contexto.
- **Siguiente:** resumen de todo y conversación sobre **cómo hacer las predicciones**.
- Las preguntas al superior (código 9, habilitación, obstetricia) quedan descartadas por ahora.

**HECHO (30-09): perfil del hospital, `notebooks/10_perfil_del_hospital.ipynb`**, con datos
enmascarados.
- Se genera con `python -m extraccion --perfil`: solo agregados y casillas < 5 ocultas. Se
  versionan 9 tablas; `perfil_dx_diario` se queda local.
- **El SES recibe todo y se queda con un tercio** (la mitad hasta 2023).
- Obstetricia crece.
- Hay **series de diagnóstico desde 2020 sin NLP**: respiratorio, diarrea, trauma y embarazo, cada
  una con su época del año.
- Remite por falta de especialidad o de convenio con la EPS.
- Preguntas abiertas en `CONTEXTO.md` (30-09): el código 9, la «no habilitación», la obstetricia.
- **Siguiente natural:** enfrentar los estados del entorno (cuaderno 09) y sus interacciones
  contra el triage total **y** contra las series por diagnóstico, preregistrando antes. La primera
  es frío × virus × mayores sobre respiratorio.

**HECHO (29-09, noche): el entorno conectado consigo mismo**, que es la decisión del propietario.
- `notebooks/09_el_entorno.ipynb` está hecho, sin errores y sin datos del hospital. Trae el
  calendario → violencia, las cadenas clima → IRA con rezago y los estados del entorno (calma,
  frío y húmedo, seco y cálido, decembrino, Feria).
- **Sección 6 hecha**: lo observado contra lo publicado, con la revisión en
  `calendarios/docs/LITERATURA_ENTORNO.md` (86 referencias). Casi todo coincide. Aportes propios:
  quincena → violencia intrafamiliar, y la interacción frío × virus × mayores.
- Datos nuevos: `enso_oni.csv` y `calendario_escolar_manizales.csv`.
- **Después:** enfrentar los estados y sus interacciones contra el hospital (cuaderno 10 o 11;
  el perfil del hospital espera, #13).

**HECHO (29-09, tarde): los cuadernos 01-08 cuentan la historia completa.**
- Índice y hilo en `notebooks/README.md`.
- 01, 02, 03 (nuevo), 05 (convertido), 06, 07 y 08 (nuevo) corren **sin errores**.
- Llevan recuadros de corrección, incluido el del clima.
- **El 08 (los picos)** dejó tres relojes: la noche festiva (baja de día, sube de madrugada, y el
  día siguiente sube), el arranque de año (3 de enero +14 %) y la temporada de mitad de año
  (vacaciones +6,5 %). Fiestas de pueblos lejanos: +2 %.
- **El clima está corregido otra vez** (pluviómetro roto, `pluviometro_fallido`).
- **Siguiente:** fijar las variables definitivas y probarlas fuera de muestra (origen rodante).
  Pendientes del propietario: #10, #11, #12 (CRUE).

**(histórico de la mañana) Los cuadernos cuentan la historia completa** (`CONTEXTO.md`, entrada del 29).
Tres agentes trabajan en paralelo, sin compartir archivos:
- **01 y 02: TERMINADOS**, 38 y 36 celdas, sin errores, con 22 y 24 recuadros de corrección.
  `CLAUDE.md` también corregido: la segunda joroba es a las 14-15 h, los huecos van nombrados y
  la caída se atribuye a Nueva EPS.
  - **Pendiente:** ningún script regenera `triage_diario` ni `triage_horario`. Hay que añadirlos
    a `extraccion --series`.
- **Calendario de fiestas:** un agente está integrando `scratchpad/picos_contexto/fiestas_A.csv`
  (93 filas con URL y los aplazamientos por el terremoto) en
  `calendarios/fiestas_caldas_2020_2026.csv`.
- **03 nuevo** (fuentes externas) y **05 convertido a cuaderno**, con el defecto de marzo de 2024
  arreglado.
- **Investigación de picos**: calendario de fiestas de los municipios de Caldas en
  `calendarios/fiestas_caldas_2020_2026.csv`, y contexto oficial de diciembre, enero y mitad de
  año en `<scratchpad>/picos_contexto/INFORME.md`.

**Después:** el cuaderno **08, los picos**, con las hipótesis ya preregistradas
(`diciembre_noches_festivas`, `fiestas_pueblos`, `mitad_de_anio`); `notebooks/README.md` con el
hilo; y ajustes al 06 y al 07. **Ya medido:** hay dos tipos de pico. Días puntuales en
diciembre-enero (12-15 por cada 100 días) y semanas altas sostenidas en marzo-mayo (mayo: 45 % de
sus semanas).

**NUEVO (28-09, noche): método por mecanismos** (`CONTEXTO.md`, «Cambio de método»).
- Ventanas preregistradas en `patrones/datos/variables.csv`.
- Serie nueva por asegurador: `salidas/triage_entidad.parquet` (`python -m extraccion
  --entidad`), agrupada con `extraccion/entidades.py`, que es un borrador a revisar.
- `notebooks/07_mecanismos.ipynb`: Nueva EPS explica los escalones de nov-2025 y jul-2026; la
  Feria tiene huella propia (SOAT +37 % contra +12 %); seco → lluvioso daba +22 % en 0-4 años (**+13 % ± 15, no significativo, tras corregir el
  pluviómetro el 29-09**) a
  1-2 semanas.
- Las lecturas del 06 están corregidas.
- **Pendiente del propietario (#11):** fechas de suspensión y reanudación de servicios entre el
  SES y Nueva EPS, y revisar la clasificación de entidades.

**Sigue, en orden** (el propietario elige):
1. **Calendario del sistema de salud (H1).** Es la señal más visible y no existe como dato.
   Se arma con la API de noticias de la Alcaldía (8.746 desde 2020) mientras llega el derecho de
   petición a la DTSC (#10c).
2. **Catástrofes de la UNGRD**, que sustituyen `desastres_manizales_2020_2026.csv`.
3. **Eventos sociales grandes**, que sustituyen el calendario manual: Feria con asistencia y
   número de eventos por año, que es lo único que la haría medible.
4. **Tarea semanal que congele el Power BI.** Hoy hay una sola instantánea.
5. **Preregistrar H1-H5** en `patrones/datos/variables.csv` antes de cualquier prueba fuera de
   muestra.

---

**Detalle del calendario 1 (vigilancia):**

| | |
|---|---|
| Código | `calendarios/vigilancia/sivigila.py` (`--sin-descargar` rehace todo desde el caché en ~16 s) |
| Salidas versionables | `calendarios/vigilancia_sivigila.csv.gz` (203.772 filas; Manizales, Caldas y Colombia) y `vigilancia_sivigila_instituciones.csv.gz` (130 instituciones) |
| Crudo | `calendarios/vigilancia/crudo/`, 1,6 GB, **ignorado**: trae datos de quien notifica |
| Porqué | `calendarios/docs/VIGILANCIA.md` |
| Fuentes | `calendarios/docs/FUENTES_VIGILANCIA.md` |
| Cobertura | 995 usable **2015-2025**; 998 de 2011 a 2025 |

**Lo que hay que saber para usarlo** (detalle en `CONTEXTO.md`):
- La proporción IRA / todas las causas **solo se compara dentro de cada año**: el denominador
  tiene escalones de +60 % y +35 %. Para comparar entre años, usar el conteo.
- La IRA 0-4 de la ciudad correlaciona **r = 0,703** con el triage 0-4 del hospital. En
  diferencias semanales baja a 0,18.
- **Trampa de conteo:** el `GROUP BY` de SQL no emite días con cero. Antes de correlacionar,
  rellenar con cero.

- Los eventos individuales (300, 356, 875, 365…) **solo entran al pronóstico con rezago**:
  son parte del desenlace.
- Pendiente: una proporción sobre un panel fijo de instituciones, para quitar los escalones
  del denominador.

Las copias del scratchpad con datos de quien notifica (`d995.xlsx`, `d995_2025.parquet`) se
borraron el 28. El único crudo que queda es el de `crudo/`, ignorado por git.

## Lo más nuevo, y lo que más cambia el plan

**0. (2026-09-28) Validación «sin motivo» medida — ver `CONTEXTO.md`, entrada del 28.**
`python notebooks/05_validacion_sin_motivo.py`. En corto: el motivo **no hace falta** para
predecir ni para probar el mecanismo (la edad lo prueba: frío/humedad → +6-11 % de consultas
0-14 años a 1-2 semanas). Pero **ninguna variable externa actual mejora el pronóstico del
total** fuera de muestra (semanal: estacionalidad 5,23 % de MAPE, con externas 5,64 %), porque
los calendarios son sobre todo calendario disfrazado (vigilancia: 67 % ventanas fijas; el mes
explica 93-100 % de ellas) y las rupturas seca→lluvia son solo 7 semanas. Lo que más mueve el
conteo es institucional (nov-2025, terremoto −21,5 %). **Espera decisión del propietario** (#7).
Fuera del repositorio hay dos cosas útiles:
- **Microdatos SIVIGILA 995** (IRA por institución × semana, Manizales, 2011-2025): es una serie
  de vigilancia real para reemplazar las ventanas fijas. Al cargarlos hay que descartar las
  columnas del notificador, que son dato personal.
- Los **cierres a Nueva EPS**: Avidanti el 21-ago-2025 y Santa Sofía el 1-dic-2025. Son el
  candidato a explicar noviembre-diciembre de 2025.

Detalle y enlaces en `CONTEXTO.md`.

**1. La vía pediátrica pasa a ser el camino principal.** Las bandas 0-4 y 5-14 tienen
**72,5 % y 43,5 % de amplitud estacional** contra 5-8 % de las adultas, con pico en mayo y
valle en enero. Es la firma de una temporada respiratoria, y prueba la hipótesis central
**con 6,7 años y sin depender del NLP**. `salidas/triage_edad.parquet`, 100 % de cobertura.

**2. El clima unificado está ARREGLADO (2026-09-23).** Tenía seis errores, no uno; el peor
fabricaba tormentas cada vez que el pluviómetro dejaba de reportar (+20,05 mm/día falsos,
ahora −0,36). Ya se puede cruzar contra clima. **Límite: solo el 42,9 % de los días tiene
pluviómetro** — para transiciones día a día, `precip_con_estacion` o acumulados de 7 días.
Ver `calendarios/docs/CLIMA.md`.

**3. El nivel de triage mide la decisión del hospital, no la gravedad del paciente.**
Corrección del propietario. Todos los registros son demanda real. De ahí la distinción que
ahora organiza todo: **conteo, edad y hora miden a la población; nivel y estancia miden a la
institución.** Para comparar años, solo los primeros.

**4. Aquí no hace calor, nunca.** 0 días con máxima > 26 °C en 2.432. Descarta la vía
vectorial local y deja la respiratoria, que es la hipótesis original.

---

## EN CURSO (2026-09-24): competencia de modelos ligeros en CPU — Llama 3 y otros

**Qué se busca**: si un modelo local y ligero (Llama 3.x u otro) resuelve lo que qwen3:8b no
pudo —descartes falsos inestables, duda → certeza, negaciones, «no me baja el azúcar»,
«oídos tapados»— con igual o menos recursos. Diseño y porqué: `docs/CONTEXTO.md`, entrada
del 2026-09-24 «Se reabre la competencia de modelos EN CPU».

**Estado (10:55)**: corriendo la competencia en **igualdad de condiciones**, diseño y puntaje
**preregistrados** en `CONTEXTO.md` (bloque «Diseño final»): 63 notas (sonda + muestra nueva
de los bancos), prompt v1.7, modo solo, un modelo a la vez. Orden: llama3.1:8b → qwen3:8b →
tulu3:8b → Llama-3.1-Storm-8B → gemma3:12b → gemma4:12b-it-qat. Un agente revisor escribe la
lista de verificación de las 63 notas antes de juzgar.

**Ya medido (15:40)** — puntaje preregistrado sobre 63 notas, modo solo / con filtros:
**gemma4:12b-it-qat +25 / +26** · qwen3:8b +7 / +15,5 · gemma3:12b +6,5 / +7,5 (0 descartes
falsos) · tulu3:8b −8 / +2,5 · llama3.1:8b −19,5 / −9,5 · llama3.2:3b piso. Detalle y lectura
en `CONTEXTO.md`. **gemma4:12b es el candidato**, con un defecto: 5 descartes falsos.

**Juez ciego: confirmado** (gemma4 mejor en 31 de 43 notas distintas, qwen en 3).

**NUEVA FASE (16:10), decisión del propietario: un prompt propio por modelo**, gana el primero
que cruce la barrera preregistrada (≥ 12/16 notas duras, 0 aciertos dañados, 0 descartes
falsos) y la confirme en una validación que ningún agente de prompt ve. Protocolo completo en
`CONTEXTO.md`, entrada «Cada modelo con su propio prompt». En curso:
- 5 agentes escribiendo la ronda 1 (gemma4, qwen3, gemma3, tulu3, llama3.1) en
  `scratchpad/prompts/<modelo>_r1.py`, con `prompts/REGLAMENTO.md` y `prompts/verificar.py`.
- Validación en construcción: `scratchpad/validacion_privada/` (~49 notas nuevas de 8
  familias, fuera de la muestra de 63).
- Storm 8B corriendo con v1.7; después `cola4.sh` (segunda pasada real y prueba de reuso).
- Cancelada la vuelta de gemma4 con `v1_7_14b.py` (la reemplaza su prompt propio).

**2026-09-25, 08:00 — se reanuda tras un reinicio de la máquina.** La ronda 1 no había guardado
nada (R1_gemma4 quedó vacío). Ollama se actualizó solo a **0.34.4** (ayer 0.34.3): las salidas
a temperatura 0 de ayer podrían no ser idénticas byte a byte. Solo había **5,6 GB libres** (VS
Code, Edge, Brave), así que la cola se reordenó para empezar por lo que cabe: R1_qwen3 →
validación de qwen v1.7 → R1_gemma4 → R1_gemma3 → R1_tulu3 → R1_llama31. **Los ~12B necesitan
~8,5 GB: cerrar navegadores antes de que les toque.**

**Para correr un prompt de ronda** (modo cadena, que es el que decide la barrera):
`python <scratchpad>/comparar.py --modelo <tag> --modo cadena --prompt <scratchpad>/prompts/<m>_r1.py --muestra <scratchpad>/muestra64.csv --salida <scratchpad>/comparacion/<m>_r1.jsonl`

**Herramientas y prompts, versionados** (2026-09-24): `NLP/competencia/` (comparar, segunda,
filtrar, verificar, despachador, REGLAMENTO) y `NLP/prompts/candidatos/<m>_r1.py`. Método y
números: `NLP/docs/COMPETENCIA.md`. **El material con texto clínico no se versiona**: en esta
sesión vive en su scratchpad (muestras, notas enmascaradas, listas de verificación, salidas,
`revision_modelos.md`, `validacion_privada/`); las herramientas del repo lo buscan en
`NLP/salidas/competencia/` (ignorado). Para seguir en otro equipo hay que regenerar la muestra
desde la base local, que solo existe aquí.

---

## EN CURSO: seguir el trabajo desde el equipo de casa (RTX 4060, 8 GB)

**Qué quiere el propietario:** clonar este repositorio en su equipo de casa y seguir desde
allí; que la GPU procese de noche las ~95.000 notas y pruebe prompts y modelos, y traer los
resultados de vuelta. El porqué y lo descartado: `docs/CONTEXTO.md`, 2026-09-24.

**Hecho y certificado (2026-09-24):**
- `NLP/salidas/tabla/notas_triage.csv.gz` — 95.424 notas, 2025-01-08 a 2026-09-24 (el último
  día incompleto: descartarlo al analizar). Seis columnas: `id, fecha, nivel, nivel_nombre,
  edad_banda, nota`. Lo identificable **borrado**. Auditoría: **0 fallos**. Su certificado
  (conteos y sha256 del CSV) es `auditoria.json`, al lado. Se rehace con
  `python -m NLP.nube.tabla --exportar --forzar` (solo aquí: necesita la base).
- `mapa_local.parquet` (`id → OID`) **se queda aquí**. Es lo único que devuelve una fila a su
  triage. Hay dos mapas apartados en la misma carpeta, de una muestra y de una corrida
  fallida: sus CSV nunca salieron, se pueden borrar.
- `requirements.txt` rehecho; `calendarios/clima_unificado.csv.gz` (antes `.csv`).
- Retirados del índice: `triage_limpio_antiguo.csv` y `exploracion.ipynb` (texto real).

**Versionado y en el commit `9c43633`** (2026-09-24): el CSV de notas, su certificado, las
cinco series `salidas/triage_*.parquet`, `clima_unificado.csv.gz` y `.claude/skills/`. El
mapa, las DuckDB y `NLP/salidas/nube/` siguen fuera (bloque «NUNCA» de `.gitignore`).
**El push lo hace el propietario** (a Claude se lo bloquea el sistema de permisos).

**El historial sigue sucio, por decisión del propietario** (se sube al repo actual): un clon
copia las notas crudas de los commits viejos. Decisión #6 abajo, pendiente.

**En el equipo de casa, para arrancar:**
```
git clone https://github.com/SebastianGuerr/puebas.git
cd puebas
python -m venv .venv && .venv\Scripts\activate
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
python -m pytest NLP/tests -q
```
y Ollama con `qwen3:8b` (y los candidatos que se quieran probar).

**Falta:**
1. **El código de casa no existe:** leer el CSV, armar el prompt con la versión que se elija
   de `NLP/prompts/`, llamar a Ollama en la GPU, guardar cada resultado con `id`,
   `version_prompt` y `modelo`. Y aquí, el camino de vuelta: resultado → `id` → mapa → OID.
2. **Pasar el arreglo de las fechas con guion a `enmascarar.py`** (hoy solo lo tiene la
   tabla, `_red_de_fechas`): el paquete de la nube tiene el mismo hueco.
3. En el equipo de casa la regla 6 («No hay GPU») no aplica: hay RTX 4060 de 8 GB.

---

## EN CURSO: fase de CPU cerrada; la red de seguridad está construida

**Decisión del propietario (2026-09-24): no se itera más el prompt en la CPU.** Lo que la CPU
podía enseñar ya está medido. Candidatos listos en `NLP/prompts/v1_7.py` (8B) y
`NLP/prompts/v1_7_14b.py` (14B, abstención suavizada); **producción (`NLP/prompt.py`, v1.6)
intacta**. La corrida de producción está **parada**.

**Qué se sabe del modelo** (detalle en `docs/CONTEXTO.md`, entradas del 2026-09-24):
- **El 8B llegó a su techo**: ~9-10/17 fallos de la sonda arreglados, leídos a mano.
- **El 14B es mejor en fidelidad** (duelo 5-2, sonda leída 11/17) pero **no es viable en
  CPU**: 9,3 GB, ~8 min de carga, 20-120 s/nota. En GPU sí.
- **El riesgo que queda son los descartes falsos**, y son **inestables** (la misma nota sale
  bien o descartada según la corrida). No se arreglan con prompt.
- **No hay acumulación de contexto**: cada llamada es independiente; la tasa de fallo es
  plana por orden de procesamiento. La inestabilidad en una nota es señal de que adivina.

**La red de seguridad, construida el 2026-09-24** (`NLP/cadena.py`): toda salida «sin motivo
clinico» cuya nota trae evidencia clínica se repite con `construir_segunda_pasada()`, un
prompt que no admite abstenerse. Si vuelve a descartar o inventa, queda «sin motivo clinico»
**marcada `revisar`**. Integrada en `banco.py` (la sonda marca `<segunda>` / `<revisar>`) y
en `NLP/nube/` como dos viajes (`--exportar --segunda-pasada`; los pendientes **no** se
fusionan con la base). Documentada en `NLP/docs/EVALUACION.md` y `NLP/docs/NUBE.md`.
283 pruebas en verde.

**Medición real de la red**: sonda de 32 notas con qwen3:8b + v1.7 + cadena completa,
**corriendo el 2026-09-24** (salida en el scratchpad de la sesión, `sonda_cadena_8b.txt`).
Si se perdió: `python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py`, **nada más en
paralelo**.

```
python -m NLP.banco --oid <OID> --prompt NLP/prompts/v1_7.py               una nota
python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py                   la sonda (32 notas)
python -m NLP.banco --sonda --prompt ... --sin-filtros                     el modelo solo
python -m NLP.duelo --modelos qwen3:8b qwen3:14b --oids ...                mismo prompt, sin filtros
```

**Filtros de `posprocesar()`**, en este orden, todos con pruebas: `es_tramite_puro` →
`quitar_lado_inventado` → `quitar_parte_inventada` → `quitar_embarazo_inventado` →
`restaurar_antier` (también «el día anterior») → `quitar_identificadores`. Solo quitan,
salvo `restaurar_antier`, que devuelve la palabra exacta de la nota.

**Límite duro de esta máquina**: 15,9 GB de RAM. Correr modelo + agentes en paralelo **colgó
la terminal** el 2026-09-23. Una sola cosa pesada a la vez.

---

## Antes de contratar GPU

Recomendada: **RTX PRO 6000 (96 GB) a ~2.088 COP/h** — 33 COP/h más que la 5090 con el triple
de memoria. Costo estimado de todo: decenas de miles de pesos; el piloto de 30 min da la cifra
real antes de comprometerse.

- [x] **Capa de seguridad `NLP/nube/`** (2026-09-23): sale solo `id` aleatorio + prompt con la
      nota enmascarada; OID, fechas y mapa quedan en local; paquete barajado; auditoría que
      falla cerrado. Auditada de forma independiente sobre 300 notas reales: 0 restos, orden
      vs OID +0,049, 323→323 términos clínicos. Ver `NLP/docs/NUBE.md`.
- [x] **Comprobación de fidelidad automática**: 13 detectores fuertes en `fidelidad.py`,
      cada uno validado leyendo lo que marca.
- [x] **Fase de CPU cerrada** (2026-09-24): el 8B llegó a su techo; el 14B es mejor pero
      solo en GPU. El modelo final se decide en la GPU, con la sonda.
- [x] **Red de seguridad contra descartes falsos** (`NLP/cadena.py`), local y nube.
- [ ] **Cuatro entradas de glosario** que son trabajo del propietario: «no me baja el azúcar»,
      «oídos tapados», «congestionado», «hipo».
- [ ] **Banco completo** con el candidato final (~420 llamadas).
- [ ] **Promover a producción**: `NLP/prompt.py` + `procesar.py` llamando a
      `cadena.procesar_nota` + columnas `version_prompt`, `modelo` y `pasada` en
      `nota_triage`. **Sin la columna `pasada`, al fusionar un `revisar` se vuelve un
      descarte normal**: hoy la única marca es `NLP/salidas/nube/revisar.txt`.
- [ ] **Probar que el enmascarado no cambia la salida**: mismas notas enmascaradas y sin
      enmascarar, mismo modelo.
- [ ] **Decisión institucional** sobre procesar datos de salud en infraestructura de un
      tercero. La capa técnica reduce el riesgo; la autorización no la da el código.
- [ ] En la GPU: competencia de 2-3 modelos (el agente de investigación recomienda
      `gemma4:26b` o `gemma4:31b`, `qwen3:32b` como control, y el 8B de referencia) con la
      sonda y el banco, antes de la corrida completa.

---

## Lo que cambió hoy y hay que saber antes de nada

**La regla 1 estaba mal escrita.** No es «no tocar la base», es «no exponer dato personal».
La base **sí** se explora: esquema primero, clasificar columnas, y solo agregados de las no
sensibles. El protocolo está en `extraccion/__init__.py`. Eso desbloqueó todo lo de abajo en
una sola sesión.

**Se encontraron dos derivas de medición no documentadas**, y eso convierte la auditoría en
un paso obligatorio:

1. **El criterio de triage derivó desde enero de 2025.** La caída del 23,9 % del volumen es
   en buena parte reclasificación: «no urgente» −57,4 %, «diferido» +101,5 %.
2. **La estancia tiene tres regímenes de registro** (saltos en 2021-08 y 2026-07). Solo vale
   el régimen 2: agosto 2021 a junio 2026.

**Antes de usar cualquier columna nueva: mirar su serie mensual buscando escalones.**

---

## Qué está corriendo

**La corrida de producción (`NLP.procesar`) está parada** desde el 2026-09-23. Quedó en
~3.087 notas, todas de enero de 2025, **procesadas con v1.6**: habrá que rehacerlas con la
versión final. Al relanzar, hacerlo con la cola **por hash del OID** (hoy procesa en orden
cronológico, `procesar.py:223`, `disperso=False`).

---

## Qué existe y se puede usar hoy

| Archivo | Qué es | Cobertura |
|---|---|---|
| `salidas/triage_diario.parquet` | 2.454 días | 2020-2026 |
| `salidas/triage_horario.parquet` | 55.844 casillas día×hora | 2020-2026 |
| `salidas/triage_nivel.parquet` | 177.864 filas día×hora×nivel | **100 %** desde 2020 |
| `salidas/triage_edad.parquet` | 12.339 filas día×banda | **100 %** desde 2020 |
| `salidas/triage_estancia.parquet` | 2.455 días | 91,1 %, **solo vale régimen 2** |
| `salidas/triage.duckdb` | `nota_triage` + `embedding` | 1,5 % del corpus |
| `NLP/salidas/tabla/notas_triage.csv.gz` | 95.424 notas sin identidad, auditadas | 2025-01-08 a 2026-09-24 |
| `calendarios/clima_unificado.csv.gz` | clima diario unificado (antes `.csv`) | 2020-01-01 a 2026-08-28 |

Los cuatro parquet se regeneran con `python -m extraccion --series`. **Los cuadernos leen de
ahí y no de SQL Server**, que es lo que permite que otra persona reproduzca las figuras.

---

## Lo construido, y cómo se corre

```
python -m extraccion --esquema            columnas y su clasificación. No baja datos
python -m extraccion --cobertura          qué está lleno y desde cuándo
python -m extraccion --series             escribe salidas/*.parquet

python -m clustering.visualizaciones      7 figuras sobre la serie total
python -m clustering.visualizaciones.pruebas    5/5

notebooks/01_la_serie_de_triage.ipynb     25 celdas, 6 figuras, 0 errores
notebooks/02_el_hospital.ipynb            20 celdas, 2 figuras, 0 errores
```

**`clustering/visualizaciones/`** — 994 líneas en 6 archivos, 3 con cálculo. La regla que
lleva dentro: nunca se dibuja el conteo crudo de una categoría, siempre el índice de
especialización, y las casillas con esperado < 5 se tapan en gris.

**`extraccion/`** — 2 archivos. El único módulo que habla con SQL Server. Todas las
consultas llevan `GROUP BY`.

**`notebooks/01_la_serie_de_triage.ipynb`** — ejecutado, 0 errores. Cubre: el volumen y su
caída, el ritmo horario, qué tipo de hospital es, la reclasificación y los regímenes de la
estancia. Cada figura con su lectura y sus límites.

---

## Hallazgos que condicionan lo que venga

1. **La serie no crece: −23,9 % desde el pico de 2024** — y buena parte es reclasificación.
2. **2020 es un cráter de COVID** (−64 % enero→abril). No entra en entrenamiento sin tratarlo aparte.
3. **La hora manda: 13,9× contra 1,57 ×** del día de la semana.
4. **El día tiene dos jorobas** → harán falta 2-3 armónicos de 24 h, no uno.
5. **Hay interacción hora × día**: la madrugada pesa 1,62× más el domingo que el jueves.
6. **51,4 % del hospital es no urgente; las emergencias son el 0,4 %.** Sostiene el
   mecanismo de la incapacidad que el proyecto quiere medir.
7. **12,6 % es obstétrico** (niveles `-G`). Población aparte, conviene separarla.
8. **`GENDIAGNO1` está vacío (0,6 %)**: no hay CIE-10 gratis. No volver a buscarlo.
9. **La ventana con texto (2025-2026) es justo la ventana contaminada** por la deriva.

---

## Esperando decisión del propietario

| # | Qué | Por qué importa |
|---|---|---|
| 1 | **¿Qué pasó en enero y en noviembre de 2025?** ¿Directriz, contrato, auditoría? | Es la única explicación de la deriva que no está en la base |
| 2 | **¿Qué significa `HCCFECSAL`** en cada régimen? | Sin eso la estancia no se interpreta ni dentro del régimen 2 |
| 3 | **La lista de 6-8 categorías clínicas** | Bloquea el banco etiquetado, y el banco bloquea la comparación de métodos |
| 4 | **Reordenar la cola del NLP por hash del OID** (parar y relanzar la corrida) | Muestra uniforme de 20 meses en ~5 días en vez de 70 días en orden cronológico |
| 6 | **Limpiar el historial de git**: repo nuevo con un commit limpio (recomendado) o `git filter-repo` + `push --force`. El 2026-09-24 el propietario eligió subir al repo actual y dejarlo para después | Hoy un clon copia 6.501 notas crudas con OID y otros bancos de notas. Irreversible: lo decide el propietario |
| 7 | **¿Se congela el NLP y se sigue sin motivo?** (2026-09-28, conversación con el superior). La medición apoya congelarlo *para el pronóstico*; lo que se pierde es solo la vía respiratoria adulta. Si se sigue sin motivo, lo que falta no es modelo sino **mejores externas**: series semanales reales de vigilancia (no ventanas fijas), pronóstico de clima, y un calendario **institucional** (EPS, cierres de la red, directrices) | Decide en qué se gasta la GPU y el tiempo de las próximas semanas |
| 14 | ~~Perfil del hospital, decisiones abiertas~~ **RESUELTA el 30-09**: no existe diccionario, se enmascara con supresión < 5 y cruces gruesos, y se versionan las tablas suprimidas (no la diaria). Cuaderno 10 hecho. **Queda preguntar**: el código 9 de causa de ingreso, la «no habilitación» de 2025-2026 y el alza de obstetricia | — |
| 13 | ~~Perfil del hospital: en espera~~ **RESUELTA el 30-09**: el superior dio el contexto y se hizo el cuaderno 10. Texto original: (2026-09-29). El propietario habla con su superior para conseguir documentación de base (servicios, qué se reporta, qué se atiende) antes de construirlo. Tablas candidatas ya vistas en el esquema: `DIM_INGRESO` (causa de ingreso, servicio, cama), `CONTROL_DIAGNOSTICO` (CIE-10) y `SEGUIMIENTO_REMISIONES_DW` (con datos personales: solo agregados) | Define qué factores deberían importarle al SES y qué es el 40 % que sí se atiende |
| 12 | **Informes del CRUE (remisiones), a mano** (2026-09-29): 119 informes mensuales en `saluddecaldas.gov.co/documentos/338/referencia-y-contrarreferencia-caldas/`, con reCAPTCHA en cada descarga. Empezar por diciembre, enero, junio y julio. Derecho de petición propuesto en `calendarios/docs/CONTEXTO_PICOS.md` §4.3 | Es la única vía para medir la hipótesis «lo que el pueblo no atiende termina en Manizales» |
| 11 | **Fechas de la relación SES-Nueva EPS** (2026-09-28): ¿qué pasó a mediados de noviembre de 2025, en marzo de 2026 y en julio de 2026 (suspensión, reanudación, cambio de contrato)? Y revisar `salidas/entidades_clasificadas.csv` | Es la variable de mayor efecto (±40-55 % del triage de Nueva EPS) y se conoce por adelantado |
| 10 | **Acciones de fuentes que solo puede hacer el propietario** (2026-09-28; detalle en `calendarios/docs/FUENTES_EXTERNAS.md`): (a) calidad del aire del CDIAC: la red institucional lo bloquea como «Malicious Websites»; pedir a TI que lo reclasifique, bajarlo desde casa o pedírselo a Corpocaldas; (b) registro en ACLED para la API de protestas; (c) derecho de petición a la DTSC con alertas hospitalarias, novedades REPS de urgencias, hospitalización y UCI, y ocupación, 2020-2026; (d) serie histórica de afiliados por EPS de MinSalud; (e) histórico de medidas de la Supersalud; (f) aceptar o no las API no documentadas (ESPN, SGC); (g) autorizar que se empiece a guardar la foto mensual de la BDUA | Sin (c) no hay calendario del sistema de salud, que es la familia que coincide con las semanas más extremas. (g) pierde historia cada mes |
| 9 | ~~¿El hospital aparece en el SIVIGILA 995?~~ **RESUELTA el 28-09**: es el SES Hospital Universitario de Caldas, `170010010301` «SERVICIOS ESPECIALES DE SALUD». Reporta ~0 IRA; se excluye de las consultas de la ciudad | Si aparece, parte de la correlación r = 0,703 es mecánica (son las mismas consultas) y hay que excluirlo de la serie de la ciudad para usarla como variable externa |
| 8 | **¿Se avisa al INS de que los modelos públicos de sus tableros Power BI por evento exponen columnas identificables?** (2026-09-28) | El proyecto no las usa, pero están expuestas a cualquiera. Es una decisión ética e institucional, no técnica |
| 5 | **Permitir una primera pasada léxica en SQL** sobre `HCTMOTCON`: `CASE WHEN ... LIKE` + `GROUP BY` día; el texto nunca sale del servidor | Calendario de motivos de los 20 meses **hoy**, y es además el «piso léxico» del banco de comparación |

---

## Pendiente de hacer, en orden

1. ~~Arreglar el clima unificado~~ — **hecho el 2026-09-23.**
2. **Cuaderno 03: la estacionalidad pediátrica año a año.** ¿Se repite, o la fabrica el
   promedio de siete años? Y separar lluvia de calendario escolar, que hoy están confundidos.
3. **Cuaderno 04: el ciclo horario con Fourier.** Periodograma y cuántos armónicos hacen falta.
4. **Añadir `nivel_triage` a `nota_triage`** y que `NLP/` lo extraiga, como hace con la
   fecha. **No tocar mientras la corrida esté viva.**
5. **Auditar `HCAREA`** de `HCNCONCOTRI_DW` — posible categoría estructural gratis desde 2020.
   Mirar su serie mensual buscando escalones antes de usarla.
6. **Reescribir `clustering/`** contra la base: retirar `fechas.py`, las anclas posicionales
   y las salidas sueltas.
7. **Borrar los archivos muertos** — lista aprobada, ejecución pendiente. Todos están en git.

---

## Trampas conocidas

- **Cuatro defectos de los filtros de producción** (2026-09-24, tabla en
  `NLP/docs/COMPETENCIA.md`): `quitar_embarazo_inventado` borra un embarazo real;
  `quitar_parte_inventada` borra una parte del cuerpo real si la nota la escribe con errata; el
  filtro de trámites deja «la eps»; la segunda pasada se dispara en trámites puros bien
  descartados. Arreglar con prueba antes de promover ningún prompt.
- **`banco.enmascarar` tapa de más**: ocultó «desaturaciones» y «como urgencia» como si
  fueran nombres. No afecta al modelo (recibe la nota entera) pero sí a quien juzga.

- **En Windows, detener una tarea de fondo NO mata a sus hijos** (2026-09-24). Se detuvo una
  cola `bash cola.sh` y siguieron vivos el bash y su `python`: tres corridas pidieron modelos a
  la vez, Ollama cargó qwen3:8b y llama3.1:8b juntos, la RAM libre bajó a 0,6 GB y cada nota
  pasó de ~80 s a ~3 min. **Para parar una corrida: buscar los PID con
  `Get-CimInstance Win32_Process` y `Stop-Process` a cada uno, y confirmar con `ollama ps`
  que queda un solo modelo.** `cola3.sh` descarga todo modelo cargado antes de empezar otro.

- **Hueco de privacidad, encontrado el 2026-09-24 y SIN arreglar**: la abreviatura **«doc»**
  (doctor) no está en `NLP/banco.py:316` (`enmascarar`), ni en `NLP/fidelidad.py:717`
  (`_TRATO`) ni en `:834` (`quitar_identificadores`). Una nota con «doc + nombre y apellido»
  sale con el nombre visible, y un modelo que lo copie no pasa por el filtro. Caso real en la
  muestra de la competencia. Arreglo: sumar `doc` a las tres, con prueba.

- **DuckDB admite un solo escritor y bloquea a los lectores.** Leer de `triage_vista.duckdb`.
- **`calplot` no está instalado**; el calendario está reimplementado en `figuras.py`.
- **Las salidas de `clustering/salidas/` y `patrones/salidas/` están muertas** (bge-m3,
  corpus de 9.256 notas que ya no existe). No citar esos números.
- **El supuesto del lift no está medido**: se asume que la cobertura de `HCTMOTCON` no
  depende de la categoría.
- **`ipykernel`, `nbformat` y `nbconvert`** ya están en `requirements.txt` (2026-09-24), con
  `hdbscan`, `umap-learn` y `pytest`, que también se usaban sin estar.
- **`ollama pull` puede fallar por DNS** contra `r2.cloudflarestorage.com` en la red local; al
  reintentar funcionó. Alternativa: `ollama pull hf.co/usuario/repo:Q4_K_M` (Hugging Face).
- **`CLAUDE.md` todavía dice «No hay GPU» (regla 6) y «33 pruebas en verde»**: los dos quedaron
  viejos (hoy son 283 pruebas). Se actualizan al cerrar la sesión.
- **La segunda pasada en la nube va a otro archivo de respuestas** (`correr_en_gpu.py
  --salida respuestas_segunda.jsonl`): el mapa del 2º paquete reemplaza al del 1º.
