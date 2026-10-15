# Actualizadores de los calendarios hechos a mano: eventos de Manizales y fiestas de Caldas

**Decisión de origen:** `docs/CONTEXTO.md`, entrada del 2026-10-15. Cada fuente externa de M3s se actualiza sola.
Los dos calendarios escritos a mano se acababan en 2026: `eventos_manizales_2020_2026.csv` el 29-nov y
`fiestas_caldas_2020_2026.csv` el 8-dic. Sin filas para 2027, `fut_m_feria_d0_4` y `fut_m_fiesta_lejana`
(`notebooks/mecanismos.py`) se quedaban en cero en silencio. Construido el 2026-10-15.

## Cómo se usa

```
python calendarios/eventos/actualizar_eventos.py           agrega lo que falte y rehace la lista por confirmar
python calendarios/eventos/actualizar_fiestas.py           lo mismo para las fiestas
python calendarios/eventos/actualizar_eventos.py --seco    muestra lo que agregaría, sin escribir nada
... --hoy 2026-10-15 --anios 2                             fecha de corte y años a proyectar después del actual
```

| Pieza | Qué hace |
|---|---|
| `calendarios/eventos/reglas.py` | El motor común: festivos, familias de regla, ajuste, medida, planificación, escritura solo al final del archivo y lista por confirmar |
| `calendarios/eventos/actualizar_eventos.py` | Agrupa los eventos por nombre, decide qué series se proyectan y fabrica las filas, con la edición incrementada |
| `calendarios/eventos/actualizar_fiestas.py` | Lo mismo para las fiestas, por municipio + nombre. Lee `periodicidad` y `mes_tipico` |
| `salidas/contexto/por_confirmar_eventos.csv` | Lo que una persona tiene que confirmar. Lo escriben los dos scripts; cada uno rehace solo sus filas |

Sale con código 1 ante cualquier falla, con el mensaje en stderr. Ejemplos: un archivo con otras columnas, una
fecha mal escrita, o un horizonte que pasa del final de `calendario_Colombia.csv` (hoy, 2030).

## Garantías

1. **Nunca se modifica una fila existente.** Las filas nuevas se agregan al final, con el mismo fin de línea del
   archivo: CRLF en eventos y LF en fiestas. Después de escribir se comprueba que el contenido anterior quedó
   intacto **byte a byte** como prefijo. Si no, se restaura el original y el script falla. Los nombres de archivo no
   cambian.
2. **Idempotente.** Si una serie ya tiene fila en un año, de cualquier estado y calidad, no recibe otra. Medido el
   2026-10-15: con una segunda corrida, los dos CSV y la lista por confirmar quedan con la misma huella sha256.
3. **El pasado no se toca.** Solo se agrega una fila si su fecha estimada de inicio es posterior a la fecha de
   corte. Si una edición del año en curso falta y ya pasó, va a la lista por confirmar (`falta_pasada`) y no se
   estima. Medido el 2026-10-15: entre el 2020-01-01 y el 2026-10-14 hay 0 días distintos, antes y después de
   escribir, en `fut_m_feria_d0_4`, `fut_m_fiesta_lejana` y las ocho columnas `fut_ev_*` y `fut_fiestas_*` de
   `notebooks/pronostico.py`.
4. **Las filas nuevas se distinguen.** Llevan `estado = programado`, para que el modelo las use, y
   `calidad_fecha = estimada_auto`. La regla y su acierto quedan en `descripcion` (eventos) o al principio de
   `fuente_url` (fiestas). Las fiestas llevan además `marca = I` (inferido).

**Para confirmar o corregir una fila estimada**, se edita a mano: se pone la fecha real y
`calidad_fecha = confirmada`. Desde ahí es una fila más y el script no la toca. Si la edición se cancela, se cambia
el `estado` a `cancelado`. **No hay que borrarla:** si se borra, la siguiente corrida la vuelve a estimar.

## Cómo se deduce la regla

