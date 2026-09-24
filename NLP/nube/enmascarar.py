# -*- coding: utf-8 -*-
"""
Tapa lo que identifica a una persona en el texto de UNA nota, antes de que salga.

    enmascarar(texto, identidad, nombres) -> (texto_enmascarado, conteo_por_tipo)

LO QUE TAPA, EN ESTE ORDEN
    1. correos y URL                               -> [CORREO] [URL]
    2. el documento del propio paciente            -> [DOC]
    3. fechas completas                            -> [FECHA]
    4. telefonos y numeros de 5 o mas cifras       -> [NUM]
    5. residencia y direccion                      -> [LUGAR]
    6. nombre y apellidos del propio paciente      -> [NOMBRE]
    7. terceros nombrados por contexto (sra, dr,
       madre, acompanado de, remitido por...)      -> [NOMBRE]
    8. nombre + apellido seguidos, sin contexto    -> [NOMBRE]
    9. una palabra que casi solo existe como
       nombre en esta poblacion, donde aparezca    -> [NOMBRE]

    El orden importa: cada etapa ve las marcas de las anteriores como fichas
    opacas, asi que un nombre dentro de una direccion ya tapada no se vuelve a
    contar, y una fecha dentro de un barrio ('barrio 20 de julio') queda tapada
    aunque la etapa de lugar no la reconozca.

LO QUE NO TOCA, A PROPOSITO
    Las duraciones y cifras clinicas: 'hace 3 dias', '36 semanas de gestacion',
    '37.4 semanas', 'desde las 16', '11 kilos', 'eva 8/10', 'ta 120/80',
    'fuerza 5/5'. Ninguna tiene 5 cifras seguidas ni forma de fecha completa, y
    las pruebas de NLP/tests/test_nube.py lo fijan una por una.

LA REGLA DE LA LISTA DE BLOQUEO
    Un nombre de pila que tambien es palabra corriente o clinica (Dolores, Luz,
    Rosa, Blanca, Clara, Severo...) NO se tapa por si solo: se tapa unicamente
    si va pegado a otra parte de la identidad del mismo paciente que si se tapo.

        paciente Dolores Garcia    'dolores musculares'        -> intacto
                                   'paciente dolores garcia'   -> 'paciente [NOMBRE]'

    Lo mismo vale para apellidos que son palabras (Cortes, Rojas, Puerta, Mesa,
    Palma) y para cualquier termino que aparezca en NLP/recursos/*.json. El
    coste es conocido y se acepta: una paciente llamada Luz cuyo nombre aparece
    solo en la nota queda con 'luz' a la vista. Un nombre de pila muy comun,
    sin apellido, sin documento y sin fecha, no identifica; borrar 'dolores' de
    'dolores musculares' si destruye el dato que se va a medir.

POR QUE LA COMPARACION ES SOBRE UNA COPIA PLANA DEL TEXTO
    Las notas vienen en mayusculas, minusculas o mezcladas, con y sin tildes.
    Todo se busca sobre una copia en minusculas y sin tildes que tiene EXACTAMENTE
    la misma longitud que el original (una letra por letra), y las marcas se
    ponen en el original. Asi al modelo le llega la nota como esta en la base
    -mayusculas y tildes incluidas-, con solo lo identificable sustituido: la
    salida en la nube se parece lo mas posible a la que daria la corrida local.

No hay anonimizacion perfecta en texto libre. Esto reduce lo obvio y lo
frecuente; los limites estan escritos en NLP/docs/NUBE.md.
"""

import csv
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache

from NLP import rutas

TIPOS = ("doc", "nombre_paciente", "nombre_tercero", "nombre_suelto", "num", "fecha",
         "correo", "url", "lugar")

_MARCA_DE = {
    "doc": "[DOC]", "nombre_paciente": "[NOMBRE]", "nombre_tercero": "[NOMBRE]",
    "nombre_suelto": "[NOMBRE]", "num": "[NUM]", "fecha": "[FECHA]", "correo": "[CORREO]",
    "url": "[URL]", "lugar": "[LUGAR]",
}

# ==========================================================
# VOCABULARIO
# ==========================================================

# La lista del enunciado del proyecto, mas los nombres y apellidos colombianos
# que tambien son palabras CON SENTIDO EN UNA NOTA: un color que describe una
# lesion o una secrecion, una intensidad, una parte del cuerpo, el objeto de un
# trauma ('golpe con la puerta', 'se cayo de la mesa').
#
# Lo que NO entra, a proposito: apellidos que son palabras corrientes pero sin
# sentido clinico (Vega, Campos, Prado, Rios, Pena, Rubio, Moreno, Torres...).
# Bloquearlos no protege ningun dato de la nota y deja ese apellido a la vista
# cada vez que aparece solo.
#
# Los de la segunda tanda SI tienen sentido clinico y la frecuencia no los
# separa de un apellido: 'largo' lo llevan 1.051 personas y sale en 9 notas
# ('cuello posterior, largo, cerrado' en un tacto vaginal), igual que un
# apellido cualquiera. Medido el 2026-09-23 en la calibracion de 3.000 notas.
BLOQUEO = frozenset("""
dolores luz rosa cruz paz fe esperanza flor alba blanca clara angel angeles amparo
consuelo socorro pilar mercedes victoria rocio soledad reyes sol milagros salud gracia
remedios angustias
blanco claro negro negra negros negras rojo roja rojos rojas amarillo amarilla morado
morada oscuro oscura verde franco franca severo severa fuerte fuertes grande seco seca
duro dura caliente frio frias dulce bravo mora
largo larga corto corta delgado delgada grueso gruesa blando blanda sano sana bueno buena
pared paredes fuente fuentes agua aguas cabello
cortes cortez corte puerta mesa palma palmas espina piedra piedras sierra calle casa
casas sala salas correa cabeza cabezas barriga mano manos pie pies boca ojos pecho
cuello nieto nieta
eva sat
""".split())

