# Literatura: cómo se relacionan entre sí los factores del entorno

Revisión hecha el 2026-09-29, **antes** de mirar los datos del cuaderno 09 («El entorno»), por
decisión del propietario (entrada «Primero el entorno entre sí» de `docs/CONTEXTO.md`). Fija
**lo esperado** —dirección, tamaño y rezago publicados— para que lo observado en Manizales se
contraste contra algo escrito antes. Es el espíritu del preregistro.

**Alcance.** Relaciones entorno ↔ entorno (clima, calendario, ENSO, volcán, fiestas, alcohol,
violencia, vigilancia). La relación de cada factor con el hospital viene después.

**Marcas de verificación.**
- **[V]** leído: al menos el resumen, abierto en PubMed (E-utilities) o en la web del editor.
- **[B]** visto solo en un buscador; la cifra no se comprobó en la fuente.

Ninguna cifra de este documento sale de memoria: si no se encontró, se dice.

> Estado: completa para una primera pasada (2026-09-29). Búsqueda en PubMed (E-utilities),
> OpenAlex, buscador web y PDF oficiales (Forensis 2023, boletín INS semana 53 de 2025, IDEAM,
> Poveda 2004). No es una revisión sistemática con protocolo.

## Tabla resumen

«Fuerza» se refiere a la evidencia **para el contexto de Manizales**, no en general: una
relación sólida en Europa y sin estudio andino queda en «media» o «baja».

| # | Relación | Dirección | Tamaño publicado | Rezago | Contexto de la evidencia | Fuerza | Referencias clave |
|---|---|---|---|---|---|---|---|
| 1 | Lluvia → VSR / IRA | + | IRR ~1,01 por mm de lluvia mensual (Bogotá); pico marzo-mayo | mensual (0-1 mes); transmisibilidad ~51 días antes del pico (Filipinas) | Bogotá 2.650 m; trópico | **Media** | Rodriguez-Martinez 2015; Gamba-Sanchez 2016; Tamerius 2013; Paynter 2014 |
| 1b | Temperatura → VSR en el trópico andino | + (meses cálidos = lluviosos en Bogotá); − en el mundo templado | IRR 2,25-3,14 por °C mensual (Bogotá); RR 0,13 por °C (metaanálisis global) | mensual | Bogotá vs. global | **Baja** (signo inestable) | Gamba-Sanchez 2016; Shang 2026; Tang 2014 |
| 1c | Cambio brusco de temperatura → consultas | + | +1,44 % de urgencias por °C de cambio entre días | 0-21 días | China, EE. UU. | **Media** (sin estudio andino) | Wang 2022; Zhan 2017 |
| 2 | Regreso a clases → transmisión respiratoria | + | cierre: −20 a −37 % de transmisión; onda 2-5 semanas tras la reapertura; pico de asma +17,7 días | 2-5 semanas | Francia, **México**, Canadá, Polonia | **Alta** (influenza); **baja** (VSR) | Cauchemez 2008; Chowell 2011; Johnston 2006; Zaremba 2025; Dallagiacoma 2024 |
| 3 | El Niño → Andes colombianos | − lluvia, + temperatura | sin cifra por unidad de ONI verificada; La Niña más marcada que El Niño | 0-2 meses (La Niña), 2-4 meses (El Niño) | Colombia | **Alta** (dirección) | Poveda 2004; Poveda & Mesa 1997; Poveda 2001; Salas 2020 |
| 3b | ENSO → enfermedades | El Niño + dengue, + malaria; + EDA (Lima) | +6,9 pp de probabilidad de exceso de dengue por DE de TSM; EDA ×2 en El Niño 1997-98 (Lima) | meses; más corto en los Andes | Colombia (dengue), Perú (EDA) | **Alta** (dengue); **nula** (respiratorias) | Muñoz 2021; Gutiérrez 2026; Checkley 2000 |
| 4 | Ceniza volcánica → consultas respiratorias | + | IRA baja RR 2,22, alta RR 1,72, asma RR 1,97 (Quito); +4,8 % por día de ceniza (Islandia) | 0-3 semanas; dura 3-4 semanas | **Quito 2000**, Islandia, St. Helens | **Media** (sin estudio del Ruiz) | Naumova 2007; Carlsen 2015; Baxter 1983; Gudmundsson 2011 |
| 5 | Fin de semana / festivo / quincena → alcohol → violencia | + | domingo 20,4 % de los homicidios; sábado-domingo 38,8 % de las lesiones; alcohol OR 15 en lesión violenta; restricción laxa IRR 1,42 | mismo día (noche) + lunes | **Colombia** (Forensis, Cali, Bogotá), Latinoamérica | **Alta** (fin de semana, alcohol); **baja** (quincena) | Forensis 2023; Borges 2008; Sánchez 2011; Villaveces 2000 |
| 6 | Pólvora en diciembre → quemados | + | 1.628 lesionados en el país; Caldas 48, Manizales 16 (2025-26) | 1 dic-17 ene; picos 7-8, 24-25 y 31 dic-1 ene | **Colombia** (INS) | **Alta** (pequeño en volumen) | INS BES semana 53 de 2025; Chaparro-Narváez 2017 |
| 7 | Lluvia → siniestros viales | + riesgo por viaje; − exposición | +38 % (+36-52 % según intensidad) de riesgo de choque; menos graves | mismo día u hora | EE. UU., Europa | **Media** (sin estudio latinoamericano) | Tafazzol 2025; Bergel-Hayat 2013; Qiu & Nixon 2008 [B] |
| 8 | Lluvia intensa → EDA | + tras periodo seco; − tras periodo húmedo | IRR 1,39 tras seca; IRR 0,74 tras húmedo | 0-2 semanas (historial de 8 semanas) | **Ecuador** rural; revisión global | **Media** | Carlton 2014; Levy 2016 |
| 9 | Frío → mortalidad y descompensación cardiorrespiratoria | + | +3,4 % de muertes por °C en frío extremo (Latinoamérica); EPOC RR acumulado 1,39 | 0-21 días (hasta 23) | **326 ciudades de Latinoamérica**; Europa; China | **Alta** (dirección); **media** (tamaño local) | Kephart 2022; Gasparrini 2015; Analitis 2008; Liu 2021 |
| 9b | Lluvia → dolor osteomuscular | nula | 6,35 % vs. 6,39 % de las consultas | — | EE. UU. | **Alta** (a favor del nulo) | Jena 2017; Dixon 2019 |
| 10 | Eventos masivos → infecciones / lesiones | lesiones +; respiratorio pequeño | carnaval: OR 2,34 de homicidio diario; brotes grandes raros | mismo día (lesiones); 1-2 semanas (infección) | Barranquilla; Bélgica; Hajj | **Media** (lesiones); **baja** (infección) | Guarin-Ardila 2019; Van Remoortel 2022; Hui 2023; Ewing 2017 |
| 11 | Interacciones | sinergia plausible | influenza → infarto ×6,05 en 7 días; PM10 × calor | 7 días (virus→IAM) | Canadá; metaanálisis | **Baja** para la triple frío × virus × edad | Kwong 2018; Li 2017; Ramírez 2018 |

---

## 1. Clima → circulación de virus respiratorios

### Lo que se encontró

**Bogotá (2.650 m, el análogo más cercano a Manizales en la literatura).** Dos series del mismo
grupo, Fundación Hospital La Misericordia, niños < 3 años hospitalizados por infección
respiratoria baja:

- Rodriguez-Martinez et al. 2015 **[V]** (PMID 25591796, doi:10.1017/S0950268814003793).
  2010-2011, 1.548 niños, 77,1 % VSR+. Análisis **mensual**. En el multivariable, temperatura
  (IRR 3,14; IC95 1,56-6,30) y lluvia (IRR 1,008 por mm; 1,00-1,01) se asocian con el VSR;
  humedad relativa, viento y radiación, no. Actividad continua todo el año con un **aumento
  abrupto en marzo-mayo, la primera temporada de lluvias**.
- Gamba-Sanchez et al. 2016 **[V]** (PMID 26888544, doi:10.1017/S0950268816000273).
  2009-2013, 4.559 niños, 64,8 % VSR+. Temperatura IRR 2,25 (1,11-4,53) y lluvia IRR 1,01 por mm
  (1,00-1,02). Pico marzo-mayo. **No analizaron rezagos**: todo es a escala mensual.

  Lectura: en Bogotá el VSR sube con la lluvia y, a escala mensual, con los meses *más cálidos*
  del año (que allí coinciden con la primera temporada de lluvias). Es lo contrario del patrón
  templado. Las IRR de temperatura son por °C de media mensual y tienen intervalos anchos.
- Evelyn et al. 2019 **[V]** (PMID 31601181, doi:10.1186/s12887-019-1734-x): metapneumovirus en
  Bogotá, 2015-2017, prevalencia 5,2 % entre IRA con virus detectado, y evalúan su relación con
  la lluvia. El resumen no da la cifra de esa relación.
- **Cali** (ciudad interandina más cálida): el VSR se concentra en el primer semestre, con pico
  marzo-abril, **sin asociación clara con la lluvia** **[B]** (PMC8189202,
  doi:10.1111/irv.12833; visto en buscador, no abierto).
- **Medellín**: Arango et al. 2015 **[V]** (PMID 25100179, doi:10.1111/irv.12271), vigilancia
  centinela de ETI 2007-2012 en un hospital: influenza A detectada **casi todo el año**, sin
  estación marcada; influenza B «sin patrón». No hay análisis con clima.
- **Manizales**: Cotes et al. 2012 **[V]** (PMID 23250321, doi:10.1590/s0124-00642012000100011)
  estudia hospitalizados por enfermedad respiratoria en temporadas de influenza 2000-2006 en
  Bogotá y Manizales, pero es clínico (complicaciones), no de clima. **No se encontró ningún
  estudio de clima y virus respiratorios en Manizales.**

**Trópico y mundo.**

- Tamerius et al. 2013 **[V]** (PMID 23505366, doi:10.1371/journal.ppat.1003194), 78 sitios.
  Dos regímenes: «frío-seco» y «húmedo-lluvioso». Donde la humedad específica o la temperatura
  mensual bajan de ~11-12 g/kg y ~18-21 °C, la influenza pica en la estación fría y seca. Donde
  no bajan de esos umbrales, pica en los meses de **lluvia máxima, por encima de ~150 mm/mes**.
  Manizales (16,5 °C de media) queda **por debajo del umbral de temperatura todo el año**, lo
  que por ese criterio la pondría en el régimen «frío-seco»; pero su temperatura casi no varía
  entre meses y sus meses frescos son los lluviosos, así que **ningún régimen encaja limpio**.
  Bogotá, en la misma situación, se comporta como «húmedo-lluvioso» para el VSR (ver arriba).
  Es una predicción abierta, no cerrada.
- Paynter et al. 2015 **[V]** (PMID 25307020, doi:10.1017/S0950268814002702), revisión de
  mecanismo: la lluvia tropical favorecería la **transmisión por contacto** (superficies, gotas)
  más que la aérea, y por eso favorece más al VSR que a la influenza.
- Tang et al. 2014 **[V]** (PMID 24421259, doi:10.1002/rmv.1771), revisión sistemática del VSR:
  en el trópico las correlaciones con temperatura y humedad son **variables e inconsistentes**;
  en zonas subtropicales y templadas, VSR con frío y humedad alta de forma consistente.
- Shang et al. 2026 **[V]** (PMID 41690197, doi:10.1016/j.envint.2026.110120), metaanálisis de
  108 estudios y 9,22 millones de casos. Por cada +1 °C: VSR RR 0,13, influenza 0,37,
  metapneumovirus 0,48; pero parainfluenza RR 2,35. La lluvia **reduce** la influenza (RR 0,67)
  y **aumenta** la parainfluenza (RR 1,91). **El VSR y el metapneumovirus son más sensibles al
  clima en el trópico.** Hay heterogeneidad grande por zona climática: los RR globales están
  dominados por estudios templados.

**Cambios bruscos de temperatura** (lo más cercano a «la transición, no el nivel»):
- Zhan et al. 2017 **[V]** (PMID 28162760, doi:10.1016/j.scitotenv.2017.01.177), 106 ciudades
  de EE. UU.: el «cambio de temperatura entre días vecinos» (TCN) es factor independiente, con
  efecto acumulado a **0-21 días**; más fuerte en ≥ 75 años y muertes por neumonía y EPOC.
  Ojo con la dirección: allí el **aumento** brusco es el dañino (RR 1,46 al percentil 99), y la
  caída brusca aparece protectora (RR 0,63).
- Wang et al. 2022 **[V]** (PMID 35963321, doi:10.1016/j.envres.2022.113963), 20 sitios de
  China, **urgencias**: +1 °C de TCN → +1,44 % (0,93-1,96) de las visitas totales; el TCN sube
  las **respiratorias en invierno**. El rango diurno (DTR): +0,29 % por °C.
- **No se encontró** un estudio de cambio brusco de temperatura o de «inicio de lluvias tras
  sequía» sobre virus respiratorios en los Andes ni en Colombia.

### Rezago publicado

Casi todos los estudios tropicales trabajan a escala **mensual** y no estiman rezago. Los
estudios diarios de temperatura usan ventanas de 0-21 días. Del mecanismo (incubación del VSR y
la influenza, de 1 a 8 días, y transmisión en cadena) se espera que el efecto de un cambio de
clima sobre la circulación tarde **1-3 semanas**, pero eso es **inferencia**, no una cifra
medida en el trópico andino.

### Lo que Manizales debería ver si la literatura se cumple

- La IRA/ERA de vigilancia de Caldas debería subir en **marzo-mayo** (primera lluvia), con un
  segundo repunte menor posible en octubre-noviembre.
- Dentro del año, la serie respiratoria debería correlacionar **positivamente con la lluvia** a
  escala mensual, con 0-1 mes de rezago, más para VSR que para influenza.
- La influenza no tiene por qué tener estación clara (Medellín) y puede aparecer en brotes
  fuera de temporada.
- Un cambio brusco de temperatura debería anticipar un aumento respiratorio en **1-3 semanas**,
  con tamaño pequeño (pocos %) en el total.

---

## 2. Calendario escolar → transmisión respiratoria

### Lo que se encontró

- Cauchemez et al. 2008 **[V]** (PMID 18401408, doi:10.1038/nature06732), Francia, red
  Sentinelles: las vacaciones escolares **reducen un 20-29 % la tasa de transmisión de la
  influenza a los niños**, sin efecto detectable en los contactos entre adultos, y evitan el
  16-18 % de los casos de la temporada.