**Con qué datos.** La regla se ajusta con las filas de `calidad_fecha` `confirmada` o `recurrente_anual` que tienen
`fecha_inicio`. Se usan los estados `realizado`, `programado`, `cancelado` y `aplazado`: en una edición cancelada o
aplazada, la fecha prevista también dice cuándo se programa la fiesta.
- Se excluyen las ediciones `virtual` o `hibrido`: en 2020-2021 la virtualidad movió las fechas (la Feria del Libro
  pasó a julio).
- Se excluyen las filas `estimada` y `estimada_auto`: una estimación no puede servir para medir otra.
- En las fiestas, `mes_tipico` puede declarar un cambio de régimen. «… (desde 2024)» deja solo los años desde 2024.
  «agosto (2021-2022 en noviembre)» excluye 2021 y 2022.

**Tres familias de regla, todas evaluadas:**

| Familia | Ejemplo |
|---|---|
| `fijo`: el mismo día del mismo mes | Día de las Velitas, 7 de diciembre |
| `festivo`: N días antes o después de un festivo en su fecha trasladada (Ley Emiliani), o de la Pascua; como mucho a 15 días | Festival de los Palenques: 3 días antes del lunes festivo de La Asunción |
| `semana`: el primer «día de la semana» desde el día D del mes M | Feria de Manizales: primer sábado de enero |

Cada familia se prueba también con el ajuste «si cae en festivo, al día siguiente». Los festivos salen de
`calendarios/calendario_Colombia.csv`, que llega hasta 2030 e incluye el nuevo festivo de Chiquinquirá de 2027.

**Cómo se elige la regla.** Gana la que reproduce exactamente más años. Si hay empate, decide, en este orden:
1. el menor desvío total;
2. la familia más simple: fijo, luego festivo, luego semana;
3. la regla sin el ajuste antes que con él;
4. el festivo más cercano;
5. el n-ésimo día de la semana canónico (desde el 1, 8, 15 o 22);
6. la ventana más centrada en lo observado.

**Dos medidas, y la honesta es la segunda:**
- **Dentro de muestra:** cuántos años confirmados reproduce exactamente la regla elegida, y el desvío en días de los
  que falla (predicción − real).
- **Dejando uno fuera:** para cada año confirmado, se elige la regla con los demás años y se predice ese año. Elegir
  entre cientos de reglas candidatas con 2-6 años sobreajusta, y esta medida lo destapa. Con 2 años, «dejando uno
  fuera» equivale a «la misma fecha que el otro año».
- **Confianza** (para ordenar la revisión, no es una probabilidad):
  - `alta`: al menos 3 años y 2/3 de aciertos exactos dejando uno fuera;
  - `media`: desvío medio de 3 días o menos dejando uno fuera;
  - `baja`: el resto;
  - `sin medir`: menos de 2 años.

**Qué series se proyectan y a qué años.** Los años son el actual y los `--anios` siguientes, 2 por defecto: con
corte el 2026-10-15, lo que queda de 2026, 2027 y 2028.

| Caso | Qué se hace |
|---|---|
| Periodicidad (fiestas) | Se toma de la última fila escrita a mano. `anual`, `anual desde AAAA` y `anual (antes bienal)` → todos los años. `bienal … pares` o `impares` → los años de esa paridad. `años sin Cordialidad` → pares, porque la Cordialidad de Manzanares es bienal en impares. `irregular`, `desconocida`, `única` o `bienal/irregular` → no se proyecta (`no_proyectada`) |
| Periodicidad (eventos) | No hay columna: es anual si la serie tiene filas en 2 o más años. No se proyectan la categoría `emergencia` ni los eventos de un solo año (partidos, elecciones, la Vuelta) |
| Serie viva | Tiene que tener una fila escrita a mano del año pasado (o del antepasado, si es bienal). Si ya se proyectó, aguanta 3 años sin confirmación a mano, con aviso; después deja de proyectarse. Así quedó fuera el Congreso Iberoamericano de Teatro, sin filas desde 2024 |
| Un solo año con fecha | No se proyecta, porque no se puede medir. Va a la lista con una fecha sugerida |
| Temporada Taurina | Se proyecta solo hasta el 21-07-2027: la Ley 2385 de 2024 prohíbe las corridas desde el 22-07-2027. Entra la de enero de 2027; la de 2028 no |
| Edición | Es la última que gastó número más una por cada año intermedio que se espera. Una edición cancelada no gasta número: en la Feria, la 65 se canceló en 2021 y se hizo en 2022. En las fiestas va en el nombre, con el mismo estilo (romano, arábigo o «N años», que cuenta años) |
| Fecha de fin | Inicio + la mediana de la duración de los años confirmados. Vacía si no se conoce ninguna |

