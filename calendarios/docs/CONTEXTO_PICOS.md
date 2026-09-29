# Contexto oficial de los picos (diciembre, enero, mitad de año) — informe de investigación (2026-09-29)

> Copia del informe del agente, con la sección 1bis sobre el calendario de fiestas completado. [V] = abierto y leído; [B] = solo visto en el buscador; [I] = inferido. Qué se decidió con esto está en `docs/CONTEXTO.md`, entrada del 29-09.

# Contexto oficial de los picos de triage (SES HUC, Manizales) — informe de investigación

Iniciado 2026-09-29. [V] = abierto y leído; [I] = inferido; [B] = solo visto en resultado de buscador (título/extracto), sin abrir.

## Bitácora
- Inicio. Estructura creada.

## 1. Fiestas de Caldas 2020-2026
(pendiente)

## 2. Diciembre y enero
(pendiente)

## 3. Mitad de año
(pendiente)

## 4. Remisiones
(pendiente)

---
## 2. Diciembre y enero — notas de trabajo (se consolidan al final)

### 2.0 Lo que ya hay en el repositorio (SIVIGILA evento 452, lesiones por artefactos explosivos)
[V] `calendarios/vigilancia_sivigila_eventos.csv.gz`, evento 452, suma de semanas epidemiológicas 48 a 2 (temporada):
| Temporada | Caldas (ocurrencia) | Manizales (ocurrencia) |
|---|---|---|
| 2019-20 | 38 | 13 |
| 2020-21 | 24 | 8 |
| 2021-22 | 33 | 8 |
| 2022-23 | 28 | 4 |
| 2023-24 | 47 | 17 |
| 2024-25 | 42 | 21 |
| 2025-26 | 51 (solo hasta SE53-2025; faltan SE1-2 de 2026) | 17 |
Semana pico siempre la que contiene el 31-dic/1-ene, y la segunda la de velitas (SE49/50). [V] cálculo propio con awk.
Nota: el evento 452 incluye minas antipersonal; en Caldas es casi todo pólvora [I].

### 2.1 Quemados por pólvora — balances oficiales
- [V] Temporada 2023-24. DTSC, publicado 11-dic-2023: acumulado 13 casos en 2023; 8 nuevos el fin de semana de velitas; 11 hombres, 2 mujeres, 5 niños, 2 hospitalizados; municipios Marmato, La Dorada, Palestina, Manizales, Chinchiná; «incremento del 75 % comparado con el año anterior». https://saluddecaldas.gov.co/publicaciones/4247/el-fin-de-semana-de-velitas-deja-8-nuevos-casos-de-quemados-con-polvora-en-el-departamento-de-caldas/
- [V] Temporada 2023-24. DTSC, publicado 02-ene-2024: 44 casos en Caldas, 11 menores; entre 31-dic y 1-ene 17 quemados, 14 el 1 de enero; Manizales 3 casos el 1 de enero; 50 % en estado de alicoramiento; 13 hospitalizados; «incremento del 50 % comparado con el año anterior». Municipios: Manizales, La Dorada, Manzanares, Neira, Chinchiná, Anserma, Villamaría, Marmato, Palestina. https://saluddecaldas.gov.co/publicaciones/4266/en-el-fin-de-ano-aumentan-los-casos-de-quemados-con-polvora-en-el-departamento-de-caldas/
- [V] Temporada 2024-25. Gobernación de Caldas, publicado 13-ene-2025: 37 lesionados, 6 menores; Manizales 15, Riosucio 4, La Dorada 3, Chinchiná 3, Palestina 2, Samaná 2, Aguadas/Anserma/Filadelfia/La Merced/Marquetalia/Neira/Norcasia/Viterbo 1 c/u; ~50 % primer grado, 42 % segundo; artefacto con más lesiones: el «tote». https://caldas.gov.co/noticias-gobernacion/14909-a-37-asciende-el-numero-de-casos-de-personas-quemadas-con-polvora-en-caldas-6-son-menores-de-edad
- [V] Temporada 2024-25. DTSC (fecha mostrada 01-feb-2025, probablemente 01/02 = 1-ene... ver nota): 33 casos acumulados; 31-dic 11 casos, 1-ene 1, 2-ene 1; Manizales ~50 % (15); La Dorada y Riosucio 3 c/u; 13 casos en las fechas de fin de año vs 20 el año anterior (−30 %); 2 hospitalizados. https://saluddecaldas.gov.co/publicaciones/4834/el-departamento-de-caldas-registra-33-casos-de-quemados-por-polvora/
  - [I] La fecha «01/02/2025» es ambigua (formato dd/mm o mm/dd); por contenido (casos del 2-ene) es de comienzos de enero de 2025.
  - Inconsistencia: el cierre de la Gobernación (13-ene-2025) dice 37; La Patria 1-ene-2026 dice que a la misma fecha del año anterior había 35. [V]
