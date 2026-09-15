# Plan de desarrollo de la fase NLP

Versión 2 — 2026-09-15. Documento vivo. El historial de cambios del plan está en la
sección 12; cada modificación de alcance se registra allí y en `bitacora/`.

Este plan es el contrato de trabajo entre sesiones. Una sesión nueva, o varias en
paralelo, debe poder leer `ESTADO.md`, elegir un ítem de aquí, ejecutarlo, cerrarlo con
la evidencia exigida y dejar la documentación al día, sin necesidad de contexto
adicional. Quien lo lea dentro de un año debe entender qué se hizo, por qué, con qué
evidencia y qué quedó pendiente.

---

## 0. Cómo usar este documento

1. Leer `ESTADO.md`: estado por ítem, quién lo tiene, bloqueos, próximas acciones.
2. Elegir un ítem cuyas dependencias estén cerradas. Reclamarlo en `ESTADO.md` antes de
   tocar código.
3. Ejecutarlo según su ficha (sección 8). Si el ítem está mal planteado, corregir el plan
   y anotarlo en la sección 12, no improvisar.
4. Cerrarlo solo con la evidencia exigida (sección 3) y con la documentación actualizada
   (sección 4), en `bitacora/AAAA-MM-DD-E<n>.<m>.md`.
5. Las decisiones técnicas medidas van a `decisiones/`, una por archivo.

Nomenclatura: **fases** (1–6) son las del pipeline de texto; **etapas** (E0–E7) son las
del plan. Los ítems se identifican `E<n>.<m>`. *(P)* marca ítems que requieren una
persona.

---

## 1. Peticiones del propietario del proyecto

Registro fiel de lo solicitado en la sesión del 2026-09-15, en orden. Cada ítem del plan
indica qué petición atiende.

- **P1.** Investigar los componentes del equipo donde corre el pipeline.
- **P2.** La corrección ortográfica y la extracción de contexto no eran adecuadas.
  Mantener las correcciones baratas para los casos obvios; para los casos en que la
  corrección cambia la frase, el contexto o el motivo, o no corrige, comparar con el
  original y corregir la corrección. Estandarizar la nota a una forma más legible para
  que el agrupamiento tenga mejor separación. Se propusieron HUMADEX/spanish_medical_ner,
  un modelo Llama pequeño u otro modelo conveniente.
- **P3.** Añadir herramientas para manejar mejor las notas: la lista de palabras del
  español de victorhck y MeSpEn_Glossaries.
- **P4.** Ajustar el modelo para que, además de extraer la parte importante del motivo,
  detecte incoherencias o palabras sin sentido, compare con el original y corrija la
  corrección ortográfica. Revisar imports sin usar, funciones en el limbo y
  "alucinaciones" en cada fase.
- **P5.** Detener el procesamiento en curso (no había ninguno). Los resultados estaban
  corruptos. Crear un script que enfrente el flujo nuevo a los datos actuales de
  `triage_limpio.csv`: conservar las notas correctas, corregir las de mala ortografía,
  las que cambiaron de palabra y contexto, y las que no recibieron corrección; mantener
  los datos para no empezar de cero y que las notas nuevas se procesen progresivamente.
  Monitorear, detener ante error, corregir y relanzar hasta resultados satisfactorios.
  Permitido: subagentes, investigación en internet (minería de texto, corrección
  ortográfica, sintaxis y lingüística, bases médicas, artículos y tesis). Todo dentro de
  `NLP/`.
- **P6.**
  - (a) Documentación de la fase en `NLP/docs/`: qué se hace, qué se requiere, qué se
    investigó, referencias citadas profesionalmente, función de cada archivo. No más
    documentación extensa en comentarios ni al inicio de cada archivo (poco legible,
    poco práctica, parece un registro de correcciones). Documento formal de referencias
    por derechos de autor y para que un próximo empleado entienda qué hay y por qué.
  - (b) Implementar las técnicas y conclusiones investigadas: probar cuáles sirven,
    cuáles no, cuáles complementan; combinar; construir un flujo de trabajo y un ciclo
    de vida correctos. Las decisiones las toma quien desarrolla, con evidencia.
  - (c) Arquitectura dentro de `NLP/`: carpetas, subcarpetas, módulos reutilizables, sin
    archivos innecesariamente grandes, sin código redundante ni procesos confusos.
  - (d) Antes de desarrollar, un plan con formato de resultados, evidencia de
    completitud y evidencia clara de que se puede pasar al siguiente ítem.
  - (e) La sesión del 15/09 solo desarrolla el plan y documenta las peticiones, para que
    una sesión nueva o varias en paralelo tengan el handoff. Quien ejecuta actúa como
    orquestador generando los agentes necesarios. Se pueden descargar e instalar
    herramientas, bibliotecas y recursos si se ha revisado que son seguros y no
    infringen las normas de ciberseguridad de la empresa.
  - (f) *(Añadida en la versión 2.)* La documentación se actualiza y amplía a medida que
    se desarrolla y se completan objetivos, no al final, para quienes se encuentren con
    el proyecto en el futuro. El plan debe recoger lo que se dijo en la sesión con el
    mismo detalle con que se dijo, y la investigación debe estar citada y enlazada.

---

## 2. Diagnóstico de partida

Lo que se midió el 2026-09-15 antes de planificar. Son los hechos que justifican cada
etapa; las cifras completas están en `decisiones/` y en `bitacora/`.

### 2.1 Entorno

Lenovo ThinkPad 20LEA01100, Intel i7-8550U (4 núcleos / 8 hilos, 1,8 GHz, AVX2 sin
AVX-512 VNNI), 16 GB DDR4-2133 (5,9 GB libres durante la medición), Intel UHD 620 sin
CUDA, 241 GB de disco libres. `torch 2.6.0+cpu`. Ollama 0.34 con `qwen2.5:3b-instruct`
(1,9 GB) y `gemma4:26b` (18 GB, no cabe en RAM). Java 21 y LanguageTool 6.8 operativos.
Base de datos `DWSES` en `ls-cobra`: 94.136 notas en `DIM_TRIAGE.HCTMOTCON`.

Consecuencia: un modelo generativo de 3 B rinde 5,5 tokens/s; sobre 9.311 notas serían
~22 h y sobre el corpus, ~10 días. Nada generativo sobre el corpus completo; nada de
modelos de más de ~125 M de parámetros en el bucle de calibración.

### 2.2 El CSV existente (9.311 notas al cierre; 8.751 al medir)

| Hecho | Medición | Causa raíz |
|---|---|---|
| La fase 5 descartaba el motivo de consulta | media del contenido descartado 0,195; 18,1 % de las notas perdían más de la mitad; en notas de varias oraciones sobrevivían las cortas y se perdían las largas (p. ej. quedaba la negación y se perdía el motivo) | `salidas/lexico_clinico.json` no existía → `densidad_clinica()` = 0 para toda oración → toda oración de ≥ 8 palabras se descartaba |
| La fase 2 corregía sin vocabulario ni protección de nombres | `en_vocabulario()` devolvía False para toda palabra (`dipirona`, `cefalea`, `gestante` expuestas); `entidades()` devolvía vacío | modelo spaCy `es_core_news_md` no instalado |
| Restauración de siglas y clasificador de tramos inactivos | sin señal visible | `lexico_casing.json` y `clasificador_frases.joblib` no existían |
| Correcciones que cambian el sentido | `ahogado → abogado`, `volcamiento → tocamiento`, `mareado → marcado`, `tosiendo → comiendo`, `laceraciones → alteraciones` | detección falsa: la palabra correcta faltaba en el léxico y el candidato ganaba por frecuencia en corpus general |
| Glosas en el texto de embedding | 38,1 % de las notas | diseño de la fase 3 (modo `anotar`) |
| Cobertura de cola larga | `ginecobstetricia`, `tensionales`, `volcamiento`, `tosiendo` no reconocidas | léxico curado incompleto |