# Los de la lista de bloqueo que son SOLO nombre de pila, sin sentido clinico.
_NOMBRES_BLOQUEADOS = frozenset("""
luz rosa cruz paz fe esperanza flor alba angel angeles amparo consuelo socorro pilar
mercedes victoria rocio soledad reyes sol milagros gracia
""".split())

# Partes del cuerpo y sintomas cortos: van como palabra EXACTA y no como raiz,
# porque 'pie' como raiz se comeria a Piedrahita y 'pene' a Penelope.
_CLINICAS_EXACTAS = frozenset("""
ojo ojos mano manos pie pies tos dedo dedos codo codos cara boca pene una unas ano
""".split())

# Nunca forman parte de un nombre por si solas, pero van dentro de muchos
# ('maria del pilar', 'de la cruz', 'san martin').
PARTICULAS = frozenset("de del la las los y e da do dos san santa santo van von mc".split())

# Palabras que no son nombre en ninguna nota: funcion, verbos de la nota, roles,
# tiempo, cifras escritas y los rellenos que aparecen en las columnas de nombre
# cuando falta el dato ('NO REFIERE', 'NN', 'RN'). Una ficha de identidad que
# cae aqui se ignora; una palabra de aqui nunca se toma por nombre de tercero.
VACIAS = frozenset("""
a al ante bajo con contra de del desde durante en entre hacia hasta mediante para por
segun sin sobre tras el la lo los las un una uno unos unas y e o u ni que quien quienes
cual cuales como cuando donde cuanto este esta esto estos estas ese esa eso esos esas
aquel aquella su sus mi mis tu tus le les se me te nos yo ella ellos ellas usted ustedes
muy mas menos tan tanto tambien tampoco ya aun todavia solo sola solamente pero sino
aunque porque pues entonces luego despues antes ademas asi si no nada nadie algo alguien
algun alguna alguno todo toda todos todas otro otra otros otras mismo misma cada vez veces
refiere refieren refirio manifiesta manifiestan presenta presentan presento consulta
consultan consulto acude acuden llega llegan llego ingresa ingresan ingreso trae traen
traido traida traidos dice dicen indica indican informa informan cuenta comenta comentan
relata expresa describe tiene tienen tenia tuvo estan estaba estuvo es son era fue
fueron ha han habia hay hace hizo hacen da dio dan dieron siente sienten sintio nota noto
observa observan encuentra encuentran viene vienen vino va van sale salio queda quedo
pide solicita requiere necesita desea quiere puede pudo debe llama llamo llamado llamada
nombre nombres apellido apellidos vive reside trabaja estudia ser estar tener hacer
paciente pte pcte pac usuario usuaria menor menores bebe nino nina ninos ninas adulto
adulta adultos mayor mayores joven anciano anciana persona personas gestante primigestante
familia familiar familiares acompanante acompanantes cuidador cuidadora acudiente tutor tutora
madre mama padre papa hijo hija hijos hijas hermano hermana hermanos abuelo abuela tio tia
primo prima sobrino sobrina esposo esposa pareja novio novia companero companera cunado
cunada suegro suegra vecino vecina amigo amiga tercero terceros particular policia
bomberos ejercito transito defensa civil crue ambulancia medico medica medicos doctor
doctora dr dra sr sra srta senor senora senorita don dona enfermero enfermera enfermeria
auxiliar jefe especialista general turno urgencias urgencia hospital clinica centro puesto
eps ips sede servicio externa remision remitido remitida remiten valoracion control cita
orden autorizacion traslado egreso triage cama piso sala consultorio
hoy ayer anoche manana tarde noche madrugada dia dias hora horas minuto minutos semana
semanas mes meses ano anos lunes martes miercoles jueves viernes sabado domingo enero
febrero marzo abril mayo junio julio agosto septiembre setiembre octubre noviembre diciembre
dos tres cuatro cinco seis siete ocho nueve diez once doce quince veinte treinta primer
primero primera segundo segunda tercer tercera
nuevo nueva viejo vieja mejor peor pequeno pequena alta bajo baja leve moderado moderada
intenso intensa agudo aguda cronico cronica frecuente constante continuo continua
ocasional repentino subito progresivo desconocido desconocida desconocidos indigente
habitante extranjero extranjera venezolano venezolana colombiano colombiana preocupado
preocupada asustado asustada tranquilo tranquila consciente alerta orientado orientada
estable motivo cuadro evolucion clinico sintomas sintoma signos antecedente antecedentes
niega asociado asociada posterior previo previa actual actualmente aproximadamente aprox
trabajo colegio escuela via publica carro moto bicicleta finca barrio vereda municipio
ciudad pueblo sector zona rural urbana nn rn sn na x xx sin refiere dato datos registra
reporta lactante neonato recien nacido nacida infante preescolar escolar adolescente
gemelo gemela
ortopedista ortopedia pediatra pediatria ginecologo ginecologa ginecologia cirujano
cirujana internista medicina interna neurologo neurologa neurocirujano neurocx urologo
urologa psiquiatra psicologo psicologa cardiologo cardiologa oftalmologo oftalmologa
otorrino dermatologo dermatologa radiologo anestesiologo odontologo odontologa
nutricionista fisioterapeuta terapeuta trabajadora social especialidad residente interno
""".split())