- [V] Temporada 2025-26. La Patria (fuente DTSC), 1-ene-2026: 40 lesionados entre 1-dic-2025 y 1-ene-2026, +14 % frente a 35 del mismo periodo 2024-25; 10 casos nuevos reportados el 1 de enero; menores desde los 6 años (caso de La Dorada; adolescente de 17 en Chinchiná). https://www.lapatria.com/salud/caldas-inicia-el-2026-con-aumento-de-quemados-por-polvora-ya-van-40-lesionados-5-mas-que-el
- [V] Temporada 2021-22. La Patria (fuente DTSC e INS), 3-ene-2022: 32 lesionados en Caldas; 11 entre 31-dic y madrugada del 1-ene, 3 de ellos menores; Manizales 8, La Dorada 6, Salamina 3, Riosucio/Manzanares/Villamaría/Pácora 2 c/u, Neira/Supía/Chinchiná/Victoria/Viterbo/Pensilvania 1 c/u. https://archivo.lapatria.com/salud/32-quemados-por-polvora-suma-caldas-485344
- [V] Temporadas 2018-19 a 2021-22. La Patria (fuente DTSC), 5-ene-2022, «1 de enero, el coco mayor»: temporada 2020-21 = 24 casos en Caldas; 2021-22 = 32 casos; en las tres últimas temporadas, 20 lesionados el 1 de enero y 9 el 31 de diciembre; 1-ene-2019: 8 casos; 1-ene-2020: 6 casos; Manizales 9 casos en 2021-22 (vs 8 la anterior) [nota: el artículo del 3-ene decía 8]. https://archivo.lapatria.com/informe-especial/1-de-enero-el-coco-mayor-con-la-polvora-en-caldas-485445
- [B] Temporada 2022-23: 28 casos en Caldas (a 12-ene-2023, boletín INS). Solo visto en extracto de buscador; coincide con SIVIGILA del repo (28). No abrí un balance DTSC de esa temporada.
- [V] Temporada 2024-25. BC Noticias (fuente DTSC, Carolina Castañeda Gómez), 15-ene-2025: periodo 1-dic-2024 a 11-ene-2025: 37 lesionados frente a 47 en 2023-24 (−21,7 %); menores de 11 a 5 (−54,8 %); 91 % primer y segundo grado; 2 amputaciones; 1 lesión visual; 4 hospitalizados. https://www.bcnoticias.com.co/caldas-reduce-en-un-21-7-los-casos-de-lesiones-por-polvora-durante-la-temporada-decembrina/
  - Inconsistencia de menores 2024-25: Gobernación dice 6, DTSC vía BC dice 5. Y el cierre 2023-24 fue 47 (el 2-ene-2024 iban 44).
- [V] Temporada 2025-26. BC Noticias (fuente DTSC), 1-ene-2026: 40 casos, 13 menores y 27 adultos; los 10 nuevos del 1-ene: Marmato 3, Manizales 2, La Dorada 2, Risaralda 1, Chinchiná 1, Aranzazu 1; 6 hospitalizados; sin muertes; voladores y tacos. https://www.bcnoticias.com.co/caldas-reporta-10-nuevos-quemados-por-polvora-y-suma-40-casos-en-2026/
- No encontré el cierre final DTSC 2025-26 (mediados de enero de 2026).

Manizales (Secretaría de Salud Pública / Alcaldía):
- [V] 2023-24 y 2024-25: 16 casos cada una; 2024-25: 15 adultos, 1 menor de 15 años, 1 amputación de dedos; fechas de mayor incidencia: 1-dic, 24, 25, 31-dic y 1-ene; comunas San José, Ciudadela del Norte, Cumanday. La Patria, 17-ene-2025, fuente secretario de Salud David Gómez. https://www.lapatria.com/salud/manizales-cerro-el-2024-con-16-quemados-con-polvora-la-misma-cifra-que-en-2023
- [V] Velitas 2024: cero menores quemados en Manizales, 1 adulto (40 años, leve); >3.600 elementos de pólvora incautados; 19 capturados; 1.201 requerimientos atendidos; homicidios acumulados 2024: 24 vs 30 en 2023 a la misma fecha. Alcaldía, 9-dic-2024. https://centrodeinformacion.manizales.gov.co/en-el-fin-de-semana-de-las-velitas-manizales-no-registro-menores-de-edad-quemados-por-polvora/
- [V] 29-nov-2024: explosión en el barrio Los Alcázares, 4 lesionados y 1 fallecido; 1-dic-2024 primer lesionado de diciembre (47 años, alicorado, papeleta). La Patria, 1-dic-2024. https://www.lapatria.com/salud/quemado-con-polvora-de-manizales-llama-la-atencion-de-david-gomez-secretario-de-salud
- [V] 2025-26 parcial: 6 casos entre 1 y 16-dic-2025 (5 adultos, 1 menor de 16), 2 asociados a alcohol, sin amputaciones. Eje21, 16-dic-2025, fuente Secretaría de Salud. https://www.eje21.com.co/2025/12/lesiones-por-polvora-en-manizales-se-mantienen-estables-durante-diciembre/
- [V] 2025-26 cierre: 12 casos entre 1-dic-2025 y 17-ene-2026; 3 menores, 9 adultos; 5 bajo efecto de alcohol; 50 % primer grado, 50 % segundo; 67 % hombres; 43 comparendos; 2.261 unidades incautadas. Alcaldía de Manizales (fecha mostrada «enero 1, 2026», incompatible con el periodo al 17-ene: la fecha real de publicación es posterior [I]). https://centrodeinformacion.manizales.gov.co/reportan-dos-nuevos-casos-de-quemaduras-por-polvora-en-la-ciudad/
- Nota de fuente: la cifra municipal (12) es menor que la de SIVIGILA-Manizales por ocurrencia en SE48-53 (17). Distintos cortes y reglas de asignación; no comparar sin decirlo [I].

