# -*- coding: utf-8 -*-
"""Los detectores tienen que atrapar lo inventado y dejar pasar lo bien traducido.

Los casos de 'atrapa' salen de fallos reales del modelo (NLP/docs/EVALUACION.md).
Los de 'no confunde' son traducciones legitimas que un detector ingenuo marcaria.
"""
import pytest

from NLP import fidelidad as f


# ---------- atrapa lo inventado ----------

def test_atrapa_la_alucinacion_real_de_las_remisiones():
    # Caso real del banco del 2026-09-18: nota de tramite, queja inventada entera.
    r = f.revisar("ME INDICAN CONSULTAR POR URGENCIAS",
                  "dolor abdominal intenso y persistente desde hace 24 horas")
    assert "numero_inventado" in r["banderas"]
    assert "cuerpo_inventado" in r["banderas"]
    assert f.es_fallo(r)


def test_atrapa_un_lado_que_la_nota_no_dice():
    assert "lado_inventado" in f.revisar("ME CAI Y ME DUELE EL BRAZO",
                                         "trauma en brazo derecho")["banderas"]


def test_atrapa_una_parte_del_cuerpo_que_la_nota_no_nombra():
    r = f.revisar("ME CAI", "posible fractura de brazo izquierdo")
    assert "brazo" in r["partes_inventadas"]


def test_atrapa_el_descarte_de_una_nota_con_sintomas():
    assert "descarte_falso" in f.revisar("TIENE FIEBRE Y TOS HACE 2 DIAS",
                                         "sin motivo clinico")["banderas"]


def test_atrapa_salida_vacia_o_larguisima():
    assert "formato" in f.revisar("FIEBRE", "")["banderas"]
    assert "formato" in f.revisar("FIEBRE", "fiebre " * 60)["banderas"]


def test_frase_comodin_necesita_repetirse_y_no_tener_base():
    filas = [(i, f"ME INDICAN CONSULTAR {i}", "dolor abdominal intenso") for i in range(4)]
    revisiones = f.revisar_corpus(filas)
    assert all("frase_comodin" in r["banderas"] for r in revisiones.values())


# ---------- no confunde lo bien hecho ----------

@pytest.mark.parametrize("original, salida", [
    ("ME DUELE LA BARRIGA", "dolor abdominal"),
    ("DOLOR DE CABEZA DESDE AYER", "cefalea desde hace 1 dia"),
    ("DOLOR EN EL PECHO", "dolor toracico"),
    ("FIEBRE HACE DOS DIAS", "fiebre de 2 dias de evolucion"),
    ("ME CORTE UNA HERIDA EN LA MANO IZQ", "herida en mano izquierda"),
    ("CAMBIO DE VENDAJE", "sin motivo clinico"),
])
def test_no_marca_una_traduccion_fiel(original, salida):
    r = f.revisar(original, salida)
    fuertes = [b for b in r["banderas"] if b in f.FUERTES]
    assert fuertes == [], (original, salida, r)


def test_una_salida_repetida_con_base_no_es_comodin():
    # 'tos' se repite cientos de veces con razon: repetirse no basta.
    filas = [(i, f"PACIENTE CON TOS {i}", "tos") for i in range(10)]
    revisiones = f.revisar_corpus(filas)
    assert not any("frase_comodin" in r["banderas"] for r in revisiones.values())


# ---------- la familia medida el 2026-09-23 ----------

@pytest.mark.parametrize("original, salida", [
    ("REMITIDO DE OTRO MUNICIPIO", "dolor en el pie derecho por caida desde altura"),
    ("TRAIDA EN AMBULANCIA", "trauma por aplastamiento en dedo izquierdo"),
    ("DERIVADA DESDE LA EPS", "dolor abdominal intenso y persistente desde hace 24 horas"),
    ("TENGO", "dolor abdominal intenso"),
])
def test_atrapa_la_queja_en_una_nota_de_tramite(original, salida):
    assert "queja_sin_sintoma" in f.revisar(original, salida)["banderas"]


