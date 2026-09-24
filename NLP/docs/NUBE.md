# Procesar en una GPU alquilada sin exponer a los pacientes

`NLP/nube/`. Existe desde el 2026-09-23. Cómo se ejecuta paso a paso está al principio de
`NLP/nube/correr_en_gpu.py`; este documento dice **por qué** está hecho así.

## El problema

Procesar las ~94.000 notas con el modelo en la CPU local lleva semanas. En una GPU alquilada
lleva horas y cuesta decenas de miles de pesos. Pero la GPU es de **un tercero**, y el texto
de las notas es información clínica de pacientes reales, que a veces trae nombres,
documentos o direcciones escritos a mano. Los datos de salud son datos sensibles (Ley 1581
de 2012). La regla 1 de `CLAUDE.md` no es «no tocar la base»: es **no exponer dato
personal**.

## Qué sale y qué no

| Sale a la nube | Se queda en el equipo local |
|---|---|
| Un `id` aleatorio (16 caracteres hex) por nota | El OID |
| El prompt completo, con la nota **ya enmascarada** | La fecha y la hora del triage |
| `opciones.json`: modelo y parámetros | Las columnas de nombre y documento (ni siquiera se guardan: se usan en memoria) |
| El script `correr_en_gpu.py`, solo biblioteca estándar | El texto original, el mapa `id → OID` y el código del proyecto |

**Nada más.** Ni fechas, ni columnas, ni metadatos, ni el orden: el paquete va **barajado**,
porque en orden de OID revelaría la cronología.

## Por qué cada decisión

**El prompt se construye en local.** La máquina remota no recibe el código del proyecto, ni
los diccionarios, ni `fidelidad.py`. Recibe texto y lo devuelve. Los filtros de
`posprocesar()` se aplican **al volver**, en local, contra la nota **original** sin
enmascarar, que nunca salió.

**Se enmascara con las columnas del propio paciente.** Para cada nota se leen en memoria
`GPADOCUME`, `GPANOMBRE`, `GPASEGNOM`, `GPAAPELLI` y `GPASEGAPE` de **esa** fila, y se buscan
dentro del texto: es la forma más precisa de encontrar el nombre del paciente escrito a mano.
Además:
- 5 o más dígitos seguidos → `[NUM]`
- fechas completas → `[FECHA]`
- correos y URLs
- nombres tras «sr», «dra», «traído por», «hijo de»… → `[NOMBRE]`
- «residente de», «barrio», «vereda», «dirección» → `[LUGAR]`

**Los nombres de pila que son palabras comunes no se enmascaran solos.** «Dolores», «Luz»,
«Rosa», «Consuelo», «Amparo»… Si la paciente se llama Dolores, enmascarar «dolores» a secas
destruiría «dolores musculares». Se enmascaran solo junto a su apellido o tras un trato.

**Las duraciones clínicas no se tocan.** «Hace 3 días», «36 semanas de gestación», «11 kilos»:
son el motivo y el análisis de rezagos, no datos personales.

**La auditoría falla cerrado.** `python -m NLP.nube --auditar` revisa cada línea antes de dar
el paquete por bueno: solo `id` y `prompt`; ningún resto del nombre o documento de ese
paciente; ningún número largo, fecha, correo ni URL; ids y orden sin correlación con el OID.
**Si algo falla, borra el paquete** y reporta solo conteos. También mide el
sobre-enmascarado: los términos clínicos de la nota antes y después.

## La segunda pasada: dos viajes, no uno

Añadida el 2026-09-24. En local, `NLP/cadena.py` hace la red de seguridad contra descartes
falsos dentro de la misma nota: si la salida es «sin motivo clinico» pero la nota trae
evidencia clínica (`fidelidad.necesita_segunda_pasada`), se le vuelve a preguntar al modelo
con `construir_segunda_pasada()`, un prompt que no admite abstenerse. En la nube eso no se
puede hacer así: la máquina remota no tiene `fidelidad.py` —y no debe tenerlo—, así que la
decisión de repetir se toma **al volver**, en local, y la repetición es un segundo paquete.