### 2.2 Riñas, lesiones y homicidios en diciembre y Año Nuevo
No hay un balance oficial consolidado de Año Nuevo para Manizales que haya podido abrir. Lo que sí:
- [V] Velitas 2025 (vie 5 a lun 8-dic-2025), Alcaldía de Manizales, 9-dic-2025: 12 capturas; 43 comparendos por pólvora; 2.261 unidades incautadas; 4 lesionados por pólvora; 98 armas cortopunzantes; 220 comparendos; 44 traslados al Centro Transitorio; 3 adolescentes. No da riñas ni llamadas 123. https://centrodeinformacion.manizales.gov.co/balance-de-seguridad-de-fin-de-semana-de-velitas-en-manizales/
- [V] Velitas 2024 (fin de semana), Alcaldía, 9-dic-2024: 1.201 requerimientos atendidos, >3.600 elementos de pólvora incautados, 19 capturas, 0 menores quemados; homicidios del año 24 vs 30 en 2023. https://centrodeinformacion.manizales.gov.co/en-el-fin-de-semana-de-las-velitas-manizales-no-registro-menores-de-edad-quemados-por-polvora/
  - [B] Extracto de buscador (misma temporada, no confirmado en el texto abierto): 115 llamadas por riñas, 236 por perturbación, 49 por violencia intrafamiliar; homicidio durante la Noche de Velitas 2024 con intervención policial (Pulzo).
- [V] Semana Santa 2025 (para escala), Policía Nacional, 21-abr-2025: 2.541 llamadas 123, 237 por riñas, 331 por alteración a la tranquilidad; lesiones personales −30 % vs 2024; sin homicidios. https://www.policia.gov.co/noticia/balance-seguridad-en-manizales
- [B] Tintiando (medio local), 25-dic-2021: «Balance policial de la noche de Navidad en Manizales y Villamaría» — no abierto. https://www.tintiando.com/2021/12/25/balance-policial-de-la-noche-de-navidad-en-manizales-y-villamaria/

**Serie oficial diaria que ya está en el repo** — MinDefensa/Policía (datos.gov.co), Manizales, `calendarios/seguridad_mindefensa.csv.gz` [V], cálculo propio [V]. Lesiones personales (LP) y homicidios (H) denunciados por día:
| Temporada | 7-dic LP,H | 8-dic | 24-dic | 25-dic | 31-dic | 1-ene | LP dic | H dic | LP ene | H ene |
|---|---|---|---|---|---|---|---|---|---|---|
| 2019-20 | 3,1 | 7,2 | 3,0 | 14,1 | 0,0 | 13,0 | 129 | 5 | 108 | 6 |
| 2020-21 | 2,0 | 2,1 | 2,1 | 5,0 | 3,0 | 6,0 | 66 | 4 | 57 | 4 |
| 2021-22 | 4,0 | 3,0 | 6,0 | 10,0 | 2,0 | 7,0 | 97 | 2 | 73 | 1 |
| 2022-23 | 4,0 | 2,0 | 1,0 | 5,0 | 0,1 | 8,0 | 49 | 2 | 70 | 0 |
| 2023-24 | 3,0 | 3,1 | 4,0 | 3,1 | 0,2 | 9,0 | 68 | 7 | 57 | 1 |
| 2024-25 | 2,1 | 6,0 | 1,0 | 2,0 | 1,0 | 4,0 | 46 | 4 | 40 | 4 |
| 2025-26 | 8,0 | 9,0 | 1,0 | 2,1 | 0,1 | 3,0 | 46 | 6 | 45 | 1 |
Media diaria de LP: 2019 4,16 · 2020 2,43 · 2021 2,38 · 2022 1,89 · 2023 1,95 · 2024 1,50 · 2025 1,37. Media mensual de LP 2019-12 a 2026-08: diciembre 71,6 (el mes más alto), enero 64,3, febrero 65,0; junio 48,0 (el más bajo), julio 54,1.
Lectura [I]: el 1-ene y el 25-dic multiplican por 2-5 la media diaria de lesiones personales; el 31-dic casi no (la lesión se denuncia con fecha de la madrugada del 1). Velitas 2025 (7-8-dic: 8 y 9) fue el pico del periodo reciente. Denuncia ≠ atención en urgencias. La serie cae a un tercio entre 2019 y 2025 (igual que la tendencia del triage no es comparable sin controlar).

### 2.3 Intoxicaciones por alcohol o metanol
- [V] Manizales, Navidad 2022: 84 establecimientos inspeccionados; «NO se ha detectado ninguna botella de licor adulterado y tampoco se ha contabilizado ningún caso de intoxicación por metanol». Contexto nacional: alerta por 33 intoxicados, 19 fallecidos. Alcaldía, 26-dic-2022. https://centrodeinformacion.manizales.gov.co/secretaria-de-salud-confirma-que-en-manizales-no-se-ha-detectado-circulacion-de-licor-adulterado/
- [B] DTSC: advertencia sobre licor adulterado y de contrabando en festividades (publicación 4260, sin fecha vista). https://saluddecaldas.gov.co/publicaciones/4260/direccion-territorial-de-salud-de-caldas-advierte-sobre-los-riesgos-del-consumo-de-licor-adulterado-y-de-contrabando-durante-las-festividades/
- [V] Repo: SIVIGILA evento 380 (metanol) en Caldas: 1, 4, 2, 1, 8, 3, 0, 1, 0, 0, 1 casos/año 2015-2025 → «volumen insuficiente» (`vigilancia_sivigila_eventos_censo.csv`). La intoxicación etílica aguda **no es evento de notificación obligatoria** en SIVIGILA [I, conocimiento general]; no hay serie oficial pública.
- Alcohol como factor: DTSC 2-ene-2024, 50 % de los quemados alicorados [V]; Manizales 2025-26, 5 de 12 quemados bajo efecto de alcohol [V].