@pytest.mark.parametrize("original, salida", [
    # Falsos positivos reales de la primera version del detector (408 marcadas):
    # vocabulario clinico que ninguna lista de sintomas cubre.
    ("TENGO HEMORROIDES", "hemorroides"),
    ("SE ME TAPO LA SONDA", "sonda tapada"),
    ("NO VEO BIEN", "no veo bien"),
    ("INDUCCION DEL PARTO", "induccion del parto"),
    ("TIENE UNA SECRECION FETIDA", "secrecion fetida"),
    ("ESTOY ASFIXIADO", "disnea"),
])
def test_vocabulario_clinico_fuera_de_la_lista_no_es_queja_sin_sintoma(original, salida):
    assert "queja_sin_sintoma" not in f.revisar(original, salida)["banderas"]


@pytest.mark.parametrize("original, salida", [
    # Falsos positivos reales de la segunda version, que como filtro habrian
    # borrado un motivo real (el peor error: el paciente sale de la cuenta).
    ("ESTA MUY BORRACHO", "intoxicacion alcoholica"),
    ("ABORTO", "aborto"),
    ("ME OPERARON", "consulta posoperatoria"),
    ("AMREO", "mareo"),
    ("ESTA MUY AMARILL,A AYER TUVE CITA CON PEDIATRIA", "amarillamiento"),
])
def test_motivo_real_escrito_raro_no_es_tramite(original, salida):
    assert "queja_sin_sintoma" not in f.revisar(original, salida)["banderas"]


def test_una_remision_con_sintoma_no_es_queja_sin_sintoma():
    r = f.revisar("REMITIDA POR DOLOR ABDOMINAL", "dolor abdominal")
    assert "queja_sin_sintoma" not in r["banderas"]


@pytest.mark.parametrize("original, salida", [
    ("NO ME BAJA EL AZUCAR", "cifras tensionales elevadas"),
    ("HACE UNA HORA SE LE BAJO LA PRESION", "cifras tensionales elevadas"),
    ("ME CAI EN LA CASA", "trauma por aplastamiento en dedo"),
])
def test_atrapa_la_copia_de_un_ejemplo_del_prompt(original, salida):
    assert "copia_de_ejemplo" in f.revisar(original, salida)["banderas"]


@pytest.mark.parametrize("original, salida", [
    ("ME MACHUQUE UN DEDO CON LA PUERTA", "trauma por aplastamiento en dedo"),
    ("TENGO LA PRESION ALTA", "cifras tensionales elevadas"),
])
def test_el_ejemplo_con_respaldo_en_la_nota_no_es_copia(original, salida):
    assert "copia_de_ejemplo" not in f.revisar(original, salida)["banderas"]


@pytest.mark.parametrize("original, salida", [
    ("ABCESO EN MIEMBRO SUPERIOR DEREHCO", "absceso en miembro superior derecho"),
    ("ZARPULLIDO EN MEJILLA IQUIERDA", "zarpullido en mejilla izquierda"),
    ("DOLOR ABDOIMINAL GENERALIZADO", "dolor abdominal generalizado"),
    ("TRAUMA EN MSD", "trauma en miembro superior derecho"),
])
def test_una_errata_o_una_sigla_de_la_nota_no_es_invencion(original, salida):
    fuertes = [b for b in f.revisar(original, salida)["banderas"] if b in f.FUERTES]
    assert fuertes == [], (original, salida, fuertes)


def test_el_nombre_de_un_servicio_no_es_un_sintoma():
    r = f.revisar("REMITIDO DE MEDICINA DEL DOLOR", "sin motivo clinico")
    assert "descarte_falso" not in r["banderas"]


def test_normal_no_contiene_mal():
    assert not f.evidencia_clinica("SIGNOS VITALES NORMALES, REMITIDO")


# ---------- los filtros: quitan lo inventado y respetan lo que la nota dice ----------