Ninguno de los cuatro artefactos ausentes hacía fallar el pipeline: el CSV salía
completo, con todas sus filas y columnas, y equivocado.

### 2.3 Lo que se corrigió el mismo día (previo al plan; se consolida en E0.1)

- Léxico reconstruido (32.315 formas): descarte medio 0,195 → 0,121; notas que pierden
  > 50 %: 18,1 % → 8,7 %; 25,1 % de las notas recuperan contenido; 9,5 s por 8.751 notas.
- spaCy instalado; casing (4.843 entradas) y clasificador (exactitud 0,971 sobre 19.586
  tramos curados) reconstruidos.
- `nucleo/requisitos.py`: detiene la corrida si falta un artefacto exigido.
- Fase 2b `coherencia.py`: deshace correcciones incoherentes con la nota; 0,4 % de notas
  tocadas, 2,6 ms por nota, 32 reversiones distintas verificadas a mano (tres iteraciones:
  1,5 % → 0,5 % → 0,4 %, eliminando falsos positivos como `deposion → deposicion`).
- `reparacion/`: reprocesa el CSV desde `texto_original`. Cuatro defectos encontrados y
  corregidos con el bucle de monitoreo sobre 100 notas (fase 3 no corría; sin léxico de
  frecuencias el corrector dejaba `dolro`; el clasificador descartaba motivos enteros;
  la métrica contaba relleno). Resultado: 69 intactas, 24 recuperan motivo, 3 ortografía,
  4 alarmas (las cuatro administrativas).
- `VERSION_CORRECTOR` → 4; caché anterior apartada.

### 2.4 Lo que la investigación cambió en el enfoque

- Los fallos son de **detección**, no de elección de candidato: la palanca es el léxico
  de dominio y una política de precisión (F0.5), no un modelo mejor
  (`INVESTIGACION.md` §1–2).
- HUMADEX/spanish_medical_ner se descarta: base `bert-base-cased`, inglés
  (`INVESTIGACION.md` §5.1).
- Las glosas dañan el agrupamiento y `clustering/etiquetas.py` depende de ellas
  (`INVESTIGACION.md` §6.1; sección 7 de este plan).
- Con notas de 6 palabras, la pregunta útil no es qué NER sino cómo enlazar la mención
  a un concepto (`INVESTIGACION.md` §5.3).

### 2.5 Estado del código

49 archivos, 12.419 líneas. Seis archivos de más de 400 líneas (`reduccion.py` 864,
`auditoria.py` 851, `procesar.py` 811, `ortografia.py` 730, `contexto.py` 605,
`extractor.py` 593). Duplicaciones: cuatro `texto_gritado`, tres `sin_tildes`, dos
`_es_expansion`, dos léxicos clínicos paralelos, tres distancias de edición, cuatro
`RE_ENCABEZADO` (`ARQUITECTURA.md` §5). Sin pruebas automatizadas. `alarmas.reiniciar()`
nunca se invoca. `evaluacion/referencia.py` inoperante por una salida nunca generada.
Documentación extensa dentro del código, con historia de incidentes, y README
desactualizado.

---

## 3. Principios de trabajo

1. **Evidencia antes que criterio.** Nada se adopta sin medirlo contra los datos reales
   y contra la línea base (E0.5). Cifra y descarte quedan en `decisiones/`.
2. **Precisión antes que cobertura.** Cambiar una palabra correcta cuesta más que dejar
   un error. Métricas de referencia: F0.5 y tasa de intervención sobre texto limpio.
3. **El modelo propone, las reglas verifican.** Ningún modelo escribe texto que llegue al
   CSV sin verificación literal contra la nota. Ningún modelo generativo reescribe texto
   clínico.
4. **El contrato con el resto del proyecto no se rompe** (sección 7). Los cambios que lo
   afecten se coordinan con `embedding/` y `clustering/` y se validan con
   `python -m clustering --validar`.
5. **Documentación en `docs/`, no en el código; y al día, no al final** (sección 4).
6. **Nada se cierra sin evidencia reproducible** (sección 3.1).
7. **Los datos de pacientes no salen del entorno institucional.** Ni en prompts a
   servicios externos, ni en la documentación: ejemplos anonimizados o sintéticos.
8. **Cada técnica entra tras una bandera.** Toda técnica nueva se activa con una
   constante de configuración, para poder medir con y sin ella y para volver atrás.

---

## 4. Definición de "cerrado", evidencia y mantenimiento de la documentación

### 4.1 Formato de la evidencia de cierre

Cada ítem se cierra con `bitacora/AAAA-MM-DD-E<n>.<m>.md`:

```
# E<n>.<m> — <título>
Sesión: <identificador o persona>   Fecha: AAAA-MM-DD   Estado: cerrado | bloqueado
Petición atendida: P<k>

## Objetivo
<una frase>

## Comandos ejecutados
<comando exacto, con directorio de trabajo>

## Salida relevante
<fragmento literal de la salida, con los números>

## Artefactos producidos
<ruta> — <filas o tamaño> — <sha256 si es un dato versionado o descargado>

## Métricas frente a la línea base
| métrica | línea base | resultado | diferencia |

## Criterio de aceptación
<el criterio de la ficha del ítem, y si se cumplió>

## Decisión
<qué se adopta, qué se descarta; enlace a decisiones/ si aplica>

## Documentación actualizada
[ ] ESTADO.md (fila del ítem, problemas conocidos, próximas acciones)
[ ] ARQUITECTURA.md (si cambió un archivo, una constante, una dependencia)
[ ] FLUJO.md (si cambió lo que hace una fase)
[ ] OPERACION.md (si cambió un comando, un artefacto o un procedimiento)
[ ] REFERENCIAS.md e INVESTIGACION.md (si se usó o descartó una fuente nueva)
[ ] decisiones/ (si se fijó un umbral o se eligió un método)
[ ] docstring del módulo tocado, breve, apuntando a docs/

## Pendientes que deja
<lista, o "ninguno">
```

Un ítem sin comandos reproducibles y salida literal no está cerrado, aunque el código
exista. Un ítem con la lista de documentación sin marcar no está cerrado.

### 4.2 Gate de etapa

Cada etapa termina con un gate: condición verificable que autoriza a empezar la
siguiente. Todo gate incluye, además de lo específico de la etapa, dos condiciones
fijas: `evaluacion/paridad_docs.py` en 0 faltantes / 0 huérfanas (desde que exista,
E1.2), y `ESTADO.md` con todos los ítems de la etapa en `cerrado` o `bloqueado` con
motivo.

### 4.3 Registro de decisión

`decisiones/AAAA-MM-DD-<tema>.md`:

```
# <tema>
Fecha, ítem del plan, autor.
## Pregunta
## Opciones consideradas
## Medición (datos, muestra, comandos, resultados)
## Decisión y motivo
## Qué la invalidaría
```

### 4.4 Política de mantenimiento de la documentación

La documentación es parte del producto y se actualiza en el mismo ítem que cambia el
código, no en una etapa posterior. Reglas:

1. **Quién**: quien cierra el ítem. El orquestador no cierra un ítem con documentación
   pendiente.