# Raices clinicas: una ficha de identidad que empieza asi no se tapa sola. Es el
# seguro contra el peor error posible aqui, borrar el sintoma que se va a medir
# porque coincide con el apellido del paciente.
_RAIZ_CLINICA = re.compile(r"""^(?:
    dolor|duel|dolid|fiebre|febril|vomit|emesis|diarre|sangr|hemorr|mareo|marea|cefal|
    trauma|golpe|golpi|caida|herid|cortad|cortan|quemad|quemadur|fractur|fisur|ahog|disnea|
    respir|convuls|desmay|picad|picadur|mordid|mordedur|intoxic|envenen|hinch|inflam|ardor|
    nause|palpit|adormec|debilid|malestar|gripa|gripe|congest|machuc|aplast|torcedur|esguinc|
    luxac|absces|edema|prurit|picazon|alergi|alergic|ronch|infecc|colic|calcul|presion|
    tension|hipertens|hipotens|azucar|glucos|glicem|sincop|orina|embaraz|gestac|gestant|
    contracc|flujo|ansied|depres|suicid|agitac|agitad|accident|atropell|lesion|mancha|
    ampoll|herpes|hongo|irritac|parto|aborto|cirug|sutur|curacion|drenaj|estornud|mocos|
    flema|expector|garganta|abdom|torax|torac|espalda|lumbar|rodilla|tobillo|hombro|brazo|
    pierna|muslo|cadera|oido|oreja|nariz|diente|muela|piel|vagin|testic|enrojec|
    cabez|pecho|cuello|barrig|estomag|ombligo|labio|lengua|encia|ingle|inguin|
    hernia|tumor|masa|bulto|brote|erupc|rasquin|comezon|escalofri|sudor|temblor|
    tembl|debil|cansanc|fatiga|insomn|llanto|irritab|somnol|confus|desorient|
    esputo|epistax|otalg|odinofag|disuri|hematur|melena|rectorr|ictericia|amarill
)""", re.X)


def _plano(texto):
    """Minusculas y sin tildes (para vocabulario, no para texto con posiciones)."""
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def _fichas(texto):
    return re.findall(r"[a-z0-9]+", _plano(texto))