## La Feria de Manizales, verificada a mano

Años con fecha confirmada en el CSV: 2020-01-04, 2022-01-02, 2023-01-02, 2024-01-05, 2025-01-04 y **2026-01-03**
(2021 se canceló). La prensa confirma 2024 (5-14 ene), 2025 (4-12 ene) y 2026 (3-11 ene): radionacional.co,
larepublica.co y colombia.com.

Regla elegida: **primer sábado de enero; si cae en festivo (el 1-ene), al día siguiente.**
- Dentro de muestra: **4/6 exactos**. Falla 2023 por +5 días (empezó el lunes 2) y 2024 por +1 (empezó el viernes 5).
- Dejando uno fuera: **3/6 exactos, desvío medio 1,2 días**. Confianza media.
- Sin el ajuste del festivo, la regla acierta 3/6 y en 2028 daría el 1-ene. En 2022, cuando el 1-ene cayó en sábado,
  la Feria empezó el domingo 2.

Proyección: **edición 70, del 2027-01-02 al 2027-01-10**, y edición 71, del 2028-01-02 al 2028-01-10.
`fut_m_feria_d0_4` queda en 1 del 2 al 6 de enero de 2027.

**No se confirma la fecha desde la web.** El 2026-10-15 no había anuncio oficial de la edición 70. Además, la
programación se publica en portales distintos cada año (Alcaldía, Instituto de Cultura y Turismo, prensa), sin un
formato estable. Raspar eso daría una «confirmación» frágil, y es preferible estimar y avisar. La fila queda en la
lista por confirmar con la fuente donde mirarla.

## Las reglas y su acierto medido (corte 2026-10-15)

### Eventos de Manizales