- Chowell et al. 2011 **[V]** (PMID 21629683, doi:10.1371/journal.pmed.1000436), México,
  pandemia H1N1 2009 (IMSS, 117.626 casos de ETI). El cierre obligatorio de 18 días se asoció a
  una **reducción del 29-37 % de la transmisión**. Las ondas de otoño de cada estado **empezaron
  2-5 semanas después de la reapertura de los colegios**, con un corrimiento de la edad de los
  casos. Es la evidencia latinoamericana más directa de un «back-to-school» respiratorio.
- Zaremba et al. 2025 **[V]** (PMID 39663466, doi:10.1093/aje/kwae453), Polonia, experimento
  natural con las vacaciones de invierno escalonadas: en las **4 semanas** siguientes al cierre,
  la ETI baja 75 % en escolares, 55 % en adultos, 26 % en preescolares y 31 % en mayores; la
  mortalidad respiratoria de los mayores baja 7 %. O sea, el efecto **se derrama a los adultos**.
- Johnston et al. 2006 **[V]** (PMID 16522453, doi:10.1016/j.jaci.2005.11.034), Canadá
  1990-2002, la «epidemia de asma de septiembre»: el pico de hospitalización por asma en
  escolares llega **17,7 días (IC95 16,8-18,5) después del regreso a clases**; preescolares
  1,7 días después y adultos 6,3 días después que los escolares. Mecanismo: rinovirus
  transmitidos en el colegio.
- Dallagiacoma et al. 2024 **[V]** (PMID 38847423, doi:10.1111/apa.17313), Suecia, VSR: un solo
  receso (otoño 2021) redujo la incidencia; los demás recesos dieron resultados mixtos. **No
  apoya un efecto universal de las vacaciones sobre el VSR**, cuyo motor es el lactante y el
  hogar más que el colegio.
- Paynter et al. 2014 **[V]** (PMID 24587222, doi:10.1371/journal.pone.0090094), Filipinas
  (trópico): el pico de transmisibilidad del VSR tendría que ocurrir **~51 días (49-67) antes**
  del pico de casos observado. De los candidatos (lluvia, humedad, temperatura, nutrición,
  vacaciones escolares), el calendario de **lluvia y nutrición** encajaba; las vacaciones no.

**No se encontró** un estudio del calendario escolar colombiano sobre virus respiratorios. Si
el calendario A de Caldas sigue el patrón habitual (clases de finales de enero o febrero a
noviembre, receso a mitad de año y en diciembre-enero; **a verificar con las resoluciones**, que
el proyecto va a integrar), el regreso de febrero y la primera lluvia (marzo) **quedan
superpuestos**: es un confusor estructural, no un detalle.

### Lo que Manizales debería ver

- La serie respiratoria de vigilancia debería **subir 2-5 semanas después del regreso a clases**
  (febrero y julio) y bajar en las 2-4 semanas siguientes al inicio de las vacaciones
  (mitad de año y diciembre).
- El efecto debería ser más nítido en la influenza y el rinovirus que en el VSR.
- Como el regreso de febrero precede a la lluvia de marzo, **no se podrá separar colegio y
  lluvia en el primer semestre** con una sola serie; el receso de mitad de año, que cae en la
  temporada relativamente seca, es donde el colegio queda aislado del clima.

---

## 3. ENSO (El Niño / La Niña) → clima de los Andes colombianos → enfermedades

### 3a. ENSO → clima de Colombia

- Poveda 2004 **[V]** (Rev. Acad. Colomb. Cienc. 28(107), doi:10.18257/raccefyn.28(107).2004.1991;
  texto completo leído), síntesis de la hidroclimatología de Colombia: durante **El Niño** bajan
  la lluvia, los caudales, la humedad del suelo y la actividad vegetal, y **sube la temperatura
  media del aire**; **La Niña** da lo contrario, con lluvias muy intensas, crecientes,
  avalanchas e inundaciones. Los efectos son **más fuertes y más inmediatos en el occidente** del
  país (donde está Manizales) que en el oriente, y se concentran en el año de inicio (0) y el de
  finalización (+1) del evento. El texto no da cifras de rezago en meses.
- Poveda & Mesa 1997 **[V]** (J. Climate, doi:10.1175/1520-0442(1997)010<2690:FBHPIT>2.0.CO;2):
  El Niño → anomalías negativas de lluvia y caudal; La Niña → positivas. **Los impactos de La
  Niña son más pronunciados que los de El Niño**, y el efecto sobre los caudales llega
  progresivamente más tarde hacia el oriente.
- Poveda et al. 2001 **[V]** (Water Resour. Res., doi:10.1029/2000WR900395): anomalías más fuertes
  en **diciembre-febrero** y más débiles en **marzo-mayo**. Humedad de suelo medida en la zona
  cafetera de los Andes centrales (el entorno de Manizales): déficit fuerte en El Niño 1997-98,
  sobre todo en las dos temporadas secas; máximos en La Niña 1998-99.
- Salas et al. 2020 **[V]** (Front. Appl. Math. Stat., doi:10.3389/fams.2020.00003): la
  sincronía ENSO-hidrología en las regiones Andina, Pacífica y Caribe es **fuerte en La Niña y
  débil en El Niño** (asimetría). El transporte de humedad por los chorros del Caribe y del Chocó
  se sincroniza con las anomalías de lluvia a **0-2 meses** de rezago en La Niña y **2-4 meses**
  en El Niño, en el noroccidente de Colombia.
- Vega et al. 2024 **[V]** (Landslides, doi:10.1007/s10346-024-02225-9), Andes colombianos
  1981-2022: los deslizamientos siguen el ciclo bimodal de lluvia; **en años La Niña son más
  frecuentes durante todo el año**; en El Niño se concentran en meses concretos. La lluvia
  antecedente importa.
- IDEAM **[V]** (boletín de seguimiento ENSO de 2023, descargado de ideam.gov.co, documento
  público 6446): El Niño (La Niña) → déficit (aumento) significativo de lluvia y aumento
  (disminución) importante de la temperatura del aire, **sobre todo en las regiones Caribe,
  Andina y Pacífica**, con impacto **diferencial** en el territorio. No da cifras por
  departamento en el texto extraíble.

**Tamaño.** No se encontró una cifra publicada, verificada, de cuántos mm o cuántos °C cambia
Manizales o el Eje Cafetero por unidad de ONI. Lo verificado es la dirección y la asimetría.

### 3b. ENSO → enfermedades

- **Dengue en Colombia.** Muñoz et al. 2021 **[V]** (PMID 34555353,
  doi:10.1016/j.actatropica.2021.106136), 2007-2017: El Niño (La Niña) → **más (menos)
  dengue**, explicado por el aumento de temperatura y la baja de lluvia; correlación máxima a
  **rezagos más cortos en las regiones Andina y Pacífica**; asociación más fuerte en
  diciembre-febrero. Gutiérrez et al. 2026 **[V]** (PMID 41576105,
  doi:10.1371/journal.pgph.0005796), 1.044 municipios 2013-2023, aprendizaje causal: +1 DE de la
  TSM en Niño 3 (1,24 °C) → **+6,9 puntos porcentuales** en la probabilidad de exceso de dengue;
  efecto mayor a **mayor altitud**. Salazar-Ceballos et al. 2025 **[V]** (PMID 41325567): ONI y
  dengue en el Caribe colombiano, positivo en El Niño 2023.
- **Malaria en Colombia.** Poveda et al. 2001 **[V]** (PMID 11401760, doi:10.1289/ehp.01109489):
  El Niño no cambia la estacionalidad, **la intensifica**; efecto más fuerte en el segundo
  semestre del año 0 y el primero del año +1. Poco relevante para Manizales (no es zona malárica).
