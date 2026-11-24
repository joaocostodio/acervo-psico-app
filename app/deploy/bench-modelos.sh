#!/usr/bin/env bash
# Disputa de modelos para a Susmi (docs/escolha-do-modelo-ia.md). Roda em /root/bench,
# longe do app no ar: copie o backend para /root/bench/backend antes.
# Cada modelo: baixa, cria a variante com o mesmo Modelfile da Susmi, roda avaliar.py
# (15 perguntas) e descarrega da memória antes do próximo.
cd /root/bench/backend || exit 1
PY=/opt/crepop/backend/.venv/bin/python
OL=http://127.0.0.1:11434
descarregar() { curl -s $OL/api/generate -d "{\"model\":\"$1\",\"keep_alive\":0}" >/dev/null; }
for m in $(curl -s $OL/api/ps | python3 -c 'import sys,json;[print(x["name"]) for x in json.load(sys.stdin)["models"]]'); do descarregar "$m"; done

# formato: base|pensar(none/false)
CANDIDATOS="${CANDIDATOS:-gemma4:e4b-it-qat|false gemma4:e2b-it-qat|false qwen3.5:4b-mtp-q4_K_M|false qwen3.5:4b-q4_K_M|false atual|none}"
for c in $CANDIDATOS; do
  base=${c%%|*}; pensar=${c##*|}
  if [ "$base" = atual ]; then nome=acervo-psico
  else
    nome="bench-$(echo "$base" | tr ':.' '--')"
    echo "### $(date -u +%H:%M) baixando $base"
    ollama pull "$base" >/dev/null 2>&1 || { echo "### falhou o pull de $base"; continue; }
    sed "s|^FROM .*|FROM $base|" ia/Modelfile > /tmp/Modelfile.bench
    ollama create "$nome" -f /tmp/Modelfile.bench >/dev/null 2>&1 || { echo "### falhou o create de $nome"; continue; }
  fi
  echo "### $(date -u +%H:%M) avaliando $nome (base $base, pensar=$pensar)"
  if [ "$pensar" = none ]; then unset IA_PENSAR; else export IA_PENSAR=$pensar; fi
  $PY avaliar.py "$nome" --saida "/root/bench/res-$nome.json" 2>&1 | grep --line-buffered -E '^\[|^MODELO|Error|error|Traceback'
  descarregar "$nome"
  free -m | awk 'NR==2{print "### memória livre: "$7" MB"}'
done
echo "### $(date -u +%H:%M) FIM"