| Serie | Periodicidad | Regla elegida | Dentro de muestra | Dejando uno fuera | Confianza |
|---|---|---|---|---|---|
| Feria de Manizales | anual | primer sabado de enero; si cae en festivo, al dia siguiente | 4/6 anios exactos; fallos: 2023 +5 d, 2024 +1 d | 3/6 exactos; desvio medio 1.2 d | media |
| Temporada Taurina | anual | primer lunes desde el 2 de enero | 4/6 anios exactos; fallos: 2020 +2 d, 2025 +1 d | 3/6 exactos; desvio medio 1.7 d | media |
| Reinado Internacional del Cafe | anual | primer sabado desde el 7 de enero | 4/5 anios exactos; fallos: 2025 -1 d | 2/5 exactos; desvio medio 3.0 d | media |
| Festival Internacional de Teatro de Manizales | anual | primer viernes desde el 24 de septiembre | 1/4 anios exactos; fallos: 2022 -3 d, 2023 -21 d, 2024 +25 d | 0/4 exactos; desvio medio 19.0 d | baja |
| Aniversario de Manizales | anual | 5 dias antes del festivo Día de la Raza (fecha trasladada) | 3/5 anios exactos; fallos: 2021 +2 d, 2023 -1 d | 3/5 exactos; desvio medio 0.6 d | media |
| Grita Fest | anual | primer sabado desde el 11 de octubre | 2/5 anios exactos; fallos: 2024 +1 d, 2025 +1 d, 2026 -14 d | 0/5 exactos; desvio medio 5.0 d | baja |
| Feria del Libro de Manizales | anual | primer lunes desde el 26 de agosto | 2/4 anios exactos; fallos: 2022 +13 d, 2023 +2 d | 0/4 exactos; desvio medio 5.8 d | baja |
| Festival Internacional de Musica CiMa | anual | 7 dias despues del festivo La Asunción (fecha trasladada) | 2/3 anios exactos; fallos: 2024 -14 d | 2/3 exactos; desvio medio 4.7 d | alta |
| Semana Santa | anual | 7 dias antes del Domingo de Pascua | 7/7 anios exactos | 7/7 exactos; desvio medio 0.0 d | alta |
| Fiesta Virgen del Carmen | anual | cada anio el 16 de julio | 7/7 anios exactos | 7/7 exactos; desvio medio 0.0 d | alta |
| Dia de las Velitas | anual | cada anio el 7 de diciembre | 6/6 anios exactos | 6/6 exactos; desvio medio 0.0 d | alta |
| Novenas de Aguinaldos | anual | cada anio el 16 de diciembre | 6/6 anios exactos | 6/6 exactos; desvio medio 0.0 d | alta |
| Marcha del Orgullo LGBTIQ+ | anual | 5 dias despues del festivo San Pedro y San Pablo (fecha trasladada) | 3/3 anios exactos | 3/3 exactos; desvio medio 0.0 d | alta |
| Media Maraton de Manizales | anual | primer domingo desde el 27 de noviembre | 3/4 anios exactos; fallos: 2023 -7 d | 3/4 exactos; desvio medio 3.5 d | alta |
| Alumbrado Navideno Aguinaldo Manizaleno | anual | cada anio el 1 de diciembre | 2/3 anios exactos; fallos: 2024 -2 d | 1/3 exactos; desvio medio 1.7 d | media |

### Fiestas de Caldas

