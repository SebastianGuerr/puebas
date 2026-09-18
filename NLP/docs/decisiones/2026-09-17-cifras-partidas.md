# El guardián de cifras dejaba partir la cifra en dos
Fecha: 2026-09-17. Ítem del plan: continuación de `2026-09-16-cifras.md`. Autor: sesión de
comparación contra el CSV del 11/09.

## Qué se encontró

Comparando `salidas/triage_limpio.csv` (16/09) con `triage_limpio_antiguo.csv` (11/09)
aparecieron salidas así:

```
original   INGRESA PACIENTE GESTANTE CON 39+5 SEMANAS DE GESTACIÓN
11/09      ... con 39+5 semanas de gestación ...
16/09      ... con 39+ 5 semanas de gestación ...
```

Y lo mismo con `22/04/2025` → `22/ 04/ 2025`, `glasgow 15/15` → `glasgow 15/ 15`,
`intensidad 6/10` → `intensidad 6/ 10`, `msd 128/77` → `msd 128/ 77`.

Recuento del patrón `\d\s*[/+]\s+\d` por columna:

| CSV | original | corregido | normalizado | embedding |
|---|---|---|---|---|
| 11/09 (6.501 notas) | 3 | 3 | 3 | 3 |
| 16/09 (9.311 notas) | 5 | **250** | 250 | 217 |

En el CSV antiguo las tres apariciones ya venían en el original: no había daño. En el nuevo
el salto ocurre en `texto_corregido`, es decir en la fase 2.

## Causa

LanguageTool propone, en categoría `TYPOS`, separar el signo de la cifra. El guardián que
introdujo `2026-09-16-cifras.md` comparaba **solo los grupos de dígitos**:

```python
def mismas_cifras(original, reemplazo):
    return RE_CIFRAS.findall(str(original)) == RE_CIFRAS.findall(str(reemplazo))
```

`RE_CIFRAS.findall("39+5")` y `RE_CIFRAS.findall("39+ 5")` valen los dos `['39', '5']`, así
que la sustitución pasaba el guardián. El guardián atrapaba `1000cc → 100cc`, que era el
caso para el que se escribió, y no veía este.

Lo que se rompe con eso es dato clínico: edad gestacional, escala de Glasgow, tensión
arterial, escala de dolor y fechas. Partida en dos tokens, la cifra deja de leerse como una
sola magnitud aguas abajo.

## Decisión

`mismas_cifras()` exige además que un token que trae cifra **y no trae espacios** no salga
partido. Es la condición mínima que cubre el caso sin tocar ninguna corrección legítima:
`dolro → dolor` sigue pasando, y un original que ya venía espaciado (`gestante 35 + 4`) no
se toca porque nunca fue un solo token.

El mismo guardián se replica en `vocabulario.py`, donde SymSpell aplica sus propuestas, para
que las dos rutas de corrección no se contradigan.

## Verificación

Sobre las 12 primeras notas dañadas del CSV, pasadas de nuevo por fase 1 + fase 2 con el
arreglo: **11 quedan intactas**. La duodécima (`gestante 35 + 4`) ya venía así en el
original — es un falso positivo del detector, no daño.

`python -m pytest NLP/tests -q` → 38 en verde.

## Historial

| Fecha | Cambio |
|---|---|
| 2026-09-17 | Primera versión |