def _vocabulario_de_recursos():
    """
    Toda palabra de NLP/recursos/*.json, claves y significados, salvo dos grupos.

    FUERA: 'geografia', 'instituciones_marcas' y 'no_restaurar_mayuscula' de
    siglas.json. Son nombres propios (la tercera es una lista de formato que
    mezcla terminos con municipios y hasta 'maria'), no vocabulario clinico, y
    varios son apellidos corrientes en Caldas (Marulanda, Neira, Belalcazar,
    Manzanares, Caldas, Ceron, Munar). Meterlos aqui los volveria intapables como
    apellido del paciente. Por lo mismo se restan al final todas las palabras de
    esos grupos y de lugares.csv, aparezcan donde aparezcan ('caldas' tambien
    esta en el significado de una sigla administrativa).
    """
    vocabulario, propios = set(), set()
    fuera = {"geografia", "instituciones_marcas", "no_restaurar_mayuscula"}

    def recorrer(valor):
        if isinstance(valor, str):
            vocabulario.update(_fichas(valor))
        elif isinstance(valor, dict):
            for clave, sub in valor.items():
                if not str(clave).startswith("_"):
                    vocabulario.update(_fichas(clave))
                recorrer(sub)
        elif isinstance(valor, list):
            for sub in valor:
                recorrer(sub)

    for ruta in (rutas.SIGLAS, rutas.COLOQUIALISMOS, rutas.TERMINOLOGIA_CLINICA):
        try:
            datos = json.load(open(ruta, encoding="utf-8"))
        except OSError:
            continue
        for grupo, valor in datos.items():
            # las claves que empiezan por _ son notas del autor, no terminos,
            # salvo las listas de siglas y expresiones que si son terminos
            if grupo in fuera:
                if grupo != "no_restaurar_mayuscula":
                    propios.update(_fichas(" ".join(str(k) for k in valor)))
                continue
            if grupo.startswith("_") and not isinstance(valor, list):
                continue
            recorrer(valor)
    try:
        with open(rutas.LUGARES, encoding="utf-8-sig", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                propios.update(_fichas(fila.get("municipio", "")))
                propios.update(_fichas(fila.get("departamento", "")))
    except OSError:
        pass
    return frozenset(p for p in vocabulario - propios if len(p) >= 3 and not p.isdigit())


RECURSOS = _vocabulario_de_recursos()


def _cargar_lugares():
    """Municipios y departamentos DIVIPOLA, planos, para no tomar 'villa maria'
    por el nombre de una persona."""
    lugares = set()
    try:
        with open(rutas.LUGARES, encoding="utf-8-sig", newline="") as archivo:
            for fila in csv.DictReader(archivo):
                for campo in ("municipio", "departamento"):
                    if fila.get(campo):
                        lugares.add(" ".join(_fichas(fila[campo])))
    except OSError:
        pass
    return frozenset(lugares)


LUGARES = _cargar_lugares()


@lru_cache(maxsize=None)
def es_comun(palabra):
    """Palabra corriente o clinica: no se tapa sola ni se toma por nombre."""
    return (palabra in BLOQUEO or palabra in RECURSOS or palabra in _CLINICAS_EXACTAS
            or bool(_RAIZ_CLINICA.match(palabra)))


def es_clinica(palabra):
    """Solo lo clinico, sin los nombres de la lista de bloqueo. Lo usa la etapa
    de lugar: 'barrio la cruz' es un barrio, 'barrio ... dolor' ya no."""
    return (palabra in _CLINICAS_EXACTAS or bool(_RAIZ_CLINICA.match(palabra))
            or (palabra in RECURSOS and palabra not in BLOQUEO))


def es_vacia(palabra):
    return palabra in VACIAS or palabra in PARTICULAS


# ==========================================================
# IDENTIDAD DEL PROPIO PACIENTE
# ==========================================================

@dataclass(frozen=True)
class Identidad:
    """
    Lo que dice DIM_TRIAGE de quien es el paciente de ESA nota. Vive solo en
    memoria: se construye con las columnas GPA* al bajar la nota y se tira al
    terminar. Nunca se escribe a disco.

    fuertes     fichas que se tapan donde aparezcan (y con erratas leves)
    bloqueadas  fichas que son palabra corriente: solo pegadas a una fuerte
    documento   las cifras del documento, si tiene 5 o mas
    doc_texto   el documento entero si lleva letras (pasaporte, permiso)
    """
    fuertes: frozenset = frozenset()
    bloqueadas: frozenset = frozenset()
    documento: str = ""
    doc_texto: str = ""

    @classmethod
    def de_valores(cls, documento="", nombres=(), apellidos=()):
        fuertes, bloqueadas = set(), set()
        for valor in list(nombres) + list(apellidos):
            for ficha in _fichas(valor):
                if len(ficha) < 3 or ficha.isdigit() or es_vacia(ficha):
                    continue
                (bloqueadas if es_comun(ficha) else fuertes).add(ficha)
        documento = "" if documento is None else str(documento).strip()
        if documento.lower() in ("nan", "none"):
            documento = ""
        cifras = re.sub(r"\D", "", documento)
        letras = re.sub(r"[^0-9a-z]", "", _plano(documento))
        return cls(frozenset(fuertes), frozenset(bloqueadas),
                   cifras if len(cifras) >= 5 else "",
                   letras if (letras != cifras and len(letras) >= 5) else "")

    @classmethod
    def de_fila(cls, fila):
        """Desde una fila de DIM_TRIAGE (dict o Series con las columnas GPA*)."""
        def valor(columna):
            v = fila.get(columna)
            # NaN de pandas: str() lo volveria la ficha 'nan'
            if v is None or (isinstance(v, float) and v != v):
                return ""
            return str(v)
        return cls.de_valores(valor("GPADOCUME"),
                              (valor("GPANOMBRE"), valor("GPASEGNOM")),
                              (valor("GPAAPELLI"), valor("GPASEGAPE")))


# ==========================================================
# NOMBRES CONOCIDOS (para terceros)
# ==========================================================

@dataclass(frozen=True)
class Nombres:
    """
    Las fichas que en esta poblacion son nombre de pila o apellido. Se arma en
    memoria (ver exportar.cargar_nombres) y nunca se escribe.

    nombres, apellidos
        Salen de un GROUP BY sobre las columnas de nombre de DIM_TRIAGE, SIN las
        que en las notas funcionan como palabra ('blando', 'ruedas', 'falla',
        'quinto': apellidos reales que aparecen en cientos de notas). Deciden si
        lo que sigue a 'madre' o a 'acompanado de' es un nombre.
    sueltos
        Las que casi solo existen como nombre: aparecen en 2 notas o menos de
        todo el corpus, o en menos de 1 nota por cada 50 personas que se llaman
        asi. Se tapan donde aparezcan, sin necesidad de contexto: es lo que
        atrapa la firma suelta al final de una nota. Medido el 2026-09-23 sobre
        95.405 notas: de 6.555 fichas de nombre, 5.893 no aparecen en ninguna.
    """
    nombres: frozenset = frozenset()
    apellidos: frozenset = frozenset()
    sueltos: frozenset = frozenset()

    def conocido(self, palabra):
        return palabra in self.nombres or palabra in self.apellidos


# ==========================================================
# MECANICA: copia plana letra a letra
# ==========================================================

def _plano_1a1(texto):
    """Minusculas y sin tildes, con la MISMA longitud que el original."""
    salida = []
    for c in texto:
        d = unicodedata.normalize("NFKD", c.lower())
        base = "".join(x for x in d if not unicodedata.combining(x))
        salida.append(base[0] if base else c)
    return "".join(salida)


_FICHA = re.compile(r"\[[A-Z]+\]|[a-z0-9]+")
_ES_MARCA = re.compile(r"^\[[A-Z]+\]$")


def _aplicar(texto, plano, tramos):
    """Pone las marcas en el original y en la copia plana a la vez.

    tramos: (inicio, fin, tipo). Se resuelven solapes quedandose con el que
    empieza antes y, a igualdad, con el mas largo."""
    elegidos, fin_previo = [], -1
    for ini, fin, tipo in sorted(tramos, key=lambda t: (t[0], -(t[1] - t[0]))):
        if ini >= fin_previo and fin > ini:
            elegidos.append((ini, fin, tipo))
            fin_previo = fin
    conteo = Counter()
    for ini, fin, tipo in reversed(elegidos):
        marca = _MARCA_DE[tipo]
        texto = texto[:ini] + marca + texto[fin:]
        plano = plano[:ini] + marca + plano[fin:]
        conteo[tipo] += 1
    return texto, plano, conteo


# ==========================================================
# 1-4. PATRONES
# ==========================================================

_CORREO = re.compile(r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
_URL = re.compile(r"\b(?:https?://|www\.)\S+")

_MES = r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)"
_MES_CORTO = r"(?:ene|feb|mar|abr|may|jun|jul|ago|sep|sept|set|oct|nov|dic)"
_DIA = r"(?:0?[1-9]|[12]\d|3[01])"
_MES_NUM = r"(?:0?[1-9]|1[0-2])"
_ANIO4 = r"(?:19|20)\d{2}"

FECHAS = [
    # 25/12/2024, 25-12-24, 25.12.2024
    re.compile(rf"(?<![\d/.-]){_DIA}\s*([/.-])\s*{_MES_NUM}\s*\1\s*(?:{_ANIO4}|\d{{2}})(?![\d/])"),
    # 2024-12-25
    re.compile(rf"(?<![\d/.-]){_ANIO4}([/.-]){_MES_NUM}\1{_DIA}(?![\d/])"),
    # 25 de diciembre (de 2024)
    re.compile(rf"\b{_DIA}\s*(?:de\s+|del\s+|/|-|\.)?\s*{_MES}\b(?:\s*(?:de|del|/|-|,)?\s*{_ANIO4}\b)?"),
    # 25-dic-2024, 25 dic 24
    re.compile(rf"\b{_DIA}\s*[-/. ]\s*{_MES_CORTO}\.?\s*[-/. ]\s*(?:{_ANIO4}|\d{{2}})\b"),
    # diciembre de 2024, dic/2024
    re.compile(rf"\b(?:{_MES}|{_MES_CORTO})\s*[./-]?\s*(?:de|del)?\s*{_ANIO4}\b"),
]

# dd/mm sin ano: solo si no puede ser una escala. 'eva 8/10', 'fuerza 5/5' y
# '1/2 tableta' se quedan; '23/09', '05/10' y 'el 3/9' se tapan.
_DIA_MES = re.compile(rf"(?<![\d/.]){_DIA}/{_MES_NUM}(?![\d/])")
_PISTA_FECHA = re.compile(
    r"(?:\b(?:el|dia|fecha|hoy|fum|fur|fpp|desde|hasta|del|cita|control|ingreso|egreso|"
    r"cirugia|parto|nacio|nacimiento)\s*:?\s*)$")


def _dia_mes_es_fecha(plano, m):
    dia, mes = m.group().split("/")
    if dia.startswith("0") or mes.startswith("0") or int(dia) >= 13:
        return True
    return bool(_PISTA_FECHA.search(plano[max(0, m.start() - 14):m.start()]))


_TELEFONO_PISTA = re.compile(
    r"\b(?:tel|telf|telefono|tels|cel|cels|celular|movil|whatsapp|wsp|contacto|"
    r"numero de contacto|llamar al)\b\.?\s*:?\s*((?:\+?\s*57\s*)?\d[\d\s.-]{5,}\d)")
_TELEFONO_FORMA = re.compile(r"(?<![\d.,])(?:\+?57\s*)?\d{3}[\s.-]\d{3}[\s.-]?\d{4}(?![\d.,])")
_MILES = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3}){2,}(?![\d])")
_CIFRAS = re.compile(r"\d{5,}")