2. **Qué documento toca cada tipo de cambio**:

   | Cambio | Documentos |
   |---|---|
   | Archivo nuevo, eliminado, movido o dividido | `ARQUITECTURA.md` §1–§3, `paridad_docs.py` |
   | Constante de configuración nueva o cambiada | `ARQUITECTURA.md` (entrada del archivo), `OPERACION.md` si el operador la toca |
   | Comportamiento de una fase | `FLUJO.md` |
   | Comando, artefacto, procedimiento | `OPERACION.md`, `ESTADO.md` §2 |
   | Umbral o método elegido con medición | `decisiones/` |
   | Fuente, recurso o modelo usado o descartado | `REFERENCIAS.md` y `INVESTIGACION.md` (con enlace y veredicto) |
   | Alcance del plan | `PLAN.md` §12 |
   | Estado de un ítem | `ESTADO.md` (al reclamar y al cerrar) |

3. **Cómo**: cada documento lleva al final una sección `Historial` con fecha, ítem y
   resumen del cambio. Los ejemplos de notas se anonimizan.
4. **Verificación**: `paridad_docs.py` comprueba la correspondencia archivo ↔ entrada en
   `ARQUITECTURA.md`; la revisión de `REFERENCIAS.md` es parte de E7.4; la lectura de
   `FLUJO.md` + `OPERACION.md` por un agente sin contexto es la prueba de E1.3–E1.4 y se
   repite en el gate de E6.
5. **Estilo**: formal, sobrio, en español; sin narrativa de incidentes en el código (eso
   va a `decisiones/` y `bitacora/`); tablas donde haya más de tres elementos
   comparables; cifras siempre con su muestra y su fecha.

### 4.5 Formatos de resultados de datos

- CSV: `encoding="utf-8-sig"`, escritos con `NLP/nucleo/salida.py` (QUOTE_ALL, CRLF).
- Métricas: `salidas/metricas/<fecha>-<item>.json` con las claves de E2.2, más una fila en
  `salidas/metricas/historico.csv` (`fecha, item, version_corrector, F0.5,
  precision_deteccion, cobertura_deteccion, precision_correccion, cobertura_correccion,
  tasa_intervencion, acuerdo_motivo, notas, comentario`).
- Léxicos y listas de protección: `datos/lexicos/<nombre>.txt`, una forma por línea,
  cabecera de comentarios con fuente, licencia, fecha y sha256 del origen.
- Recursos externos: `recursos_externos/` (ignorado por git) y
  `datos/recursos_manifiesto.json` (versionado: URL, licencia, sha256, fecha, tamaño,
  archivos extraídos).
- Conjunto de evaluación: `datos/evaluacion/gold_v<n>.csv` con `OID, texto_original,
  texto_correcto, motivo_span, gravedad, anotador, comentario`.

---

## 5. Protocolo de sesión y trabajo en paralelo

1. Al abrir: leer `ESTADO.md`; `python -m NLP.nucleo.requisitos`; `git status`.
2. Reclamar el ítem en `ESTADO.md` (columna *sesión*, con fecha) antes de tocar código.
3. Trabajar en una rama `nlp/E<n>.<m>-<tema>`; con sesiones simultáneas, cada una en su
   propio `git worktree`.
4. Un ítem por rama; se integra a `main` con la bitácora escrita. Conflictos en
   `ESTADO.md` se resuelven conservando ambas filas.
5. Los artefactos de `salidas/` no se versionan; si un ítem necesita el de otro, lo
   regenera con el comando documentado.
6. Nunca dos sesiones sobre el mismo ítem. Un ítem sin avance en una sesión se anota
   `bloqueado` con el motivo.
7. Orquestación con agentes (P6e): el orquestador entrega a cada agente el texto de la
   ficha del ítem, las secciones 3 y 4 de este plan y la política de seguridad
   (sección 6). El agente entrega evidencia; **no cierra ítems ni edita `ESTADO.md`**. El
   orquestador re-ejecuta al menos el comando principal antes de cerrar. Los agentes de
   investigación no modifican el repositorio. Los agentes de implementación no ejecutan
   comandos que escriban en `datos/` sin que la ficha lo diga expresamente (lección de
   `frases_etiquetadas.csv`).

---

## 6. Política de seguridad para descargas e instalaciones

1. **Fuente oficial únicamente**: Zenodo con DOI; repositorios de la organización autora
   (PlanTL-GOB-ES, BSC-NLP4BIA, ICB-UMA, lcampillos, hpi-dhc); portales estatales
   (datos.gov.co, DANE, AEMPS, INE); PyPI; Hugging Face con tarjeta de modelo. Sin
   espejos.
2. **Licencia registrada antes de descargar** en `REFERENCIAS.md` y en el manifiesto.
   Sin licencia identificable no se integra.
3. **Solo datos y pesos; nunca ejecutables ni instaladores.** TSV, CSV, JSON, XML, XLSX,
   TXT, ZIP con solo lo anterior, `safetensors`, ONNX. Los ZIP se listan antes de extraer
   y se extrae solo lo necesario.
4. **Pesos de modelos**: preferir `safetensors`; con `pytorch_model.bin` (pickle) dejar
   constancia y cargar con las protecciones disponibles; nunca `trust_remote_code=True`.
5. **Paquetes Python**: PyPI, versión fijada en `requirements.txt`, en el `.venv` del
   proyecto; comprobar mantenimiento, licencia y dependencias transitivas; sin
   compiladores ni binarios externos no documentados. Registrar en `REFERENCIAS.md` §4.
6. **Integridad**: sha256 de cada archivo en `datos/recursos_manifiesto.json`; el
   descargador (E3.1) rechaza un hash que no coincida.
7. **Sin credenciales ni datos de pacientes en peticiones salientes.** Los servicios con
   registro (UMLS, MedLexSp) los gestiona una persona.
8. **Antivirus institucional**: nada se desactiva; los archivos quedan en disco local
   para su análisis.
9. **Licencias con obligaciones** (AGPL, CC-BY-SA, uso solo investigación): no entran a
   producción sin decisión explícita del propietario, registrada en `decisiones/`.

---

## 7. Contrato con el resto del proyecto

Determinado por inspección de `embedding/`, `clustering/`, `patrones/` y `calendarios/`
el 2026-09-15.

| Consumidor | Archivo | Columnas obligatorias | Comportamiento si falta |
|---|---|---|---|
| `embedding/corpus.py` | `triage_limpio.csv` | `OID`, `texto_embedding` | `SystemExit`; el resto de columnas se ignora |
| `embedding/estructurar.py` | `triage_limpio.csv` | `OID` y la primera disponible de `texto_normalizado`, `texto_corregido`, `texto_original` | `ValueError`; lista `texto_limpio`, que no existe |
| `clustering/anclas.py` | `notas_descartadas.csv` | `OID` | degrada a ceros en silencio si el archivo falta |

- `OID` numérico (`int64`); no se exige único (gana la última aparición). Ceros a la
  izquierda romperían `clustering/fechas.py` y anularían `anclas.py` en silencio.
- CSV con BOM utf-8-sig y separador `,`; `embedding/corpus.py` lee sin `encoding=`.
- Ventana de `bge-m3`: 128 tokens (~1,99 tokens por palabra); p99 actual 95, máximo 170;
  se truncan 10 de 5.020 textos. Alargar `texto_embedding` aumenta la truncación sin
  aviso: correr `python -m clustering --validar` tras cualquier cambio de longitud.
- **`clustering/etiquetas.py` usa las glosas entre paréntesis de `texto_embedding` para
  nombrar clusters.** Quitarlas sin darle otra fuente degrada los nombres sin fallo
  visible (condiciona E5.1).
- `embedding/` deduplica por `sha1(texto)[:16]`, no por `OID`: un texto reparado se
  revectoriza solo; no hace falta `--rehacer`; los vectores viejos quedan huérfanos en
  `vectores.f32` (disco).