@pytest.mark.parametrize("original, salida, esperada", [
    ("ME CORTE LA MANO CON UNA TEJA", "herida cortante en mano derecha", "herida cortante en mano"),
    ("ME MORDIO UN GATO CALLEJERO", "mordedura en la mano derecha", "mordedura"),
    ("ME GOLPEO MI NOVIO", "dolor en el abdomen por golpe de novio", "dolor por golpe de novio"),
])
def test_los_filtros_quitan_lo_inventado(original, salida, esperada):
    assert f.quitar_parte_inventada(original, f.quitar_lado_inventado(original, salida)) == esperada


@pytest.mark.parametrize("original, salida", [
    ("ABCESO EN MIEMBRO SUPERIOR DEREHCO", "absceso en miembro superior derecho"),
    ("DOLOR EN MANO IZQ", "dolor en mano izquierda"),
    ("DOLOR DEL LADO DERECHO DEL ABDOMEN", "dolor abdominal del lado derecho"),
    ("ME DUELE LA BARRIGA", "dolor abdominal"),
])
def test_los_filtros_no_tocan_lo_que_la_nota_dice(original, salida):
    assert f.quitar_parte_inventada(original, f.quitar_lado_inventado(original, salida)) == salida


def test_el_articulo_una_no_es_una_mano():
    r = f.revisar("SE CORTO CON UN VIDRIO", "una herida por vidrio")
    assert "mano" not in r["partes_inventadas"]


@pytest.mark.parametrize("original, salida", [
    ("ME ARDE", "ardor general"),
    ("ESTA TEMBLANDO", "temblor"),
    ("ESTA CON MOCOS", "mucosidad nasal"),
    ("TENGO", "dolor abdominal"),
])
def test_el_filtro_de_tramite_nunca_toca_notas_cortas(original, salida):
    assert not f.es_tramite_puro(original, salida)


def test_el_filtro_de_tramite_si_actua_sobre_una_remision():
    assert f.es_tramite_puro("REMITIDO DE OTRO MUNICIPIO", "dolor desde hace 2 horas")


# ---------- lo que la salida pierde o tuerce (reglas 4, 6 y 7), barrido del 2026-09-23 ----------
#
# Frases sinteticas con la forma de los fallos reales del barrido de 3.087 notas.
# Los casos de 'no marca' son los falsos positivos que tuvo cada detector en su
# primera version, o traducciones correctas que un detector ingenuo marcaria.

@pytest.mark.parametrize("original, salida", [
    ("SECUNDIGESTANTE DE 30 SEMANAS QUE CONSULTA POR DOLOR DE CABEZA Y ZUMBIDO EN LOS OIDOS",
     "cefalea y zumbido en oidos"),
    ("PACIENTE CON 11 SEMANAS DE GESTACION QUE INGRESA REFIRIENDO SANGRADO VAGINAL", "sangrado vaginal"),
    ("PRIMIGESTANTE DE 9 SMS CON VOMITO Y DIARREA", "vomito y diarrea"),
    ("TENGO PRUEBA DE EMBARAZO EN SANGRE POSITIVA Y DOLOR BAJITO", "dolor en hipogastrio"),
    # errata en la unidad y en 'gestacion'
    ("PACIENTE CON 30.2 SEMASN DE GESTAICON, DOLOR DE CABEZA", "cefalea"),
])
def test_atrapa_el_embarazo_perdido(original, salida):
    r = f.revisar(original, salida)
    assert "embarazo_perdido" in r["banderas"]
    assert f.es_fallo(r)