def _tramos_patrones(plano, identidad):
    tramos = []
    tramos += [(m.start(), m.end(), "correo") for m in _CORREO.finditer(plano)]
    tramos += [(m.start(), m.end(), "url") for m in _URL.finditer(plano)]
    return tramos


def _tramos_documento(plano, identidad):
    tramos = []
    if identidad.documento:
        patron = r"(?<!\d)" + r"[\s.,-]?".join(identidad.documento) + r"(?!\d)"
        tramos += [(m.start(), m.end(), "doc") for m in re.finditer(patron, plano)]
    if identidad.doc_texto:
        patron = r"(?<![a-z0-9])" + re.escape(identidad.doc_texto) + r"(?![a-z0-9])"
        tramos += [(m.start(), m.end(), "doc") for m in re.finditer(patron, plano)]
    return tramos


def _tramos_fechas(plano):
    tramos = []
    for patron in FECHAS:
        tramos += [(m.start(), m.end(), "fecha") for m in patron.finditer(plano)]
    tramos += [(m.start(), m.end(), "fecha") for m in _DIA_MES.finditer(plano)
               if _dia_mes_es_fecha(plano, m)]
    return tramos


def _tramos_numeros(plano):
    tramos = []
    for m in _TELEFONO_PISTA.finditer(plano):
        if len(re.sub(r"\D", "", m.group(1))) >= 7:
            tramos.append((m.start(1), m.end(1), "num"))
    tramos += [(m.start(), m.end(), "num") for m in _TELEFONO_FORMA.finditer(plano)]
    tramos += [(m.start(), m.end(), "num") for m in _MILES.finditer(plano)]
    tramos += [(m.start(), m.end(), "num") for m in _CIFRAS.finditer(plano)]
    return tramos


# ==========================================================
# 5. RESIDENCIA Y DIRECCION
# ==========================================================

_RESIDENCIA = re.compile(
    # 'recide', 'recidente': la errata mas comun, medida en la calibracion
    r"\b(?:re[sc]id(?:e|en|ente|entes|enciad[oa])|domiciliad[oa]|vive|viven|habita)"
    r"\s+(?:de|en|del|por)\b"
    r"|\b(?:barrio|brr|bario|vereda|vda|corregimiento|urbanizacion|urb|conjunto residencial"
    r"|asentamiento)\b\.?"
    r"|\bb/"
    r"|\b(?:direccion|dir de residencia|domicilio)\b\s*:?")
_DIRECCION = re.compile(
    r"\b(?:calle|cll|carrera|cra|kra|kr|avenida|avda|diagonal|transversal|manzana|mz|"
    r"apto|apartamento)\s*\.?\s*\d+[a-z]?\b"
    r"(?:\s*(?:#|no\.?|n\xb0|nro\.?|numero)?\s*\d+[a-z]?\b(?:\s*-\s*\d+[a-z]?\b)?)?"
    r"(?:\s*(?:casa|lote|torre|bloque|apto|apartamento|piso|int|interior|mz|manzana)"
    r"\s*\.?\s*\d+[a-z]?\b)*")

# lo que corta un lugar: un verbo, un conector, una unidad de tiempo
_CORTE_LUGAR = frozenset("""
quien que con y e o consulta consulto consultan refiere presenta presento desde hace por
porque paciente pte cuando donde pero tiene trae traen traido traida acude ingresa llega
sin para al se le su sus a hacia es fue era esta estaba ahora hoy ayer anoche
dia dias hora horas semana semanas mes meses ano anos minuto minutos
""".split())
_ARTICULOS = frozenset("el la los las de del".split())
_MAX_FICHAS_LUGAR = 6