- **EDA.** Checkley et al. 2000 **[V]** (PMID 10841124, doi:10.1016/s0140-6736(00)82010-3),
  Lima: en El Niño 1997-98 la temperatura subió hasta 5 °C sobre lo normal y los ingresos
  diarios por diarrea llegaron al **200 %** de la tasa previa; antes del evento, **+8 % por
  cada +1 °C**. Bennett et al. 2012 **[V]** (PMID 22594750, doi:10.2105/AJPH.2011.300573), misma
  ciudad, comunidad: +55 % de incidencia de diarrea en la primavera de El Niño. Ojo: en Lima El
  Niño **calienta y moja**; en los Andes colombianos calienta y **seca**, así que la dirección
  no se traslada tal cual.
- **Respiratorias.** **No se encontró** un estudio que vincule ENSO con IRA o influenza en
  Colombia ni en los Andes. Londono-Avendano et al. 2021 **[V]** (PMID 33830644) solo menciona
  que en 2017 subieron hospitalizaciones respiratorias en regiones «con influencia distinta del
  ENSO» que Bogotá, sin cuantificar. Anyamba et al. 2019 **[V]** (doi:10.1038/s41598-018-38034-z)
  muestra brotes mundiales durante El Niño 2015-16 (2,5-28 % más actividad en regiones
  teleconectadas), pero no respiratorios.

### Lo que Manizales debería ver

- **La Niña → más lluvia** y temperatura algo menor; **El Niño → menos lluvia** y más calor,
  con respuesta local a **0-4 meses** del índice del Pacífico (más rápida en La Niña). La
  asimetría (La Niña más marcada) debería notarse.
- Las anomalías deberían ser más fuertes en **diciembre-febrero** y más débiles en marzo-mayo.
- Deslizamientos y emergencias por lluvia **concentrados en años La Niña**. En la ventana
  2020-2026 está el episodio triple de La Niña que el IDEAM da por terminado a comienzos de
  2023, y el El Niño que pronosticaba para mediados de 2023; las fechas exactas se toman del ONI
  cuando se integre.
- Dengue en Caldas (en municipios cálidos, no en Manizales) **subiendo en El Niño**.
- **Ninguna predicción publicada** para ENSO → IRA en los Andes: si aparece algo, será
  exploratorio, no confirmatorio.

---

## 4. Ceniza volcánica → material particulado → síntomas y consultas

### Lo que se encontró

- **Quito, Guagua Pichincha, abril de 2000** — el mejor análogo andino. Naumova et al. 2007
  **[V]** (PMID 17650330, doi:10.1186/1476-069X-6-21), serie temporal de urgencias del
  Hospital Pediátrico Baca Ortiz (5.169 consultas respiratorias en 2000, Poisson). En las **tres
  semanas** siguientes a la erupción: infección respiratoria **baja RR 2,22** (1,95-2,52) y
  **alta RR 1,72** (1,49-1,97); menores de 5 años RR ~2,2; asma y afines **RR 1,97** (1,19-3,24)
  durante la actividad fumarólica. **28 días de actividad y emisión de ceniza → 345 (241-460)
  consultas adicionales.** Es el único estudio de series de urgencias en un volcán andino que se
  encontró.
- **Islandia (Eyjafjallajökull 2010, Grímsvötn 2011).** Carlsen et al. 2015 **[V]** (PMID
  25872017, doi:10.3390/ijerph120404047), Reikiavik, 2007-2012: en los días en que el PM10
  superó 50 µg/m³ por ceniza (20 días), las visitas de urgencia cardiorrespiratorias subieron
  **4,8 % (0,6-9,2) por día** de exposición sin ajustar y 7,3 % (−0,4 a 15,5) ajustado —
  inconcluso—. Carlsen et al. 2012 **[V]** (PMID 22403340, doi:10.1136/bmjopen-2011-000343),
  población rural muy expuesta: **la mitad de los adultos refirió irritación ocular y de vía
  aérea alta**; los asmáticos empeoraron; **ningún problema grave que requiriera
  hospitalización**.
- **Mount St. Helens 1980.** Baxter et al. 1983 **[V]** (PMID 6870351,
  doi:10.1080/00039896.1983.10543994): aumento de consultas de urgencias por asma y bronquitis en
  las **4 semanas** siguientes, con partículas totales en suspensión por encima de
  30.000 µg/m³; la ceniza exacerbó la enfermedad pulmonar crónica en un tercio de quienes la
  tenían aunque no consultaran.
- **Revisiones.** Gudmundsson 2011 **[V]** (PMID 21159135, doi:10.1111/j.1752-699X.2010.00231.x):
  síntomas agudos de asma y bronquitis y exacerbación de enfermedad pulmonar y cardiaca previas
  bien descritos; **sin efectos de largo plazo** en la función pulmonar; el efecto depende del
  tamaño de partícula (fracción respirable) y de la sílice cristalina, que **varían entre volcanes
  y entre erupciones**. Simbaña-Rivera et al. 2025 **[V]** (PMID 41069801,
  doi:10.3389/fpubh.2025.1658384), revisión de alcance, 27 volcanes: lo más reportado son
  síntomas respiratorios agudos, **conjuntivitis**, dermatitis, hipertensión y estrés
  postraumático; niños y mayores, más afectados. Mueller et al. 2020 **[V]** (PMID 32642627,
  doi:10.1029/2020GH000256): la evidencia es escasa y la exposición casi nunca se mide; lo más
  defendible es aplicar las curvas concentración-respuesta del PM urbano.
- **Tungurahua (Ecuador).** Eychenne et al. 2022 **[V]** (PMID 36545343,
  doi:10.1029/2022GH000680) caracteriza la ceniza respirable de la erupción de 2006 y su
  respuesta *in vitro*; no es un estudio epidemiológico. **No se encontró** un estudio de
  consultas por la ceniza del Tungurahua ni del Popocatépetl (lo encontrado del Popocatépetl es
  química de metales en la ceniza).
- **Nevado del Ruiz / Manizales.** Ordoñez et al. 2024 **[V]** (PMID 39271698,
  doi:10.1038/s41598-024-72058-y): el volcán emitió **ceniza y gas de forma sostenida de 2012 a
  2023**, con un domo en 2015-2019 — es decir, **toda la ventana del triage (2020-2026) tiene
  actividad**. Saffon et al. 2022 **[V, solo la ficha]** (doi:10.53010/nys2.06): correlacionan
  PM10 de Manizales (CDIAC) con asma, bronquitis, rinitis e infección respiratoria en una
  clínica, 2019-2020; la ficha no da cifras. **No se encontró un estudio que cuantifique el
  efecto de la ceniza del Ruiz sobre consultas.** Las recomendaciones de la Secretaría de Salud
  de Manizales ante caída de ceniza **[B]** (centrodeinformacion.manizales.gov.co) confirman que
  el evento ocurre en la ciudad, no su tamaño.

### Tamaño y duración

Episodio agudo con ceniza sobre la ciudad: urgencias respiratorias pediátricas **×1,7 a ×2,2
durante unas 3-4 semanas** (Quito, St. Helens). Exposición menor o lejana: **+5 % por día** de
ceniza, con intervalo que roza el cero (Islandia). Síntomas oculares y de vía alta frecuentes
pero **leves**. El efecto depende de si la ceniza cae en la ciudad (viento), del tamaño de
partícula y de la sílice.

### Lo que Manizales debería ver

- Los días con **reporte de caída de ceniza en Manizales** (boletines del SGC) deberían
  coincidir con **PM10 por encima de lo habitual** en las estaciones de la ciudad el mismo día
  o el siguiente.
