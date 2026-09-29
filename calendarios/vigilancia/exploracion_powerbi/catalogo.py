import json, collections, sys
sys.stdout.reconfigure(encoding='utf-8')
# El catalogo lo guarda calendarios/vigilancia/eventos.py en crudo/ en cada corrida
# (antes era micro.json en el scratchpad de la sesion del 2026-09-28).
from pathlib import Path
_ruta = Path(__file__).resolve().parent.parent / 'crudo' / 'catalogo_microdatos.json'
d = json.load(open(_ruta, encoding='utf-8'))
d = d['value'] if isinstance(d, dict) else d
ev = collections.defaultdict(set); nm = {}
for r in d:
    c = r['CodigoEvento']; ev[c].add(int(r['FileLeafRef'].split('_')[1])); nm[c] = r['NombreEvento']
def rng(ys):
    ys = sorted(ys); out = []; s = p = ys[0]
    for y in ys[1:]:
        if y == p + 1:
            p = y; continue
        out.append(f"{s}-{p}" if s != p else str(s)); s = p = y
    out.append(f"{s}-{p}" if s != p else str(s)); return ", ".join(out)
# (relevancia, serie semanal no vacia en Manizales, porque). [V] = medido hoy.
R = {
'100':('baja','no','Ofidismo rural; Manizales 5/año (2024 R) y 5 en 2026 [V].'),
'101':('baja','no','Solo 2025 en microdatos; 20 casos Manizales en 2026, 0,5/sem [V].'),
'110':('baja','no','Desenlace perinatal, no demanda general de urgencias.'),
'112':('baja','no','Mortalidad; volumen mínimo.'),
'113':('baja','no','Desnutrición <5 años: 80/año Manizales 2024 (1,5/sem) [V]; no es consulta urgente típica.'),
'155':('baja','no','Cáncer: crónico, sin dinámica semanal de urgencias.'),
'205':('baja','no','Chagas: sin transmisión en Manizales.'),
'210':('baja','no','Dengue: 7 residentes Manizales en 2018 [V], 0 filas en 2026 [V]; ciudad a 2.150 m. A lo sumo, marcador regional de remitidos.'),
'217':('baja','no','Chikungunya: sin transmisión local.'),
'220':('baja','no','Dengue grave: 0 residentes Manizales 2024; 2 notificados en Manizales (remitidos) [V].'),
'228':('baja','no','Exposición a flúor (centinela).'),
'230':('baja','no','Difteria: casi inexistente.'),
'298':('baja','no','ESAVI: volumen mínimo.'),
'300':('ALTA','sí','Agresiones animales: ~29/sem 2026, 38/38 sem [V]; se atienden en urgencias (profilaxis antirrábica). Componente directo del triage, sensible a fines de semana y vacaciones.'),
'305':('baja','no','Tracoma: no aplica.'),
'310':('baja','no','Fiebre amarilla: no aplica.'),
'320':('baja','no','Tifoidea: 0 Manizales 2024 [V].'),
'330':('baja','no','Hepatitis A: 39/año 2024 (0,75/sem, 24 sem) [V]; 2 en 2026. Solo para brotes.'),
'340':('baja','no','Hepatitis B: crónica.'),
'341':('baja','no','Hepatitis C: crónica.'),
'343':('baja','no','Tamizaje neonatal.'),
'345':('baja','no','ESI-IRAG centinela: Manizales no es sitio centinela (0 residentes 2024; 3 en Caldas) [V]. Solo como señal NACIONAL de circulación viral.'),
'346':('media','no','IRA por virus nuevo (COVID): 6 casos 2026 [V]; clave en 2020-2022, pero para esos años la fuente es datos.gov.co gt2j-8ykr [V existe].'),
'348':('media','no','IRAG inusitado: 8/año Manizales 2024 [V]; marcador de gravedad, serie casi vacía.'),
'349':('media','no','ETA colectivo (brotes): 7 brotes con 180 enfermos en Manizales 2024 [V]. Marcador de evento puntual, no serie.'),
'356':('ALTA','sí','Intento de suicidio: 603/año 2024, 11,6/sem, 52/52 sem [V]; ingresa por urgencias. Crece (365 en 2016).'),
'360':('media','parcial','Plaguicidas: 41/año 2024, 26 sem [V]. Mejor sumado en «365 Intoxicaciones».'),
'370':('ALTA','sí','Intoxicación por medicamentos: 374/año 2024, 7,2/sem, 52/52 sem [V]; urgencias. Sumar en 365.'),
'380':('baja','no','Metanol: brotes raros.'),
'390':('baja','no','Metales pesados.'),
'400':('baja','no','Solventes.'),
'410':('baja','no','Otras sustancias químicas; sumar en 365.'),
'412':('baja','no','Gases (CO): 7/año 2024 [V].'),
'414':('media','parcial','Sustancias psicoactivas: 60/año 2024, 34 sem [V]; ligada a fiestas (Feria de enero). Sumar en 365.'),
'420':('baja','no','Leishmaniasis cutánea: 3 residentes Manizales 2024 [V]; sin transmisión.'),
'430':('baja','no','Leishmaniasis mucosa.'),
'440':('baja','no','Leishmaniasis visceral.'),
'450':('baja','no','Lepra.'),
'452':('media','no','Pólvora: 23/año 2024, concentrados en SE48-SE1 [V]. Marcador de diciembre (ya lo captura el calendario).'),
'455':('baja','no','Leptospirosis: 4/año [V]; ligada a la lluvia pero sin volumen.'),
'456':('baja','no','Leucemia pediátrica.'),
'457':('baja','no','Leucemia pediátrica.'),
'458':('media','no','Pólvora, código antiguo (2007-2014); empalma con 452.'),
'459':('baja','no','Cáncer infantil.'),
'460':('baja','no','Malaria mixta: sin transmisión.'),
'470':('baja','no','Malaria falciparum.'),
'480':('baja','no','Malaria malariae.'),
'490':('baja','no','Malaria vivax.'),
'495':('baja','no','Malaria complicada.'),
'500':('baja','no','Meningitis: grave pero muy rara.'),
'510':('baja','no','Meningitis por Hib.'),
'520':('baja','no','Meningitis por neumococo.'),
'530':('baja','no','Meningitis tuberculosa.'),
'540':('baja','no','Mortalidad por malaria.'),
'549':('media','sí','Morbilidad materna extrema: 5,7/sem 2026, 38/38 sem [V]. Relevante solo si el triage incluye obstetricia.'),
'550':('baja','no','Mortalidad materna.'),
'560':('baja','no','Mortalidad perinatal.'),
'580':('baja','no','Mortalidad por dengue.'),
'590':('baja','no','Mortalidad por EDA en <5 años.'),
'600':('baja','no','Mortalidad por IRA: rara; marcador de gravedad.'),
'610':('baja','no','PFA: solo 2009.'),
'620':('media','parcial','Parotiditis: 53/año 2024, 30 sem [V]; brotes en población universitaria. Serie dispersa.'),
'670':('baja','no','Rabia humana.'),
'710':('baja','no','Rubéola.'),
'730':('baja','no','Sarampión: casi inexistente (alerta regional 2026 en el BES).'),
'735':('baja','no','Anomalías congénitas.'),
'739':('baja','no','MIS-C.'),
'740':('baja','no','Sífilis congénita.'),
'750':('baja','no','Sífilis gestacional.'),
'760':('baja','no','Tétanos accidental.'),
'770':('baja','no','Tétanos neonatal.'),
'780':('baja','no','Tifus epidémico (solo 2025).'),
'790':('baja','no','Tifus endémico.'),
'800':('baja','no','Tos ferina: 2/año Manizales 2024 [V].'),
'810':('baja','no','TB extrapulmonar: crónica.'),
'820':('baja','no','TB pulmonar: crónica.'),
'825':('baja','no','TB farmacorresistente.'),
'831':('media','sí','Varicela: 212/año 2024, 4,1/sem, 46/52 sem [V]; transmisión escolar; casi toda ambulatoria (209 de 212 sin hospitalización) [V].'),
'850':('baja','no','VIH: crónico.'),
'875':('ALTA','sí','Violencia de género e intrafamiliar: ~24/sem 2026, 38/38 sem [V] (514/año en 2013 [V]); atención urgente (violencia sexual); ligada a fines de semana, quincena y fiestas.'),
'880':('baja','no','Mpox.'),
'895':('baja','no','Zika: sin transmisión.'),
'995':('ALTA','sí','IRA colectiva, con denominador. La integra OTRO agente; no se tocó.'),
'998':('ALTA','sí','EDA colectiva: 31.606 en Manizales en 2012 (microdatos) [V]; ~456/sem en 2026 (tablero) [V]. Análogo gastrointestinal del 995.'),
}
print('| cód | evento | años en microdatos (n) | relevancia | ¿serie semanal no vacía en Manizales? | por qué |')
print('|---|---|---|---|---|---|')
for c in sorted(ev, key=int):
    rel, ser, why = R.get(c, ('?', '?', ''))
    print(f'| {c} | {nm[c]} | {rng(ev[c])} ({len(ev[c])}) | {rel} | {ser} | {why} |')
faltan = [c for c in ev if c not in R]
if faltan: print('\nFALTAN:', faltan)
