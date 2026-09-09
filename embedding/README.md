# Paquete embedding — fase 4

Toma el CSV que dejan las fases 1-3 (`NLP/salidas/triage_limpio.csv`) y convierte
cada nota en un registro estructurado y en el texto canonico que se le manda a
bge-m3. No corrige ortografia ni normaliza siglas: eso ya paso antes.

```bash
# desde la raiz del repositorio
python -m embedding.estructurar
python -m embedding.estructurar --csv "D:\ruta\a\otro_triage_limpio.csv"
```

| archivo | que hace |
| --- | --- |
| `estructurar.py` | orquesta la fase: lee el CSV y escribe las tres salidas |
| `extraccion.py` | sintomas, valores numericos y categoria de la nota |
| `negacion.py` | negacion, incertidumbre y antecedente en espanol clinico |
| `texto_embedding.py` | construye la frase canonica que va al modelo |
| `rutas.py` | unico sitio que sabe donde vive cada archivo |

Misma regla de carpetas que en `NLP/`: `datos/` se edita a mano y se versiona
(`catalogo_sintomas.json`), `salidas/` lo escribe un script y esta ignorado por
git (`triage_estructurado.jsonl`, `triage_estructurado.json`,
`resumen_estructuracion.txt`).

Este paquete depende de `NLP/`: `texto_embedding.py` usa `NLP/reduccion/` para
recortar la nota, y `rutas.py` toma de `NLP.rutas` la ubicacion del CSV de
entrada. El recorte vivia aqui como `recorte.py` y se movio a `NLP/`, que es
donde estan las demas fases de texto y desde donde `procesar.py` puede
escribir la columna `texto_embedding` sin invertir la dependencia. La dependencia va en un solo sentido; `NLP/` no importa nada de aca,
salvo la ruta del catalogo de sintomas.