- Puntos de contacto que deben sobrevivir a cualquier refactor: `NLP.rutas`
  (`TRIAGE_LIMPIO`, `NOTAS_DESCARTADAS`, `CATALOGO_SINTOMAS`; `embedding/rutas.py` lo
  importa a nivel de módulo), `NLP.nucleo.morfologia.sin_tildes`,
  `NLP.nucleo.conexion_bd.obtener_engine`, `NLP.reduccion.reduccion.recortar`.
- Acoplamiento inverso: `NLP/rutas.py` apunta a `embedding/datos/catalogo_sintomas.json`;
  lo leen `NLP/recursos/lexico.py`, `NLP/depuracion/depuracion.py`,
  `NLP/nucleo/requisitos.py`, `embedding/extraccion.py`, `clustering/validacion.py`.
- Transparentes: cambiar el contenido de columnas de texto; añadir columnas; reorganizar
  módulos respetando los puntos de contacto; cambiar `motivo_descarte`.

---

## 8. Etapas e ítems

Ficha de cada ítem: **Por qué** (hecho del diagnóstico o de la investigación),
**Cómo** (enfoque y fuente), **Entregable** (con formato), **Evidencia de cierre**,
**Criterio de aceptación** (numérico cuando es posible), **Dependencias**,
**Esfuerzo** (orden de magnitud: horas / día / días; CPU si aplica), **Responsable**
(agente / orquestador / persona), **Documentación que toca**.

Orden: E0 → (E1 ∥ E2) → E3 → E4 → E5 → E6 → E7. Dentro de cada etapa se indica qué ítems
pueden ir en paralelo.

### E0 — Consolidación y línea base

Objetivo: dejar el repositorio en un estado conocido, reproducible y medido antes de
cambiar nada más. Sin esto, ningún experimento posterior puede afirmar que mejora.

**E0.1 Consolidar el trabajo del 2026-09-15** *(P5, P6e)*
- Por qué: hay 13 archivos modificados o nuevos sin commit (`ESTADO.md` §2); una sesión
  nueva no puede distinguir lo hecho de lo pendiente.
- Cómo: commit en `main` con mensaje que enlace a `bitacora/2026-09-15-sesion-diagnostico-y-plan.md`.
- Entregable: commit. Evidencia: hash; `git status` limpio; `python -m
  NLP.nucleo.requisitos` todo en OK.
- Criterio: `git diff --stat main` vacío tras el commit.
- Dependencias: ninguna. Esfuerzo: minutos. Responsable: persona (autoriza) +
  orquestador. Documentación: `ESTADO.md` §2.

**E0.2 Terminar y revisar la reparación completa** *(P5)*
- Por qué: el job sobre 9.311 notas quedó corriendo sin `--aplicar`; hay que juzgar su
  informe antes de sustituir el CSV.
- Cómo: `informe_reparacion.csv` y el resumen por término que imprime `reparar.py`;
  revisar cada término de `perdio_motivo` y clasificarlo benigno (administrativo,
  examen físico, relleno) o real (motivo, mecanismo, síntoma, lateralidad, negación).
  Muestra de 100: 4 alarmas, las cuatro benignas.
- Entregable: tabla término → veredicto en la bitácora; recuento por categoría.
- Evidencia: salida literal del resumen; tabla.
- Criterio: `recupero_motivo` > `perdio_motivo`; **cero términos con veredicto real**;
  si hay alguno, se abre un ítem con la causa antes de E0.3.
- Dependencias: job terminado. Esfuerzo: 1 h de revisión. Responsable: orquestador.
  Documentación: `ESTADO.md`, `decisiones/` si aparece una causa nueva.

**E0.3 Aplicar la reparación y revectorizar** *(P5)*
- Por qué: el CSV actual es la materia prima de `embedding/` y `clustering/`; mientras no
  se sustituya, el clustering trabaja sobre datos corruptos.
- Cómo: `python -m NLP.reparacion.reparar --aplicar` (guarda copia con sello); `python -m
  embedding.vectorizar`; `python -m clustering --validar`.
- Entregable: `triage_limpio.csv` sustituido; copia previa; almacén de vectores
  actualizado.
- Evidencia: salida de los tres comandos; número de textos revectorizados.
- Criterio: textos revectorizados = textos cuyo `texto_embedding` cambió (contar por
  hash antes/después); `--validar` sin truncaciones nuevas respecto a las 10 de 5.020.
- Dependencias: E0.2. Esfuerzo: horas de CPU (vectorización). Responsable: orquestador.
  Documentación: `ESTADO.md` §2–3, `OPERACION.md` (procedimiento de aplicación).

**E0.4 Homogeneizar la escritura de CSV y las rutas** *(P6c)*
- Por qué: `reparar.py` escribe con pandas (QUOTE_MINIMAL) y `procesar.py` con
  `nucleo/salida.py` (QUOTE_ALL); un `procesar.py` posterior añadiría filas con otro
  entrecomillado. La copia `triage_limpio.previo-<sello>.csv` no la purga `rotar()`.
  `triage_reparado.csv` e `informe_reparacion.csv` se definen fuera de `rutas.py`.
- Cómo: `reparar.py` usa `EscritorCSV`; nombre de copia compatible con el glob de
  `rotar()`; constantes en `rutas.py`.
- Evidencia: `diff` de cabecera y de una fila entre ambos escritores (idénticos);
  prueba en E2.1.
- Criterio: byte-idéntico para la misma fila.
- Dependencias: ninguna. Esfuerzo: 1–2 h. Responsable: agente. Documentación:
  `ARQUITECTURA.md` (rutas), `OPERACION.md`.

**E0.5 Línea base de métricas** *(P6b)*
- Por qué: sin cifra de partida no se puede afirmar que un experimento mejora.
- Cómo: `python -m NLP.evaluacion.metricas --gold datos/evaluacion/gold_v0.csv` (E2.2)
  sobre el corrector actual (`VERSION_CORRECTOR` 4) más el corpus autoinducido y el
  conjunto limpio de E2.3.
- Entregable: `salidas/metricas/<fecha>-linea-base.json` y primera fila de
  `historico.csv`.
- Evidencia: el archivo y el comando.
- Criterio: existen las doce claves del formato 4.5 con valor numérico.
- Dependencias: E0.6, E2.2, E2.3. Esfuerzo: 1 h. Responsable: orquestador.
  Documentación: `ESTADO.md` §3, `decisiones/<fecha>-linea-base.md`.

**E0.6 Conjunto de evaluación v0** *(P)* *(P6b)*
- Por qué: es la vara de todas las etapas siguientes. La investigación (§3.5) indica
  cómo construirlo con poco esfuerzo humano.
- Cómo: partir de `evaluacion/escaneo.py --muestra` (muestreo estratificado por rareza,
  hoy nunca ejecutado) y `evaluacion/referencia.py` (anotaciones existentes en
  `datos/referencia_correcciones.json`). Estratos: distancia de edición, ratio de
  frecuencia original/corrección, longitud; sobremuestrear alto riesgo. 300–500 notas;
  ~200 con doble anotación. Guía de anotación con la taxonomía de gravedad
  (`INVESTIGACION.md` §3.4). Un agente prepara muestreo, guía y plantilla; una persona
  con criterio clínico anota.
- Entregable: `datos/evaluacion/gold_v0.csv`; `docs/anotacion.md`.
- Evidencia: distribución por estrato; κ de Cohen sobre las dobles.
- Criterio: ≥ 300 notas; κ ≥ 0,7 (si es menor, revisar la guía y re-anotar la muestra
  de calibración).