| Serie | Municipio | Periodicidad | Regla elegida | Dentro de muestra | Dejando uno fuera | Confianza |
|---|---|---|---|---|---|---|
| Feria Nacional de la Horticultura | Villamaría | anual | cada anio el 27 de junio | 1/2 anios exactos; fallos: 2023 -1 d | 0/2 exactos; desvio medio 1.0 d | media |
| Festival de Música Colombiana Campo Elías Vargas Duque | Villamaría | anual | cada anio el 14 de noviembre | 2/4 anios exactos; fallos: 2021 +16 d, 2022 +11 d | 0/4 exactos; desvio medio 10.5 d | baja |
| Fiestas Aniversarias | Villamaría | anual | cada anio el 17 de octubre; si cae en festivo, al dia siguiente | 1/2 anios exactos; fallos: 2022 -1 d | 0/2 exactos; desvio medio 2.0 d | media |
| Fiestas de la Arriería vereda Pueblo Rico | Neira | anual | 3 dias antes del festivo Día de la Raza (fecha trasladada) | 2/2 anios exactos | 0/2 exactos; desvio medio 3.0 d | media |
| Carnavales del Café | Chinchiná | anual | 6 dias antes del festivo Día de la Raza (fecha trasladada) | 2/4 anios exactos; fallos: 2023 -24 d, 2024 -47 d | 0/4 exactos; desvio medio 31.5 d | baja |
| Fiestas aniversarias / del Recuerdo / del Regreso | Palestina | anual | 3 dias antes del festivo Independencia de Cartagena (fecha trasladada) | 2/4 anios exactos; fallos: 2023 +28 d, 2024 +21 d | 0/4 exactos; desvio medio 26.2 d | baja |
| Juegos Deportivos y Fiestas Regionales | Filadelfia | anual | segundo sabado de agosto | 2/5 anios exactos; fallos: 2022 +3 d, 2024 -3 d, 2025 +1 d | 0/5 exactos; desvio medio 2.4 d | media |
| Fiesta de la Cabuya y del Paisaje Cultural Cafetero | Aranzazu | anual | 9 dias antes del festivo Día de la Raza (fecha trasladada) | 3/4 anios exactos; fallos: 2026 -2 d | 2/4 exactos; desvio medio 1.2 d | media |
| Fiestas del Paisaje | Belalcázar | pares | 7 dias antes del festivo Día de Todos los Santos (fecha trasladada) | 1/2 anios exactos; fallos: 2024 +1 d | 0/2 exactos; desvio medio 4.0 d | baja |
| Fiestas de Mitos y Leyendas | San José | pares | 5 dias antes del festivo Día de la Raza (fecha trasladada) | 1/2 anios exactos; fallos: 2022 +1 d | 0/2 exactos; desvio medio 2.0 d | media |
| Fiestas de San Pedro | Anserma | anual | cada anio el 27 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Fiestas del Regreso | Anserma | pares | 4 dias antes del festivo La Asunción (fecha trasladada) | 1/3 anios exactos; fallos: 2022 +1 d, 2026 -55 d | 0/3 exactos; desvio medio 37.3 d | baja |
| Fiestas del Saman y el Ecoturismo | Viterbo | anual | primer viernes desde el 24 de junio | 3/4 anios exactos; fallos: 2026 +19 d | 1/4 exactos; desvio medio 8.2 d | baja |
| Exposición Equina | Salamina | anual | cada anio el 27 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Noche del Fuego | Salamina | anual | cada anio el 7 de diciembre | 4/5 anios exactos; fallos: 2021 +4 d | 4/5 exactos; desvio medio 0.8 d | alta |
| Feria de la Colacion | Supía | pares | 4 dias antes del festivo San Pedro y San Pablo (fecha trasladada) | 2/3 anios exactos; fallos: 2024 +1 d | 1/3 exactos; desvio medio 2.0 d | media |
| Festival de Musica Colombiana | Supía | anual | cada anio el 14 de noviembre | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Pregon de la Feria de la Colacion | Supía | impares | cada anio el 29 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Fiestas de San Juan Bautista | Marmato | anual | 11 dias antes del festivo San Pedro y San Pablo (fecha trasladada) | 1/2 anios exactos; fallos: 2023 -43 d | 0/2 exactos; desvio medio 46.0 d | baja |
| Fiestas de San Antonio de Padua | Marmato | anual | cada anio el 4 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Fiestas del Barequero | Marmato | anual | segundo martes de octubre | 1/3 anios exactos; fallos: 2021 +1 d, 2025 -14 d | 0/3 exactos; desvio medio 11.3 d | baja |
| Carnaval de Riosucio | Riosucio | impares | 3 dias antes del festivo Día de los Reyes Magos (fecha trasladada) | 2/2 anios exactos | 0/2 exactos; desvio medio 3.0 d | media |
| Encuentro de la Palabra | Riosucio | anual | 4 dias antes del festivo La Asunción (fecha trasladada) | 4/4 anios exactos | 4/4 exactos; desvio medio 0.0 d | alta |
| Primer Gran Decreto del Carnaval de Riosucio | Riosucio | pares | cada anio el 17 de agosto | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Encuentro de Parapentismo | La Merced | anual | cada anio el 21 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Fiestas de la Municipalización | La Merced | anual | 3 dias despues del festivo Corpus Christi (fecha trasladada) | 2/3 anios exactos; fallos: 2025 -1 d | 2/3 exactos; desvio medio 0.3 d | alta |
| Cumpleaños del municipio y pregón Fiestas del Agua | Pácora | anual | cada anio el 11 de octubre | 1/2 anios exactos; fallos: 2023 -1 d | 0/2 exactos; desvio medio 1.0 d | media |
| Fiestas del Agua | Pácora | pares | 3 dias antes del festivo Día de la Raza (fecha trasladada) | 2/3 anios exactos; fallos: 2022 +1 d | 2/3 exactos; desvio medio 0.3 d | alta |
| Día del Manzanareño y Encuentro de Arriería | Manzanares | pares | cada anio el 27 de junio | 1/1 anios exactos | sin medir (menos de 2 anios) | sin medir |
| Fiestas de la Cordialidad | Manzanares | impares | 3 dias despues del festivo Corpus Christi (fecha trasladada) | 2/2 anios exactos | 0/2 exactos; desvio medio 11.0 d | baja |
| Fiestas de la Cordillera | Marquetalia | pares | cada anio el 8 de octubre | 1/2 anios exactos; fallos: 2024 -1 d | 0/2 exactos; desvio medio 1.0 d | media |
| Festival Nacional del Pasillo Colombiano | Aguadas | anual | 3 dias antes del festivo La Asunción (fecha trasladada) | 4/4 anios exactos | 4/4 exactos; desvio medio 0.0 d | alta |
| Fiestas del Hacha | Pensilvania | pares | primer martes desde el 24 de octubre | 1/3 anios exactos; fallos: 2022 +17 d, 2024 -2 d | 0/3 exactos; desvio medio 20.7 d | baja |
| Ferias y Fiestas de la Ceiba | Victoria | anual | 4 dias antes del festivo San Pedro y San Pablo (fecha trasladada) | 4/4 anios exactos | 4/4 exactos; desvio medio 0.0 d | alta |
| Festival de los Palenques | Samaná | anual | 3 dias antes del festivo La Asunción (fecha trasladada) | 5/5 anios exactos | 5/5 exactos; desvio medio 0.0 d | alta |
| Carnaval del Rio y el Sol | La Dorada | anual | 4 dias antes del festivo Día de la Raza (fecha trasladada) | 1/2 anios exactos; fallos: 2025 +6 d | 0/2 exactos; desvio medio 7.0 d | baja |
| Fiestas del Aguacate y el Turismo | Norcasia | anual | 4 dias antes del festivo Corpus Christi (fecha trasladada) | 2/5 anios exactos; fallos: 2022 -7 d, 2023 -1 d, 2024 -8 d | 0/5 exactos; desvio medio 7.4 d | baja |