def _tramos_lugar(plano):
    """
    'residente en X', 'vive en X', 'barrio X', 'vereda X', 'direccion X' -> la X.

    La X termina en la siguiente coma o punto, y ANTES si aparece un verbo o un
    conector ('vive en neira CON su madre', 'residente de chinchina QUIEN
    consulta'), un termino clinico, una unidad de tiempo, o se pasa de seis
    palabras. Sin ese corte, una nota sin comas perderia el motivo entero
    detras de su residencia.
    """
    tramos = [(m.start(), m.end(), "lugar") for m in _DIRECCION.finditer(plano)]
    fichas = list(_FICHA.finditer(plano))
    for m in _RESIDENCIA.finditer(plano):
        es_direccion = plano[m.start():m.start() + 3] in ("dir", "dom")
        tope = _MAX_FICHAS_LUGAR + 2 if es_direccion else _MAX_FICHAS_LUGAR
        j = next((k for k, f in enumerate(fichas) if f.start() >= m.end()), None)
        if j is None or not re.fullmatch(r"[\s:.#-]*", plano[m.end():fichas[j].start()]):
            continue
        inicio = fin = None
        contenido = 0
        for k in range(j, len(fichas)):
            if k > j and re.search(r"[,;:()\n]|\.(?:\s|$)", plano[fichas[k - 1].end():fichas[k].start()]):
                break
            palabra = fichas[k].group()
            articulo = palabra in _ARTICULOS or palabra in PARTICULAS
            if articulo:
                if inicio is None:
                    continue
            elif _ES_MARCA.match(palabra):
                pass
            elif palabra in _CORTE_LUGAR or es_clinica(palabra):
                break
            elif palabra.isdigit() and not es_direccion:
                break
            if inicio is None:
                inicio = fichas[k].start()
            fin = fichas[k].end()
            # los articulos no cuentan: 'vereda el rosario del municipio de neira'
            # son cuatro palabras de lugar, no siete
            contenido += not articulo
            if contenido >= tope:
                break
        if inicio is not None:
            # sin articulos colgando al final ('manizales de' -> 'manizales')
            trozo = plano[inicio:fin]
            while True:
                recortado = re.sub(r"\s+(?:el|la|los|las|de|del|y|san|santa)$", "", trozo)
                if recortado == trozo:
                    break
                trozo = recortado
            if trozo.strip() not in _ARTICULOS:
                tramos.append((inicio, inicio + len(trozo), "lugar"))
    # 'vive en la vereda X' dispara dos veces sobre el mismo sitio: se unen, no
    # se descarta uno de los dos (el descartado podia ser el que llegaba mas lejos)
    unidos = []
    for ini, fin, tipo in sorted(tramos):
        if unidos and ini <= unidos[-1][1]:
            unidos[-1] = (unidos[-1][0], max(fin, unidos[-1][1]), tipo)
        else:
            unidos.append((ini, fin, tipo))
    return unidos


# ==========================================================
# 6. NOMBRE Y APELLIDOS DEL PROPIO PACIENTE
# ==========================================================

def _distancia(a, b, tope):
    """Levenshtein con corte: devuelve tope + 1 en cuanto se pasa."""
    if abs(len(a) - len(b)) > tope:
        return tope + 1
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        if min(actual) > tope:
            return tope + 1
        previa = actual
    return previa[-1]


def _errata_de(palabra, identidad):
    """
    Una errata leve de una ficha fuerte ('gonzales' por 'gonzalez').

    Solo si es seguro: ficha de 6+ letras, misma primera letra, una letra de
    diferencia (dos desde 10 letras), y la palabra de la nota no es corriente ni
    clinica. 'medica' esta a una letra de 'medina', y por eso esta ultima
    condicion no es opcional.
    """
    if len(palabra) < 5 or es_vacia(palabra) or es_comun(palabra):
        return False
    for ficha in identidad.fuertes:
        if len(ficha) < 6 or ficha[0] != palabra[0]:
            continue
        tope = 2 if len(ficha) >= 10 else 1
        if _distancia(palabra, ficha, tope) <= tope:
            return True
    return False


def _solo_espacio(hueco):
    return re.fullmatch(r"[\s-]*", hueco) is not None


def _tramos_identidad(plano, identidad):
    if not (identidad.fuertes or identidad.bloqueadas):
        return []
    fichas = list(_FICHA.finditer(plano))
    marcada = [False] * len(fichas)
    for i, f in enumerate(fichas):
        palabra = f.group()
        if _ES_MARCA.match(palabra):
            continue
        if palabra in identidad.fuertes or _errata_de(palabra, identidad):
            marcada[i] = True

    # Las bloqueadas solo pegadas a algo ya tapado del mismo paciente:
    # 'dolores garcia' se tapa entero, 'dolores musculares' no se toca.
    def vecina_tapada(i):
        for j in (i - 1, i + 1):
            if not 0 <= j < len(fichas):
                continue
            a, b = (fichas[j], fichas[i]) if j < i else (fichas[i], fichas[j])
            if not _solo_espacio(plano[a.end():b.start()]):
                continue
            if marcada[j] or fichas[j].group() == "[NOMBRE]":
                return True
        return False

    cambio = True
    while cambio:
        cambio = False
        for i, f in enumerate(fichas):
            if not marcada[i] and f.group() in identidad.bloqueadas and vecina_tapada(i):
                marcada[i] = cambio = True

    return _unir(fichas, marcada, plano, "nombre_paciente")


def _unir(fichas, marcada, plano, tipo):
    """Fichas marcadas y seguidas (solo espacio entre ellas) -> un solo tramo."""
    tramos, i = [], 0
    while i < len(fichas):
        if not marcada[i]:
            i += 1
            continue
        inicio, fin = fichas[i].start(), fichas[i].end()
        i += 1
        while i < len(fichas) and marcada[i] and _solo_espacio(plano[fin:fichas[i].start()]):
            fin = fichas[i].end()
            i += 1
        tramos.append((inicio, fin, tipo))
    return tramos


# ==========================================================
# 7-8. TERCEROS
# ==========================================================

# Tras un trato ('sra', 'doctor') casi siempre viene un nombre: basta con que la
# palabra no sea corriente. Tras un parentesco o un 'remitido por' puede venir
# cualquier cosa ('madre refiere', 'remitido por medico general'): ahi se exige
# ademas que la palabra sea un nombre conocido en esta poblacion.
#
# 'dr' y 'dra' van con los parentescos y no con los tratos: en estas notas
# tambien abrevian 'derecho' y 'derecha' ('ojo dr enrojecido', 'mano dra').
_TRATO = r"sr|sra|srta|senor|senora|senorita|don|dona|doctor|doctora|dctor|dotor"
_PARENTESCO = (
    r"dr|dra|hij[oa]s?\s+de|madre|mama|padre|papa|espos[oa]|companer[oa]|"
    r"acompanad[oa]\s+(?:de|por)|traid[oa]\s+por|remitid[oa]\s+por|familiar|herman[oa]|"
    r"abuel[oa]|ti[oa]|prim[oa]|sobrin[oa]|niet[oa]|cunad[oa]|suegr[oa]|novi[oa]|pareja|"
    r"vecin[oa]|amig[oa]|acudiente|cuidador[a]?|enfermer[oa]|jefe|medic[oa]|llamad[oa]|"
    r"de\s+nombre|se\s+llama|nombre|"
    # quien atendio o mando: casi siempre un medico con nombre propio
    r"(?:citad|valorad|atendid|derivad|enviad|intervenid|operad|ordenad|indicad|"
    r"formulad|comentad)[oa]s?\s+(?:por|con)")