- Las semanas con ceniza sobre la ciudad deberían anteceder un aumento de **ERA/IRA en la
  vigilancia de Caldas** (sobre todo < 5 años y asma) durante **0-3 semanas**.
- Si la emisión es continua y de bajo nivel, sin caída en la ciudad, el efecto esperado es
  **pequeño o nulo**: la actividad del volcán (nivel de alerta) no es exposición; la ceniza en
  la ciudad sí.
- Posible aumento de **conjuntivitis** en los mismos días.

---

## 5. Fiestas, fines de semana, festivos y quincena → alcohol → violencia y lesiones

### Lo que se encontró

**Distribución temporal en Colombia (Forensis).** Forensis 2023 **[V]** (Instituto Nacional
de Medicina Legal, publicado en diciembre de 2024; PDF descargado de medicinalegal.gov.co y
leído el texto):
- Homicidios 2023 (N = 14.260): **domingo 20,36 %** y **sábado 16,35 %**, contra martes 11,58 %
  y miércoles 12,00 % (un reparto plano daría 14,3 % por día). El **lunes** también sale alto,
  «probablemente influenciado por los eventos del fin de semana». Por mes: **pico en diciembre**
  (1.340 casos, frente a un promedio 2014-2022 de 1.144 para ese mes); julio y diciembre, los
  mayores.
- Violencia interpersonal (lesiones no fatales): **38,83 % entre sábado y domingo**, lunes
  14,15 %, martes a viernes 47,01 %. Con el lunes, el fin de semana concentra **más del 50 %**.
- Homicidio de Manizales en 2023: tasa 38,78 por 100.000 **[V]** (tabla municipal del mismo
  informe). Útil como denominador, no como relación.
- El informe no trae un análisis de **festivos, puentes ni quincena**: esa relación no está en
  Forensis 2023.

**Alcohol como mecanismo, con diseño causal.**
- Borges et al. 2008 **[V]** (PMID 18373010, doi:10.1590/s0036-36342008000700003), estudio
  colaborativo OMS en urgencias de Argentina, Brasil y México, casos cruzados: el **46 %** de las
  lesiones por violencia involucraba alcohol (11,5 % en las no intencionales); beber antes del
  evento multiplica el riesgo de **lesión por violencia OR 15,0** (5,8-39,1) y de lesión no
  intencional **OR 4,2** (2,7-6,5). Andreuccetti et al. 2012 **[V]** (PMID 22340601): la revisión
  latinoamericana confirma la alta prevalencia de alcohol en lesionados de urgencias.
- Sánchez et al. 2011 **[V]** (PMID 21450681, doi:10.1093/ije/dyr051), **Cali 2004-2008**:
  frente a la restricción más estricta (sin alcohol de 2 a 10 a. m.), la moderada (desde las
  3 a. m.) tuvo **IRR 1,15** (IC90 1,05-1,26) de homicidios y la laxa (desde las 4 a. m.)
  **IRR 1,42** (1,26-1,61). No cambió las muertes por lesión no intencional.
- Duailibi et al. 2007 **[V]** (PMID 17971559, doi:10.2105/AJPH.2006.092684), Diadema (Brasil):
  cerrar bares a las 11 p. m. redujo **casi 9 homicidios al mes**.
- Villaveces et al. 2000 **[V]** (PMID 10703790, doi:10.1001/jama.283.9.1205), Cali y Bogotá:
  se prohibió el porte de armas **en los fines de semana después de la quincena, en festivos y en
  días de elecciones** —porque ahí se concentraban los homicidios— y la tasa bajó (RR 0,86 en
  Cali, 0,87 en Bogotá). Es la prueba indirecta de que **fin de semana de quincena y festivo**
  son días de más violencia en Colombia: la política se diseñó sobre ese patrón.
- Concha-Eastman et al. 2002 **[V]** (PMID 12431354), Cali 1993-1998: homicidios **de noche y
  en fin de semana**; alcohol en la víctima asociado a riña con arma blanca (OR 1,9).

**Fiestas.**
- Guarin-Ardila et al. 2019 **[V]** (PMID 31861509, doi:10.3390/ijerph17010035), **Carnaval de
  Barranquilla** 2005-2015, ajustado por clima: probabilidad de al menos un homicidio de hombre
  por día **OR 2,34** (1,19-4,58) en carnaval frente a un día estándar; «similar a lo hallado
  para otros festivos». (El OR de mujeres que da el resumen, 1,22 con IC 1,22-7,36, es
  internamente incoherente; no usarlo.)
- Wilches-Gutiérrez et al. 2012 **[V]** (PMID 22296949), municipio mexicano 1986-2008: más
  muertes en Navidad, Todos los Santos y Año Nuevo; en los hombres, más muertes **traumáticas**
  en festivos.

**Quincena / día de pago.**
- Evans & Moore 2012 **[V, resumen]** (Rev. Econ. Stat. 94(2):400-418,
  doi:10.1162/REST_a_00184), EE. UU.: la mortalidad **baja antes del día 1 del mes y sube justo
  después**, en muchas causas; lo atribuyen a la liquidez (más actividad cuando llega el pago).
  El resumen no da el tamaño.
- **No se encontró** un estudio colombiano o latinoamericano que cuantifique el efecto de la
  quincena (15 y 30) sobre lesiones o consultas. Lo único local es el diseño de la prohibición
  de Villaveces 2000.

### Lo que Manizales debería ver

- Lesiones por violencia interpersonal y homicidios de Manizales/Caldas (SIEDCO de la Policía,
  Medicina Legal) **concentrados en sábado-domingo-lunes (≥ 50 %)**, con el domingo como pico
  (~20 % de los homicidios).
- **Diciembre** (y en menor grado julio) por encima del resto del año.
- Los **fines de semana de quincena** y los **puentes festivos** deberían estar por encima de
  un fin de semana normal. La magnitud no está publicada: medirla es aporte propio.
- La **Feria de Manizales** (enero) debería mostrar un exceso de lesiones y riñas del orden del
  observado en el Carnaval de Barranquilla (probabilidad diaria de homicidio ~×2), si el
  mecanismo es el mismo (alcohol en espacio público).
- Si hubo cambios de horario de venta de alcohol (ley seca, «hora zanahoria»), las noches con
  restricción deberían tener menos lesiones.

---

## 6. Pólvora en diciembre → quemados

### Lo que se encontró

- **INS, Boletín Epidemiológico Semanal 53 de 2025** **[V]** (PDF de ins.gov.co leído, tema
  central). La vigilancia intensificada va del **1 de diciembre al 17 de enero**. Al corte del
  5 de enero de 2026: **1.628 lesionados** en el país (+22,8 % frente al mismo corte de
  2024-2025); 30 % menores de 18 años, 54 de ellos en presencia de adultos bajo efectos del
  alcohol. **Caldas 48 casos; Manizales 16** en la temporada 2025-2026. Quemaduras en el 90 %
  (53,7 % de grado II-III); el 68,9 % manipulaba el artefacto y el 24,4 % era observador.
  Artefactos: «totes» 32,2 %, voladores 18,0 %.
- Chaparro-Narváez et al. 2017 **[V]** (PMID 27576924, doi:10.1016/j.burns.2016.07.005),
  vigilancia nacional 2008-2013: **6.585 lesionados**; tendencia creciente (+28 % anual en
  2008-2011, +3,5 % en 2011-2013). La hospitalización se asocia con lesión en el trabajo, el
  almacenamiento y el transporte; la muerte, sobre todo con almacenamiento (OR 19,5).
