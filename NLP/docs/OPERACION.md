# Runbook de operación

Ítem E1.4 del plan (`PLAN.md` §8). Instrucciones para instalar, ejecutar y
diagnosticar el pipeline de `NLP/` sin necesidad de leer el código. Todos los
comandos se ejecutan **desde la raíz del repositorio**
(`C:\Users\ad6708\Documents\puebas`) con el intérprete del proyecto:

```
C:\Users\ad6708\Documents\puebas\.venv\Scripts\python.exe -m NLP.<paquete>.<modulo>
```

Este documento usa `python` como atajo de esa ruta completa. Las salidas de
consola con tildes pueden verse mal en `cmd.exe` (códigos de página cp1252); usar
PowerShell o fijar `PYTHONIOENCODING=utf-8` si aparecen caracteres corruptos.

## 1. Instalación desde cero

| Paso | Comando | Qué verifica |
|---|---|---|
| 1. Python 3.11 | `python --version` debe dar `3.11.x` (verificado el 2026-09-16: `Python 3.11.9`) | la versión que fija `requirements.txt` |
| 2. Entorno virtual | `python -m venv .venv` en la raíz del repositorio | aísla las dependencias del proyecto |
| 3. Activar | PowerShell: `.venv\Scripts\Activate.ps1` | — |
| 4. Dependencias | `.venv\Scripts\python.exe -m pip install -r requirements.txt` | instala pandas, spaCy, symspellpy, language-tool-python, torch, transformers, etc. (ver `requirements.txt` para la lista fijada y las exclusiones justificadas) |
| 5. Modelo de spaCy | `python -m spacy download es_core_news_md` | exigido por `requisitos.py`; sin él la fase 2 corrige sin vocabulario ni protección de nombres propios |
| 6. Java (para LanguageTool) | comprobar con `java -version`; se necesita un JRE/JDK instalado aparte (no lo instala `pip`) | verificado el 2026-09-16: `java version "21.0.12.1"`. `language_tool_python` descarga el paquete de LanguageTool la primera vez que se instancia (necesita red la primera vez) |
| 7. Ollama (opcional, fase 5b) | instalar desde ollama.com; luego `ollama pull qwen2.5:3b-instruct` | verificado el 2026-09-16: `ollama version is 0.34.1`. Sin él, `extractor.disponible()` da `False` y la fase 5 sigue solo por reglas — no detiene la corrida |
| 8. Conexión a la base de datos | credenciales integradas contra `ls-cobra` / `DWSES` (`nucleo/conexion_bd.py`) | necesaria para una corrida nueva (`procesar.py`) y para las frecuencias de una reparación; **no** para reparar con `--csv` de respaldo, ni para `requisitos.py`, ni para `paridad_docs.py` |

Tras instalar, verificar con:

```
python -m NLP.nucleo.requisitos
```

Salida esperada (verificada el 2026-09-16, con todos los artefactos ya
construidos):

```
REQUISITOS DEL PIPELINE

  [OK ] exigido   lexico_clinico
  [OK ] opcional  lexico_casing
  [OK ] opcional  clasificador_frases
  [OK ] exigido   lexico_externo
  [OK ] exigido   catalogo_sintomas
  [OK ] exigido   diccionario_siglas
  [OK ] exigido   es_core_news_md

Todo en su sitio.
```

Si falta alguno, este mismo comando imprime, para cada exigido, qué se rompe y el
comando que lo arregla — **con una excepción documentada en la sección 5**: la
receta que imprime para `clasificador_frases` es peligrosa, no seguirla al pie de
la letra.

## 2. Artefactos: tabla completa

Fuente: `NLP/nucleo/requisitos.py` (tabla `ARTEFACTOS`) y `ESTADO.md` §2. "Exigido"
significa que, sin él, la corrida termina completa y con datos equivocados
(`requisitos.exigir()` la detiene primero); "opcional", que su ausencia deja una
señal visible.

| Artefacto | Tipo | Comando que lo regenera | Qué se rompe si falta |
|---|---|---|---|
| `datos/diccionario_siglas.json` | exigido, versionado | viene con el repo (`NLP/datos/`); se edita a mano | no se expande ninguna sigla |
| `embedding/datos/catalogo_sintomas.json` | exigido, versionado | viene con el repo (`embedding/datos/`) | la depuración no reconoce ningún síntoma |
| `datos/lexico_externo.txt` | exigido, generado | `python -m NLP.recursos.extraer_cie10` | el léxico clínico se queda sin el vocabulario del CIE-10 |
| `salidas/lexico_clinico.json` | exigido, generado | `python -m NLP.recursos.lexico` | la fase 5 descarta toda oración larga: se pierde el motivo de consulta (medido: 25,1 % de notas pierden contenido, 18,1 % pierden más de la mitad — `decisiones/2026-09-15-artefactos-y-version-corrector.md`) |
| modelo spaCy `es_core_news_md` | exigido, externo | `python -m spacy download es_core_news_md` | la fase 2 corrige sin vocabulario ni protección de nombres propios |
| `salidas/lexico_casing.json` | opcional, generado | `python -m NLP.recursos.casing` (requiere BD) | no se restaura ninguna sigla a mayúscula |
| `salidas/clasificador_frases.joblib` | opcional, generado | `from NLP.reduccion import frases; frases.entrenar()` — **NUNCA** `python -m NLP.reduccion.frases` (sección 5) | la fase 5 pierde la capa que cubre trámite no enumerado por los patrones |

