# Los cuadernos: la historia, en orden

Cada cuaderno contesta **una pregunta**. Trae sus datos, sus figuras, sus fuentes, su lectura y
sus límites, y **lo que se supo después**.

**Las afirmaciones que resultaron falsas no se borran.** Quedan a la vista, con un recuadro
«Corrección del AAAA-MM-DD» debajo que dice qué cambió y por qué. El recorrido, con sus errores,
es parte del resultado. Las decisiones y su evidencia están en `docs/CONTEXTO.md`.

**La pregunta del proyecto:** *¿cuándo va a subir la cantidad de solicitudes de triage de urgencias
del SES Hospital Universitario de Caldas, y por qué?* El desenlace es siempre el **conteo total**.

---

## El hilo

| # | Pregunta | Lo que dejó | Lo que se supo después |
|---|---|---|---|
| **01** La serie de triage | ¿Cómo se comporta el conteo solo? | Ritmo semanal y horario (dos jorobas: 10 h y 14-15 h). La serie sube hasta 2024 y cae un 23,9 %. Reclasificación del nivel desde 2025 | La caída del **volumen** es de **Nueva EPS**, no de la reclasificación, porque reetiquetar no cambia el conteo. Hay huecos de registro (19-21-mar-2024) |
| **02** El hospital | ¿Qué mide cada variable? | Tres familias: la **población** (conteo, edad, hora), la **institución** (nivel, estancia) y la **red** (quién paga). Estacionalidad pediátrica | La gripa y los niños eran un **ejemplo**, no el objetivo. El asegurador resultó la variable institucional más grande |
| **03** Las fuentes externas | ¿De dónde sale cada dato externo y cuánto vale? | 16 fuentes oficiales (SIVIGILA, Power BI del INS, clima, MinDefensa, fiestas…), su cobertura, rezago y **23 escalones** | Se descubrió el **pluviómetro roto** (oct-2025 a jul-2026) y se corrigió |
| *04* | *Ciclo horario con Fourier* | *pendiente* | |
| **05** Validación sin motivo | ¿Se puede predecir sin el motivo de la nota? | El motivo no hace falta. Con los calendarios hechos a mano, **ninguna externa mejora el pronóstico** | Esa conclusión medía niveles semanales sobre el total. Con mecanismos (07) sí aparece señal |
| **06** Búsqueda de patrones | ¿Qué se mueve con el triage total? | Correlaciones con rezago: casi nada por encima del azar | **Sesgo de supervivencia**: se quitó la estacionalidad antes de mirar, y eso borró los efectos que se repiten cada año |
| **07** Mecanismos | ¿Qué deja huella si cada factor se mide con su reloj? | **Nueva EPS** explica los escalones de nivel. La **Feria** tiene huella propia (SOAT +37 % frente a +12 %). El tránsito de la ciudad no llega al SES | Con el pluviómetro corregido, «seco → lluvioso» en niños bajó de +22 % a +13 % ± 15: ya no es significativo |
| **08** Los picos | ¿Cuándo son, de qué tipo y qué los rodea? | **Tres relojes:** la noche festiva (baja de día, **sube de madrugada**, y el día siguiente sube), el arranque de año (3 de enero +14 %) y la **temporada de mitad de año** (vacaciones +6,5 %). Fiestas de pueblos lejanos: +2 % | Corrige lo dicho sobre la mitad de año: el control descontaba las vacaciones |

| **09** El entorno | ¿Cómo se relacionan los contextos externos entre sí, sin el hospital? | El calendario mueve la violencia (domingo ×1,78; noche festiva ×1,96; quincena → violencia intrafamiliar ×1,20). **Frío → IRA de la ciudad a 4 semanas**, humedad y lluvia a 5, y el receso escolar la corta. Estados: calma (febrero-mayo), frío y húmedo, seco y cálido (El Niño), decembrino y Feria. Todo contrastado con 86 estudios | Pendiente: enfrentar los estados y sus interacciones contra el hospital |
| **10** Perfil del hospital | ¿Qué hospital es el SES y qué pasa con quien llega? | **Recibe todo y se queda con un tercio** (la mitad hasta 2023); ingresa a los mayores y remite a los niños. Atiende síntomas, trauma, embarazo (creciente), urinario, respiratorio. **Series por diagnóstico desde 2020 sin NLP**: respiratorio (mayo-julio y enero), diarrea (marzo-abril), trauma (diciembre). Remite por falta de especialidad o de convenio con la EPS. Solo agregados, casillas < 5 ocultas | Preguntas: el código 9 de causa, la «no habilitación», el alza obstétrica |

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
