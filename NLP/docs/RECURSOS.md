# Los cuatro diccionarios

`NLP/recursos/` es lo que le da contexto al modelo. Se edita a mano, se versiona
y ningún script lo regenera: **si se borra, se pierde trabajo humano.**

Sin estos archivos el modelo sigue corriendo, pero deja de entender el habla de
Caldas y las abreviaturas del hospital, y cuando no entiende, inventa.

## Qué hay en cada uno

### `siglas.json` — 592 entradas útiles

Siglas, abreviaturas, nombres propios y erratas verificadas del hospital.

| Bloque | Qué contiene | Cómo lo usa `glosario.py` |
|---|---|---|
| `_grupos_expandibles` (9 grupos) | qué grupos pueden expandirse en el prompt | filtro de entrada |
| `diagnosticos`, `examenes`, `farmacos`, `anatomia`, `obstetricia`, `cardiologia`, `signos_vitales`, `vias_y_pautas`, `unidades`, `eponimos`, `terminos_clinicos`, `escalas_scores`, `respiratorio_soporte`, `administrativo` | `sigla → significado` | «Equivalencias del hospital» |
| `instituciones_marcas` (32), `geografia` (65) | EPS, clínicas, barrios | «Nombres propios» → el modelo los elimina |
| `correcciones_directas` (51) | erratas ya verificadas a mano | «Erratas conocidas» |
| `_siglas_ambiguas` (71) | lista negra: nunca se expanden | se descartan aunque estén en un grupo expandible |
| `_siglas_inequivocas` (141) | lista blanca declarada | documenta qué se dio por seguro |

**La política está dentro del archivo, no en el código.** `_siglas_ambiguas` es
lo que impide que `PA` se expanda a «presión arterial» en una nota donde
significa otra cosa. Añadir una sigla a un grupo expandible sin revisar si es
ambigua es el error que este diseño previene.

### `coloquialismos.json` — 260 expresiones

Habla popular colombiana y caldense mapeada a término clínico, por aparato:
`sintomas_generales` (80), `trauma` (58), `piel` (24), `urinario_genital` (24),
`digestivo` (22), `oido_garganta_nariz` (19), `neurologico_general` (16),
`fiebre_infeccion` (12), `negaciones_frecuentes` (5), `codigos_hospitalarios` (4).

Dos formatos, y la diferencia importa:

```jsonc
"maluca": "malestar general"          // se aplica siempre

"fuego": {                            // se aplica solo en contexto
  "significado": "herpes labial",
  "contexto": ["labio", "boca"]
}
```

La forma con `contexto` existe porque una expresión popular puede ser dos cosas
distintas. `fuego` es herpes labial cuando la nota habla del labio, y es una
quemadura o un arma cuando no. Sin el contexto, el diccionario acertaría en un
caso y estropearía el otro.

`_nota_inferencias` deja escrito qué expresiones se excluyeron a propósito: las
que obligan a inferir algo que la nota no dice.

### `lugares.csv` — 1.122 municipios

Listado oficial DIVIPOLA (DANE), columnas `departamento` y `municipio`.

Está aquí para **eliminar**, no para conservar: la procedencia del paciente es
dato identificable y no es motivo de consulta. El bloque que se inyecta le dice
al modelo que lo que reconoció es un lugar y que lo quite.

`glosario.buscar_lugares()` no ofrece el departamento por separado si ya ofreció
un municipio suyo, para no llenar el prompt de repeticiones.

### `terminologia_clinica.json` — 82 conceptos, 395 variantes

Catálogo de síntomas canónicos del proyecto:

```jsonc
"epistaxis": {
  "categoria": "otorrinolaringologia",
  "variantes": ["sangrado nasal", "sangra la nariz", ...]
}
```

Es el único de los cuatro que le dice al modelo qué **conservar**. Cuando la nota
usa una variante, el prompt le ofrece el término canónico. Eso hace que la misma
dolencia se escriba igual en todas las filas, que es lo que permite agrupar
después.

Trae además `_categorias` (19), `_prioridad_categorias` (18) y
`_localizaciones_dolor` (74), que hoy no se inyectan en el prompt: los consume
`clustering/` aguas abajo.

## Cómo se busca dentro de una nota

`glosario.py` compara **sin tildes, sin distinguir mayúsculas y por palabra
completa**. El límite de palabra no es un detalle:

> Sin él, `pop` coincidiría dentro de `popo` y expandiría a «postoperatorio» una
> nota que habla de deposiciones.

Cada sección del bloque se corta en 12 entradas (`bloque(nota, maximo=12)`), y
las expresiones más largas van primero porque son las más específicas.

## Cómo se amplía

1. Añadir la entrada al archivo que le corresponde.
2. Si es una sigla, comprobar que no esté en `_siglas_ambiguas`.
3. Si la expresión puede significar dos cosas, usar la forma con `contexto`.
4. `python -m pytest NLP/tests -q`.
5. Comprobar el bloque que se le va a inyectar al modelo con una nota real:

```python
from NLP import glosario
print(glosario.bloque("PCTE DE CHINCHINA SE PUSO MOTRADA Y CON CHUZONES"))
```

**Cuidado al validar contra ejemplos propios.** Varias equivalencias del
diccionario coloquial las propuso un asistente, no un clínico. Una nota cuya
respuesta esperada salió del mismo glosario que se le inyecta al modelo no mide
si el modelo acierta: mide si sabe copiar. Para medir de verdad hace falta que
un clínico fije la respuesta esperada sin ver el diccionario.