```
python -m NLP.nube --exportar ...                 1er paquete (prompt normal)
   ... GPU:  correr_en_gpu.py                      -> respuestas.jsonl
python -m NLP.nube --importar respuestas.jsonl    resultados.parquet + segunda_pasada.txt
python -m NLP.nube --exportar --segunda-pasada --forzar   2º paquete: solo esos OID
python -m NLP.nube --auditar                      la misma compuerta, sin excepciones
   ... GPU:  correr_en_gpu.py --salida respuestas_segunda.jsonl
python -m NLP.nube --importar respuestas_segunda.jsonl     reemplaza a los pendientes
```

Cada fila de `resultados.parquet` lleva su columna `pasada`:

| `pasada` | Qué quiere decir | ¿Se fusiona con `nota_triage`? |
|---|---|---|
| `primera` | salida normal, o descarte de una nota sin evidencia clínica | sí |
| `pendiente_segunda` | descartada **con** evidencia clínica; espera el 2º paquete | **no** |
| `segunda` | la segunda pasada dio un motivo, y es fiel | sí |
| `revisar` | descartada dos veces, o la segunda pasada inventó. Queda «sin motivo clinico» y su OID va a `revisar.txt` | sí, como descarte |

**Por qué un descarte pendiente no entra a la base.** Un descarte es un paciente que sale de
la cuenta del desenlace. Si entrara antes de su segunda pasada, la serie tendría un hueco que
todavía se puede cerrar, y nada en la base diría que es provisional.

**Por qué, si la segunda pasada inventa, gana el descarte.** Un descarte marcado se puede
revisar; un motivo inventado sin marca se cuenta como verdadero. Es la misma regla de
`NLP/cadena.py`.

**Qué no cambia en la seguridad.** El segundo paquete pasa por el mismo enmascarado y la
misma auditoría; sus `id` son aleatorios y distintos de los del primero, así que las dos
listas de respuestas no se pueden cruzar entre sí en la máquina remota. `segunda_pasada.txt`
y `revisar.txt` son OIDs y **nunca salen** del equipo.

**La respuesta de la segunda pasada va en otro archivo** (`--salida`). El mapa del segundo
paquete reemplaza al primero (el anterior queda apartado como `mapa_local_<fecha>.parquet`);
si las dos tandas fueran al mismo `respuestas.jsonl`, las del primer paquete saldrían como
«sin entrada en el mapa».

**Lo que falta.** `nota_triage` no tiene todavía columnas de versión, modelo ni pasada: al
fusionar, un `revisar` se vuelve indistinguible de un descarte normal. Mientras no se decida
(docs/HANDOFF.md), `revisar.txt` es la única marca.

## Verificado sobre una muestra real de 300 notas (2026-09-23)

Auditoría del propio módulo **y** una auditoría independiente, escrita aparte:

| Comprobación | Resultado |
|---|---|
| Claves por línea | solo `id` y `prompt` |
| Restos de 5+ dígitos, fechas, correos, URLs, OIDs | **0** |
| Orden del paquete contra el OID | correlación **+0,049** (barajado) |
| Columnas sensibles guardadas, incluso en local | **ninguna** |
| Términos clínicos antes → después | **323 → 323** |

## Límites, dichos sin rodeos

- **En texto libre no existe anonimización perfecta.** Un nombre de tercero sin palabra que
  lo anuncie («María dice que…») no se detecta. Tampoco una descripción rara que identifique
  a alguien por contexto.
- **Lo que reduce el riesgo es el conjunto**: aunque un nombre suelto se escapara, viaja sin
  OID, sin fecha, sin documento y en orden aleatorio. No se puede ligar a una persona ni a la
  base del hospital.
- **Falta la decisión institucional.** Esta capa reduce mucho la exposición, pero la
  autorización para procesar datos de salud en infraestructura de un tercero no la da el
  código.

## Cómo no gastar de más

1. Todo se deja listo y probado **en local** antes de encender la máquina.
2. **Piloto de 30 minutos** (`--piloto 30`): mide notas por minuto y proyecta el costo total
   antes de comprometerse.
3. La corrida es **reanudable**: una desconexión no obliga a repetir.
4. Al terminar: descargar `respuestas.jsonl`, **borrar con `shred`** paquete y respuestas, y
   **destruir la máquina**, no solo apagarla (algunos proveedores conservan el disco).
