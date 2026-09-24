# La tabla de notas sin nada que lleve a la persona

`NLP/nube/tabla.py`. Existe desde el 2026-09-24. Cómo se ejecuta está al principio del
módulo; este documento dice **por qué** está hecho así.

## Para qué

Para trabajar el texto de las notas —procesarlas con el modelo, comparar prompts y
modelos, cruzarlas con clima y calendario— en un equipo **sin acceso a la base clínica**.
Ese equipo necesita el texto, el día, el nivel y la edad. No necesita saber de quién es
cada nota, y el análisis tampoco: el proyecto estudia tendencias, no personas.

Es hermana de `NLP/docs/NUBE.md`, con otro propósito. El paquete de la nube lleva prompts
ya armados para una GPU alquilada que no debe recibir nada del proyecto. La tabla lleva
**la nota sola**, para que quien la trabaje pueda armar el prompt que quiera.

## Qué sale y qué no

| Sale: `notas_triage.csv.gz` | Se queda en este equipo |
|---|---|
| `id` aleatorio de 16 hex | el OID, en `mapa_local.parquet` (`id → OID`) |
| `fecha`: el día | la hora del triage |
| `nivel` y `nivel_nombre`; los raros como `otro` | el nivel raro |
| `edad_banda` | la edad exacta |
| `nota` con lo identificable **borrado** | el texto original y las columnas de identidad (esas ni se guardan) |

## Por qué cada decisión

**Borrar, no marcar.** Decisión del propietario. `[NOMBRE]` o `[FECHA]` no le dicen nada
clínico al modelo y sí le dan algo que copiar: `importar.py` tiene que quitar marcas que el
modelo repite en su respuesta. Lo que se borra es exactamente lo que tapa `enmascarar.py`,
el mismo detector con las mismas pruebas. La marca se sustituye por un espacio y no por
nada, para que dos números a sus lados no se peguen.

**El día y no la hora.** Con el día, cada nota queda entre las ~170 de ese día. Con la hora
exacta, la fila apunta a una persona: quien sepa que alguien fue a urgencias a tal hora
encuentra su nota. El patrón por hora ya existe contado en `salidas/triage_horario.parquet`,
sin texto. **La hora ni siquiera se lee**: `CAST(HCTFECTRI AS DATE)` se hace en SQL Server.

**La edad en bandas, calculadas en SQL Server.** Es la regla de `CLAUDE.md` y de
`extraccion/`, con el mismo `CASE` y las mismas etiquetas de `salidas/triage_edad.parquet`,
así que las dos se cruzan sin traducir. La edad exacta tampoco llega a Python. Y la banda
aporta mucho al argumento: si un cambio de clima pega más en 0-4 y 65+ que en 15-44, eso ya
no es coincidencia, es el mecanismo.

**Una segunda pasada para fechas.** `enmascarar.py` no toca a propósito una fecha pegada a
un guion (`(?<![\d/.-])`), para no partir series de signos como `120/80-…`. La auditoría
solo excluye una cifra delante, así que es más estricta. En la primera corrida completa
(2026-09-24) eso **tumbó el CSV**: 3 de 95.424 notas. Vistas solo por su forma (cifras
como `9`): una fecha real `(aa. -99/99/9999)` y dos series con forma de fecha
(`99/999/99-99/99/99`, `9-9-9-9-9-99`). La tabla las borra igual con los patrones de la
auditoría (`_red_de_fechas`), y lo que quita se cuenta aparte como `fecha_red`. Perder la
cola de una serie de signos en dos notas vale menos que dejar salir una fecha. El caso de
la fecha real es un fallo de `enmascarar.py` que también afecta al paquete de la nube.

**Los niveles raros salen como `otro`.** Es la supresión de celdas pequeñas de cualquier
boletín: un nivel con menos de 100 notas en toda la tabla (`MINIMO_NIVEL`) no sale con su
nombre. El caso que lo motivó: `MUERTO` tiene 285 triages en seis años, y «día + murió en
urgencias + lo que pasó» se cruza con una noticia. En la ventana con texto quedaron
agrupados `I-G, IV-G, M, UA, V-G`. El umbral se calcula con un `GROUP BY` sobre toda la
tabla, no sobre la muestra, así que una exportación de 300 notas agrupa lo mismo que una
completa.