Lectura de las reglas:
- **Las fiestas atadas a un puente festivo se predicen bien**, con 4/4 o 5/5 exactos también dejando uno fuera:
  Palenques, Pasillo, Ceiba y Encuentro de la Palabra. También las de fecha fija: Velitas, Novenas, Virgen del Carmen
  y Noche del Fuego.
- **Fallan las que se mueven por agenda o presupuesto**: Teatro, Feria del Libro, Grita, Carnavales del Café,
  Palestina, Hacha y Aguacate, con desvíos de 5 a 30 días dejando uno fuera.
- Con 2 años, «2/2 dentro de muestra» no dice nada: con una sola observación, cualquier regla encaja. Por eso manda
  la columna «dejando uno fuera».
- Algunas reglas son coincidencias que valen mientras se midan. La Marcha del Orgullo sale como «5 días después de
  San Pedro» y no como «primer sábado desde el 4 de julio»; las dos aciertan 3/3 y dan la misma fecha en 2027.

## Resultado de la primera corrida (2026-10-15)

| | Eventos | Fiestas |
|---|---|---|
| Filas agregadas | **32**: 3 de 2026 (Velitas, Novenas, Alumbrado), 15 de 2027 y 14 de 2028 | **50**: 1 de 2026 (Campo Elías Vargas, nov), 22 de 2027 y 27 de 2028 |
| De ellas, a 60 km o más (entran en `fut_m_fiesta_lejana`) | — | 33: 14 de 2027 y 19 de 2028 |

Comprobación con `mecanismos.columnas(2026-01-01 … 2027-12-31)`:
- `fut_m_feria_d0_4` pasa a tener 5 días en enero de 2027;
- `fut_m_fiesta_lejana` pasa de 0 a 66 días en 2027 (ene 9, may 5, jun 17, jul 8, ago 8, oct 14, dic 5);
- de 2026 no cambia ni un día.