- Dependencias: ninguna técnica; tiempo de una persona. Esfuerzo: agente 2–3 h; persona
  1–2 jornadas. Documentación: `docs/anotacion.md`, `ESTADO.md`.

**Gate E0**: commit hecho; reparación aplicada con cero pérdidas reales y revectorización
verificada; línea base registrada; gold v0 con κ reportado; condiciones fijas de 4.2.

### E1 — Documentación

Objetivo (P6a, P6f): que una persona nueva entienda qué hay en `NLP/`, por qué y cómo se
ejecuta, sin leer el código; y que la documentación quede estructurada para mantenerse
en cada ítem posterior. Puede ir en paralelo con E2.

**E1.1 Estructura de `docs/`** — Estado: hecho en la versión inicial (README, PLAN,
ESTADO, INVESTIGACION, REFERENCIAS, ARQUITECTURA, decisiones/, bitacora/). Falta `FLUJO.md`,
`OPERACION.md`, `anotacion.md` (E0.6) y la sección `Historial` en cada documento.
Criterio: todos los enlaces del índice resuelven; cada documento tiene `Historial`.

**E1.2 `ARQUITECTURA.md` y paridad automática**
- Por qué: la versión inicial existe (49 archivos, grafo, E/S, duplicaciones); sin
  comprobación automática se desactualiza en el primer refactor.
- Cómo: `evaluacion/paridad_docs.py` recorre `NLP/**/*.py` y las entradas
  `**\`ruta.py\`**` del documento; informa faltantes y huérfanas; opción `--estricto`
  devuelve código de salida distinto de cero.
- Evidencia: salida "0 faltantes, 0 huérfanas". Criterio: idem, y el script forma parte
  del gate de todas las etapas.
- Esfuerzo: 2 h. Responsable: agente. Documentación: `ARQUITECTURA.md` §6 (guía de
  estilo, con E1.6).

**E1.3 `FLUJO.md`**
- Cómo: por fase (1, 2, 2b, 3, 4, 5, y 6 cuando exista): entrada, salida, artefactos que
  consume, constantes que la gobiernan, decisiones enlazadas, tres ejemplos sintéticos
  (no reales) del antes y el después, y qué medición respalda cada paso.
- Evidencia y criterio: la prueba de E1.4.
- Esfuerzo: medio día. Responsable: agente + orquestador (revisión).

**E1.4 `OPERACION.md` (runbook)**
- Cómo: instalación desde cero (Python 3.11, `.venv`, `requirements.txt`, Java, modelo
  spaCy, Ollama opcional); artefactos obligatorios y cómo regenerarlos; comandos por
  escenario (corrida nueva, reanudar, reparar, rehacer, revectorizar); qué mirar en la
  salida; errores conocidos y su solución; advertencia sobre `frases.py`.
- Evidencia: un agente **sin contexto previo**, siguiendo solo `FLUJO.md` y
  `OPERACION.md`, ejecuta el pipeline sobre 50 notas y obtiene el CSV; su transcripción
  se adjunta.
- Criterio: la prueba se completa sin preguntar nada a nadie.
- Esfuerzo: medio día. Responsable: agente; verificación por un segundo agente.

**E1.5 Migrar la documentación del código a `docs/`** *(P6a)*
- Por qué: los docstrings actuales narran incidentes y cifras; el propietario los
  considera ilegibles y poco prácticos; el contenido, sin embargo, es valioso y no debe
  perderse.
- Cómo: por archivo: (1) extraer cada bloque explicativo; (2) decidir destino
  (`decisiones/` si es un umbral medido, `FLUJO.md` si explica una fase,
  `ARQUITECTURA.md` si explica una responsabilidad, `bitacora/historico.md` si es
  historia); (3) dejar un docstring de módulo de ≤ 5 líneas y de función de ≤ 3 líneas
  que diga qué hace y apunte a `docs/`; (4) registrar en la bitácora del ítem la tabla
  bloque → destino.
- Evidencia: tabla bloque → destino por archivo; `pyflakes` limpio; conteo de líneas de
  docstring antes y después.
- Criterio: ningún bloque eliminado sin destino anotado; ningún docstring de módulo > 5
  líneas; `pytest` (E2.1) verde.
- Dependencias: E1.3, E2.1. Esfuerzo: 1–2 días (49 archivos). Responsable: agentes por
  subpaquete, en paralelo; orquestador revisa la tabla de destinos.

**E1.6 Guía de estilo** — Sección 6 de `ARQUITECTURA.md`: nombres en español; `rutas.py`
único origen de rutas; `datos/` vs `salidas/`; escritura de CSV; tamaño máximo de
archivo (400 líneas); formato de docstring; banderas de configuración; anonimización de
ejemplos. Criterio: el texto existe y E1.5 lo aplica.

**Gate E1**: paridad 0/0; prueba de ejecución por agente sin contexto superada;
`REFERENCIAS.md` e `INVESTIGACION.md` revisados por el propietario; cada documento con
`Historial`.

### E2 — Infraestructura de evaluación

Objetivo: poder afirmar con números si un cambio mejora o empeora (principios 1 y 2).
Paralelo con E1. Los ítems E2.1–E2.4 son independientes entre sí.

**E2.0 Contadores de alarmas** — `alarmas.reiniciar()` está documentado como parte de la
corrida y nunca se llama. Entregable: llamada al inicio de `procesar.main()` y
`reparar.main()`. Evidencia: prueba de E2.1 con dos corridas en el mismo proceso.
Esfuerzo: minutos.

**E2.1 Pruebas de regresión**
- Por qué: no hay ninguna prueba automatizada; cada arreglo de hoy se verificó a mano.
- Cómo: `NLP/tests/` con `pytest`. Casos fijos de la sesión: `dolro → dolor`,
  `anuseas → nauseas`, `ahogado` / `volcamiento` / `mareado` / `tosiendo` intactos,
  `deposion → deposicion` no revertido, `comisura labial` conservada por la fase 5,
  trámite puro descartado, `requisitos.exigir()` detiene sin léxico, escritor de CSV
  byte-idéntico (E0.4), contadores reiniciados (E2.0). Más una prueba de salida
  byte-idéntica de las fases 1–5 sobre 50 notas sintéticas fijadas en
  `tests/datos/`.
- Evidencia: `pytest -q` en verde con tiempo. Criterio: todo verde en < 5 min sin
  LanguageTool ni BD (mocks o marcadores `slow`).
- Esfuerzo: 1 día. Responsable: agente. Documentación: `OPERACION.md` (cómo correr las
  pruebas), `ARQUITECTURA.md` (carpeta `tests/`).

**E2.2 Módulo de métricas**
- Por qué: `INVESTIGACION.md` §3.6.
- Cómo: `NLP/evaluacion/metricas.py`: precisión y cobertura de detección; precisión y
  cobertura de corrección; F0.5; `tasa_intervencion_texto_limpio`; CER/WER (control);
  acuerdo de `motivo_span` con el gold (Jaccard de tokens); CLI `python -m
  NLP.evaluacion.metricas --gold <csv> [--csv <salida>] [--guardar]`; escribe el JSON y
  la fila de `historico.csv` (formato 4.5).
- Evidencia: ejecución sobre gold v0; JSON. Criterio: las doce claves; el módulo se usa
  en todas las bitácoras de E3–E5.
- Esfuerzo: 1 día. Responsable: agente.

**E2.3 Corpus de errores autoinducidos y conjunto limpio**
- Por qué: mide cobertura sin anotar (Fivez 2017; Bravo-Candel 2021) y precisión sobre
  texto correcto, la evaluación que faltaba.