Artefactos adicionales que no comprueba `requisitos.py` pero que la corrida
necesita o usa (`ESTADO.md` §2 y observación directa, sección 6 de este
documento):

| Artefacto/servicio | Comando | Si falta |
|---|---|---|
| Servidor LanguageTool (Java) | se levanta solo al llamar `ortografia.iniciar_languagetool()` | si Java no está instalado, `iniciar_languagetool()` puede fallar sin capturarse (ver sección 6); si el servidor arranca pero una consulta puntual falla, `corregir()` lo captura y sigue sin esa corrección |
| `datos/diccionario_coloquial.json` | viene con el repo; se edita a mano | la fase 3 no expande coloquialismos (si falta el archivo, `normalizacion.cargar()` lanza excepción al leerlo) |
| `salidas/cache_correcciones.json` | se llena solo, procesando | sin ella cada corrida repite toda la fase 2 desde cero (más lenta, no incorrecta) |

## 3. Comandos por escenario

### 3.1 Corrida nueva (desde la base de datos)

```
python -m NLP.nucleo.requisitos
python -m NLP.procesar
```

Qué mirar: la primera línea imprime `Registros a procesar: N | LLM: si/no`. Si
`N` es menor que lo esperado, revisar `LIMITE_REGISTROS` en `procesar.py:70`
o pasar `--limite`. El progreso se imprime bloque a bloque
(`BLOQUE_ESCRITURA = 250`, `procesar.py:93`); el CSV se puede abrir mientras
corre. Al final: "Correcciones sospechosas de estropear la nota" (revisar antes
de dar la corrida por buena), "Correcciones frenadas por el guardián clínico"
(qué reglas de protección actuaron), "Palabras dejadas intactas por falta de
evidencia" (candidatas a entrar en el diccionario), y el resumen de notas
señaladas por `motivo_descarte`.

Opciones: `--limite N` (procesa N notas nuevas, no relee las ya hechas);
`--sin-llm` (desactiva el extractor de Ollama en la fase 5); `--rehacer` (aparta
el CSV existente con `rotar()` y procesa todo desde cero — perder esto significa
perder el progreso incremental, usar con intención).

### 3.2 Reanudar una corrida interrumpida

