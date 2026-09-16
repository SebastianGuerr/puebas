# Los tres bloques de la nota larga: por qué se quitan por frase y no por oración

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/reduccion.py`
(`RE_EXAMEN`, `RE_CONDUCTA`, `RE_ANTECEDENTES`).

## Pregunta

El 15,9 % del corpus pasa de 30 palabras. ¿Qué sobra en esas notas y con
qué granularidad (oración o frase/tramo) hay que quitarlo?

## Medición

Sobre las notas largas, lo que sobra son tres bloques, ninguno de los
cuales responde a por qué vino el paciente:

- **Examen físico**: "paciente en el momento clínicamente estable,
  consciente orientado en sus tres esferas mentales, sin signos de
  deshidratación, normotenso, normocardia, normal saturado". 369 notas
  repiten la primera frase palabra por palabra.
- **Conducta**: "se realiza rastreo ecográfico", "se dan recomendaciones y
  signos de alarma", "se decide derivar paciente" — lo que hizo el
  hospital, no lo que traía el paciente.
- **Antecedentes**: un listado de enfermedades crónicas previas encabezado por
  "paciente con antecedentes de...". En la nota más larga del corpus (153 palabras)
  ocupa 60 de ellas, es decir el 39 % del texto, sin aportar nada al motivo de
  consulta de esa visita. *(Ejemplo descrito, no citado: el contenido original era la
  historia clínica de un paciente identificable por su OID; `PLAN.md` §3, principio 7.)*

`_quitar_institucional()` descarta oraciones enteras (separa por punto y
punto y coma). La nota larga de triage no usa ninguno de los dos: es una
sola frase corrida separada por comas. Ahí el filtro por oración es todo o
nada — o deja el bloque entero o se lleva la nota entera.

## Decisión y motivo

Estos tres bloques se quitan con patrones de frase (recortan el tramo
exacto que sobra) en vez de patrones de oración, y corren tanto en la
pasada agresiva como en la suave, porque a diferencia del trámite ninguno
de los tres puede ser nunca el motivo de consulta: quitarlos no arriesga
dejar la nota vacía.

## Qué la invalidaría

Una nota real donde el examen físico o la conducta SÍ sean el único
contenido clínico (por ejemplo, un hallazgo del examen que sea el motivo de
consulta) haría falta revisar el patrón para no perder ese caso.