- Cómo: `evaluacion/perturbar.py` con reglas: transposición, omisión, duplicación,
  homófonos `b/v` `ll/y` `h`, dígrafos `qu/k` `cc/c`, tildes, teclado adyacente;
  semilla fija; ≥ 5.000 pares desde notas cuyos tokens están todos en el léxico de alta
  frecuencia (≥ 20). El conjunto limpio son esas mismas notas sin perturbar.
- Evidencia: tamaños; métricas del corrector actual sobre ambos (entra en E0.5).
- Criterio: los archivos se regeneran de forma determinista (mismo sha256 con la misma
  semilla).
- Esfuerzo: medio día. Responsable: agente.

**E2.4 Auditoría por par distinto**
- Por qué: `INVESTIGACION.md` §3.2; revisar 300 pares por hora en vez de miles de notas.
- Cómo: `evaluacion/pares.py` → `salidas/pares_correccion.csv` con `original,
  correccion, ocurrencias, freq_original, freq_correccion, distancia,
  fonetica_igual, cubo, decision_humana`; cubos: revertir (freq_orig ≥ freq_corr, o
  original en lista de protección, o cambia negación/número/lateralidad), aceptar
  (freq_orig ≤ 2, freq_corr ≥ 50, distancia ≤ 2, misma clave fonética), revisar (resto),
  ordenado por ocurrencias × riesgo.
- Evidencia: número de pares distintos; cobertura acumulada de los 200 primeros;
  distribución por cubo.
- Criterio: la tabla existe y se puede regenerar; la columna `decision_humana` la rellena
  una persona (alimenta E0.6 y E4).
- Esfuerzo: medio día. Responsable: agente.

**Gate E2**: `pytest` verde; línea base calculada con `metricas.py`; tabla de pares
generada; condiciones fijas.

### E3 — Recursos léxicos y listas de protección

Objetivo (P2, P3): atacar la causa raíz — detección falsa por léxico incompleto —
integrando cada recurso por separado y midiendo su efecto. Todos dependen de E3.1;
E3.2–E3.8 son independientes entre sí y se pueden repartir.

Medición común a todos los ítems: métricas de E2.2 sobre gold v0 y sobre E2.3; tamaño
del léxico antes/después; lista de las palabras frecuentes no reconocidas antes/después
(la de 35 de la sesión del 15/09); casos de cola larga (`ginecobstetricia`,
`tensionales`, `volcamiento`, `tosiendo`, `mareado`) reconocidos.

**E3.1 Descargador con manifiesto**
- Cómo: `recursos/descargar.py` lee `datos/recursos_manifiesto.json` (nombre, URL,
  licencia, sha256, archivos a extraer, User-Agent si hace falta), descarga a
  `recursos_externos/`, verifica hash, registra fecha; cumple la sección 6.
- Evidencia: manifiesto; una descarga verificada; rechazo demostrado con un hash
  alterado. Criterio: ningún recurso de E3 entra al léxico sin pasar por aquí.
- Esfuerzo: medio día. Responsable: agente. Documentación: `OPERACION.md`,
  `REFERENCIAS.md` §2.

**E3.2 Siglas protegidas** — `datos/lexicos/siglas_protegidas.txt`, ~40 entradas a mano
(`INVESTIGACION.md` §4.6), integradas como lista de protección (bypass antes del
corrector). Evidencia: prueba de regresión "ninguna se corrige"; métricas. Criterio: cero
intervenciones sobre ellas en el conjunto limpio. Esfuerzo: 1 h.

**E3.3 Léxico del corpus propio** — `datos/lexicos/corpus_frecuencia.tsv` (forma,
frecuencia) sobre las 94.136 notas, con umbral de protección configurable; probar ≥ 2 y
≥ 5 (Singh 2026). Evidencia: métricas con cada umbral; casos de cola larga. Criterio: se
elige el umbral con mejor F0.5 sin superar 0,1 % de intervención; registro en
`decisiones/`. Esfuerzo: medio día + CPU minutos.

**E3.4 Gazetteers SympTEMIST y DISTEMIST** — integrados como fuente curada en
`recursos/lexico.py` (nueva etiqueta de fuente) y como terminología de referencia para el
detector por no pertenencia (Lee 2021). Evidencia: tamaño del léxico antes/después;
lista de no reconocidas antes/después; métricas. Criterio: F0.5 ≥ línea base y cola
larga reconocida. Esfuerzo: 1 día. Riesgo: el ZIP de SympTEMIST pesa 452 MB; extraer
solo el TSV.

**E3.5 Fármacos** — `datos/lexicos/farmacos.txt` desde CUM (`descripcionatc`, nunca
`principioactivo`) y AEMPS (`DICCIONARIO_PRINCIPIOS_ACTIVOS.xml`, con User-Agent),
excluyendo tokens que son palabras comunes del español. Evidencia: recuento; `losartan`,
`dipirona`, `dutasteride` protegidos; métricas. Criterio: cero intervenciones sobre la
lista en el conjunto limpio. Esfuerzo: medio día.

**E3.6 Topónimos y nombres** — `datos/lexicos/lugares.txt` (DIVIPOLA municipios;
GeoNames columna 2 opcional) y `datos/lexicos/nombres.txt` (REPS profesionales + INE),
con exclusión de palabras comunes (`correa`, `leon`, `rosa`, `palma`, `crespo`) y con
IPS aparte. Evidencia: recuentos; `villamaria`, `manizales`, `orozco`, `giraldo`
protegidos; comprobar que `dorada` sigue protegida y que la exclusión no bloquea
correcciones legítimas (medir en E2.3). Esfuerzo: 1 día.

**E3.7 Negación** — disparadores de NegEx-MES en `datos/lexicos/negacion.txt`; medspaCy
configurado en español. Evidencia: 30 notas del gold con negación, alcance correcto.
Criterio: ≥ 27/30. Esfuerzo: medio día.

**E3.8 Abreviaturas propias** — `recursos/abreviaturas.py` mina `SIGLA (definición)` y
`definición (SIGLA)` sobre el corpus (técnica AbreMES) y produce candidatos con
frecuencia; los no ambiguos (un solo sentido observado) se proponen para
`datos/diccionario_siglas.json` tras revisión. Evidencia: lista de candidatos; cuántos se
incorporaron y cuáles se rechazaron. Esfuerzo: medio día + revisión humana.

**E3.9 MedLexSp** *(P)* — solicitud de licencia; integración de las formas flexionadas
como fuente curada. Evidencia: métricas; nota de licencia en `REFERENCIAS.md` §5.
Bloqueado hasta recibir el recurso.

**E3.10 MeSpEn (columna español)** — tercera capa. Evidencia: ganancia marginal medida.
Criterio: si F0.5 no sube ≥ 0,5 puntos, se documenta y no se integra.

**Gate E3**: `tasa_intervencion_texto_limpio` ≤ 0,1 %; F0.5 ≥ línea base; cola larga
reconocida; `pytest` verde; una decisión en `decisiones/` por recurso con su cobertura;
`REFERENCIAS.md` §2 con estado actualizado por recurso; condiciones fijas.

### E4 — Corrector: experimentos

Objetivo (P2, P4, P6b): probar las técnicas de `INVESTIGACION.md` §2 una a una, cada
una tras una bandera, contra la línea base y el gold. Un experimento que no mejora F0.5
o sube la intervención sobre texto limpio se descarta y se documenta igual: el descarte
es un resultado. E4.1–E4.8 son independientes entre sí; E4.9 los compone.

Ficha común: **Cómo** = implementar tras bandera en el módulo indicado; **Evidencia** =
tabla de métricas frente a la línea base y frente al último experimento aceptado, tiempo
por nota, ejemplos anonimizados de lo que cambia; **Criterio** = F0.5 sube y la
intervención sobre texto limpio no sube; **Documentación** = `decisiones/<fecha>-E4.<m>.md`,
`FLUJO.md` (fase 2), `ARQUITECTURA.md` (constantes).