### 2.4 Alertas hospitalarias
- [V] **Feria de Manizales (año no impreso; por el número de noticia 15945 > 14909 de ene-2025, es la Feria 2026 [I])**: DTSC monitorea con el CRUE; ocupación hospitalaria 76 % en el departamento y **92 % en Manizales**; pide uso racional de urgencias. No declara alerta con color. Diana Pilar Perdomo, subdirectora de Prestación de Servicios y Aseguramiento DTSC. https://caldas.gov.co/15945-territorial-de-salud-de-caldas-monitorea-la-capacidad-hospitalaria-de-la-region-durante-la-feria-de-manizales-e-invita-al-uso-racional-de-las-urgencias
- [V] **Julio de 2025 — alerta hospitalaria en Manizales** por la Secretaría de Salud (David Gómez): urgencias hasta **200 % de ocupación en días punta, frente a 60-80 % habitual**; causa: morosidad de EPS y falta de medicamentos; Oficio 045 del 24-jul-2025 al MinSalud. Consultorsalud, 24-jul-2025 https://consultorsalud.com/manizales-alerta-hospitalaria-morosidad-giros/ ; Infobae, 23-jul-2025 (ocupación >100 % en varios centros) https://www.infobae.com/colombia/2025/07/23/se-declara-alerta-hospitalaria-en-manizales-ante-colapso-en-la-red-de-urgencias/
  - **Relevante para «mitad de año»**: es una alerta a mitad de año, pero por causa de oferta (EPS), no de demanda festiva [I].
- [V] Abril de 2026: la alerta hospitalaria **sigue**; causa, incumplimiento de pagos de **Nueva EPS**; marco Decreto 0642 de 2019. Alcaldía, 15-abr-2026. https://centrodeinformacion.manizales.gov.co/sigue-alerta-hospitalaria-ante-crisis-del-sistema-de-salud-y-riesgo-en-la-prestacion-de-servicios-por-deudas-de-la-nueva-eps/ — conecta con el hallazgo del cuaderno 07 (caída del triage = Nueva EPS).
- [B] «Declaran alerta roja hospitalaria en Manizales» (La Silla Vacía, RCN, BC Noticias): no pude abrir; fecha desconocida. BC devolvió 404.
- [V] DTSC alerta amarilla hospitalaria departamental por **frente frío y lluvias atípicas**, publicada 18-feb-2026. https://saluddecaldas.gov.co/publicaciones/5378/caldas-en-alerta-amarilla-hospitalaria-ante-fenomeno-de-frente-frio/
- [V] DTSC alerta amarilla hospitalaria por **paro de transportadores**, publicada 05-sep-2024. https://saluddecaldas.gov.co/publicaciones/4569/dtsc-activa-alerta-amarilla-hospitalaria-en-caldas-por-paro-de-transportadores-servicios-de-salud-continuan-sin-afectaciones/
- [B] Alerta amarilla en la red hospitalaria y CRUE de Manizales para el **6-8 de agosto de 2026** (extracto del buscador; ligado a medidas del 7 de agosto). No abierto.
- [V, de pasada] La Gobernación menciona una **calamidad pública por el sismo del 10 de agosto de 2026** (portada de caldas.gov.co, 28-sep-2026). No investigado; debería ir a `desastres_manizales` si no está.
- No encontré alerta hospitalaria declarada específicamente por la temporada de diciembre en Caldas (sí la hay en el Valle, p. ej.).

### 2.5 Alumbrado navideño de Manizales y Día de Velitas
| Temporada | Encendido | Fin | Fuente | Marca |
|---|---|---|---|---|
| 2020-21 | «a más tardar el 7 de diciembre» (plan de Invama, oct-2020); presupuesto recortado a $900 M; CHEC se retiró y donó $650 M a hospitales por la pandemia | desconocido | https://archivo.lapatria.com/entretenimiento/hay-cortocircuito-en-el-alumbrado-navideno-de-manizales-465915 (28-oct-2020) | [V] fecha solo prevista |
| 2021-22 | no encontrado | — | — | — |
| 2022-23 | 1-dic-2022, 6 p.m., Plaza de Bolívar (con lanzamiento de la Feria 2023); 14 puntos; ~$4.300 M | 9-ene-2023 [B, extracto de La Patria] | https://centrodeinformacion.manizales.gov.co/alcalde-y-gerente-de-chec-anuncian-que-el-alumbrado-navideno-se-encendera-el-1-de-diciembre-fecha-en-la-que-se-lanzara-la-feria-de-manizales-2023/ (21-nov-2022) | [V] encendido |
| 2023-24 | 1-dic-2023, Plaza de Bolívar, «Manizales es Colombia» | 15-ene-2024 [B, extracto] | https://centrodeinformacion.manizales.gov.co/alcaldia-de-manizales-gerente-de-chec-aguas-de-manizales-e-invama-anunciaron-alumbrado-navideno-para-este-2023-bajo-el-nombre-manizales-es-colombia/ (21-nov-2023) | [V] encendido |
| 2024-25 | 2-dic-2024 (se aplazó desde el vie 29-nov), Parque del Agua | 12-ene-2025 | https://centrodeinformacion.manizales.gov.co/manizales-encendio-el-alumbrado-navideno-2024/ (3-dic-2024); https://www.lapatria.com/manizales/el-encendido-del-alumbrado-navideno-en-manizales-cambia-de-fecha-sepa-cuando-sera (28-nov-2024) | [V] |
| 2025-26 | 1-dic-2025, 43 días | 12-ene-2026 | https://centrodeinformacion.manizales.gov.co/con-una-inversion-de-6-802-millones-alcaldia-de-manizales-chec-e-invama-iluminaran-la-ciudad-con-el-alumbrado-navideno/ (19-nov-2025) | [V] |
Nota: `eventos_manizales_2020_2026.csv` ya tiene 2023-2025 con URL genérica `https://www.manizales.gov.co`; su fecha 2024 (3-dic) no coincide con la oficial (2-dic) y la de 2023 (1-dic a 15-ene) coincide [V/B]. Encendido y alumbrado son concentraciones nocturnas en diciembre, sin balance de salud propio.
Día de Velitas: 7 de diciembre (noche del 7, víspera de la Inmaculada, 8-dic festivo) — fecha fija de calendario [I, conocimiento general]; en Manizales la fecha pico de quemados/riñas cae el 7-8 según el año (tabla 2.2).