@pytest.mark.parametrize("original, salida", [
    # falso positivo real: la edad gestacional es la del recien nacido
    ("RECIEN NACIDO DE 37 SEMANAS DE GESTACION, SE CAYO DE LA CAMA", "trauma por caida en recien nacido"),
    # la nota no afirma el embarazo
    ("ME DUELE EL ABDOMEN Y NO SE SI ESTOY EMBARAZADA", "dolor abdominal"),
    ("SANGRADO VAGINAL, SE SOSPECHA EMBARAZO", "sangrado vaginal"),
    ("ANTECEDENTES: HTA GESTACIONAL. DOLOR DEBAJO DEL SENO", "dolor debajo del seno"),
    # la salida lo conserva sin decir la palabra
    ("GESTANTE DE 38 SEMANAS CON CONTRACCIONES, MOVIMIENTOS FETALES ACTIVOS",
     "contracciones y movimientos fetales activos"),
    ("PRIMIGESTANTE DE 12 SEMANAS CON SANGRADO", "sangrado vaginal en embarazo de 12 semanas"),
    ("14 SEMANAS DE GESTACION, BOTANDO LIQUIDO", "salida de liquido amniotico"),
])
def test_no_marca_embarazo_conservado_o_no_afirmado(original, salida):
    assert not f.embarazo_perdido(original, salida)


def test_un_descarte_de_gestante_es_descarte_no_embarazo_perdido():
    # una sola cosa por detector: eso ya lo marca descarte_falso
    assert not f.embarazo_perdido("GESTANTE DE 40 SEMANAS CON DOLOR", "sin motivo clinico")


@pytest.mark.parametrize("original, salida", [
    ("CREO QUE SE ME REACTIVO LA MIASTENIA", "mialgia muscular relacionada con miastenia"),
    ("LE HICIERON RX Y AL PARECER TIENE FRACTURA", "fractura confirmada por radiografia"),
    # la palabra dudada sale traducida, no literal
    ("CREO QUE TENGO LA PRESION ALTA", "cifras tensionales elevadas"),
    ("REMITIDA POR SOSPECHA DE ABSCESO PERIAMIGDALINO", "absceso periamigdalino"),
    ("CREO TENGO UNA INFECCION URINARIA", "infeccion urinaria"),
    ("PACIENTE CON PRESUNTA VIOLENCIA DE GENERO", "trauma relacionado con violencia de genero"),
])
def test_atrapa_la_duda_vuelta_certeza(original, salida):
    r = f.revisar(original, salida)
    assert "duda_a_certeza" in r["banderas"]
    assert f.es_fallo(r)


@pytest.mark.parametrize("original, salida", [
    # la salida conserva la duda
    ("CREO QUE TENGO LA PRESION ALTA", "posible elevacion de cifras tensionales"),
    ("SE CAYO Y AL PARECER SE FRACTURO", "trauma por caida con sospecha de fractura"),
    ("PROBABLE PIELONEFRITIS", "pielonefritis probable"),
    # lo dudado era la fractura, no la mano: omitir la duda no es afirmarla
    ("CREO QUE ME FRACTURE LA MANO", "dolor en mano"),
    # 'posible' sin duda clinica detras
    ("CUERPO EXTRANO EN NARIZ, NO FUE POSIBLE EXTRAERLO", "cuerpo extrano en nariz"),
    # la nota lo afirma fuera de la duda
    ("SOSPECHA DE NEUMONIA, RX CONFIRMA NEUMONIA", "neumonia"),
    # 'como que' describe, no duda
    ("SIENTO COMO QUE ME AHOGO", "sensacion de ahogo"),
])
def test_no_marca_la_duda_conservada_u_omitida(original, salida):
    assert not f.duda_a_certeza(original, salida)


@pytest.mark.parametrize("original, salida", [
    # la negacion deformada: el modelo escribio otra palabra
    ("DOLOR EN CADERA IZQUIERDA DESDE EL DOMINGO NIEGA TRAUMAS", "dolor en cadera izquierda nieta traumas"),
    ("DOLOR PELVICO, NIEGA PERDIDAS VAGINALES", "dolor pelvico y nega perdidas vaginales"),
    # la negacion volteada
    ("CON HIPO DESDE AYER, NIEGA DOLOR EN EL PECHO", "dolor toracico inespecifico"),
    ("DOLOR ABDOMINAL, NIEGA VOMITO", "dolor abdominal y vomito"),
])
def test_atrapa_la_negacion_perdida(original, salida):
    r = f.revisar(original, salida)
    assert "negacion_perdida" in r["banderas"]
    assert f.es_fallo(r)