_DISPARADOR = re.compile(rf"\b(?:(?P<trato>{_TRATO})|(?P<parentesco>{_PARENTESCO}))\b")
_RELLENO = frozenset("su sus el la los las de del por mi nombre llamado llamada quien se llama un una".split())
_MAX_NOMBRE = 3


def _parece_doctor(palabra):
    """'docrore', 'doctro', 'dotora': el trato con errata. Medido el 2026-09-23:
    'EL DOCRORE <apellido>' se escapaba. 'dolor' esta a dos letras de 'doctor',
    y por eso se descarta todo lo clinico antes de comparar."""
    if not (5 <= len(palabra) <= 8) or palabra[0] != "d" or es_comun(palabra):
        return False
    if palabra in ("doctor", "doctora", "dotor", "dctor"):
        return False                      # ya los atrapa _TRATO
    return min(_distancia(palabra, "doctor", 2), _distancia(palabra, "doctora", 2)) <= 2


_NO_NOMBRE = re.compile(r"(?:mente|cion|sion|ando|iendo)$")


def _parece_nombre(ficha, palabra, texto, nombres, mixto, trato):
    if (len(palabra) < 3 or not palabra.isalpha() or es_vacia(palabra)
            or es_comun(palabra)):
        return False
    if trato:
        return True
    if nombres is not None and nombres.conocido(palabra):
        return True
    # en una nota escrita en mayusculas y minusculas, 'Maria' tras 'madre' es un
    # nombre aunque no este en la lista. 'Previamente' no: la mayuscula de un
    # adverbio o de un gerundio es la de principio de frase.
    original = texto[ficha.start():ficha.end()]
    return (mixto and original[:1].isupper() and original[1:].islower()
            and not _NO_NOMBRE.search(palabra))


def _es_mixto(texto):
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return False
    mayus = sum(c.isupper() for c in letras)
    return 0 < mayus < 0.5 * len(letras)


_ABREVIATURAS = frozenset("sr sra srta dr dra".split())


def _disparadores(plano, fichas):
    """(fin_del_disparador, es_trato, admite_punto) de cada 'sra', 'madre',
    'citado por'... y de cada 'doctor' mal escrito.

    El punto solo se salta tras una abreviatura ('dr. perez'). Tras cualquier
    otra cosa es fin de frase: 'en compania de madre y esposo. Previamente
    sana' no lleva ningun nombre (falso positivo de la calibracion)."""
    salida = [(m.end(), m.group("trato") is not None, m.group() in _ABREVIATURAS)
              for m in _DISPARADOR.finditer(plano)]
    salida += [(f.end(), False, False) for f in fichas if _parece_doctor(f.group())]
    return salida


def _tramos_terceros(texto, plano, nombres):
    fichas = list(_FICHA.finditer(plano))
    mixto = _es_mixto(texto)
    marcada = [False] * len(fichas)
    for fin_disparador, trato, admite_punto in _disparadores(plano, fichas):
        j = next((k for k, f in enumerate(fichas) if f.start() >= fin_disparador), None)
        hueco = r"[\s.,:;-]*" if admite_punto else r"[\s,:;-]*"
        if j is None or not re.fullmatch(hueco, plano[fin_disparador:fichas[j].start()]):
            continue
        # rellenos: 'acompanada de SU madre', 'hijo de LA senora', 'de NOMBRE', y
        # basura corta que no es nombre ('citada por ELD <nombre>')
        saltos = 0
        while j < len(fichas) and saltos < 3 and (
                fichas[j].group() in _RELLENO
                or (len(fichas[j].group()) <= 3 and fichas[j].group().isalpha()
                    and not (nombres and nombres.conocido(fichas[j].group())))):
            j += 1
            saltos += 1
        tomados, k = 0, j
        while k < len(fichas) and tomados < _MAX_NOMBRE:
            ficha = fichas[k]
            if k > j and not _solo_espacio(plano[fichas[k - 1].end():ficha.start()]):
                break
            palabra = ficha.group()
            # el nombre de pila ya tapado por la etapa del paciente: el apellido
            # que lo sigue es del mismo nombre ('madre [NOMBRE] lopez')
            if palabra == "[NOMBRE]":
                tomados += 1
                k += 1
                continue
            if _parece_nombre(ficha, palabra, texto, nombres, mixto, trato):
                marcada[k] = True
                tomados += 1
                k += 1
                continue
            # un apellido que es palabra de la lista de bloqueo, DESPUES de un
            # nombre ya tomado: 'dr. [NOMBRE] franco', 'hijo de ana cortes'. Solo
            # las de la lista de bloqueo, nunca una raiz clinica.
            if tomados and palabra in BLOQUEO and not _RAIZ_CLINICA.match(palabra) \
                    and palabra not in _CLINICAS_EXACTAS:
                marcada[k] = True
                tomados += 1
                k += 1
                continue
            # particula DENTRO de un nombre: 'maria del carmen'
            if tomados and palabra in PARTICULAS:
                siguiente = k + 1
                while siguiente < len(fichas) and fichas[siguiente].group() in PARTICULAS:
                    siguiente += 1
                if (siguiente < len(fichas)
                        and _parece_nombre(fichas[siguiente], fichas[siguiente].group(),
                                           texto, nombres, mixto, trato)):
                    for x in range(k, siguiente):
                        marcada[x] = True
                    k = siguiente
                    continue
            break
    return _unir(fichas, marcada, plano, "nombre_tercero")


