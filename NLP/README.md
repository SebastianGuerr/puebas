# NLP — motivo de consulta estandarizado

Convierte las notas crudas de triage (`DIM_TRIAGE.HCTMOTCON`) en una línea por
nota con el motivo de consulta limpio, usando un modelo local de Ollama guiado
por los diccionarios del hospital.

```bash
python -m NLP.procesar --limite 500
```

Entrada: la tabla `DIM_TRIAGE`. Salida: la tabla `nota_triage` de
`salidas/triage.duckdb` (`OID`, `fecha_triage`, `frase_original`,
`frase_procesada`). Hasta el 2026-09-21 era un CSV; `--importar-csv` migra uno
anterior.

## Qué hay en cada archivo

```
NLP/
├── procesar.py        ← el comando de la corrida local
├── prompt.py            el prompt de PRODUCCIÓN (v1.6) + el hueco del glosario
├── prompts/             candidatos en prueba; producción no se toca hasta promover uno
│   ├── v1_7.py            para qwen3:8b: prompt + posprocesar() + segunda pasada
│   └── v1_7_14b.py        el mismo con la abstención suavizada, para qwen3:14b
├── glosario.py          busca en los diccionarios los términos de ESTA nota
├── modelo.py            cliente de Ollama: comprueba, genera, limpia
├── cadena.py            UNA nota de punta a punta: modelo, filtros, segunda pasada
├── fidelidad.py         detectores de alucinación y filtros deterministas
├── banco.py             bancos de fallos y aciertos, la sonda, --oid: medir un cambio
├── duelo.py             el mismo prompt en varios modelos, uno detrás de otro
├── monitor.py           mira la base mientras se llena, sin bloquear al escritor
├── rutas.py             único sitio que sabe dónde vive cada archivo
│
├── nucleo/
│   ├── conexion_bd.py   abre el engine de SQL Server
│   ├── datos.py         consulta las notas, excluyendo los OID ya escritos
│   ├── almacen.py       el escritor de nota_triage en DuckDB
│   └── salida.py        escritor CSV genérico; hoy ningún módulo de NLP/ lo importa
│
├── nube/              ← salir a una GPU alquilada sin exponer a nadie
│   ├── enmascarar.py      tapa identidad, cifras, fechas, terceros
│   ├── exportar.py        base -> paquete.jsonl (id aleatorio + prompt) y mapa local
│   ├── auditar.py         la compuerta: si una línea falla, borra el paquete
│   ├── correr_en_gpu.py   lo ÚNICO que se copia a la máquina remota
│   ├── importar.py        respuestas -> resultados.parquet, emparejando en local
│   └── tabla.py           la tabla de notas sin nada que lleve a la persona
│
├── recursos/          ← escrito a mano, versionado. Si se borra, se pierde
│   ├── siglas.json               siglas, nombres propios y erratas del hospital
│   ├── coloquialismos.json       habla popular colombiana y caldense
│   ├── lugares.csv               1.122 municipios DIVIPOLA (para eliminar)
│   └── terminologia_clinica.json 82 conceptos canónicos (para conservar)
│
├── salidas/           ← lo generan los scripts, ignorado por git
│   ├── banco/                    fallos, aciertos, sonda (la revisión humana vive aquí)
│   ├── nube/                     paquete, mapa, resultados, segunda_pasada.txt, revisar.txt
│   └── tabla/                    notas_triage.csv.gz y su mapa
│
├── tests/             python -m pytest NLP/tests -q
└── docs/
```

## Documentación

| Archivo | Qué responde |
|---|---|
| [docs/FLUJO.md](docs/FLUJO.md) | cómo viaja una nota de la base a la tabla, y las decisiones de diseño |
| [docs/RECURSOS.md](docs/RECURSOS.md) | qué hay en cada diccionario y cómo ampliarlo |
| [docs/PROMPT.md](docs/PROMPT.md) | por qué cada regla dice lo que dice |
| [docs/EVALUACION.md](docs/EVALUACION.md) | cómo se mide que el modelo no alucina: detectores, filtros, sonda, segunda pasada |
| [docs/NUBE.md](docs/NUBE.md) | procesar en una GPU alquilada sin exponer a los pacientes |
| [docs/TABLA.md](docs/TABLA.md) | la tabla de notas para trabajar sin acceso a la base |

## Antes de ejecutar

**Ollama tiene que estar respondiendo.** En Windows la aplicación de la bandeja
lo arranca sola al iniciar sesión; `ollama serve` fallará con «bind: solo se
permite un uso de cada dirección de socket» porque ya está levantado. Comprobar:

```bash
curl http://127.0.0.1:11434/api/tags
```

**Un solo proceso a la vez.** DuckDB admite un solo escritor, y ese escritor
bloquea también a los lectores. Para mirar una corrida en vivo: `python -m
NLP.monitor`. Y en este equipo (15,9 GB, sin GPU) el modelo ya es la cosa pesada:
nada más en paralelo.

## Reglas del repositorio que afectan a esta carpeta

- **No exponer dato personal** (regla 1 de `CLAUDE.md`). `HCTMOTCON` es texto
  clínico de pacientes reales: lo lee el modelo local y **nunca se imprime en
  crudo**. No ejecutar `python -m NLP.procesar` sin decirlo: son horas de
  generación y toma la base DuckDB. Lo que sale del equipo pasa por `nube/`.
- `recursos/` se edita a mano y se versiona; `salidas/` lo regenera el script y
  está ignorado por git. Un archivo nuevo que no encaje en ninguna de las dos
  está mal ubicado.
- La documentación vive en `docs/`, no en los docstrings, y se actualiza en el
  mismo cambio que toca el código.