---
## 4. Remisiones desde los municipios (CRUE Caldas)

### 4.1 Lo que SÍ existe: informes mensuales públicos de referencia y contrarreferencia del CRUE
[V] La DTSC publica en https://saluddecaldas.gov.co/documentos/338/referencia-y-contrarreferencia-caldas/ **119 archivos** (12 páginas), uno por mes con huecos, **desde enero de 2015 hasta agosto de 2026**. Nombres [V]: 2015 (ene, mar-jun, jul, ago, sep-nov, dic), 2016 (ene-mar, jun, ago…), 2017-2019 casi completos, 2020 (ene .xls, feb, mar, may, jul, oct, nov, «2020» anual), 2021 (jun-dic), 2022 (may, jul, ago y varios sin mes en el nombre: «referencia (1).pdf», «Referencia (5).pdf»…), 2023 (feb, mar, may, jun, jul, ago, sep, oct .docx, dic), 2024 (ene-dic salvo huecos; desde may-2024 en .xls), 2025 (ene-jun, sep-dic, .xls), 2026 (ene, mar-ago, .xls). Lista completa guardada en `scratchpad/picos_contexto/crue/lista.json`.
- **No pude leer su contenido**: la descarga pasa por un **reCAPTCHA v2** (formulario `validarProcess`). No lo evadí. Por tanto **no sé** si traen remisiones por municipio de origen, por institución receptora (SES HUC), por día o solo totales. [V] el bloqueo; contenido desconocido.
- También hay «Informe disponibilidad de camas» mensual (nov-2021 a jul-2022, [V] nombres) en https://saluddecaldas.gov.co/documentos/336/informe-disponibilidad-de-camas/ y un «Informe de gestión» del CRUE (solo I-semestre 2015) en https://saluddecaldas.gov.co/documentos/337/informes-de-gestion/ .
- CRUE: Resolución 1220 de 2010 (MinProtección); teléfono (606) 8817930 ext. 208; celulares 315-4134769, 310-4267906; 24 h [V] https://saluddecaldas.gov.co/publicaciones/3914/centro-regulador-de-urgencias-crue/

### 4.2 Evidencia cualitativa de la red (prensa con fuente oficial)
- [V] 1-mar-2025: urgencias del **SES HUC con sobrecarga del 200 %**; gerente Juan Felipe Valencia: «Todos los pacientes del departamento con urgencias de este tipo están llegando al SES» (fallo eléctrico en Avidanti; San Marcel sin hemodinamia; Santa Sofía sin neurología/cardiología). https://www.lapatria.com/salud/colapso-en-la-red-de-urgencias-de-manizales-hospital-de-caldas-al-200-de-ocupacion ; 2-mar-2025 https://www.lapatria.com/salud/urgencias-de-alta-complejidad-la-pasan-mal-en-manizales-colapso-de-la-red-hospitalaria
- [V] 13-may-2025: urgencias del SES HUC **>140 %** de capacidad; «más de 50 solicitudes de aceptación de pacientes en remisión» (de otras entidades y municipios); causa según Secretaría de Salud: entrega incompleta de medicamentos → descompensación → urgencias. https://www.lapatria.com/salud/manizales-capacidad-instalada-de-las-urgencias-del-ses-hospital-universitario-de-caldas
- [V] 26-jul-2025: Avidanti con 20 pacientes esperando referencia y «50 % de los pacientes no son de Manizales»; Ospedale 10 en espera; Assbasalud 8 psiquiátricos en espera; SES con zonas de expansión habilitadas. https://www.eje21.com.co/2025/07/crisis-silenciosa-en-las-urgencias-de-manizales-hospitales-colapsados-y-pacientes-en-espera/
- [V] 28-feb-2024: el SES HUC anuncia que **no atiende en urgencias a usuarios de Salud Total y Sanitas** por capacidad, tras el cierre parcial de urgencias de la Clínica Ospedale (comunicado DTSC del 27-feb-2024). https://www.bcnoticias.com.co/hospital-de-caldas-advierte-que-no-atiende-pacientes-de-salud-total-y-sanitas/ — **cambio de oferta que afecta el conteo de triage del SES desde fines de feb-2024 [I]**.
- [B] Clínica Ospedale: cierre total temporal de urgencias (Alcaldía, fecha no vista). https://centrodeinformacion.manizales.gov.co/alcaldia-de-manizales-a-traves-de-secretaria-de-salud-publica-apoya-contingencia-frente-a-cierre-total-temporal-del-servicio-de-urgencias-de-la-clinica-ospedale/
- [B] Hospital Infantil Rafael Henao Toro suspende servicios a usuarios de Nueva EPS (Consultorsalud). No abierto.

