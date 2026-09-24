# Reglamento de la competencia de prompts — léelo entero antes de escribir nada

Proyecto de tesis, este repositorio (Windows; Bash con sintaxis
POSIX o Read/Grep/Write). Todo en español.

## La tarea del modelo

Un LLM local (Ollama, CPU, temperatura 0) recibe **una** nota de triage de urgencias (español de
Colombia: erratas, siglas del hospital, coloquialismos de Caldas) y devuelve **una línea** con el
motivo de consulta estandarizado, o exactamente `sin motivo clinico` si la nota no dice nada del
paciente (solo trámite: remisión, traslado, «me indican consultar», o nota cortada).

Lo que se castiga, de peor a menos malo:
1. **Descarte falso**: `sin motivo clinico` en una nota que sí trae algo del paciente (un síntoma,
   una lesión, cómo se ve, un procedimiento, un control de embarazo…). El paciente sale de la
   cuenta, y la cuenta es el desenlace de la tesis.
2. **Inventar**: lado, parte del cuerpo, cifra, embarazo, mecanismo o síntoma que la nota no dice.
3. **Cambiar el sentido**: perder una negación («niega X» → X), volver certeza una duda («al
   parecer», «creo que», «posible»), cambiar la duración («antier» no es «ayer» ni «anoche»),
   traducir mal un coloquialismo.
4. **Perder detalle** que la nota da y que importa: semanas de gestación, duración, localización.
5. Copiar nombres de personas o de instituciones.

## Cómo se puntúa (preregistrado en `docs/CONTEXTO.md`, entrada «Cada modelo con su propio prompt»)

Sobre 63 notas (la sonda + una muestra nueva), juzgadas **leyendo** contra una lista de
verificación: fallo arreglado +1 (parcial +0,5); acierto dañado **−2** (parcial −1). Descartes
falsos aparte. Se mide en modo **cadena** (filtros de producción + segunda pasada).

**La barrera que hay que cruzar**: ≥ 12 de las 16 notas duras bien · **0 aciertos dañados** ·
**0 descartes falsos**. Quien la cruce se confirma en un **conjunto de validación que tú nunca
vas a ver**, con notas nuevas de las mismas familias. Por eso:

## Reglas que no se negocian

1. **Nada de memorizar la muestra.** Tu prompt lleva **reglas generales**. Prohibido escribir en
   el prompt frases, palabras raras, coloquialismos concretos o casos que aparezcan en las notas
   de la muestra o en sus salidas (p. ej. si una nota dice «tengo X», no escribas una regla sobre
   «X»). Los ejemplos, si los usas, **inventados** y de otros temas. Un revisor audita cada prompt
   y descalifica el que memorice. Motivo: la validación es con notas que no ves; memorizar solo
   te hace fracasar ahí, y además es trampa.
2. **Lección aprendida del proyecto** (léela en el docstring de `NLP/prompts/v1_7.py` y en
   `NLP/docs/PROMPT.md`): **cualquier palabra clínica concreta escrita en el prompt acaba
   apareciendo en las respuestas**, se ponga como ejemplo o como prohibición. El molde «en
   gestante de N semanas» de la regla 6 de v1.7 hizo que los modelos Llama inventaran embarazos
   en 9-15 notas. Habla de categorías, no de términos.
3. **No abras** la carpeta `NLP/salidas/competencia/validacion_privada/` ni `clave_no_abrir/`.
4. **No ejecutes Ollama** ni nada pesado (la máquina tiene 16 GB y un solo modelo a la vez; dos
   cosas pesadas la cuelgan). El orquestador corre tu prompt y te devuelve el juicio.
5. **No edites el repositorio.** Tu prompt vive en `NLP/prompts/candidatos/<tu_modelo>_rN.py`.
6. Nunca copies en tus respuestas más de ~50 caracteres de una nota; nombres → [NOMBRE].

## El módulo que entregas

Un `.py` que se carga con `NLP.banco._cargar_prompt(ruta)`. Debe definir:

```python
from NLP import glosario                       # para el bloque de equivalencias por nota
from NLP.prompts import v1_7 as _base          # los filtros de producción, SIN cambios

VERSION = "<modelo>-r1"
FORMATO = None     # opcional: "motivo" -> Ollama obliga a {"motivo": ...}
                   #           "razonado" -> {"razonamiento": ..., "motivo": ...} (piensa y luego responde)
OPCIONES = {}      # opcional, p. ej. {"num_predict": 300}. temperature se fuerza a 0.

def construir(nota: str) -> str: ...           # el prompt completo para una nota
def posprocesar(original, salida):             # OBLIGATORIO así, sin tocar:
    return _base.posprocesar(original, salida)
def construir_segunda_pasada(nota: str) -> str: ...   # red contra el descarte falso: la misma
    # nota con un aviso de que SÍ trae algo del paciente y un cierre que no admite abstenerse
```

Puedes cambiar todo el texto: orden, idioma de las instrucciones (la salida siempre en español),
separar reglas, quitar reglas que a tu modelo le hacen daño, usar el glosario
(`glosario.bloque(nota)` devuelve las equivalencias de ESA nota; mantenlo, es trabajo humano del
hospital). Mira `NLP/prompts/v1_7.py` (base) y `NLP/prompts/v1_7_14b.py` (abstención suavizada).

**Antes de entregar**, compruébalo sin llamar al modelo, desde la raíz del repo:

    python NLP/competencia/verificar.py NLP/prompts/candidatos/<tu_modelo>_r1.py

## ACLARACIÓN (2026-09-24, vale para TODOS los modelos por igual)

La segunda pasada se dispara también en trámites puros bien descartados (el detector
`descarte_falso` tiene falsos positivos: dos notas de la muestra). Con un cierre que
prohíbe abstenerse, ahí solo se puede copiar el trámite o inventar, y se dañan aciertos por
diseño. Por eso **`construir_segunda_pasada` PUEDE admitir la abstención en un único caso: cuando
lo único que la nota trae es trámite** (de dónde viene, quién lo envía, qué servicio o
especialidad lo manda, la etiqueta de urgente). En ese caso `cadena` deja «sin motivo clinico»
marcado `revisar`, que una persona ve. En cualquier otro caso la segunda pasada debe seguir
obligando a extraer lo que la nota dice del paciente. Es opcional: quien prefiera el cierre
estricto de v1.7 puede mantenerlo.

## Material para conocer a tu modelo (en NLP/salidas/competencia/, fuera de git)

- `revision_modelos.md`: el juicio nota por nota de todos los modelos, con su sección propia.
- `lista_verificacion.csv`: qué debe y qué no debe decir la respuesta correcta de cada nota.
- `notas_enmascaradas.csv`: las 63 notas, enmascaradas.
- `comparacion/<modelo>_*.jsonl`: las salidas de tu modelo con v1.7 (`salida`, `llamadas[0].cruda`).
- `comparacion/filtradas.csv`: cómo quedan tras los filtros.

## Qué entregas en cada ronda (máx. 20 líneas)

La ruta del módulo, qué cambiaste y **qué familia de error ataca cada cambio**, qué riesgo ves
(qué podría dañar), y la salida de `verificar.py`. Máximo 3 rondas; en cada una recibirás el
juicio de la anterior.