**Un id aleatorio aunque hoy no se necesite volver al paciente.** No revela nada y deja la
puerta abierta: si mañana hace falta otra variable para las mismas notas, se une aquí por
el mapa en vez de reprocesar todo. Es aleatorio (`secrets`) y no un hash del OID, porque un
hash se deshace recalculándolo para cada OID candidato.

**Ordenado por día y al azar dentro del día.** El OID crece con la hora. Ordenadas por OID,
la posición de la fila diría a qué hora llegó cada paciente. Dentro del día se ordena por el
id, que es aleatorio.

**El mapa nunca se pisa.** Si un CSV anterior ya se procesó fuera, su mapa es lo único que
devuelve esas filas a su triage. `--forzar` lo aparta con su fecha.

**La auditoría falla cerrado.** Corre sola al final de `--exportar`, con la identidad de cada
paciente todavía en memoria. Si **una sola** comprobación falla, borra el CSV. Revisa por
fila: ningún resto del nombre o documento de ese paciente, ningún número de 5+ cifras,
fecha completa, teléfono, correo, URL ni marca sin borrar; el día sin hora; el nivel no raro;
la banda válida. Y del archivo entero: exactamente las seis columnas, la huella sin cambios
desde que se armó, los mismos ids que el mapa, y ni el id ni el orden dentro del día
correlacionan con el OID (límite 4/√n). El informe son solo conteos.

## Evidencia

Muestra de 300 notas contra la base real (2026-09-24): **0 fallos**, identidad verificada
contra la base, correlaciones −0,056 y 0,051 (límite 0,231), términos clínicos 323 → 324.
Se borró algo en 11 notas: fechas 5, nombres de terceros 2, lugares 2, documento 1, nombre
del paciente 1.

**Corrida completa (2026-09-24): 95.424 notas, 0 fallos**, identidad verificada contra la
base, correlaciones 0,0003 y −0,0003 (límite 0,0129), términos clínicos en 2.000 notas al
azar 2.203 → 2.207. `notas_triage.csv.gz` pesa 4,2 MB; va del 2025-01-08 al día de la
corrida (el último día está incompleto). Notas con algo borrado: fecha 1.588 (1,66 %),
nombre de tercero 887, lugar 292, nombre del paciente 173, nombre suelto 152, número 49,
correo 4, documento 2, red de fechas 3. Quedaron vacías 4. Agrupados como `otro`: 209
notas de `I-G, IV-G, M, UA, V-G`. Una revisión independiente sobre el CSV leído desde fuera
dio 0 marcas, 0 números de 5+ cifras, 0 arrobas y 0 saltos de línea.

Coste: borrar cuesta ~1 ms por nota. Contar términos clínicos cuesta 12 ms, por eso esa
comprobación de calidad se hace sobre 2.000 notas al azar y no sobre todas.

`NLP/tests/test_tabla.py` fija cada promesa con datos sintéticos (36 pruebas). Se comprobó
que fallan si se rompe lo que prueban: dejando las marcas en vez de borrarlas caen 8.

## Límites, dichos sin rodeos

- **En texto libre no existe anonimización perfecta.** Un nombre sin palabra que lo anuncie
  («María dice que…») no se detecta, y una descripción muy rara puede señalar a alguien por
  contexto. Lo que baja el riesgo es el conjunto: sin OID, sin hora, sin edad exacta y sin
  documento.
- **Cada columna que se añade a la misma fila achica el grupo.** Día × banda × nivel ya
  deja casillas pequeñas en días de poco movimiento. Antes de sumar otra columna (sexo,
  municipio, diagnóstico), medir el tamaño de las casillas.
- **La autorización institucional no la da el código.** Esta capa reduce la exposición;
  decidir dónde se procesan datos de salud es de la institución.
