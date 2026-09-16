"""
E2.0: alarmas.reiniciar() vacia los contadores del guardian clinico, y
procesar.main() / reparar.main() lo llaman al empezar (ver NLP/docs/PLAN.md
E2.0). Sin esa llamada, dos corridas en el mismo proceso acumulan las alarmas
de la primera sobre las de la segunda.
"""

import inspect

from NLP.fase2_ortografia import alarmas, terminologia
from NLP import procesar
from NLP.reparacion import reparar


def test_reiniciar_vacia_alarmas_y_abstenciones():
    alarmas.anotar("motivo de prueba", "original", "candidato")
    alarmas.anotar_abstencion("palabra_suelta")
    assert alarmas.resumen_alarmas()
    assert alarmas.resumen_abstenciones(minimo=1)

    alarmas.reiniciar()

    assert alarmas.resumen_alarmas() == []
    assert alarmas.resumen_abstenciones(minimo=1) == []


def test_dos_corridas_en_el_mismo_proceso_no_acumulan():
    """
    Simula lo que evita la llamada de E2.0: sin reiniciar entre dos 'corridas',
    la segunda hereda los vetos de la primera; con reiniciar(), no.
    """
    alarmas.reiniciar()

    # corrida 1: dos vetos del mismo motivo
    terminologia.validar("hipotension", "hipertension")  # invierte el significado
    terminologia.validar("bradicardia", "taquicardia")   # invierte el significado
    primera = dict((motivo, veces) for motivo, veces, _ej in alarmas.resumen_alarmas())
    assert primera.get("invierte el significado", 0) == 2

    # sin el reinicio de E2.0, una corrida nueva heredaria estos 2 y sumaria
    alarmas.reiniciar()

    # corrida 2: un solo veto nuevo
    terminologia.validar("hipotension", "hipertension")
    segunda = dict((motivo, veces) for motivo, veces, _ej in alarmas.resumen_alarmas())
    assert segunda.get("invierte el significado", 0) == 1


def test_procesar_y_reparar_reinician_alarmas_al_empezar():
    """
    procesar.main() y reparar.main() llaman a la funcion de reinicio como
    primera accion (E2.0). No se ejecuta main() completo aqui -- exige BD y
    argumentos de linea de comandos -- se comprueba la llamada en el codigo
    fuente, que es lo que hace reproducible el comportamiento sin depender de
    la BD.
    """
    fuente_procesar = inspect.getsource(procesar.main)
    fuente_reparar = inspect.getsource(reparar.main)

    assert "alarmas.reiniciar()" in fuente_procesar
    assert "alarmas.reiniciar()" in fuente_reparar