### 4.3 Qué pedir por derecho de petición (Ley 1755 de 2015; datos agregados, sin identificación)
**A la DTSC – Subdirección de Prestación de Servicios / CRUE Caldas** (y, en paralelo, **al SES HUC** para su propia serie):
1. Número de **solicitudes de remisión/referencia gestionadas por el CRUE** con destino a IPS de Manizales, **por día** (o al menos por semana epidemiológica), 2019-01-01 a la fecha, desagregado por: municipio de origen (27 municipios), IPS receptora (en particular SES Hospital Universitario de Caldas), nivel de complejidad solicitado, servicio (urgencias, UCI, hospitalización, ginecobstetricia, pediatría, salud mental), resultado (aceptada, rechazada, pendiente) y tiempo de respuesta.
2. Las mismas remisiones por **grupo de causa** (CIE-10 capítulo o gran grupo: trauma/lesiones de causa externa, quemaduras, intoxicaciones, respiratorio, obstétrico) y bandas de edad (0-4, 5-14, 15-44, 45-64, 65+).
3. Los **informes mensuales de referencia y contrarreferencia 2015-2026 en formato original** (xls) sin CAPTCHA, o autorización para descargarlos en lote.
4. **Ocupación diaria de urgencias** reportada al CRUE por IPS de Manizales (el dato que citan: 76 % dpto., 92 % Manizales en Feria; 200 % en días punta de 2025), 2020-2026.
5. **Actos administrativos de alertas hospitalarias** (color, fecha de inicio y de levantamiento, ámbito) declaradas por la DTSC y por la Secretaría de Salud de Manizales, 2020-2026, incluida la de julio de 2025 (Oficio 045 del 24-jul-2025) y la vigente en abril de 2026.
6. Lesionados por pólvora de las temporadas 2020-21 a 2025-26 **por fecha de ocurrencia, municipio de ocurrencia e IPS que atendió** (SIVIGILA 452, que la DTSC tiene nominal pero puede entregar agregado).
**A la Secretaría de Salud Pública de Manizales**: ocupación diaria de urgencias por IPS (sus «boletines» de 2025 que citan el 200 %) y la serie de alertas.
**A la Policía Metropolitana de Manizales**: llamadas 123 por día y tipo (riñas, perturbación, violencia intrafamiliar, pólvora), 2020-2026 — la serie de MinDefensa del repo solo trae delitos denunciados, no llamadas.

### 2.6 Resumen consolidado — quemados por pólvora por temporada
| Temporada | Caldas (oficial/prensa con fuente DTSC) | Menores Caldas | Manizales (Alcaldía/DTSC) | SIVIGILA repo Caldas / Manizales (SE48-2) | Fechas pico reportadas |
|---|---|---|---|---|---|
| 2020-21 | 24 [V, La Patria/DTSC] | ? | 8 [V, La Patria] | 24 / 8 | — |
| 2021-22 | 32 [V, La Patria/DTSC] | ≥3 (entre 31-dic y 1-ene) | 8 (o 9 según otra nota) [V] | 33 / 8 | 11 casos el 31-dic/1-ene (33 %) |
| 2022-23 | 28 [B, DTSC vía prensa]; ciclo 1-dic a 14-ene (decreto MinSalud 051 de 30-nov-2022) [B] | 5 de los primeros 13 [B, Semana 26-dic-2022] | ? | 28 / 4 | primeros casos en Velitas [B] |
| 2023-24 | 44 al 2-ene-2024 [V, DTSC]; cierre 47 [V, DTSC vía BC] | 11 [V] | 16 [V, SSP Manizales] | 47 / 17 | 17 entre 31-dic y 1-ene, 14 el 1-ene [V]; 8 el fin de semana de Velitas [V] |
| 2024-25 | 37 al 13-ene-2025 [V, Gobernación]; 33 a comienzos de ene [V, DTSC] | 6 [V, Gob.] o 5 [V, DTSC vía BC] | 15 (Gob.) / 16 (SSP) [V] | 42 / 21 | 31-dic 11 casos [V]; picos 1-dic, 24, 25, 31-dic, 1-ene [V] |
| 2025-26 | 40 al 1-ene-2026 (+14 % vs 35) [V, DTSC vía La Patria y BC]; cierre final no hallado | 13 [V, BC/DTSC] | 12 al 17-ene-2026 [V, Alcaldía] | 51 (sin SE1-2 de 2026) / 17 | 10 casos el 1-ene [V]; Velitas 4 lesionados en Manizales [V] |
Lectura [I]: 25-50 quemados por temporada en todo Caldas, ~40 % en Manizales. Aun si todos llegaran al SES, son ≤1-2 triages extra por día pico frente a una media de ~177: **la pólvora no mueve el conteo total por sí sola**; lo que puede moverlo es el paquete alcohol + riñas + lesiones de la misma noche, y eso tiene su serie diaria en MinDefensa (tabla 2.2).

