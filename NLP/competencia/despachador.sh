#!/bin/bash
# UN solo proceso contra Ollama. Lee pedidos.txt linea a linea y los corre en orden.
# Formato de linea:  modelo|ruta_prompt|ruta_muestra|nombre_salida|modo
# Se agregan pedidos con:  echo "..." >> pedidos.txt      Para terminar: echo FIN >> pedidos.txt
# Para pararlo: matar ESTE bash por PID (lo imprime al empezar) y su python.
# Uso, desde cualquier sitio:  bash NLP/competencia/despachador.sh
cd "$(dirname "$0")/../.."   # la raiz del repo
S=${COMPETENCIA:-NLP/salidas/competencia}
C=$S/comparacion
P=$S/pedidos.txt
mkdir -p $C
export PYTHONIOENCODING=utf-8
touch $P
echo "=== DESPACHADOR PID $$ $(date +%T)"
n=1
while true; do
  linea=$(sed -n "${n}p" $P)
  if [ -z "$linea" ]; then sleep 15; continue; fi
  [ "$linea" = "FIN" ] && break
  IFS='|' read -r modelo prompt muestra nombre modo <<< "$linea"
  for m in $(ollama ps | awk 'NR>1 {print $1}'); do
    curl -s -m 120 http://127.0.0.1:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null; done
  echo "=== INICIO $nombre $(date +%T)"
  python NLP/competencia/comparar.py --modelo "$modelo" --modo "${modo:-cadena}" --prompt "$prompt" \
      --muestra "$muestra" --salida $C/$nombre.jsonl > $C/$nombre.log 2>&1
  echo "=== FIN $nombre exit $? $(date +%T) $(tail -1 $C/$nombre.log)"
  n=$((n+1))
done
echo "=== DESPACHADOR TERMINADO $(date +%T)"