No hace falta ninguna opción especial: `python -m NLP.procesar` **continúa** el
CSV existente por diseño (`procesar.py:568-580`, comentario "Relanzar CONTINUA el
CSV; no lo rehace"). Lee los `OID` ya escritos en `triage_limpio.csv` y la
consulta a la base de datos los excluye. La caché de correcciones
(`cache_correcciones.json`) conserva lo ya corregido, así que reanudar es barato.

### 3.3 Reparar un CSV existente sin sustituirlo

```
python -m NLP.reparacion.reparar --limite 200      # prueba sobre 200 notas
python -m NLP.reparacion.reparar                   # sobre todo el CSV, sin tocar nada
```

Por defecto **no modifica** `triage_limpio.csv`: escribe `triage_reparado.csv` e
`informe_reparacion.csv` en `salidas/`. Qué mirar: al final, el resumen por
categoría (`intacta`, `ortografia`, `recupero_motivo`, `perdio_motivo`,
`normalizacion`) y, si hay `perdio_motivo`, la tabla de términos perdidos por
frecuencia — **no aplicar la reparación mientras haya alguno con veredicto
real** (criterio de E0.2, `PLAN.md` §8).

Opciones: `--con-llm` (usa el extractor de Ollama en la fase 5, más lento);
`--csv <ruta>` (repara un CSV distinto al de `salidas/`); `--salida-dir <carpeta>`
(escribe el reparado y el informe en otra carpeta, para no pisar una reparación
en curso — **usar esto si hay un job de reparación corriendo en segundo plano**,
nunca apuntar dos reparaciones al mismo `salidas/`).

### 3.4 Revisar el informe de reparación

```
python -m NLP.reparacion.revision
python -m NLP.reparacion.revision --termino cefalea
```

Sin argumentos: recuento por categoría, veredicto `recupero > perdio: CUMPLE /
NO CUMPLE`, y la lista **completa** (no solo los 25 más frecuentes que imprime
`reparar.py`) de términos perdidos por frecuencia, con cuántas veces cada uno se
recupera en otras notas. Con `--termino <palabra>`: las notas concretas donde se
pierde ese término, con 60 caracteres de contexto antes y después — es la forma
de decidir si una pérdida es benigna (administrativa) o real.

### 3.5 Aplicar la reparación

```
python -m NLP.reparacion.reparar --aplicar
```

Repite todo el proceso de 3.3 y, si `empeoraron == 0` (ninguna nota en
`perdio_motivo`), sustituye `triage_limpio.csv` apartando la versión anterior con
`nucleo/salida.rotar()` (conserva 3 versiones con fecha). Si hay alguna nota que
pierde terminología, el comando se niega a aplicar y termina con código de salida
1 — corregir la causa antes de repetir con `--aplicar`.

### 3.6 Revectorizar tras un cambio de texto

```
python -m embedding.vectorizar
```

Verificado el 2026-09-16 (`--help`, sin argumentos adicionales que requieran
red ni BD): usa `--csv`, `--limite`, `--bloque` (2000 por defecto), `--rehacer`.
`embedding/` deduplica por `sha1(texto)[:16]`, no por `OID` (`PLAN.md` §7): un
texto reparado se revectoriza solo, sin necesitar `--rehacer`; los vectores del
texto antiguo quedan huérfanos en `vectores.f32` (ocupan disco, no rompen nada).

**Aviso**: `python -m embedding.estructurar` (fase 4 de `embedding/`, extracción
estructurada) está roto hoy — ver el error conocido en la sección 6, punto 1. No
usarlo hasta que se corrija `embedding/extraccion.py`.

### 3.7 Validar el agrupamiento

```
python -m clustering --validar
```

No se ejecutó en la preparación de este documento por ser una prueba costosa
(recalcula reducciones para varias pruebas: modelo nulo, estabilidad, siluetas,
codo de temas, catálogo clínico — el propio `--help` de `clustering` lo describe
así). Ejecutar tras cualquier cambio que altere la longitud o el contenido de
`texto_embedding`; comparar contra la referencia de `PLAN.md` §7 (p99 de 95
tokens, máximo 170, 10 de 5.020 textos truncados con `bge-m3` a 128 tokens) para
detectar más truncaciones que antes.

### 3.8 Correr las pruebas

```
python -m pytest NLP/tests -q
```

Verificado el 2026-09-16: `NLP/tests/` existe pero solo contiene una carpeta
`datos/` vacía, sin ningún archivo `test_*.py`. Salida real:

```
no tests ran in 0.07s
```

E2.1 (`PLAN.md` §8) todavía no se ha ejecutado: no hay ninguna prueba automatizada
sobre el pipeline.

### 3.9 Comprobar paridad de la documentación

```
python -m NLP.evaluacion.paridad_docs
python -m NLP.evaluacion.paridad_docs --estricto
```

Recorre `NLP/**/*.py` y las fichas de `ARQUITECTURA.md` §2. Salida real,
2026-09-16:

```
Paquete:   C:\Users\ad6708\Documents\puebas\NLP
           42 archivos .py exigen ficha; 10 __init__.py solo con docstring, exentos
Documento: C:\Users\ad6708\Documents\puebas\NLP\docs\ARQUITECTURA.md
           41 fichas reconocidas en §2

Faltantes (archivo sin ficha): 1
  - evaluacion/perturbar.py
Huérfanas (ficha sin archivo): 0
Documentos de docs/ sin sección '## Historial': 1
  - README.md

Resultado: 1 faltantes, 0 huérfanas, 1 documentos sin Historial
```

`--estricto` devuelve código de salida distinto de cero si hay algo pendiente
(útil para CI); forma parte del gate de todas las etapas (`PLAN.md` §4.2). Nota:
este documento (E1.3/E1.4) corrige el punto de `README.md` sin `Historial`; el
faltante de `evaluacion/perturbar.py` queda pendiente porque `ARQUITECTURA.md` no
está entre los archivos que este ítem puede tocar.

### 3.10 Procedimiento completo: limpiar el CSV actual y regenerar los embeddings

Deja `triage_limpio.csv` con el corrector vigente y los vectores al día. Se ejecuta entero
y en este orden desde la raíz del repositorio. `PY` es `.venv\Scripts\python.exe`.

```
REM 1. Comprobar que estan los artefactos que el proceso da por hechos
%PY% -m NLP.nucleo.requisitos

REM 2. Frecuencias del corpus completo (si no existen o son de otra corrida)
%PY% -m NLP.recursos.corpus_lexico

REM 3. Lexico clinico, con los gazetteers integrados
%PY% -m NLP.recursos.lexico

REM 4. Si VERSION_CORRECTOR cambio, migrar la cache en vez de tirarla
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva>
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva> --aplicar

REM 5. Reparar sin tocar nada, y revisar el informe termino a termino
%PY% -m NLP.reparacion.reparar
%PY% -m NLP.reparacion.revision

REM 6. Medir el resultado contra el CSV vigente ANTES de sustituirlo
%PY% -m NLP.evaluacion.calidad --csv NLP\salidas\triage_limpio.csv --comparar NLP\salidas\triage_reparado.csv

REM 7. Solo si los numeros mejoran: aplicar
%PY% -m NLP.reparacion.reparar --aplicar

REM 8. Revectorizar y validar
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

El paso 6 es el que decide: `--comparar` cruza por `OID` y muestra la diferencia columna a
columna. Lo que tiene que subir es la retención de terminología; lo que tiene que bajar es
el número de notas que se quedan sin terminología clínica.

El paso 7 no sustituye nada si quedan notas en `perdio_motivo` sin revisar: `reparar.py` se
niega y sale con código 1. La versión anterior del CSV la aparta `salida.rotar()`.

### 3.11 Generar notas nuevas desde la base de datos

```
REM Corrida normal: procesa las notas que aun no estan en el CSV
%PY% -m NLP.procesar

REM Prueba corta antes de una corrida larga
%PY% -m NLP.procesar --limite 200

REM Rehacer el CSV entero desde cero (aparta el anterior)
%PY% -m NLP.procesar --rehacer
```

`procesar.py` es incremental: lee `DIM_TRIAGE`, descarta las notas cuyo `OID` ya está
escrito y añade solo las nuevas, así que se puede lanzar tantas veces como haga falta.
Cuántas trae cada corrida lo fija `LIMITE_REGISTROS` (hoy 5.000; `None` para la tabla
entera) y `--limite` lo pisa para una corrida concreta sin tocar el archivo.

Después de añadir notas nuevas hay que vectorizarlas:

```
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

`embedding/` deduplica por el hash del texto, de modo que solo vectoriza lo que no tiene
vector todavía: no hace falta `--rehacer` salvo que cambie el modelo de embeddings.

## 4. Errores conocidos y su solución

Revisada entera el 2026-09-16 al cierre de la sesión de ejecución: cada fila se comprobó
contra el código de ese día, y las que ya no ocurren se retiraron en vez de arrastrarse.

| Error | Causa | Estado |
|---|---|---|
| **`recursos/lexico.py` y `recursos/casing.py` no usan `argparse`** | cualquier invocación con `python -m`, **incluida `--help`**, ejecuta `main()` y sobrescribe el artefacto; `casing.py` además lee la tabla completa de la base de datos | **vivo**. No invocar esos dos módulos salvo para regenerar el artefacto a propósito. Comprobado el 2026-09-16 al intentar listar su ayuda: reconstruyeron `lexico_clinico.json` y `lexico_casing.json` sin avisar |
| `perdio_motivo` cuenta `dada`, `salud`, `toma`, `signos` como terminología clínica | están en el léxico curado aunque no aportan motivo de consulta en la mayoría de sus usos | **vivo**, ruido conocido. Se revisa por término con `reparacion.revision --termino <palabra>` |
| Léxico sin cobertura de cola larga, y colombianismos que el corrector destruye (`maluca`, `cuncho`, `piquiña`, `urente`) | el español de Colombia no está en ningún diccionario general, y el corpus no repite lo bastante esas formas | **vivo**. Mitigado por `coherencia.RESPALDO_POR_CORPUS` (umbral 5) y por las listas de E3.2–E3.6; lo que queda necesita revisión humana de `pares_correccion.csv` |
| `evaluacion/referencia.py` da cero en todo | las 27 anotaciones de `datos/referencia_correcciones.json` no comparten ningún OID con `muestra_revision.csv` | **vivo**, desacople de datos. Se resuelve al anotar el gold v0 (E0.6) |
| `alarmas.reiniciar()` acumulaba entre corridas del mismo proceso | no se llamaba desde ningún punto de entrada | **resuelto** (E2.0): se llama al inicio de `procesar.main()` y de `reparar.main()` |
| `reparacion/reparar.py` escribía con pandas (`QUOTE_MINIMAL`) y `procesar.py` con `nucleo/salida.py` (`QUOTE_ALL`) | dos escritores distintos para el mismo archivo | **resuelto** (E0.4): `reparar.py` usa `EscritorCSV` y aparta la versión anterior con `rotar()` |
| `embedding/estructurar.py` fallaba con `AttributeError` al importarse | `embedding/rutas.py` re-exportaba `TRIAGE_LIMPIO` de `NLP.rutas` pero no `CATALOGO_SINTOMAS` | **resuelto** (E6.4): se re-exporta con el mismo patrón; el módulo corre de punta a punta |
| `requisitos.py` recomendaba `python -m NLP.reduccion.frases` para regenerar el clasificador | esa receta es precisamente el comando que destruye `datos/frases_etiquetadas.csv`, curado a mano | **resuelto** (2026-09-16): la receta pasa a `python -c "from NLP.reduccion import frases; frases.entrenar()"` |
| `requirements.txt` fijaba `scikit-learn==1.4.2` con 1.9.1 instalado | el archivo no se actualizó al cambiar el entorno | **resuelto**: alineado a 1.9.1 |
| `NLP/tests/` sin pruebas y sin `metricas.py` | E2.1 y E2.2 no se habían ejecutado | **resuelto**: 8 archivos de prueba, 38 pruebas en verde, y `evaluacion/metricas.py` operativo |
| La fase 1 destruía cifras (`1000mg` → `100mg`) | `RE_REPETIDOS` colapsaba cualquier carácter repetido, dígitos incluidos | **resuelto**: el grupo excluye dígitos; `tests/test_cifras.py` lo fija |
| La reparación completa abortaba al final por `OID` duplicados | `comparar()` daba por único un `OID` que el contrato (§7) declara no único | **resuelto**: se deduplica conservando la última aparición |
| La prueba byte-idéntica fallaba sin que nadie tocara el pipeline | la política `eol=lf` de `.gitattributes` normalizaba el CSV de referencia, que debe conservar CRLF | **resuelto**: `NLP/tests/datos/*.csv` marcados como binarios |

## 5. Advertencia grande: `python -m NLP.reduccion.frases`

**No ejecutar nunca `python -m NLP.reduccion.frases`.** Su función `main()`
llama a `construir_datos()`, que **regenera `datos/frases_etiquetadas.csv` desde
las reglas y sobrescribe la curación manual** que es la fuente de verdad del
clasificador de tramos. Es el mismo error que ya ocurrió una vez con este
archivo (lección registrada en `PLAN.md` §5.7 y en el briefing de este ítem).

Para reentrenar el clasificador con los datos curados que ya existen:

```python
from NLP.reduccion import frases
frases.entrenar()
```

Esto sí es seguro: lee `datos/frases_etiquetadas.csv` tal como está y escribe
`salidas/clasificador_frases.joblib`. La única vez que se justifica
`construir_datos()` (y por tanto el `main()` completo) es para arrancar el
archivo curado **desde cero**, con la curación humana ya perdida a propósito —
nunca en una corrida normal ni en una reparación.

Esta misma advertencia aplica, con menos gravedad, a `recursos/lexico.py` y
`recursos/casing.py` (sección 4): no destruyen datos curados a mano, pero
sobrescriben artefactos generados sin previo aviso ante cualquier invocación,
incluida `--help`.

## 6. Política de versión del corrector (E7.2)

Ejecutada de punta a punta el 2026-09-16, dos veces (v4 → v5 y v5 → v6). Lo que sigue no
es el procedimiento tal como lo imagina el plan, sino el que funcionó, con las dos
correcciones que hicieron falta para que funcionara.

### Cuándo hay que subir la versión

Solo cuando cambia una capa **cacheada**, es decir, algo que altere el `texto_corregido`
que produce la fase 2: un umbral, un léxico, un generador de candidatos, una capa nueva.

**No hay que subirla** cuando cambia la fase 2b (`coherencia.py`), porque se aplica fuera
de la caché a propósito, ni cuando cambian las fases 3, 4 o 5. Ese detalle ahorra horas:
la regla del mismo lema (E4.10) entró entera sin recalcular nada.

### Procedimiento

1. **Subir `VERSION_CORRECTOR`** en `procesar.py`, con un comentario que enumere qué
   cambió. La cadena entra en la clave de caché (`nucleo/cache.py`), así que subirla
   invalida la caché anterior sin borrar nada a mano.

2. **Migrar la caché en vez de tirarla.** Recalcular las ~7.300 entradas en frío costaba
   más de 20 horas medidas; migrarlas costó minutos. El criterio depende de **qué** cambió,
   por eso el comando exige declararlo:

   ```
   %PY% -m NLP.nucleo.migrar_cache --desde <vieja> --hasta <nueva> --respaldo-lexico
   %PY% -m NLP.nucleo.migrar_cache --desde <vieja> --hasta <nueva> --abstencion
   ```

   | Criterio | Cuándo se usa | Qué invalida |
   |---|---|---|
   | `--respaldo-lexico` | el generador de candidatos deja de proponer formas que el corpus no escribe (v4 → v5) | las correcciones que contienen una de esas formas |
   | `--abstencion` | una capa nueva rescata donde antes se abstenía (v5 → v6, canal ruidoso) | las correcciones que dejaron alguna palabra sin reconocer |

   Sin `--aplicar` solo informa. Resultados reales: v4 → v5 migró 7.159 de 7.321 entradas
   (162 a recalcular); v5 → v6 migró 5.842 de 7.316 (1.474 a recalcular).

   **Si el cambio nuevo no encaja en ningún criterio existente, hay que escribir uno.** El
   módulo se niega a migrar sin criterio: migrar a ciegas equivale a dar por bueno que
   nada cambia, y eso corrompe la caché en silencio.

3. **Reparar el CSV vigente** con la versión nueva y revisar el informe:

   ```
   %PY% -m NLP.reparacion.reparar
   %PY% -m NLP.reparacion.revision
   ```

4. **Aplicar.** El criterio de aceptación **no** es «cero notas que pierdan un término»:
   esa condición compara contra el CSV anterior y es imposible de cumplir cuando el
   anterior está mal generado — cualquier nota que el corrector nuevo escriba mejor cuenta
   como pérdida. Lo que decide es la **calidad absoluta**, que `reparar.py --aplicar`
   compara y muestra antes de tocar nada:

   ```
   %PY% -m NLP.reparacion.reparar --aplicar
   ```

   Se niega si empeora `retencion_media`, `prop_retencion_total`,
   `prop_sin_terminologia_en_embedding`, `prop_pierden_mas_de_la_mitad`, `notas_vacias` o
   `notas_sobre_ventana_bge`. `--forzar` salta la negativa y debe quedar justificado en una
   bitácora.

5. **Comprobar las pruebas**: `%PY% -m pytest NLP/tests -q` (38 en verde). Si falla la
   prueba de salida byte-idéntica, **el comportamiento cambió**: si el cambio es
   deliberado y está medido, se regenera con `REGENERAR_GOLDEN=1` tras revisar el diff; si
   no, hay un fallo que arreglar.

6. **Purgar copias antiguas**: `rotar()` conserva las tres últimas
   `triage_limpio_<sello>.csv`; las de `cache_correcciones.previo-<sello>.json` que deja
   el migrador se borran a mano cuando ya no hagan falta.

7. Revectorizar y validar el agrupamiento **solo cuando el propietario lo pida**: eso
   pertenece a `embedding/` y `clustering/`, fuera del alcance de la fase NLP.

### Lo que se aprendió ejecutándolo

- **La compuerta tenía el criterio equivocado** y bloqueaba una mejora evidente. Corregida
  (paso 4).
- **La comparación contra el CSV viejo no sirve como criterio de aceptación** cuando el
  viejo está corrupto; sirve como lista de revisión.
- **La caché se migra, no se tira.** Sin el migrador, cada subida de versión cuesta una
  jornada de máquina.
- **Un fallo al final de una corrida larga cuesta la corrida entera.** La reparación abortó
  dos veces por `OID` duplicados después de 90 minutos cada vez, porque la comprobación
  estaba en el último paso. Conviene validar las suposiciones sobre los datos al principio.

## Historial': 1
  - README.md

Resultado: 1 faltantes, 0 huérfanas, 1 documentos sin Historial
```

`--estricto` devuelve código de salida distinto de cero si hay algo pendiente
(útil para CI); forma parte del gate de todas las etapas (`PLAN.md` §4.2). Nota:
este documento (E1.3/E1.4) corrige el punto de `README.md` sin `Historial`; el
faltante de `evaluacion/perturbar.py` queda pendiente porque `ARQUITECTURA.md` no
está entre los archivos que este ítem puede tocar.

### 3.10 Procedimiento completo: limpiar el CSV actual y regenerar los embeddings

Deja `triage_limpio.csv` con el corrector vigente y los vectores al día. Se ejecuta entero
y en este orden desde la raíz del repositorio. `PY` es `.venv\Scripts\python.exe`.

```
REM 1. Comprobar que estan los artefactos que el proceso da por hechos
%PY% -m NLP.nucleo.requisitos

REM 2. Frecuencias del corpus completo (si no existen o son de otra corrida)
%PY% -m NLP.recursos.corpus_lexico

REM 3. Lexico clinico, con los gazetteers integrados
%PY% -m NLP.recursos.lexico

REM 4. Si VERSION_CORRECTOR cambio, migrar la cache en vez de tirarla
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva>
%PY% -m NLP.nucleo.migrar_cache --desde <version anterior> --hasta <version nueva> --aplicar

REM 5. Reparar sin tocar nada, y revisar el informe termino a termino
%PY% -m NLP.reparacion.reparar
%PY% -m NLP.reparacion.revision

REM 6. Medir el resultado contra el CSV vigente ANTES de sustituirlo
%PY% -m NLP.evaluacion.calidad --csv NLP\salidas\triage_limpio.csv --comparar NLP\salidas\triage_reparado.csv

REM 7. Solo si los numeros mejoran: aplicar
%PY% -m NLP.reparacion.reparar --aplicar

REM 8. Revectorizar y validar
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

El paso 6 es el que decide: `--comparar` cruza por `OID` y muestra la diferencia columna a
columna. Lo que tiene que subir es la retención de terminología; lo que tiene que bajar es
el número de notas que se quedan sin terminología clínica.

El paso 7 no sustituye nada si quedan notas en `perdio_motivo` sin revisar: `reparar.py` se
niega y sale con código 1. La versión anterior del CSV la aparta `salida.rotar()`.

### 3.11 Generar notas nuevas desde la base de datos

```
REM Corrida normal: procesa las notas que aun no estan en el CSV
%PY% -m NLP.procesar

REM Prueba corta antes de una corrida larga
%PY% -m NLP.procesar --limite 200

REM Rehacer el CSV entero desde cero (aparta el anterior)
%PY% -m NLP.procesar --rehacer
```

`procesar.py` es incremental: lee `DIM_TRIAGE`, descarta las notas cuyo `OID` ya está
escrito y añade solo las nuevas, así que se puede lanzar tantas veces como haga falta.
Cuántas trae cada corrida lo fija `LIMITE_REGISTROS` (hoy 5.000; `None` para la tabla
entera) y `--limite` lo pisa para una corrida concreta sin tocar el archivo.

Después de añadir notas nuevas hay que vectorizarlas:

```
%PY% -m embedding.vectorizar
%PY% -m clustering --validar
```

`embedding/` deduplica por el hash del texto, de modo que solo vectoriza lo que no tiene
vector todavía: no hace falta `--rehacer` salvo que cambie el modelo de embeddings.

## 4. Errores conocidos y su solución

Revisada entera el 2026-09-16 al cierre de la sesión de ejecución: cada fila se comprobó
contra el código de ese día, y las que ya no ocurren se retiraron en vez de arrastrarse.

| Error | Causa | Estado |
|---|---|---|
| **`recursos/lexico.py` y `recursos/casing.py` no usan `argparse`** | cualquier invocación con `python -m`, **incluida `--help`**, ejecuta `main()` y sobrescribe el artefacto; `casing.py` además lee la tabla completa de la base de datos | **vivo**. No invocar esos dos módulos salvo para regenerar el artefacto a propósito. Comprobado el 2026-09-16 al intentar listar su ayuda: reconstruyeron `lexico_clinico.json` y `lexico_casing.json` sin avisar |
| `perdio_motivo` cuenta `dada`, `salud`, `toma`, `signos` como terminología clínica | están en el léxico curado aunque no aportan motivo de consulta en la mayoría de sus usos | **vivo**, ruido conocido. Se revisa por término con `reparacion.revision --termino <palabra>` |
| Léxico sin cobertura de cola larga, y colombianismos que el corrector destruye (`maluca`, `cuncho`, `piquiña`, `urente`) | el español de Colombia no está en ningún diccionario general, y el corpus no repite lo bastante esas formas | **vivo**. Mitigado por `coherencia.RESPALDO_POR_CORPUS` (umbral 5) y por las listas de E3.2–E3.6; lo que queda necesita revisión humana de `pares_correccion.csv` |
| `evaluacion/referencia.py` da cero en todo | las 27 anotaciones de `datos/referencia_correcciones.json` no comparten ningún OID con `muestra_revision.csv` | **vivo**, desacople de datos. Se resuelve al anotar el gold v0 (E0.6) |
| `alarmas.reiniciar()` acumulaba entre corridas del mismo proceso | no se llamaba desde ningún punto de entrada | **resuelto** (E2.0): se llama al inicio de `procesar.main()` y de `reparar.main()` |
| `reparacion/reparar.py` escribía con pandas (`QUOTE_MINIMAL`) y `procesar.py` con `nucleo/salida.py` (`QUOTE_ALL`) | dos escritores distintos para el mismo archivo | **resuelto** (E0.4): `reparar.py` usa `EscritorCSV` y aparta la versión anterior con `rotar()` |
| `embedding/estructurar.py` fallaba con `AttributeError` al importarse | `embedding/rutas.py` re-exportaba `TRIAGE_LIMPIO` de `NLP.rutas` pero no `CATALOGO_SINTOMAS` | **resuelto** (E6.4): se re-exporta con el mismo patrón; el módulo corre de punta a punta |
| `requisitos.py` recomendaba `python -m NLP.reduccion.frases` para regenerar el clasificador | esa receta es precisamente el comando que destruye `datos/frases_etiquetadas.csv`, curado a mano | **resuelto** (2026-09-16): la receta pasa a `python -c "from NLP.reduccion import frases; frases.entrenar()"` |
| `requirements.txt` fijaba `scikit-learn==1.4.2` con 1.9.1 instalado | el archivo no se actualizó al cambiar el entorno | **resuelto**: alineado a 1.9.1 |
| `NLP/tests/` sin pruebas y sin `metricas.py` | E2.1 y E2.2 no se habían ejecutado | **resuelto**: 8 archivos de prueba, 38 pruebas en verde, y `evaluacion/metricas.py` operativo |
| La fase 1 destruía cifras (`1000mg` → `100mg`) | `RE_REPETIDOS` colapsaba cualquier carácter repetido, dígitos incluidos | **resuelto**: el grupo excluye dígitos; `tests/test_cifras.py` lo fija |
| La reparación completa abortaba al final por `OID` duplicados | `comparar()` daba por único un `OID` que el contrato (§7) declara no único | **resuelto**: se deduplica conservando la última aparición |
| La prueba byte-idéntica fallaba sin que nadie tocara el pipeline | la política `eol=lf` de `.gitattributes` normalizaba el CSV de referencia, que debe conservar CRLF | **resuelto**: `NLP/tests/datos/*.csv` marcados como binarios |

## 5. Advertencia grande: `python -m NLP.reduccion.frases`

**No ejecutar nunca `python -m NLP.reduccion.frases`.** Su función `main()`
llama a `construir_datos()`, que **regenera `datos/frases_etiquetadas.csv` desde
las reglas y sobrescribe la curación manual** que es la fuente de verdad del
clasificador de tramos. Es el mismo error que ya ocurrió una vez con este
archivo (lección registrada en `PLAN.md` §5.7 y en el briefing de este ítem).

Para reentrenar el clasificador con los datos curados que ya existen:

```python
from NLP.reduccion import frases
frases.entrenar()
```

Esto sí es seguro: lee `datos/frases_etiquetadas.csv` tal como está y escribe
`salidas/clasificador_frases.joblib`. La única vez que se justifica
`construir_datos()` (y por tanto el `main()` completo) es para arrancar el
archivo curado **desde cero**, con la curación humana ya perdida a propósito —
nunca en una corrida normal ni en una reparación.

Esta misma advertencia aplica, con menos gravedad, a `recursos/lexico.py` y
`recursos/casing.py` (sección 4): no destruyen datos curados a mano, pero
sobrescriben artefactos generados sin previo aviso ante cualquier invocación,
incluida `--help`.

## 6. Política de versión del corrector (E7.2)

Al cambiar cualquier cosa que afecte el resultado de la fase 2 (un umbral, un
léxico nuevo, una capa nueva tras su bandera — principio 8, `PLAN.md` §3):

1. Subir `VERSION_CORRECTOR` en `procesar.py:162` (hoy
   `"4-con-spacy-y-coherencia"`). La clave de caché incluye esta cadena
   (`nucleo/cache.py`, vía `procesar.clave_cache`), así que subirla invalida por
   sí sola toda la caché anterior sin necesidad de borrar nada a mano.
2. Reparar el CSV vigente con la versión nueva:
   `python -m NLP.reparacion.reparar` (sección 3.3), revisando el informe
   (sección 3.4) antes de aplicar.
3. Aplicar solo si `recupero_motivo > perdio_motivo` y cero términos con
   veredicto real: `python -m NLP.reparacion.reparar --aplicar` (sección 3.5).
4. Revectorizar: `python -m embedding.vectorizar` (sección 3.6). No hace falta
   `--rehacer`: la deduplicación por hash de texto revectoriza solo lo que
   cambió.
5. Purgar las copias previas que ya no hagan falta
   (`triage_limpio.previo-<sello>.csv`, que `rotar()` no purga automáticamente —
   error conocido, sección 4) y los vectores huérfanos de `embedding/salidas/
   vectores.f32` si el espacio en disco lo justifica (no hay comando dedicado
   para esto último; requiere reconstruir el almacén desde cero con
   `--rehacer` si se quiere recuperar el espacio).
6. Validar: `python -m clustering --validar` (sección 3.7), comparando contra la
   última cifra de truncaciones conocida (10 de 5.020 textos, `PLAN.md` §7).

Este procedimiento no se ha ejecutado todavía de punta a punta en esta sesión
(E7.2 sigue pendiente en `ESTADO.md`); lo que aquí se documenta es el
procedimiento tal como lo describen el código y `PLAN.md` §8, no una ejecución
verificada.

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | E7.2 | §4 revisada entera contra el código (9 errores resueltos se retiran, 4 siguen vivos); §6 reescrita con el procedimiento realmente ejecutado dos veces, la migración de caché y el criterio de aceptación por calidad absoluta |
| 2026-09-16 | E0.3 | §3.10 y §3.11: procedimiento completo de limpieza del CSV y generación de notas nuevas |
| 2026-09-16 | E1.4 | Primera versión: instalación, tabla de artefactos, comandos por escenario, errores conocidos, advertencia sobre `frases.py` y sobre `recursos/lexico.py`/`recursos/casing.py`, política de versión del corrector |