def _tramos_nombre_completo(plano, nombres):
    """
    Nombre y apellido seguidos, sin contexto que los anuncie: 'juan gomez' o
    'gomez lopez'. Exige dos fichas conocidas seguidas y al menos un apellido,
    ninguna corriente ni clinica, y que juntas no sean un municipio ('villa
    maria'). Es la red de seguridad para lo que no trae 'sra' ni 'madre' delante.
    """
    if nombres is None:
        return []
    fichas = list(_FICHA.finditer(plano))

    def conocida(k):
        palabra = fichas[k].group()
        return (len(palabra) >= 3 and palabra.isalpha() and not es_vacia(palabra)
                and not es_comun(palabra) and nombres.conocido(palabra))

    def pegadas(a, b):
        return _solo_espacio(plano[fichas[a].end():fichas[b].start()])

    tramos, i = [], 0
    while i < len(fichas):
        grupo = []
        k = i
        while k < len(fichas) and conocida(k) and (not grupo or pegadas(k - 1, k)):
            grupo.append(k)
            k += 1
        if len(grupo) >= 2:
            palabras = [fichas[x].group() for x in grupo]
            if (any(p in nombres.apellidos for p in palabras)
                    and " ".join(palabras) not in LUGARES):
                tramos.append((fichas[grupo[0]].start(), fichas[grupo[-1]].end(), "nombre_tercero"))
        i = max(k, i + 1)

    # Una ficha conocida pegada a un [NOMBRE] ya puesto es el resto de ese
    # nombre: '[NOMBRE] lopez', 'lopez [NOMBRE]'.
    for k in range(len(fichas)):
        if not conocida(k) or any(a <= fichas[k].start() < b for a, b, _ in tramos):
            continue
        antes = k > 0 and fichas[k - 1].group() == "[NOMBRE]" and pegadas(k - 1, k)
        despues = (k + 1 < len(fichas) and fichas[k + 1].group() == "[NOMBRE]"
                   and pegadas(k, k + 1))
        if antes or despues:
            tramos.append((fichas[k].start(), fichas[k].end(), "nombre_tercero"))
    return tramos


def _tramos_sueltos(plano, nombres):
    """Una ficha que casi solo existe como nombre, donde aparezca (ver Nombres)."""
    if nombres is None or not nombres.sueltos:
        return []
    fichas = list(_FICHA.finditer(plano))
    # 'hospital san jose', 'santa sofia': un santo es una institucion o un
    # lugar, no una persona. El modelo los borra igual (regla 4 del prompt).
    marcada = [f.group() in nombres.sueltos and not es_comun(f.group())
               and not (k and fichas[k - 1].group() in ("san", "santa", "santo"))
               for k, f in enumerate(fichas)]
    return _unir(fichas, marcada, plano, "nombre_suelto")


# ==========================================================
# LA FUNCION
# ==========================================================

def enmascarar(texto, identidad=None, nombres=None):
    """
    Devuelve (texto_enmascarado, conteo_por_tipo).

    identidad  Identidad del paciente de ESTA nota (o None)
    nombres    Nombres conocidos de la poblacion (o None: entonces los terceros
               solo se detectan tras un trato, o por mayuscula en notas mixtas)

    conteo_por_tipo tiene siempre todas las claves de TIPOS, con cero si no hubo.
    """
    texto = "" if texto is None else str(texto)
    if any(unicodedata.combining(c) for c in texto):
        texto = unicodedata.normalize("NFC", texto)
    identidad = identidad or Identidad()
    plano = _plano_1a1(texto)
    conteo = Counter({tipo: 0 for tipo in TIPOS})

    etapas = [
        lambda p: _tramos_patrones(p, identidad),
        lambda p: _tramos_documento(p, identidad),
        _tramos_fechas,
        _tramos_numeros,
        _tramos_lugar,
        lambda p: _tramos_identidad(p, identidad),
        lambda p: _tramos_terceros(texto, p, nombres),
        lambda p: _tramos_nombre_completo(p, nombres),
        lambda p: _tramos_sueltos(p, nombres),
    ]
    for etapa in etapas:
        tramos = etapa(plano)
        if tramos:
            texto, plano, hechos = _aplicar(texto, plano, tramos)
            conteo.update(hechos)

    # Un nombre de pila de la lista de bloqueo pegado a un nombre ya tapado es
    # parte de ese nombre: 'aceptada por luz [NOMBRE]'. Solo los que son nombre
    # y nada clinico: 'dolores', 'clara' o 'blanca' pegados a una marca pueden
    # ser el sintoma o el color, y esos se quedan.
    patron = (r"\b(" + "|".join(sorted(_NOMBRES_BLOQUEADOS)) + r")(?=[ \t]+\[NOMBRE\])"
              r"|(?<=\[NOMBRE\][ \t])(" + "|".join(sorted(_NOMBRES_BLOQUEADOS)) + r")\b")
    tramos =[(m.start(), m.end(), "nombre_tercero") for m in re.finditer(patron, plano)]
    if tramos:
        texto, plano, hechos = _aplicar(texto, plano, tramos)
        conteo.update(hechos)

    # '[NOMBRE] [NOMBRE]' dice cuantas palabras tenia el nombre: se deja una
    texto = re.sub(r"\[NOMBRE\](?:[\s-]+\[NOMBRE\])+", "[NOMBRE]", texto)
    return texto, dict(conteo)


# ==========================================================
# LO QUE LA AUDITORIA NECESITA
# ==========================================================

def restos_de_identidad(texto, identidad, excluir=frozenset()):
    """
    Cuantas fichas fuertes de la identidad, o el documento, siguen en el texto.

    Busca coincidencia EXACTA por palabra completa; las erratas no cuentan como
    resto (serian otra palabra). `excluir` son fichas que no se buscan aqui
    porque se buscan en otro sitio (ver auditar.py).
    """
    plano = _plano_1a1(str(texto or ""))
    palabras = set(re.findall(r"[a-z0-9]+", plano))
    restos = sum(1 for ficha in identidad.fuertes - set(excluir) if ficha in palabras)
    if identidad.documento and re.search(
            r"(?<!\d)" + r"[\s.,-]?".join(identidad.documento) + r"(?!\d)", plano):
        restos += 1
    if identidad.doc_texto and identidad.doc_texto in re.sub(r"[^a-z0-9]", "", plano):
        restos += 1
    return restos