| Ítem | Hipótesis | Fuente | Módulo | Esfuerzo |
|---|---|---|---|---|
| E4.1 | La regla estricta `freq(orig) ≥ freq(corr) → revertir` supera al factor 10 actual sin perder correcciones buenas | §3.2 | `coherencia.py` | horas |
| E4.2 | Distancia por longitud (1/2/3) y frecuencia mínima del candidato ≥ 5 reducen falsos positivos | Singh 2026; SymSpell | `vocabulario.py`, `candidatos.py` | horas |
| E4.3 | Clases fonéticas del español como criterio de aceptación y como generador mejoran cobertura sin subir intervención | §2.6; Bravo-Candel | `sugerencias.py`, nuevo `nucleo/fonetica.py` | 1 día |
| E4.4 | Canal ruidoso con prior de dominio (unigramas/bigramas propios) elige mejor que la frecuencia sola | Kernighan 1990; Brill y Moore 2000 | nuevo `fase2_ortografia/canal.py` | 1–2 días |
| E4.5 | No restituir tildes no empeora F0.5 y no empeora el agrupamiento | Yarowsky 1994; López Hernández 2021 | `ortografia.py`, `limpieza.py`; medir con E7.3 | 1 día + CPU de revectorización |
| E4.6 | El verificador enmascarado (`bsc-bio-ehr-es`, PLL, minúsculas) mejora la decisión solo en el cubo *revisar* | Salazar 2020; §2.7 | `contexto.py` | 1 día; CPU segundos por miles de pares |
| E4.7 | Ranking con fastText propio (clinspell) mejora el cubo *revisar* | Fivez 2017; Lee 2021 | nuevo `fase2_ortografia/semantica.py` | 1 día; entrenamiento minutos |
| E4.8 | Solo `TYPOS` en LanguageTool (ya configurado) y ninguna corrección de concordancia; verificar que nada más actúa | Bravo-Candel 2021 | `ortografia.py` | horas |
| E4.9 | La composición de los aceptados (corrector v2) supera a cada uno por separado | — | `VERSION_CORRECTOR` 5 | 1 día |

**Gate E4**: corrector v2 con F0.5 > línea base y `tasa_intervencion` ≤ 0,1 %; `pytest`
verde; `VERSION_CORRECTOR` incrementada y caché invalidada; reparación ejecutada con v2
y cero pérdidas reales; una decisión por experimento (aceptado o descartado);
condiciones fijas.

### E5 — Normalización, reducción y conceptos (fases 3–6)

Objetivo (P2, P6b): que el texto que llega al agrupamiento diga lo que dice la nota y
solo eso, sin artefactos del pipeline. E5.1–E5.4 independientes; E5.5–E5.7 después de E4.

**E5.1 Glosas** — Probar (a) concepto en columna `concepto_normalizado` y texto sin
glosa, (b) sustituir en vez de añadir. Coordinar con `clustering/etiquetas.py`
(sección 7): darle la columna nueva como fuente de nombres. Evidencia: si "tiene glosa"
predice el cluster antes y después (regresión logística sobre la asignación; AUC);
nombres de cluster con la nueva fuente; métricas de E7.3. Criterio: AUC de "tiene glosa"
≈ 0,5 después; nombres de cluster no peores (revisión). Esfuerzo: 1–2 días + CPU de
revectorización. Documentación: `FLUJO.md` (fase 3), `decisiones/`, contrato (§7).

**E5.2 Negación con alcance** — prefijo `NEG_` en el alcance antes de vectorizar
(depende de E3.7). Evidencia: pares del gold con y sin negación en clusters distintos;
silueta. Esfuerzo: 1 día.

**E5.3 Abreviaturas no ambiguas** — expandir solo las de sentido único (E3.8). Evidencia:
lista; métricas. Esfuerzo: medio día.

**E5.4 Lematización** — ninguna frente a selectiva (sustantivos y adjetivos). Evidencia:
métricas de agrupamiento. Criterio: se adopta solo si mejora ARI/silueta. Esfuerzo:
medio día.

**E5.5 Clasificador de frases** — reentrenar con el gold (`frases.entrenar()`, nunca
`main()`); medir el freno por densidad clínica; comparar con el clasificador desactivado.
Evidencia: acuerdo de `motivo_span`; pérdidas reales. Criterio: cero pérdidas reales;
acuerdo ≥ línea base. Esfuerzo: 1 día.

**E5.6 Extractor por modelo de lenguaje** — medir la ganancia marginal frente a reglas por
tramo de longitud (≤ 10, 11–20, 21–40, > 40 palabras); fijar `LONGITUD_MINIMA` por
evidencia; tiempo total. Evidencia: tabla por tramo. Criterio: se usa solo en tramos
donde el acuerdo con el gold sube ≥ 5 puntos. Esfuerzo: 1 día + CPU horas.

**E5.7 Normalización conceptual (fase 6, nueva)** — nivel 0 `PhraseMatcher` contra
SympTEMIST + DISTEMIST; nivel 1 SapBERT-es o ClinLinker-KB-GP con vecino más cercano
(FAISS o producto punto); nivel 2 NER (`carmen-symptemist`) solo en notas largas; salida:
columnas `concepto_snomed` (código) y `concepto_termino`. Prueba adicional: centroides
por concepto (WNT-softmax sin entrenar) como agrupamiento semisupervisado. Evidencia:
cobertura por nivel; acuerdo con el gold; tiempo por nota; licencia de cada modelo.
Criterio: cobertura nivel 0 + 1 ≥ 80 % de las notas con motivo; tiempo total ≤ 1 h por
5.000 notas. Esfuerzo: 2–3 días. Documentación: `FLUJO.md` (fase 6 nueva),
`ARQUITECTURA.md`, `REFERENCIAS.md` §3.

**Gate E5**: acuerdo de `motivo_span` ≥ línea base; cero pérdidas reales en la
reparación; decisiones sobre glosas, negación, lematización y conceptos; `python -m
clustering --validar` sin truncaciones nuevas; condiciones fijas.

### E6 — Arquitectura y refactor

Objetivo (P6c): estructura clara, módulos reutilizables, sin archivos grandes ni código
muerto. Se hace después de E4–E5 para no reestructurar dos veces; la prueba de que nada
cambió es la salida byte-idéntica.

**E6.0 Eliminar duplicaciones** — las de `ARQUITECTURA.md` §5: una implementación por
concepto en `nucleo/` (`texto_gritado`, `sin_tildes`, `_es_expansion`, léxico clínico
único vía `recursos/lexico.py`, listas `VACIAS`, `RE_ENCABEZADO` desde
`clinico.SECCIONES`, criterios de daño compartidos por `coherencia` y `auditoria`, una
sola distancia de edición). Evidencia: grep de cada nombre con un solo resultado;
`pytest`; E6.5. Esfuerzo: 1–2 días.

**E6.1 Diseño** — `decisiones/<fecha>-arquitectura.md`: estructura objetivo, qué se
mueve, divide o elimina, cómo se preservan los puntos de contacto. Propuesta de partida
(a validar en la decisión):