- Bonilla-Escobar et al. 2017 **[B]** (PMID 27908463): quemaduras oculares por pólvora en
  Colombia; carta sin resumen.
- Espitia-Hardeman et al. 2011 **[V]** (PMID 21278096), Pasto: la vigilancia de lesiones de la
  ciudad sirvió para diseñar prevención de las lesiones por pólvora «durante las fiestas».
- **Fechas pico.** Prensa que cita al INS **[B]**: la **Noche de Velitas (7 de diciembre)** es
  el día de mayor impacto al inicio de la temporada (172 lesionados en 2025, preliminar).
  No se abrió un boletín con la distribución diaria completa; el patrón conocido es
  7-8 de diciembre, 24-25 de diciembre y 31 de diciembre-1 de enero, pero **esa cifra diaria no
  se verificó**.

### Tamaño

Pequeño en números absolutos: Caldas ~50 casos por temporada, Manizales ~16. **Por sí sola,
la pólvora no mueve el conteo diario de un hospital** de la escala del proyecto (~177 triages
por día); sí marca días concretos, y **coincide con alcohol** (el INS lo reporta como factor).

### Lo que Manizales debería ver

- Los quemados por pólvora de Caldas concentrados **entre el 1 de diciembre y el 17 de enero**,
  con picos el **7-8 de diciembre, el 24-25 y el 31-1**.
- Esas noches deberían coincidir con un exceso de **lesiones por riña** (mismo mecanismo
  alcohol-fiesta), de modo que la pólvora es un marcador de la «temporada festiva» más que un
  factor independiente.

---

## 7. Lluvia → accidentes de tránsito y lesiones

### Lo que se encontró

- Qiu & Nixon 2008 **[B]** (Transp. Res. Rec. 2055:139-146, doi:10.3141/2055-16), metaanálisis
  de 34 estudios (1967-2005). El resumen de TRID **[V]** confirma el diseño y que la nieve sube
  la tasa de choques un 84 % y la de lesionados un 75 %, y que **la nieve pesa más que la
  lluvia**. Las cifras de lluvia que circulan en fuentes secundarias (+71 % de choques, +49 % de
  lesionados) **no se verificaron** en la fuente.
- Tafazzol et al. 2025 **[V]** (PMID 41120689, doi:10.1038/s41598-025-20760-w), Texas
  2006-2021, pares emparejados con lluvia horaria: la lluvia sube el riesgo de choque **un 38 %
  de media** (mínimo anual +32 %), y **un 36-52 % según la intensidad** (más por encima de
  25 mm/h). Los choques con lluvia son **menos graves**; el riesgo relativo es mayor en jóvenes
  de 18-30 años y menor en mayores de 65.
- Bergel-Hayat et al. 2013 **[V]** (PMID 23928504, doi:10.1016/j.aap.2013.03.006), Francia,
  Países Bajos y Atenas, series mensuales de más de 20 años: la correlación entre clima y
  lesionados es significativa, pero **su tamaño y hasta su signo cambian según el tipo de vía**.
  En Atenas la lluvia se asoció con **menos** lesionados, porque la gente sale menos. La lluvia
  actúa por dos canales opuestos: **más riesgo por viaje** y **menos viajes**.
- Saha et al. 2016 **[V]** (doi:10.1186/s12940-016-0189-x), EE. UU. 1994-2012: ~**16 %** de las
  muertes en carretera ocurrieron con clima adverso, sobre todo lluvia o pavimento mojado.
- **Latinoamérica y Colombia.** **No se encontró** un estudio publicado que mida lluvia contra
  siniestros en una ciudad latinoamericana. Existe un conjunto de datos de 175.245 accidentes de
  Bogotá 2013-2018 enriquecido con clima **[B]** (PMC9309645), sin análisis del efecto.

### Rezago

**Cero**: el efecto es del mismo día, incluso de la misma hora. La literatura no describe un
rezago de varios días.

### Lo que Manizales debería ver

- Los días (o las horas) con lluvia deberían tener **más siniestros**, del orden de **+30-50 %
  por hora de lluvia**, y **menos graves** en promedio; en Manizales, ciudad de pendientes y con
  mucha motocicleta, se espera que el efecto no sea menor, aunque no hay cifra local.
- Con datos diarios el efecto se **diluye**: un día con un aguacero corto no es un día lluvioso.
  Hace falta la variable horaria o `precip_con_estacion`, no el acumulado.
- Posible efecto contrario en el volumen total de lesiones si la lluvia vacía la calle: en los
  fines de semana la lluvia podría **reducir** las riñas en espacio público (no hay
  literatura local; es una hipótesis que queda abierta).

---

## 8. Temporada de lluvias → enfermedad diarreica aguda (EDA)

### Lo que se encontró

- **Carlton et al. 2014 [V]** (PMID 24256618, doi:10.1093/aje/kwt279), 19 comunidades de
  **Ecuador**, vigilancia activa semanal 2004-2007. Evento de lluvia intensa: 24 h por encima del
  percentil 90 (56 mm). **Tras un periodo seco**, la lluvia intensa **sube** la diarrea
  (**IRR 1,39**; 1,03-1,87); **tras un periodo húmedo**, la **baja** (IRR 0,74; 0,59-0,92). El
  historial de lluvia se mide en las **8 semanas previas**. Tratar el agua de consumo atenuó el
  efecto tras la sequía. Mecanismo: arrastre de contaminación acumulada hacia el agua de beber.
  **Es la evidencia publicada más cercana a la hipótesis del proyecto de que «importa la
  transición, no el nivel»**, aunque para EDA y no para lo respiratorio: el mismo evento de lluvia
  tiene signo opuesto según lo que vino antes.
- Levy et al. 2016 **[V]** (PMID 27058059, doi:10.1021/acs.est.5b06186), revisión sistemática
  de 141 artículos: acuerdo en una asociación **positiva entre temperatura y diarrea** (salvo la
  viral) y en un **aumento de la diarrea después de lluvias intensas e inundaciones**. Evidencia
  insuficiente para la sequía. Advierten del sesgo de publicación.
- Patel et al. 2013 **[V]** (PMID 23190782, doi:10.1097/INF.0b013e31827d3b68), 99 estudios de
  rotavirus antes de la vacuna: en países de ingreso bajo y medio-bajo la enfermedad es **de
  todo el año**; **el nivel de desarrollo predice mejor la estacionalidad que el clima**.
- Cáceres et al. 2006 **[V]** (PMID 17018220, doi:10.1590/s1020-49892006000700002), Bogotá,
  Barranquilla y Cali: el rotavirus causa el 50 % de las hospitalizaciones por diarrea en < 5
  años; la tendencia estacional de los genotipos **no varió con la temperatura, la humedad ni la
  lluvia** entre ciudades. Colombia vacuna contra rotavirus desde 2009 (dato de contexto, no
  verificado aquí), lo que debería haber aplanado aún más el componente viral.
- ENSO → EDA (Lima): ver sección 3b; +8 % de ingresos por diarrea por cada +1 °C.
- **Colombia andina.** **No se encontró** un estudio de lluvia y EDA en los Andes colombianos.

### Rezago

Carlton usa la semana del evento con el historial de 8 semanas; la incubación de los patógenos
bacterianos y parasitarios transmitidos por agua va de días a 1-2 semanas. Esperable: **0-2
semanas** tras la lluvia intensa.

### Lo que Manizales debería ver