@pytest.mark.parametrize("original, salida", [
    # negaciones validas en la salida
    ("DOLOR DE GARGANTA, NIEGA DIARREA Y/O EMESIS", "odinofagia, diarrea negada, emesis negada"),
    ("DOLOR DE GARGANTA, NIEGA DIARREA Y/O EMESIS", "odinofagia, diarrea y emesis negadas"),
    ("CEFALEA, NIEGA FIEBRE", "cefalea sin fiebre"),
    ("DOLOR ABDOMINAL, NIEGA CUADRO DE VOMITO Y DIARREA", "dolor abdominal, niega vomito y diarrea"),
    # 'niega dolor toracico' no se contradice con cualquier dolor
    ("DOLOR ABDOMINAL, NIEGA DOLOR TORACICO", "dolor abdominal"),
    # la nota lo afirma aparte
    ("VOMITO DESDE AYER, NIEGA VOMITO CON SANGRE", "vomito desde ayer"),
    # antecedentes negados
    ("ALERGIAS: NIEGA. QUIRURGICOS: NIEGA. DOLOR LUMBAR", "dolor lumbar"),
    # palabra real parecida a 'niega'
    ("DEPOSICIONES NEGRAS, NIEGA FIEBRE", "diarrea negra"),
])
def test_no_marca_una_negacion_bien_conservada(original, salida):
    assert not f.negacion_perdida(original, salida)


@pytest.mark.parametrize("original, salida", [
    ("CEFALEA DESDE ANTIER", "cefalea desde ayer"),
    ("DOLOR DE OIDO DESDE ANTENOCHE", "otalgia desde ayer noche"),
    # el 2 si esta en la nota: numero_inventado no lo ve
    ("FIEBRE HACE 3 DIAS, 2 VOMITOS", "fiebre de 2 dias"),
    ("TOS DESDE HACE 2 DIAS", "tos de 72 horas"),
    ("PRIMIGESTANTE DE 37 SEMANAS CON CONTRACCIONES", "contracciones en embarazo de 38 semanas"),
])
def test_atrapa_la_duracion_cambiada(original, salida):
    r = f.revisar(original, salida)
    assert "duracion_cambiada" in r["banderas"]
    assert f.es_fallo(r)


@pytest.mark.parametrize("original, salida", [
    # equivalencias
    ("FIEBRE DESDE AYER", "fiebre de 24 horas"),
    ("FIEBRE DESDE AYER", "fiebre desde hace 1 dia"),
    ("DOLOR HACE 8 DIAS", "dolor de 1 semana"),
    ("DOLOR DESDE ANOCHE", "dolor desde ayer"),
    ("GESTANTE DE 38.6 SEMANAS CON CONTRACCIONES", "contracciones en gestacion de 38 semanas"),
    ("GESTACION DE 6+3 SEMANAS, SANGRADO", "sangrado en gestacion de 6 semanas"),
    ("DE 2 A 3 DIAS CON FIEBRE", "fiebre de 2 dias"),
    # erratas de la unidad en la nota
    ("11 IAS DE EVOLUCION DE DOLOR LUMBAR", "dolor lumbar de 11 dias"),
    # falsos positivos reales de la primera version
    ("EPISTAXIS DESDE LAS 16, RETIRAR TAPONAMIENTO EN 12 HORAS", "epistaxis desde las 16 horas"),
    ("38 SEMANAS, INDUCCION DE PARTO PARA EL DIA DE HOPY", "induccion de parto para hoy"),
    # sin duracion en la nota no hay nada que cambiar: eso es numero_inventado
    ("DOLOR DESDE EL MARTES", "dolor de 3 dias"),
])
def test_no_marca_una_duracion_equivalente(original, salida):
    assert not f.duracion_cambiada(original, salida)