---
## 1 y 3. Estado al cierre
- CSV escrito desde las notas parciales de los agentes (fiestas_A.md, fiestas_B.md), porque hubo que entregar antes de que terminaran. Vacaciones escolares: ver mitad_anio.md (resoluciones 2021-2026 leídas [V]).


---
## 1bis. Calendario de fiestas, versión 2 (2026-09-29, tarde)

Archivo: `calendarios/fiestas_caldas_2020_2026.csv`. La versión anterior, de 75 filas, está copiada en `picos_contexto/fiestas_v1.csv`. El script que la genera es `picos_contexto/escribir_v2.py`, que lee `fiestas_A.csv`, `fiestas_B.csv`, `fiestas_v1.csv` y `altas_v2.py`.

### Qué se hizo
- **Fusión sin duplicados** de tres fuentes:
  - `fiestas_A.csv`: 93 filas, 14 municipios cercanos.
  - `fiestas_B.csv`: 79 filas, 13 municipios.
  - La v1.
  - La clave de fusión es municipio + año + festival. Se conservan las URL y las fechas de A y B. **No se rellenó con fechas estimadas lo que A o B dejaron vacío.**
  - Filadelfia venía en las dos tablas y se sustituyó por una sola serie, verificada contra la alcaldía.
  - De la v1 solo sobrevivió una fila sin equivalente: la Exposición Equina de Salamina 2025.
- **Resultado: 177 filas de 26 municipios**, frente a 75 filas de 22 municipios.
  - Municipios nuevos: Filadelfia, Palestina, Risaralda y Marquetalia.
- **Referencias textuales: de 48 a 0.**
  - 167 filas llevan URL real.
  - 10 no llevan fuente (ver «Qué no se encontró»).
  - Cuando una fila tiene más de una fuente, las URL van separadas por ` ; `.
- **Nueva columna `marca`**, la última:
  - 130 filas V (verificado).
  - 8 filas B (solo buscador).
  - 39 filas I (inferido).
- **`calidad_fecha`**: 119 confirmadas y 58 estimadas.

### Valores válidos de `estado` (documentación)
| Valor | Significado | Filas |
|---|---|---|
| `realizado` | Se hizo en las fechas dadas | 116 |
| `cancelado` | Esa edición no se hizo. Incluye los años COVID inferidos por la numeración de ediciones (marca I) | 27 |
| `virtual` | Edición virtual o híbrida (2020) | 5 |
| **`programado`** | **Nuevo.** Edición posterior al 2026-09-29 con fechas **ya anunciadas** por una fuente | 6 |
| **`aplazado`** | **Nuevo.** Suspendida (casi todas por el sismo del 10-ago-2026) sin una nueva fecha confirmada. Si se conocen, las fechas son las **previstas**, que no llegaron a cumplirse | 4 |
| *(vacío)* | Sin dato: edición esperada que no se pudo documentar | 19 |

- Regla aplicada: una edición futura sin anuncio (marca I) pasa de `programado` a vacío.
- Las 6 filas `programado` son:
  - Aranzazu, 5-12 oct.
  - Anserma, 7-12 oct.
  - Marquetalia, 8-11 oct.
  - Pácora, 9-12 oct.
  - Villamaría, cumpleaños el 19 oct.
  - Pensilvania, 27 oct-2 nov.
- Las 4 filas `aplazado` son:
  - Aguadas, Festival del Pasillo (previsto 14-16 ago).
  - Filadelfia, Juegos (empezaron el 8-ago).
  - Riosucio, Encuentro de la Palabra.
  - Manzanares, Día del Manzanareño.
- **Aviso para modelar**: en las filas `cancelado` y `aplazado`, `fecha_inicio`/`fecha_fin` **no** son días de fiesta. Hay que filtrar por `estado`.

### Distancias por carretera desde Manizales (km)
Hay una sola cifra por municipio. La fuente preferida es la ficha de cada municipio en caldas.gov.co, en la ruta `index.php/component/content/article/74-uncategorised/gobernacion/municipios/<id>` [V].
- **[V] Ficha de la Gobernación (id entre paréntesis):**
  - Villamaría 9 (368), Neira 21 (357), Chinchiná 25 (348), Palestina 27 (360), Filadelfia 49 (349), Risaralda 54 (362).
  - San José 67 (365), Anserma 74 (346), Viterbo 76 (369), Salamina 77 (363), Supía 77 (366).
  - Riosucio 91 (361), La Merced 98 (351), Pácora 111 (359), Manzanares 117 (353), Marquetalia 124 (355).
  - Marulanda 126 (356), Aguadas 126 (345), Victoria 169 (367), La Dorada 175 (350), Norcasia 207 (358).
- **[V] PDF «infomunicipios» 2014 de la Gobernación:** Aranzazu 52 y Pensilvania 148.
- **Casos que se apartan de la Gobernación:**
  - Marmato 90 [V, viajaporcolombia]. La Gobernación dice 143, pero Marmato está junto a Supía (77).
  - Samaná 170 [V, viajaporcolombia]. La Gobernación dice 113, lo que no cuadra con la ruta por el oriente.
  - Belalcázar 67 [B, extracto del buscador]. No hay ficha en la Gobernación.
- **Cambios frente a la v1:** Neira 20→21, Supía 80→77, Anserma 82→74, Aguadas 121→126, La Dorada 170→175, Norcasia 211→207, Victoria 132→169, San José 58/66→67.