```
NLP/
  docs/                 documentación (este directorio)
  datos/                curado y versionado: diccionarios, lexicos/, evaluacion/, manifiesto
  recursos_externos/    descargas verificadas (ignorado; manifiesto versionado)
  salidas/              generado
  nucleo/               rutas, conexion, salida, cache, morfologia, fonetica, linguistica,
                        reglas, requisitos, progreso, texto (gritado, tildes, encabezados)
  fases/
    f1_limpieza/  f2_ortografia/  f3_normalizacion/  f4_depuracion/  f5_reduccion/
    f6_conceptos/
  recursos/             constructores: lexico, casing, descargar, abreviaturas, cie10
  evaluacion/           metricas, auditoria, perturbar, pares, paridad_docs, escaneo, referencia
  reparacion/
  tests/
  procesar.py  rutas.py
```

**E6.2 Dividir archivos grandes** — los seis de más de 400 líneas; criterio: ningún
módulo > 400 líneas salvo justificación escrita; grafo de imports sin ciclos que
requieran importación diferida salvo los documentados.

**E6.3 Eliminar código muerto** — las funciones sin referencia de `ARQUITECTURA.md` §5,
`nucleo/clinico.py` salvo sus tablas, imports inertes. Decidir antes qué
`diagnosticar()` se conservan como herramientas documentadas en `OPERACION.md`. No tocar
re-exportaciones (`reglas.sin_tildes`, `terminologia.anotar_abstencion`). Evidencia:
`pyflakes` limpio; grep sin resultados; `pytest`.

**E6.4 Mover `catalogo_sintomas.json` a `NLP/datos/`** — actualizando `NLP/rutas.py` y
`embedding/extraccion.py` en el mismo commit; `embedding/estructurar.py` deja de listar
`texto_limpio`. Evidencia: `python -m embedding.estructurar` y `python -m clustering
--validar` funcionando.

**E6.5 Salida idéntica** — el CSV de las 50 notas fijadas de E2.1 es byte-idéntico
antes y después del refactor; métricas idénticas sobre el gold. Es la evidencia
irrefutable de la etapa.

**Gate E6**: E6.5 superado; ningún archivo > 400 líneas sin justificación; paridad 0/0
con la estructura nueva; prueba de E1.4 repetida con éxito; `ESTADO.md` y
`ARQUITECTURA.md` con la estructura nueva; condiciones fijas.

### E7 — Ciclo de vida y operación

Objetivo (P5): que el flujo funcione de forma progresiva y repetible, y que la fase quede
cerrada con su documentación y sus obligaciones cumplidas.

**E7.1 Procesamiento progresivo** — de punta a punta: N notas nuevas en BD →
`procesar.py` las añade → `embedding.centinela` las vectoriza → `clustering` las
incorpora. Evidencia: recuentos coincidentes en cada paso. Criterio: N = N = N.

**E7.2 Política de versión del corrector** — en `OPERACION.md`: al cambiar
`VERSION_CORRECTOR`: reparación sobre el CSV, revisión del informe, `--aplicar`,
revectorización, purga de copias previas y de vectores huérfanos, `--validar`. Evidencia:
el procedimiento ejecutado una vez completo.

**E7.3 Evaluación del agrupamiento** — con el gold: línea base TF-IDF de n-gramas de
caracteres; comparación `bge-m3` / `SapBERT-es` / `ClinLinker-KB-GP` /
`multilingual-e5-small` / `RigoBERTa-Clinical` (ARI, silueta); referencia de calibración
Chang 2020 (15 clusters). Coordinado con `clustering/`. Evidencia: tabla; decisión.
Esfuerzo: 1 día + CPU horas.

**E7.4 Cierre** — revisión de `REFERENCIAS.md` (DOI y URL verificados uno a uno),
obligaciones de licencia cumplidas, ejemplos anonimizados en toda la documentación,
`INVESTIGACION.md` §10 completado con lo aprendido en E3–E5, `Historial` al día en
todos los documentos.

**Gate E7**: procedimiento de operación ejecutado una vez de principio a fin con
evidencia; E7.4 completo; el propietario da por cerrada la fase.

---

## 9. Orden, paralelismo y reparto

| Etapa | Paralelismo interno | Agentes sugeridos | Requiere persona |
|---|---|---|---|
| E0 | E0.4 ∥ E0.6 ∥ (E0.2 → E0.3) | 1 implementación, 1 preparación de anotación | E0.1, E0.6 |
| E1 ∥ E2 | E1.2–E1.4 ∥ E2.1–E2.4 | 2–4 en paralelo | revisión de REFERENCIAS |
| E3 | E3.2–E3.8 tras E3.1 | hasta 7, uno por recurso | E3.9 |
| E4 | E4.1–E4.8 | hasta 8, uno por experimento | ninguna |
| E5 | E5.1–E5.4; luego E5.5–E5.7 | 3–4 | revisión de nombres de cluster |
| E6 | E6.0 ∥ E6.3; luego E6.2, E6.4; E6.5 al final | 2–3 | aprobación del diseño |
| E7 | secuencial | 1–2 | cierre |

El orquestador nunca lanza más agentes de los que puede verificar en la misma sesión:
cada bitácora se revisa antes de cerrar.

---

## 10. Riesgos y supuestos

| Riesgo | Mitigación |
|---|---|
| El gold v0 tarda en anotarse | E2.3 (autoinducido y limpio) no requiere anotación; E0.5 se calcula con eso y se recalcula con el gold |
| Un recurso cambia de URL o licencia | manifiesto con sha256, copia local, licencia registrada con fecha |
| El refactor rompe `embedding/` o `clustering/` | sección 7; E6.5 byte-idéntico; `--validar` |
| Quitar glosas degrada los nombres de cluster | E5.1 coordinado con `etiquetas.py`; se mide antes de aplicar |
| Tiempo de cómputo sin GPU | calibrar con 5.000 notas; corpus completo una vez por versión; nada generativo masivo |
| Sesiones paralelas se pisan | un ítem por rama y worktree; `ESTADO.md` como registro |
| La documentación se desactualiza | política 4.4; lista en cada bitácora; `paridad_docs.py` en todos los gates |
| Datos de pacientes en documentación o prompts | principio 7; revisión en E7.4 |
| Un agente destruye datos curados | protocolo 5.7: sin escritura en `datos/` salvo indicación expresa |

---

## 11. Glosario

- **Fase**: etapa del pipeline de texto (1 limpieza, 2 ortografía, 2b coherencia,
  3 normalización, 4 depuración, 5 reducción, 6 conceptos).
- **Etapa**: bloque del plan (E0–E7). **Ítem**: unidad de trabajo con ficha.
- **Gate**: condición verificable para cerrar una etapa.
- **Línea base**: métricas al cerrar E0. **Gold**: notas anotadas a mano.
- **Artefacto**: archivo generado en `salidas/`. **Recurso externo**: dato o modelo de
  terceros con licencia registrada.
- **Zona gris / cubo revisar**: pares original → corrección que las reglas no deciden con
  alta confianza.
- **Intervención sobre texto limpio**: proporción de tokens correctos que el corrector
  modifica.

---

## 12. Historial

| Fecha | Versión | Cambio | Motivo |
|---|---|---|---|
| 2026-09-15 | 1 | Primera versión: peticiones, principios, evidencia, protocolo, seguridad, contrato, E0–E7 | Petición P6 |
| 2026-09-15 | 1.1 | E6.0 (duplicaciones), E2.0 (alarmas), E0.6 sobre `escaneo`/`referencia`, E0.4 ampliado | Inventario de `ARQUITECTURA.md` |
| 2026-09-15 | 2 | Sección 2 (diagnóstico con cifras); sección 4.4 (mantenimiento de la documentación) y lista en la bitácora; fichas de ítem con por qué, cómo, fuente, criterio numérico, esfuerzo, responsable y documentación; P6f; principio 8; sección 9 de reparto; historial | Revisión del propietario: el plan era menos detallado que lo dicho en sesión; faltaba la política de actualización continua |
