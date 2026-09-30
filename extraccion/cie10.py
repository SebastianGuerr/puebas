"""
Los 22 capitulos de la CIE-10 (clasificacion publica de la OMS), por rango de codigo.

Sirve para agrupar diagnosticos antes de guardarlos: un capitulo por dia no apunta a nadie,
un codigo exacto por dia con cifras pequenas si podria. No habla con SQL Server.
"""

CAPITULOS = [  # (desde, hasta, numero, nombre corto)
    ("A00", "B99", "I", "Infecciosas y parasitarias"),
    ("C00", "D48", "II", "Tumores"),
    ("D50", "D89", "III", "Sangre e inmunidad"),
    ("E00", "E90", "IV", "Endocrinas y metabolicas"),
    ("F00", "F99", "V", "Mentales y del comportamiento"),
    ("G00", "G99", "VI", "Sistema nervioso"),
    ("H00", "H59", "VII", "Ojo"),
    ("H60", "H95", "VIII", "Oido"),
    ("I00", "I99", "IX", "Circulatorio"),
    ("J00", "J99", "X", "Respiratorio"),
    ("K00", "K93", "XI", "Digestivo"),
    ("L00", "L99", "XII", "Piel"),
    ("M00", "M99", "XIII", "Osteomuscular"),
    ("N00", "N99", "XIV", "Genitourinario"),
    ("O00", "O99", "XV", "Embarazo, parto y puerperio"),
    ("P00", "P96", "XVI", "Perinatal"),
    ("Q00", "Q99", "XVII", "Malformaciones congenitas"),
    ("R00", "R99", "XVIII", "Sintomas y signos"),
    ("S00", "T98", "XIX", "Traumatismos y envenenamientos"),
    ("V01", "Y98", "XX", "Causas externas"),
    ("Z00", "Z99", "XXI", "Factores que influyen en la salud"),
    ("U00", "U99", "XXII", "Codigos especiales (COVID-19)"),
]


def capitulo(cod3):
    """'J44' -> 'X Respiratorio'. Un codigo fuera de rango -> 'sin capitulo'."""
    if not isinstance(cod3, str) or len(cod3) < 3:
        return "sin capitulo"
    c = cod3[:3].upper()
    for desde, hasta, num, nombre in CAPITULOS:
        if desde <= c <= hasta:
            return f"{num} {nombre}"
    return "sin capitulo"