- EDA de vigilancia en Caldas con **poca estacionalidad** (la viral está vacunada y es de todo el
  año).
- La **primera lluvia intensa después de un periodo seco** (inicio de marzo-abril y de octubre;
  final de El Niño) debería anteceder un aumento de EDA de **~+40 % en 0-2 semanas**; la misma
  lluvia en plena temporada húmeda, **no**, o incluso una baja.
- Las semanas cálidas (El Niño) deberían tener algo más de EDA bacteriana.
- Manizales tiene acueducto con cobertura alta, que es justo el modificador que atenuó el efecto
  en Ecuador: se espera un efecto **menor** que el de Carlton en la ciudad y más visible en
  municipios rurales de Caldas.

---

## 9. Frío y cambios bruscos de temperatura → descompensación de crónicos y dolor

### Lo que se encontró

**Frío y mortalidad o ingresos.**
- Kephart et al. 2022 **[V]** (PMID 35760859, doi:10.1038/s41591-022-01872-6), **326 ciudades
  de Latinoamérica** (SALURBAL, incluye ciudades colombianas), 2002-2015, modelos de rezago
  distribuido no lineal. El **5,09 %** de las muertes es atribuible al frío, contra el 0,67 % del
  calor. En frío extremo, **+3,4 % de riesgo de muerte por cada 1 °C menos** (RR 1,034;
  1,028-1,040). El efecto es mayor en los mayores y en las causas **cardiovasculares y
  respiratorias**.
- Gasparrini et al. 2015 **[V]** (PMID 26003380, doi:10.1016/S0140-6736(14)62114-0), 384
  localidades de 13 países (incluye Brasil y Tailandia), rezago de 21 días. El 7,29 % de la
  mortalidad es atribuible al frío y el 0,42 % al calor. La temperatura de mínima mortalidad
  está en el **~percentil 60 en el trópico**. **La mayor carga viene del frío moderado, no del
  extremo.**
- Analitis et al. 2008 **[V]** (PMID 18952849, doi:10.1093/aje/kwn266), 15 ciudades europeas: por
  cada −1 °C, +1,35 % de muertes naturales, +1,72 % de cardiovasculares y **+3,30 % de
  respiratorias**. El efecto es mayor en los mayores y **en las ciudades más cálidas**, y
  **persiste hasta 23 días**, sin desplazamiento de la mortalidad.
- Liu et al. 2021 **[V]** (PMID 33408200, doi:10.1136/bmjopen-2020-039745), Pekín, EPOC: una ola
  de frío da RR 1,042 el mismo día y **RR acumulado 1,39 a 0-21 días**; crece con la intensidad
  y la duración; ≥ 65 años, más vulnerables.

**Cambio brusco de temperatura** (ver también la sección 1).
- Wang et al. 2022 **[V]** (PMID 35963321): **+1,44 % de urgencias totales por cada °C** de
  cambio entre días vecinos; el rango diurno, +0,29 %/°C.
- Fu et al. 2023 **[V]** (PMID 36778544, doi:10.3389/fpubh.2023.1112926), Pekín, 143.318
  ingresos por EPOC: relación **en U** con el cambio de temperatura; los cambios extremos, fríos
  o cálidos, suben el riesgo acumulado a 21 días, sobre todo en > 65 años.
- Zhan et al. 2017 **[V]** (sección 1): efecto a 0-21 días, mayor en ≥ 75 años y en neumonía
  y EPOC.

**Dolor osteomuscular.**
- Jena et al. 2017 **[V]** (PMID 29237605, doi:10.1136/bmj.j5326), 11,7 millones de consultas de
  Medicare: **no hay relación clínicamente relevante** entre la lluvia y las consultas por dolor
  articular o de espalda (6,35 % contra 6,39 %, en dirección contraria a la esperada).
- Dixon et al. 2019 **[V]** (doi:10.1038/s41746-019-0180-3), 2.658 pacientes con registro diario:
  relaciones **significativas pero modestas** entre el dolor y la humedad relativa, la presión y
  el viento.

**Interacción frío × virus.**
- Murtas et al. 2019 **[V]** (PMID 31684915, doi:10.1186/s12889-019-7788-8), Milán, invierno
  2016-17, > 65 años, casos cruzados: la **temperatura mínima**, la **epidemia de influenza** y
  el **PM10** tienen efectos independientes sobre la mortalidad (la influenza, OR 1,20 en causas
  naturales y 1,30 en respiratorias). El resumen los reporta por separado, no como interacción.
- Yang et al. 2011 **[V]** (PMID 22168284, doi:10.1186/1471-2334-11-342), dos ciudades
  subtropicales chinas: el exceso de mortalidad asociado a la influenza es **mayor con humedad
  absoluta alta**, es decir, el clima **modifica la gravedad** de la influenza, no solo su
  transmisión. Temperatura, menos consistente.
- **No se encontró** un estudio del trópico andino que estime formalmente la interacción entre
  frío, virus y edad.

### Tamaño y rezago

Pocos % por °C (1-3 % en mortalidad, ~1,4 % en urgencias por °C de cambio brusco), con **rezago
largo: 0-21 días, hasta 23**. En Manizales la amplitud térmica anual es pequeña (ciudad
ecuatorial de montaña), así que el «frío» relevante es **el día o la semana más fríos de lo
habitual** (frentes lluviosos), no una estación.

### Lo que Manizales debería ver

- Las semanas con temperatura mínima **por debajo de lo normal para la época** deberían
  anteceder, **1-3 semanas después**, un aumento de la mortalidad o las consultas
  cardiorrespiratorias de mayores de 65 años (si la vigilancia lo permite ver).
- Los **cambios bruscos** de temperatura entre días deberían tener un efecto propio, además del
  nivel.
- El frío y la lluvia van juntos en Manizales (nubosidad): en el entorno, las semanas frías
  deberían coincidir con las lluviosas, lo que obliga a separarlas antes de atribuirles nada.
- El dolor osteomuscular **no** debería moverse con la lluvia en ninguna escala detectable.

---

## 10. Aglomeraciones y eventos masivos → infecciones y lesiones

### Lo que se encontró

**Infecciones.**
- Hui et al. 2023 **[V]** (PMID 36876655, doi:10.1097/MCP.0000000000000956), revisión: las
  infecciones respiratorias virales (influenza, rinovirus, coronavirus estacionales) son
  **comunes** en los eventos masivos, pero **los brotes grandes son raros** cuando hay
  planeación de salud pública. La evidencia fuerte viene del Hajj, un evento de semanas con
  hacinamiento extremo, que no se parece a una feria urbana.
- Ewing et al. 2017 **[V]** (PMID 28031259, doi:10.1093/infdis/jiw642), EE. UU. 2001-2009: las
  vacaciones de fin de año **reducen** la transmisión de la influenza y **retrasan** el pico; el
  riesgo se corre de los niños a los adultos. El modelo atribuye el efecto al **cierre escolar**,
  no a los viajes ni a las reuniones familiares. Es decir, **la temporada festiva de diciembre,
  que junta gente, en neto baja la transmisión** porque cierra los colegios.
- **No se encontró** un estudio que mida la transmisión respiratoria tras una feria o un
  carnaval latinoamericano (Barranquilla, Pasto, Manizales).

**Lesiones y demanda médica.**
- Van Remoortel et al. 2022 **[V]** (PMID 35393345, doi:10.1136/emermed-2021-211745), 194
  eventos masivos en Bélgica, 148.265 atenciones: el **80 % es primeros auxilios**; la
  emergencia vital, el 0,6 %. Heridas de piel (42 %), y en fiestas urbanas y deportes más
  quemaduras, fracturas y contusiones.