@pytest.mark.parametrize("original, salida", [
    ("REMITIDA POR DR PEREZ POR HERNIA DISCAL", "hernia discal por dr perez"),
    ("ME HICIERON UNA CIRUGIA EN AVIDANTI", "posoperatorio en avidanti"),
    ("TRAUMA, DERIVADO DEL HOSPITAL SANTA SOFIA", "trauma derivado del hospital santa sofia"),
    ("TOS, SE DERIVA A CITA PRIORITARIA POR SES HUC", "tos, cita prioritaria por ses huc"),
    ("AFILIADO A NUEVA EPS, FIEBRE", "fiebre, afiliado a nueva eps"),
])
def test_atrapa_un_identificador_en_la_salida(original, salida):
    r = f.revisar(original, salida)
    assert "identificador_en_salida" in r["banderas"]
    assert f.es_fallo(r)


@pytest.mark.parametrize("original, salida", [
    # 'su eps', 'hospital local' y 'clinica estable' no identifican a nadie
    ("TOS, SE DERIVA A SU EPS", "tos, se deriva a cita prioritaria por su eps"),
    ("TRAUMA, VIENE DEL HOSPITAL LOCAL", "trauma remitido de hospital local"),
    ("CEFALEA, CLINICAMENTE ESTABLE", "cefalea, clinica estable"),
    # 'dr' seguido de una palabra comun, no de un nombre
    ("VALORADO POR EL DR DE TURNO, DOLOR TORACICO", "dolor toracico valorado por dr de turno"),
])
def test_no_marca_lo_que_no_identifica(original, salida):
    assert not f.identificador_en_salida(original, salida)


# ---------- filtros de la sonda ampliada (2026-09-23) ----------

@pytest.mark.parametrize("original, salida, esperada", [
    ("CREO QUE SE ME REACTIVO LA MIASTENIA", "miastenia grave en gestante", "miastenia grave"),
    ("SECUNDIGESTANTE DE 30 SEMANAS CON CEFALEA", "cefalea en gestante de 30 semanas",
     "cefalea en gestante de 30 semanas"),
])
def test_quitar_embarazo_inventado(original, salida, esperada):
    assert f.quitar_embarazo_inventado(original, salida) == esperada


@pytest.mark.parametrize("original, salida, esperada", [
    ("CEFALEA DESDE ANTIER", "cefalea desde ayer", "cefalea desde antier"),
    ("DOLOR DE OIDO DESDE ANTENOCHE", "otalgia desde ayer noche", "otalgia desde antenoche"),
    ("DOLOR DESDE ANTIER Y AYER EMPEORO", "dolor desde ayer", "dolor desde ayer"),
    ("FIEBRE DESDE AYER", "fiebre desde ayer", "fiebre desde ayer"),
])
def test_restaurar_antier(original, salida, esperada):
    assert f.restaurar_antier(original, salida) == esperada


@pytest.mark.parametrize("original, salida, esperada", [
    ("REMITIDA POR DR PEREZ POR HERNIA DISCAL", "hernia discal por neurocx dr perez", "hernia discal por neurocx"),
    ("ME HICIERON TURBINOPLASTIA EN AVIDANTI", "turbinoplastia en avidanti", "turbinoplastia"),
    ("LA VALORO EL DR DE TURNO", "valoracion por dr de turno", "valoracion por dr de turno"),
])
def test_quitar_identificadores(original, salida, esperada):
    assert f.quitar_identificadores(original, salida) == esperada


def test_hernia_es_evidencia_clinica():
    assert f.descarte_falso("REMITIDA POR HERNIA DISCAL", "sin motivo clinico")


def test_quitar_identificadores_no_deja_preposicion_doble_ni_la_remision():
    # salida real de qwen3:14b con el prompt suavizado (2026-09-24)
    assert f.quitar_identificadores("PACIENTE REMITIDA POR DR PEREZ POR HERNIA DISCAL",
                                    "remitida por doctor perez por hernia discal") == "hernia discal"