`notebooks/pronostico.py:contexto` corta su índice en `FIN + H`, con `FIN = 2026-09-20`. Por eso sus columnas
`fut_ev_*` y `fut_fiestas_*` todavía no llegan a 2027. No es un problema de estos calendarios.

## La lista por confirmar

Archivo: `salidas/contexto/por_confirmar_eventos.csv`.

**Columnas:**
- `calendario`, `evento`, `municipio`, `anio`, `fecha_estimada`, `fecha_fin_estimada`;
- `tipo`;
- `regla`, `acierto_historico` (dentro de muestra), `acierto_dejando_uno_fuera`, `confianza`;
- `aviso`;
- `fuente_confirmar`: la última URL conocida de la serie.

**Tipos:**

| Tipo | Qué pide |
|---|---|
| `anadida_auto` | Confirmar o corregir la fila estimada. Si una corrida posterior da otra fecha, `aviso` lo dice |
| `fila_existente_sin_estado` | La fila de 2026 existe con `estado` vacío y el modelo la ignora. **El script no la completa: es una fila escrita a mano** |
| `fila_existente_sin_fecha` | La fila tiene estado realizado, programado o aplazado, pero no tiene fecha (Encuentro de la Palabra 2026, aplazado) |
| `falta_pasada` | Una edición de este año sin fila y con la fecha ya pasada: se completa a mano |
| `no_proyectada` | Series irregulares, de periodicidad desconocida, de un solo año (con fecha sugerida), sin filas recientes, o la taurina de 2028 |

Al 2026-10-15 la lista tiene 82 `anadida_auto`, 16 `no_proyectada`, 8 `fila_existente_sin_estado`, 5
`falta_pasada` y 1 `fila_existente_sin_fecha`.

Las 8 filas sin estado son de 2026: Chinchiná, San José, La Dorada, Barequero, Belalcázar, Palestina, Noche del
Fuego y La Merced. Las de Barequero (90 km), **Belalcázar (67 km, 26-oct a 2-nov estimado)** y **Noche del Fuego
(77 km, 7-8 dic)** caen en el futuro y a 60 km o más. Mientras nadie les ponga `estado`, `fut_m_fiesta_lejana` no
las ve.

**Avisos que van en la lista:**
- «declarada anual, pero solo hay fechas cada dos años»: Arriería, Barequero, San Juan Bautista y cumpleaños de
  Pácora;
- «la última edición se canceló»: Horticultura 2026 y Palenques 2026, por el sismo.

## Límites

- **Reglas sobre pocos años.** La mitad de las series de fiestas tiene 2-3 años confirmados. Su «confianza»
  ordena la revisión, pero no es una probabilidad. Las de confianza `baja` pueden poner la fiesta en la semana
  equivocada; en las proyectadas de 2027 a 60 km o más, el desvío medio dejando uno fuera llega a 8-46 días
  (Samán, Barequero, San Juan Bautista).
- **Las ediciones fuera de lo común entran al ajuste como fallos.** Por ejemplo, las Fiestas del Regreso de Anserma
  2026, movidas a octubre por el sismo, figuran como `programado` confirmado. Solo se excluyen los años que
  `mes_tipico` declara.
- **Los alias de nombre están escritos a mano** (`ALIAS` en cada script). Si una fiesta cambia de nombre, aparece
  como una serie nueva hasta que se agregue el alias.
- **La periodicidad declarada manda.** Si una fiesta «anual» se hace en realidad cada dos años, se proyectan los
  dos años; el aviso de la lista lo señala.
- **El horizonte depende de `calendario_Colombia.csv`.** Llega a 2030. Más allá, el script falla a propósito en vez
  de proyectar sin festivos.
- **Las filas estimadas no se reestiman.** Si llegan años confirmados nuevos y la regla cambia, la fila
  `estimada_auto` antigua se queda como está, porque es una fila existente. La lista por confirmar avisa de la
  diferencia.
- **No hay confirmación automática desde la web** (ver la sección de la Feria).