- Spaepen et al. 2023 **[V]** (PMID 36833901, doi:10.3390/ijerph20043207), festival de 400.000
  asistentes: con servicio de salud dentro del evento, el traslado al hospital fue de **0,38 por
  1.000 asistentes** y el impacto sobre las urgencias locales quedó acotado.
- Carnaval de Barranquilla (sección 5) **[V]**: homicidio diario de hombres OR 2,34.

### Lo que Manizales debería ver

- La **Feria de Manizales** (primera semana de enero) debería coincidir con un exceso de
  **lesiones, riñas e intoxicación alcohólica**, y **no** con un aumento respiratorio inmediato.
- Si hay efecto respiratorio de la feria, debería aparecer **1-2 semanas después** y ser
  pequeño; en enero además los colegios siguen cerrados, lo que empuja en contra.
- Las vacaciones de diciembre-enero deberían **bajar** la transmisión respiratoria pese a las
  reuniones (Ewing 2017), y el regreso a clases de finales de enero-febrero, subirla (sección 2).

---

## 11. Interacciones entre factores

### Frío × virus × población vulnerable

- **El virus descompensa al crónico.** Kwong et al. 2018 **[V]** (PMID 29365305,
  doi:10.1056/NEJMoa1702090), serie de casos autocontrolada: en los **7 días** siguientes a una
  influenza confirmada, el ingreso por **infarto** es **6,05 veces** (3,86-9,50) el de los
  periodos control; después del día 7, no hay exceso. Es el eslabón «virus → cardiovascular» que
  hace que una temporada respiratoria se vea también en consultas no respiratorias de mayores.
- **El clima modifica la gravedad, no solo la transmisión.** Yang et al. 2011 **[V]** (sección
  9): el exceso de mortalidad por influenza es mayor con humedad alta en el subtrópico.
- **Frío, influenza y contaminación suman.** Murtas et al. 2019 **[V]** (sección 9): efectos
  independientes y simultáneos en > 65 años.
- **Temperatura × material particulado.** Li et al. 2017 **[V]** (PMID 27780592,
  doi:10.1016/j.scitotenv.2016.10.070), metaanálisis de 21 estudios: el efecto del PM10 sobre la
  mortalidad es **mayor en los días calurosos** (+0,78 % no accidental y +1,28 % cardiovascular
  por 10 µg/m³) que en los templados. El efecto del ozono es mayor en los días fríos y en los
  calurosos que en los templados. Relevante para el cruce **ceniza × temperatura**: la
  interacción existe, pero la publicada es con **calor**, no con frío.
- **Ecosindemia.** Ramírez et al. 2018 **[V]** (PMID 30477272, doi:10.3390/ijerph15122639), Piura
  (Perú), El Niño 1998: **varias enfermedades sensibles al clima se superponen** durante semanas
  en los mismos distritos; construyen un índice de riesgo multienfermedad. Es el antecedente
  metodológico más cercano a los **«estados del entorno»** del cuaderno 09.
- **No se encontró** una estimación formal de la interacción triple frío × virus × edad en el
  trópico andino. El ejemplo del propietario (población frágil + frío + virus) es plausible por
  eslabones separados, pero su **término de interacción no está publicado** para esta región.

### Festivo × alcohol × violencia

- Villaveces et al. 2000 **[V]** y Sánchez et al. 2011 **[V]** (sección 5): la violencia de los
  fines de semana de quincena y los festivos en Cali y Bogotá **responde a la disponibilidad de
  alcohol y armas**. Es decir, el festivo no es el mecanismo: es la **ocasión**, y el alcohol es
  el mediador. La restricción de horario cambia el tamaño del efecto festivo (IRR 1,15 a 1,42
  entre regímenes).
- Borges et al. 2008 **[V]**: el alcohol multiplica el riesgo de lesión violenta ×15.
- INS 2025 **[V]** (sección 6): los quemados por pólvora ocurren con adultos bajo efectos del
  alcohol; **pólvora, alcohol y violencia comparten las mismas noches**.

### Otras interacciones que la literatura sugiere

- **Colegio × lluvia** (secciones 1-2): en Colombia el regreso a clases de febrero y la primera
  lluvia de marzo coinciden, así que se confunden en el primer semestre.
- **Lluvia intensa × historial seco** (sección 8, Carlton 2014): la misma lluvia tiene signo
  opuesto según las 8 semanas previas. Es una **interacción de estado**, no una suma.
- **ENSO × ciclo anual** (sección 3): El Niño no cambia *cuándo* ocurren las cosas, **amplifica**
  el ciclo anual (Poveda 2001 en malaria; Poveda 2001 en hidrología, más fuerte en DEF).
- **Vacaciones × aglomeración** (sección 10): diciembre junta gente pero cierra colegios; en
  neto, la influenza baja (Ewing 2017).

### Lo que Manizales debería ver

- Las semanas en que coincidan **frío anómalo, circulación viral alta (vigilancia de IRA) y
  población mayor** deberían mostrar un aumento cardiorrespiratorio **mayor que la suma** de
  cada factor por separado, si la interacción existe. La literatura no da su tamaño: es la
  **pregunta abierta del proyecto**, no una predicción publicada.
- Los **fines de semana de quincena en temporada de fiestas** (diciembre, Feria de enero)
  deberían concentrar las lesiones violentas **más que** un fin de semana de quincena normal o
  que un festivo sin quincena.
- Los **estados del entorno** esperables a partir de la literatura, candidatos para el
  agrupamiento de semanas:
  1. **Temporada respiratoria**: lluvia + regreso a clases (marzo-mayo, y octubre-noviembre en
     menor medida).
  2. **Temporada festiva**: diciembre-enero, con pólvora, alcohol, violencia y colegios
     cerrados.
  3. **Calma**: meses secos de mitad de año, con los colegios cerrados, o semanas neutras.
  4. **Anomalía ENSO**: La Niña (lluvia, deslizamientos) o El Niño (calor, sequía, dengue en
     municipios bajos), que **amplifican** los estados anteriores en lugar de crear uno nuevo.
  5. **Episodio volcánico**: caída de ceniza sobre la ciudad, raro y de 3-4 semanas.

---

## Vacíos: lo que la literatura no contesta para Manizales

1. **Clima → virus respiratorios en Manizales o el Eje Cafetero**: no hay ningún estudio. El
   análogo es Bogotá, a 500 m más de altura y más fría.
2. **Rezagos a escala diaria o semanal en el trópico andino**: los estudios colombianos son
   mensuales.
3. **Ceniza del Ruiz → consultas**: no está cuantificado; el análogo es Quito 2000.
4. **Quincena → lesiones en Colombia**: la única evidencia es el diseño de una política (1993-1997).
5. **Lluvia → siniestros en ciudades latinoamericanas**: sin estudio encontrado.
6. **ENSO → respiratorias en los Andes**: sin estudio encontrado.
7. **Interacción triple frío × virus × edad**: sin estimación publicada.

Estos vacíos son **aporte posible de la tesis**, no fallas de la búsqueda, con una salvedad: la
búsqueda fue de una sesión (PubMed, OpenAlex, buscador web, informes de Medicina Legal, INS e
IDEAM) y no una revisión sistemática con protocolo. Literatura gris colombiana (tesis de la
Universidad de Caldas o la Nacional de Manizales, informes de Corpocaldas) puede existir y no
haberse encontrado.
