# Qué modelo vectoriza, y con qué evidencia se eligió

**Elegido: `BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es`**
(126 M parámetros, 768 dimensiones, Apache-2.0, pooling CLS).

Sustituye a `BAAI/bge-m3`, que era el modelo del paquete hasta el 2026-09-21.

Reproducir la medición entera:

```bash
python -m embedding.comparar_modelos --modelo sapbert_es
python -m embedding.comparar_modelos --modelo sapbert_xlmr
python -m embedding.comparar_modelos --modelo bge_m3
python -m embedding.comparar_modelos --modelo qwen3_06b
python -m embedding.comparar_modelos --tabla
```

---

## Por qué se midió en vez de elegir por reputación

Los *leaderboards* de embeddings (MTEB, MMTEB) miden recuperación de documentos
largos, casi siempre en inglés. Este corpus es lo contrario: frases canónicas de
seis palabras, en español, con terminología clínica. Un modelo puede ser el
número uno de MMTEB y separar mal «tos» de «malestar general» — que es
exactamente lo que este proyecto necesita que separe bien.

La literatura específica de clínico-español lo confirma. El estudio sobre
codificación clínica en CodiESP y DISTEMIST ([arXiv 2605.30529](https://arxiv.org/pdf/2605.30529))
encuentra que **la cobertura de idioma pesa más que el preentrenamiento
biomédico en inglés**: MiniLM-L6 genérico (F1 0,225) le ganó a BioBERT-ST
biomédico (F1 0,193), y MPNet, más grande que los dos, quedó por debajo de
ambos. Su conclusión es que manda la alineación con la tarea, no la escala.

## El diseño de la comparación

No son «los cuatro mejores» sueltos. Es un factorial de 2×2, para poder
atribuir la diferencia a una causa y no solo constatarla:

| | generalista | clínico (método SapBERT) |
|---|---|---|
| **español nativo** | — | `sapbert_es` |
| **multilingüe** | `bge_m3`, `qwen3_06b` | `sapbert_xlmr` |

- Comparar por columnas responde: *¿aporta el preentrenamiento clínico?*
- Comparar `sapbert_es` con `sapbert_xlmr` responde: *¿aporta el español
  nativo, a igual método?*
- `bge_m3` entra obligatoriamente porque es el modelo que se sustituye. Sin él
  no se puede decir «mejoró», solo «da estos números».

Descartados antes de medir:

- `jinaai/jina-embeddings-v3` — licencia CC-BY-NC. Uso hospitalario, no.
- `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` — es un MLM, no un
  codificador de frases. Es la *base* del SapBERT elegido, no un sustituto.

## Las tres pruebas

Todas sobre el mismo set congelado en `salidas/banco_frases.csv`, para que los
cuatro modelos vean exactamente las mismas frases aunque `triage_limpio.csv`
esté creciendo. **Si se vuelve a congelar, hay que volver a correr los cuatro.**

| Prueba | Qué mide | Etiquetas |
|---|---|---|
| **A · Catálogo** | ¿quedan juntas dos variantes del mismo concepto? | 390 variantes de 82 conceptos en 18 categorías, curadas a mano en `datos/catalogo_sintomas.json` |
| **B · Datos reales** | lo mismo sobre `texto_optimizado` | 397 frases, 313 categorizadas por coincidencia con el catálogo (78,8 %) |
| **C · Coste** | frases/s en CPU, y la proyección a 40.000 | — |

Dentro de B manda **`AUC_resp`**: el desenlace intermedio de toda la tesis es la
serie respiratoria (ver `CLAUDE.md`), y un modelo que no separa lo respiratorio
del resto no sirve por bueno que sea en lo demás. Hay 30 frases respiratorias en
el set. El centroide se calcula dejando fuera el propio punto; sin eso cada
positivo se ayuda a sí mismo e infla el AUC.

## Resultado (2026-09-21, 787 frases, CPU, 4 hilos de torch)

| modelo | dim | M par. | vec1 concepto | MAP concepto | vec1 categoría | silueta | knn5 real | **AUC resp** | frases/s | 40k en min |
|---|---|---|---|---|---|---|---|---|---|---|
| **sapbert_es** | 768 | **126** | **0,877** | **0,572** | **0,933** | **0,116** | 0,560 | **0,827** | **24,8** | **27** |
| sapbert_xlmr | 768 | 278 | 0,787 | 0,441 | 0,839 | 0,046 | 0,561 | 0,786 | 19,7 | 34 |
| bge_m3 *(el anterior)* | 1024 | 568 | 0,733 | 0,344 | 0,785 | −0,009 | 0,596 | 0,744 | 6,5 | 103 |
| qwen3_06b | 1024 | 596 | 0,656 | 0,315 | 0,731 | 0,016 | **0,623** | 0,674 | 4,4 | 150 |
| *piso léxico (TF-IDF)* | — | 0 | *0,627* | *0,262* | *0,710* | *0,020* | *0,599* | *0,855* | — | — |

`piso léxico` es TF-IDF de n-gramas de caracteres (`char_wb`, 3–5), sin ninguna
semántica. Está en la tabla porque **un modelo que no le gane no está
aportando nada**, y porque resultó que casi ninguno le ganaba en la prueba B.

## Lectura

**1. Gana en calidad y en velocidad a la vez.** `sapbert_es` es el mejor en
cinco de las siete métricas de calidad y es 3,8× más rápido que el modelo que
sustituye, con la cuarta parte de los parámetros.

**2. El orden es exactamente inverso al tamaño.** 126 M > 278 M > 568 M > 596 M.
Aquí no manda la escala sino el ajuste a la tarea: SapBERT se entrena con
contraste sobre pares de sinónimos de UMLS, que es literalmente el problema de
este corpus — decidir si dos frases cortas nombran el mismo concepto clínico.

**3. Se confirma el hallazgo de la literatura, y se refina.** Español nativo le
gana a multilingüe a igual método (0,877 vs 0,787), y el método clínico le gana
al generalista a igual cobertura de idioma (0,787 vs 0,733 y 0,656). Las dos
cosas aportan, y se suman.

### La excepción: `knn5_real`, y por qué no cambia la decisión

En la prueba B, `sapbert_es` queda **último** (0,560 contra 0,623 de qwen3). Eso
contradice todo lo demás, así que se investigó antes de decidir.

Las etiquetas débiles de B se asignan por **coincidencia de subcadena** con una
variante del catálogo. Dos frases que comparten la etiqueta comparten, por
construcción, un literal. Un modelo que agrupe por parecido superficial acierta
esas gratis. La comprobación:

| | knn5 todos | knn5 **excluyendo el mismo concepto** | caída |
|---|---|---|---|
| *TF-IDF léxico* | *0,599* | *0,223* | *0,376* |
| **sapbert_es** | 0,560 | **0,262** | **0,298** |
| qwen3_06b | 0,623 | 0,247 | 0,376 |
| bge_m3 | 0,596 | 0,246 | 0,351 |

Dos cosas:

- **TF-IDF, que no tiene semántica ninguna, le gana a tres de los cuatro
  modelos** en `knn5 todos`. Eso basta para concluir que esa métrica está
  midiendo solapamiento léxico, no separación clínica.
- Al quitar los vecinos que comparten concepto — es decir, los pares que
  comparten categoría pero **no** literal — **el orden se invierte**:
  `sapbert_es` pasa a primero y TF-IDF se hunde a último. Y `sapbert_es` es el
  que menos cae, o sea el que menos dependía de la fuga.

El mismo problema afecta a `AUC_resp`, donde TF-IDF marca 0,855: las frases
respiratorias comparten literales obvios (*tos*, *disnea*), así que un modelo
léxico recupera la etiqueta trivialmente. Entre los cuatro modelos el orden
sigue valiendo, pero el valor absoluto está inflado para todos.

**La prueba A no tiene ese problema**, y es donde la decisión se apoya: sus
etiquetas son conceptos curados a mano cuyas variantes son sinónimos
deliberadamente distintos, y ahí el piso léxico se queda en 0,627 mientras
`sapbert_es` llega a 0,877 — 25 puntos de ganancia que no son léxico.

## Lo que esta medición NO prueba

- **El catálogo no es una referencia independiente.** Se construyó mirando este
  mismo corpus, así que comparte su vocabulario.
- **Nada de esto mide acierto de pronóstico.** Mide calidad de representación,
  que es un insumo. Que la serie respiratoria mejore el pronóstico es otra
  medición, aguas abajo, y está sin hacer.
- **El set es pequeño** (787 frases, 30 respiratorias). Las diferencias grandes
  (0,877 vs 0,656) aguantan; las pequeñas, no.
- **No se probó afinar ninguno.** El estudio citado obtiene F1 0,709 afinando un
  bi-encoder con negativos duros, muy por encima de cualquier modelo de estante.
  Es el camino si hiciera falta más.

## Cuándo repetir esto

- Cuando `triage_limpio.csv` tenga el corpus completo (~94.000 notas). Con
  40.000 frases y varios cientos de respiratorias, los intervalos se estrechan
  mucho.
- Si cambia el prompt de `NLP/` y con él la forma de `texto_optimizado`.
- Antes de dar por buena cualquier conclusión sobre la serie respiratoria.