### Hallazgos nuevos
- [V] **viajaporcolombia**: la URL `noticias/x_<id>/` redirige a la ficha, así que se barrieron los id 8300-11050 (`picos_contexto/vpc_scan.tsv`). Resultado:
  - Salen 59 fichas de Caldas.
  - **Ninguna es de 2020**: entre la ficha 8473 (nov-2019) y la 8994 (oct-2021) no hay ni una fiesta de Caldas. Es la huella del COVID en el agregador.
- [V] Los portales de las alcaldías (plataforma «Territoriales») arman la página con JavaScript, pero tienen una API pública: `https://<municipio>-caldas.gov.co/api/v1/contents/<slug>`. De ahí salen los datos de Palestina, Aranzazu, Filadelfia, Marquetalia y Risaralda.
- [V] Villamaría publica su calendario anual en `villamaria-caldas.gov.co/Calendario de eventos/calendario AAAA.xlsx`. Ojo: el archivo «2023» trae el contenido de 2022.
- [V] **Villamaría**:
  - Aniversarias 2022: 19-23 oct.
  - Horticultura 2026: **cancelada**.
  - Campo Elías 2021: 29-31 oct.
  - Campo Elías 2025: 14-16 nov.
- [V] **Palestina**:
  - Fiestas del Recuerdo 2025: 14-17 nov.
  - 2021: 12-15 nov, verificado.
  - 2024: solo hay un desfile del 169 aniversario (18-oct).
- [V] **Aranzazu 2026**: la alcaldía anuncia la XXIX Fiesta de la Cabuya del 5 al 12 de oct.
  - Leí el anuncio yo mismo. Es de junio, anterior al sismo, y no se ha encontrado aplazamiento.
- [V] **Filadelfia**, según decretos y portal de la alcaldía:
  - Ediciones: 43 = 2022 (10-15 ago), 44 = 2023 (12-21 ago), 45 = 2024 (13-19 ago), 46 = 2025 (8-18 ago).
  - 2020-2021 no hubo edición (el salto 42→43 lo delata).
  - 2026 empezó el 8-ago y se suspendió por el sismo.
- [V] **Marquetalia**:
  - 2026: 8-11 oct, publicado por la alcaldía el 7-sep, ya después del sismo.
  - 2022 (XXI): empezó el 9-oct.
  - 2020: no hubo (I).
- [V] **Risaralda**:
  - Fraternidad y Civismo XIV: 30-oct a 3-nov-2025.
  - La XIII fue en 2021 (I).
  - Viento y Café: 31-oct a 1-nov-2025.
  - El «Festival del Viento» no aparece con ese nombre después de 2019.
- [V] **Pensilvania**: Fiestas del Café XIX, 18-21 ago 2023.
- [V] **Salamina**: Noche del Fuego 2023, 7-8 dic.
- [V] **Aguadas**: Pasillo 2026 aplazado, no cancelado (El Páramo, 12-ago-2026).
- [V] **San Pedro y San Pablo**:
  - Ningún municipio de Caldas las tiene como fiesta principal.
  - La única con ese nombre es la de la **vereda San Pedro de Anserma**:
    - 2025: 27-30 jun [V].
    - 2022: 1-4 jul [V, fechas estimadas].
  - El puente de San Pedro lo ocupan otras fiestas: Ceiba (Victoria), Colación (Supía), Municipalización (La Merced), Samán (Viterbo), Cordialidad (Manzanares) y Horticultura (Villamaría).
- **Discrepancias que se dejaron como estaban** (se conservó la fecha de A/B):
  - Aranzazu 2022: la alcaldía dice 9-17 oct, La Patria 8-17.
  - Pácora 2022: viajaporcolombia dice 14-17 oct, La Patria 13-17.
  - Festival de la Lana 2022: viajaporcolombia dice 4-7 nov, La Patria 3-7.
  - Campo Elías 2022: BC Noticias dice 4-7 nov, La Patria 3-6.
  - Aguadas 2021: se conserva la ficha 9029.

### Qué no se encontró
- **Sin fuente (10 filas, heredadas de B como marcadores inferidos):**
  - Belalcázar 2020 y 2026.
  - San José 2026.
  - La Dorada 2026.
  - Victoria 2020-2021.
  - Marmato Barequero 2020, 2022, 2024 y 2026.
- **Estado vacío (sin dato):**
  - Villamaría: aniversarias 2023 y Horticultura 2025.
  - Chinchiná: carnavales 2020 y 2026.
  - Neira: Corcho 2020.
  - Palestina: 2020, 2022 y 2026.
  - Marmato: Barequero en los años citados.
  - Victoria: 2020-2021.
  - La Merced: Municipalización 2026 (junio, ya pasó; sin fuente).
  - Anuncios de 2026 que no aparecen: La Dorada, San José, Belalcázar y Salamina (la fecha de Salamina es fija, 7-8 dic).
- **Sin nueva fecha tras el sismo:** Aguadas (Pasillo), Riosucio (Encuentro de la Palabra), Manzanares y Filadelfia.
- **Faltan fechas de fin:**
  - Horticultura 2023 (La Patria da el inicio, 28-jun).
  - Campo Elías 2023 (inicio 15-dic).
  - Marquetalia 2022.
  - Filadelfia 2026.
- **Neira**: el Corcho es bienal, así que los años impares no son una cancelación. No se crearon filas para ellos. El alcalde propone hacerlas en 2027.

