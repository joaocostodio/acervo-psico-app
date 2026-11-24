#!/usr/bin/env bash
# Diagnóstico da VM do Acervo Psico: quem usou, como usou e se está tudo saudável.
# Só LÊ, não altera nada. Rodar na VM como root:
#   ssh -J "$SALTO_SSH" "root@$VM" 'bash -s' < app/deploy/diagnostico.sh > diagnostico.txt
DIAS=${DIAS:-14}
PG="docker exec crepop-pg psql -U postgres -d crepop -P pager=off"
sec() { echo; echo "===== $* ====="; }

sec "MÁQUINA"
date; uptime
free -h
df -h / /opt 2>/dev/null | sort -u
echo "reinícios recentes:"; last -x reboot 2>/dev/null | head -5

sec "SERVIÇOS"
for s in acervo-psico nginx ollama docker cron; do printf '%-14s %s\n' "$s" "$(systemctl is-active $s)"; done
docker ps --format '{{.Names}}  {{.Status}}'
curl -s -o /dev/null -w "saude local -> %{http_code}\n" http://127.0.0.1/saude
ufw status 2>/dev/null | head -8

sec "ACESSOS SSH (quem entrou na VM)"
last -n 25 -w 2>/dev/null | grep -v '^reboot'
echo "--- falhas de senha SSH nos últimos $DIAS dias (top IPs):"
journalctl -u ssh -u sshd --since "$DIAS days ago" --no-pager 2>/dev/null \
  | grep -Eo 'Failed password .* from [0-9.]+' | awk '{print $NF}' | sort | uniq -c | sort -rn | head -10

sec "USO DO SITE (nginx, últimos arquivos de log)"
LOGS=$(ls /var/log/nginx/access.log* 2>/dev/null)
ler() { for f in $LOGS; do case $f in *.gz) zcat "$f";; *) cat "$f";; esac; done; }
echo "requisições por dia:"; ler | awk '{print substr($4,2,11)}' | sort | uniq -c | sort -k2 | tail -$DIAS
echo "--- IPs que mais acessaram:"; ler | awk '{print $1}' | sort | uniq -c | sort -rn | head -15
echo "--- logins (POST /entrar) por status e IP:"; ler | awk '$6=="\"POST" && $7=="/entrar"{print $9, $1}' | sort | uniq -c | sort -rn | head -15
echo "--- rotas mais chamadas:"; ler | awk '{print $6, $7}' | sed 's/?.*//' | sort | uniq -c | sort -rn | head -15
echo "--- respostas com erro (4xx/5xx):"; ler | awk '$9>=400{print $9}' | sort | uniq -c | sort -rn
echo "--- últimos 5 erros nginx:"; tail -5 /var/log/nginx/error.log 2>/dev/null

sec "USO DO APP (banco)"
$PG -c "SELECT login, nome, ativo, criado_em::date FROM usuario ORDER BY id_usuario;"
$PG -c "SELECT u.login, r.modo, count(*) AS qtd, min(r.criado_em)::timestamp(0) AS primeira, max(r.criado_em)::timestamp(0) AS ultima
        FROM registro_consulta r LEFT JOIN usuario u USING (id_usuario) GROUP BY 1,2 ORDER BY ultima DESC;"
$PG -c "SELECT r.criado_em::timestamp(0) AS quando, u.login, r.modo, left(r.pergunta,80) AS texto
        FROM registro_consulta r LEFT JOIN usuario u USING (id_usuario) ORDER BY r.criado_em DESC LIMIT 25;"

$PG -c "SELECT modelo, count(*) AS respostas, count(*) FILTER (WHERE guardada) AS prontas,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY primeira_ms)::numeric / 1000) AS primeira_s,
               round(percentile_cont(0.5) WITHIN GROUP (ORDER BY total_ms)::numeric / 1000) AS total_s
        FROM metrica_resposta WHERE criado_em > now() - interval '$DIAS days' GROUP BY 1;" 2>/dev/null

sec "LOG DO APP (últimos $DIAS dias)"
journalctl -u acervo-psico --since "$DIAS days ago" --no-pager 2>/dev/null | grep -c '\[login\] falha' | sed 's/^/falhas de login: /'
journalctl -u acervo-psico --since "$DIAS days ago" --no-pager 2>/dev/null | grep '\[login\] falha' | tail -10
echo "--- erros/exceções:"; journalctl -u acervo-psico --since "$DIAS days ago" -p err --no-pager 2>/dev/null | tail -15
journalctl -u acervo-psico --since "$DIAS days ago" --no-pager 2>/dev/null | grep -iE 'traceback|error' | tail -10

sec "BACKUP"
tail -5 /var/log/acervo-backup.log 2>/dev/null
ls -lh /opt/crepop/backups 2>/dev/null | tail -4

sec "IA (ollama)"
curl -s http://127.0.0.1:11434/api/ps | head -c 400; echo
