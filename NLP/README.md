# NLP — motivo de consulta estandarizado

Convierte las notas crudas de triage (`DIM_TRIAGE.HCTMOTCON`) en una línea por
nota con el motivo de consulta limpio, usando un modelo local de Ollama guiado
por los diccionarios del hospital.

```bash
python -m NLP.procesar --limite 500
```

Entrada: la tabla `DIM_TRIAGE`. Salida: `salidas/triage_limpio.csv`, con
`OID`, `texto_original` y `texto_optimizado`.

## Qué hay en cada archivo

```
NLP/
├── procesar.py        ← el comando. Único archivo que conoce la base de datos
├── prompt.py            las 15 reglas + el hueco donde se inyecta el glosario
├── glosario.py          busca en los diccionarios los términos de ESTA nota
├── modelo.py            cliente de Ollama: comprueba, genera, limpia
├── rutas.py             único sitio que sabe dónde vive cada archivo
│
├── nucleo/
│   ├── conexion_bd.py   abre el engine de SQL Server
│   ├── datos.py         consulta las notas, excluyendo los OID ya escritos
│   └── salida.py        EscritorCSV, reanudación por OID, rotación del CSV
│
├── recursos/          ← escrito a mano, versionado. Si se borra, se pierde
│   ├── siglas.json               siglas, nombres propios y erratas del hospital
│   ├── coloquialismos.json       habla popular colombiana y caldense
│   ├── lugares.csv               1.122 municipios DIVIPOLA (para eliminar)
│   └── terminologia_clinica.json 82 conceptos canónicos (para conservar)
│
├── salidas/           ← lo genera el script, ignorado por git
│   └── triage_limpio.csv
│
├── tests/             python -m pytest NLP/tests -q
└── docs/
```

## Documentación

| Archivo | Qué responde |
|---|---|
| [docs/FLUJO.md](docs/FLUJO.md) | cómo viaja una nota de la base al CSV, y las cuatro decisiones de diseño |
| [docs/RECURSOS.md](docs/RECURSOS.md) | qué hay en cada diccionario y cómo ampliarlo |
| [docs/PROMPT.md](docs/PROMPT.md) | por qué cada regla dice lo que dice |

## Antes de ejecutar

**Ollama tiene que estar respondiendo.** En Windows la aplicación de la bandeja
lo arranca sola al iniciar sesión; `ollama serve` fallará con «bind: solo se
permite un uso de cada dirección de socket» porque ya está levantado. Comprobar:

```bash
curl http://127.0.0.1:11434/api/tags
```

**Un solo proceso a la vez.** Dos corridas simultáneas escriben el mismo CSV sin
saber una de la otra y duplican OID.

## Reglas del repositorio que afectan a esta carpeta

- **Nadie más que el propietario se conecta a la base.** `HCTMOTCON` es
  información clínica de pacientes reales. No ejecutar `python -m NLP.procesar`
  sin ser quien tiene autorización para descargar esos datos.
- `recursos/` se edita a mano y se versiona; `salidas/` lo regenera el script y
  está ignorado por git. Un archivo nuevo que no encaje en ninguna de las dos
  está mal ubicado.
- La documentación vive en `docs/`, no en los docstrings, y se actualiza en el
  mismo cambio que toca el código.
