# Los cuadernos: la historia, en orden

Cada cuaderno contesta **una pregunta**. Trae sus datos, sus figuras, sus fuentes, su lectura y
sus límites. Cuando una medición posterior cambió una conclusión, el cuaderno lo dice en el texto,
con la referencia al cuaderno que la reemplaza, y no deja la cifra vieja como vigente. El recorrido,
con sus rectificaciones, es parte del resultado.

**La pregunta del proyecto:** *¿cuándo va a subir la cantidad de solicitudes de triage de urgencias
del SES Hospital Universitario de Caldas, y por qué?* El desenlace es siempre el **conteo total**.

---

## El hilo

| # | Pregunta | Lo que dejó | Matices posteriores |
|---|---|---|---|
| **00** La trayectoria | ¿Cómo se llegó hasta aquí y por qué? Es la puerta de entrada y está escrito en primera persona | Cuatro etapas: registros → motivo de triage (descartado: mediana de 5 palabras por nota y ningún modelo de lenguaje fiable) → contexto externo, con cada factor medido en su reloj → predicción (SARIMAX va adelante con una sola serie) | Las cifras por banda de edad valen para el descubrimiento y no se confirman en 2025-2026 (cuaderno 21) |
| **01** La serie de triage | ¿Cómo se comporta el conteo solo? | Ritmo semanal y horario (dos jorobas: 10 h y 14-15 h). La serie sube hasta 2024 (226,9 triages por día) y cae un 23,9 % hasta 2026 (172,6). Reclasificación del nivel desde 2025 | La caída del **volumen** es de **Nueva EPS**, no de la reclasificación, porque reetiquetar no cambia el conteo; el pico de 2024 es de SURA. Lo que compensan los demás aseguradores depende de la ventana (13 % y 22 %, o 16 % y 11 % en el cuaderno 18). Hay caídas de registro del 19 al 21 de marzo de 2024 |
| **02** El hospital | ¿Qué mide cada variable? | Tres familias: la **población** (conteo, edad, hora), la **institución** (nivel, estancia) y la **red** (quién paga). Estacionalidad pediátrica. El nivel de triage sigue a Nueva EPS en 22 meses (r = −0,80) | La gripa y los niños eran un **ejemplo**, no el objetivo. El asegurador resultó la variable institucional más grande |
| **03** Las fuentes externas | ¿De dónde sale cada dato externo y cuánto vale? | Las fuentes oficiales (SIVIGILA, Power BI del INS, clima, MinDefensa, fiestas, USGS, NOAA), su cobertura, su rezago y sus escalones de registro | El pluviómetro de La Nubia reportaba ceros mientras llovía (oct-2025 a jul-2026) y se trata como ausente. Se anuló el «seco → lluvioso» de +22 % |
| **05** Validación sin motivo | ¿Se puede predecir sin el motivo de la nota? | El motivo no hace falta. Con los calendarios hechos a mano, **ninguna externa mejora el pronóstico** | Esa conclusión medía niveles semanales sobre el total, y los calendarios manuales son en su mayoría calendario con otro nombre. Con mecanismos (07) sí aparece señal |
| **06** Búsqueda de patrones | ¿Qué se mueve con el triage total? | Correlaciones con rezago: casi nada por encima del azar. El método solo detecta efectos semanales de 5-10 % o más | Se quitó la estacionalidad antes de mirar, y eso borra los efectos que se repiten cada año. La Feria en el total (+6,3 %) depende de 2022, año de la ventana COVID: sin él da +2,1 % |
| **07** Mecanismos | ¿Qué deja huella si cada factor se mide con su reloj? | **Nueva EPS** explica los escalones de nivel. La **Feria** deja su huella en el asegurador: SOAT +36,9 ± 5,5 y otras EPS +32,0 ± 6,3, mientras el total sube +7,3 ± 8,5. El tránsito de la ciudad no llega al SES | Con el pluviómetro corregido, «seco → lluvioso» en niños de 0 a 4 años queda en +13,4 ± 15,0 con 17 episodios (+8,2 ± 13,0 sin el del 2024-04-03): no es significativo |
| **08** Los picos | ¿Cuándo son, de qué tipo y qué los rodea? | **Tres relojes:** la noche festiva (baja de día, **sube de madrugada**, y el día siguiente sube), el arranque de año (3 de enero +14 %) y la **temporada de mitad de año** (vacaciones +6,5 %). De 30 picos notables, 18 tienen factor identificado y 8 no tienen explicación con los datos disponibles | El control descontaba las vacaciones, lo que corrigió lo dicho sobre la mitad de año. El «diciembre falso» de 2021 salía de ajustar sin ningún día de ese año |
| **09** El entorno | ¿Cómo se relacionan los contextos externos entre sí, sin el hospital? | El calendario mueve la violencia (domingo ×1,78; noche festiva ×1,96; quincena → violencia intrafamiliar ×1,20). **Frío → IRA de la ciudad a 4 semanas**, humedad y lluvia a 5, y el receso escolar la corta. Estados: calma (febrero-mayo), frío y húmedo, seco y cálido (El Niño), decembrino y Feria | Contrastado con la literatura publicada; los estados y sus interacciones se enfrentan al hospital en los cuadernos siguientes |
| **10** Perfil del hospital | ¿Qué hospital es el SES y qué pasa con quien llega? | **Recibe todo y se queda con un tercio** de los triages como ingreso. El ingreso cae en escalón en mayo de 2024 (de 44,4 % a 29,9 %), antes de la crisis de Nueva EPS. **Series por diagnóstico desde 2020 sin NLP**: respiratorio, infecciosas, trauma y embarazo. Solo agregados; ninguna casilla de menos de 20 casos queda visible | Es descripción de subgrupo, no predicción |
| **11** Más cruces del entorno | ¿Qué más hace la ciudad consigo misma? | **Frío y humedad del último mes → IRA de la ciudad +8-10 % por desviación típica**, con y sin colegios; pesa más en temporada de lluvias (+12,6 % frente a +4,7 %, exploratorio). En los años recientes, enero trae una ola respiratoria que no se puede atribuir a la Feria. La lluvia baja las riñas (−5,7 %). El ENSO es solo contexto de fondo | El efecto del receso escolar no es robusto al método. El clima mueve el total entre 1,5 y 2,4 %, con efectos que no son los de la IRA (cuaderno 17) |
| **12** El clima completo | ¿Mueve el clima, entero y con método, el triage total? | Se hicieron **693 pruebas**. En 2022-2024 **34** sobreviven a BH (semana soleada y seca: +1-2 % a la vez). En 2025-2026 **se confirma 1**; el azar daría 0,85. Cuatro estados del clima: soleado y seco, bochorno húmedo, racha seca en calma y ventoso. **Ninguno se confirma**, tampoco contra respiratorio ni trauma. **La sequía de 2026 fue real** (julio −52 %) y **termina en agosto** (+44 %) | El clima mueve la IRA de la ciudad (11), pero no llega de forma medible al triage de este hospital |
| **13** La vigilancia completa | ¿Anticipa el SIVIGILA el triage? | Se hicieron **531 pruebas**; 13 sobreviven a BH y 3 se confirman, que son una sola serie: EDA hospitalizada de Caldas. **Pierde el efecto al quitarle la estación**, así que acompaña a la estación y no la anticipa. **Presión respiratoria de la ciudad → respiratorio del hospital, +11-14 %** a la vez, que llega al total en +2,2 %. La IRA 0-4 se mueve con el triage 0-4 en la misma semana, sin dirección: no avisa con semanas de adelanto | Nada entra como predictor del total. El efecto sobre lo respiratorio es de subgrupo, y solo hay 5 olas respiratorias en 2022-2025, que no se separan de la estación |
| **14** Los estados del triage | Por día y sin hora: ¿qué rodea a un pico, a un bajo y a un tramo estable? | **El calendario es el 72 % del día**; sin él, solo el 44 % de los picos del conteo siguen siendo pico. **Un pico es de toda la demanda** (todas las edades suben entre +16 y +27 %). Mayo concentra picos. La agitación es festiva o de la red. Nada externo anticipa los estados de forma estable | La asociación con las marcas acumuladas es exploratoria y no se separa de la fecha. La firma de «día soleado» de 2022-2024 se rompe en 2025 |
| **15** Predicciones tempranas | ¿Qué modelo y qué técnica predicen mejor 2026, con todos los años y todo el contexto? | Ocho modelos, LazyPredict (42 regresores), árboles afinados, jerárquico y combinaciones, en tres pruebas: corto plazo, año a ciegas y hora. **Líder: SARIMAX + LightGBM**. **El contexto externo no mejora el total**: ninguna externa pasa del 1,70 % de la ganancia, y buena parte del acierto era seguir los escalones de Nueva EPS | El 69 % de acierto es de 2026; en 2025 es cercano al 60 % (cuaderno 16) |
| **16** Hacia un entrenamiento holístico | ¿Por qué funciona la combinación, cuánto de su acierto es real y qué le falta al entrenamiento? | La combinación SARIMAX + LightGBM es la mejor también en 2025, pero con **~60 % de acierto, no el 69 % de 2026**. El modelo veía una sola EPS (SURA pasó de 8 % a 36 %), clima sin rachas ni transiciones, IRA sin EDA y ENSO sin regímenes. Límite de ~670 días independientes | El diseño por familias y regímenes se desarrolla en los cuadernos 17 a 21 |
| **17** El clima completo y sus cambios | ¿Qué parte del clima (sol, nubes, rachas, cambios bruscos) se asocia con la IRA de la ciudad, los ingresos respiratorios del hospital y el triage total? | 53 de 266 pruebas sobreviven contra la IRA de la ciudad; contra el total, los efectos son de 1,5 a 2,4 %, y ninguna prueba sobrevive contra los ingresos respiratorios | Los efectos del clima sobre la IRA y sobre el total tienen correlación −0,35: el total no es la IRA diluida |
| **18** El panel de las EPS | ¿Cómo se reparte el triage entre aseguradores y qué parte de cada escalón corresponde a cada uno? | El pico de 2024 es de SURA (de 59,0 a 91,9 triages por día entre marzo y abril). Nueva EPS y SURA suman el 77-86 % del triage. La relación de Nueva EPS con el hospital es por contratación | La compensación de los demás aseguradores es de 16 % y 11 % con la ventana de este cuaderno |
| **19** Las familias de enfermedad | ¿Cuándo sube cada familia de enfermedad de la ciudad, la mueve el clima y la ve el hospital? | Seis familias; el clima mueve las transmisibles (una racha seca larga sube la EDA +15,7 % por desviación típica) | La asociación de la varicela con el paro de 2021 no resiste ventanas al azar (un efecto igual o mayor aparece el 17,6 % de las veces). Salud mental y desastres descansa en un solo episodio, la alerta del volcán de 2023 |
| **20** Regímenes y fenómenos | ¿Dejan huella El Niño, La Niña, los sismos, el paro y los desastres? | El terremoto de agosto de 2026 baja el triage: −48,7 % el día 0, −22,3 % los días 1-7 y −4,6 % los días 8-21 contra las 8 semanas previas. Los sismos como clase (26 en la ventana del hospital) no tienen efecto. El paro no se separa de la COVID | Es un solo evento, y su efecto se mezcla con el desplome de Nueva EPS de julio de 2026 |
| **21** El triage por bandas de edad | ¿Reaparece cada factor con su tamaño en la parte donde actúa? | Firmas de clima por banda de edad en el descubrimiento (2022-03 a 2024-12), con 65 pruebas por parte | En 2025-2026 no se confirman: de 32, 8 conservan el signo, 1 se confirma y 4 se invierten |
| **23** El catálogo de variables | ¿Qué variables quedan en el modelo y se sostiene lo medido en varios años? | Catálogo de variables, validación en cuatro años y técnicas de la investigación, con probabilidades en bandas | Se retiraron las cifras de la bibliografía que no se pudieron verificar |

---

## Tres ideas que atraviesan todos los cuadernos

1. **Dos capas.** El **nivel** del volumen lo mueve la red de salud (Nueva EPS, cierres, alertas),
   a escalones que duran meses. Los **picos** los mueven otras cosas, cada una con su reloj.
2. **Cada factor tiene su reloj, su gatillo, su condición y su subgrupo.** Un promedio global sobre
   el total los diluye. Hay que mirar el cambio y no el nivel, en la ventana correcta y en la
   huella: hora, edad, asegurador.
3. **Toda fuente puede estar rota, incluida la que parece completa.** Antes de usar una serie, se
   mira buscando escalones. Ya van cuatro: el criterio de triage, la estancia, el clima dos veces
   y la serie de tránsito de la Policía.

## Cómo se corren

Todos leen agregados ya extraídos (`salidas/*.parquet`, `calendarios/*`). **Ninguno se conecta a
la base del hospital.**

```
.venv\Scripts\python.exe -m jupyter nbconvert --to notebook --execute --inplace notebooks\0X_....ipynb
```

Las fuentes y cómo se regenera cada una: `03_fuentes_externas.ipynb` y
`calendarios/docs/INVENTARIO.md`.
