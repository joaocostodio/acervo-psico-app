#!/usr/bin/env bash
# Relatório de uso do portal desde que foi liberado para a Psicologia (16/10/2026).
# Só LÊ, não altera nada. Rodar da sua máquina (pede a senha do SSH):
#   ssh -J "$SALTO_SSH" "root@$VM" 'bash -s' < app/deploy/relatorio-uso.sh > uso.txt
# No PowerShell:
#   Get-Content app/deploy/relatorio-uso.sh -Raw | ssh -J "$SALTO_SSH" "root@$VM" 'bash -s' > uso.txt
DESDE=${DESDE:-2026-10-16}
PG="docker exec crepop-pg psql -U postgres -d crepop -P pager=off"
sec() { echo; echo "===== $* ====="; }

sec "CONTAS"
$PG -c "SELECT id_usuario, login, admin, ativo, criado_em::date FROM usuario ORDER BY 1;"

sec "BUSCAS E PERGUNTAS POR DIA desde $DESDE (horário de Brasília)"
$PG -c "SET TIME ZONE 'America/Sao_Paulo';
        SELECT r.criado_em::date AS dia, u.login, u.admin,
               count(*) FILTER (WHERE r.modo = 'buscar')    AS buscas,
               count(*) FILTER (WHERE r.modo <> 'buscar')   AS perguntas_ia,
               min(r.criado_em)::time(0) AS primeira, max(r.criado_em)::time(0) AS ultima
        FROM registro_consulta r LEFT JOIN usuario u USING (id_usuario)
        WHERE r.criado_em >= DATE '$DESDE'
        GROUP BY 1, 2, 3 ORDER BY 1, 2;"

sec "TOTAL por conta desde $DESDE"
$PG -c "SELECT u.login, u.admin, count(*) AS consultas, count(DISTINCT r.criado_em::date) AS dias
        FROM registro_consulta r LEFT JOIN usuario u USING (id_usuario)
        WHERE r.criado_em >= DATE '$DESDE' GROUP BY 1, 2 ORDER BY 3 DESC;"

sec "TUDO que foi buscado/perguntado por contas NÃO-admin desde $DESDE"
$PG -c "SET TIME ZONE 'America/Sao_Paulo';
        SELECT to_char(r.criado_em, 'DD/MM HH24:MI') AS quando, u.login, r.modo, left(r.pergunta, 90) AS texto
        FROM registro_consulta r JOIN usuario u USING (id_usuario)
        WHERE r.criado_em >= DATE '$DESDE' AND NOT u.admin ORDER BY r.criado_em;"

sec "MEDIDOR (evento_uso) por dia: aparelhos = logins distintos (sem identificar a pessoa)"
$PG -c "SET TIME ZONE 'America/Sao_Paulo';
        SELECT criado_em::date AS dia, count(DISTINCT sessao) AS aparelhos,
               count(*) FILTER (WHERE tipo='login') AS logins, count(*) FILTER (WHERE tipo='tela') AS telas,
               count(*) FILTER (WHERE tipo='busca') AS buscas, count(*) FILTER (WHERE tipo='pergunta') AS perguntas,
               count(*) FILTER (WHERE tipo='pdf') AS pdfs
        FROM evento_uso WHERE criado_em >= DATE '$DESDE' GROUP BY 1 ORDER BY 1;"
$PG -c "SELECT min(criado_em) AS primeiro_evento, count(*) FILTER (WHERE sessao IS NOT NULL) AS com_sessao FROM evento_uso;"

sec "AVALIAÇÕES (👍/👎) desde $DESDE"
$PG -c "SELECT a.util, count(*), string_agg(left(a.comentario, 80), ' | ') AS comentarios
        FROM avaliacao_resposta a WHERE a.criado_em >= DATE '$DESDE' GROUP BY 1;"

sec "NGINX: o que ainda existe de log"
ls -l --time-style=+%F /var/log/nginx/access.log* 2>/dev/null
LOGS=$(ls /var/log/nginx/access.log* 2>/dev/null)
ler() { for f in $LOGS; do case $f in *.gz) zcat "$f";; *) cat "$f";; esac; done; }
echo "--- logins certos (POST /entrar -> 303) por dia e IP:"
ler | awk '$6=="\"POST" && $7=="/entrar" && $9==303 {print substr($4,2,11), $1}' | sort | uniq -c | sort -k2,2 -k3
echo "--- logins errados (POST /entrar não-303) por dia e IP:"
ler | awk '$6=="\"POST" && $7=="/entrar" && $9!=303 {print substr($4,2,11), $1, $9}' | sort | uniq -c | sort -k2,2
echo "--- IPs distintos que abriram a tela (GET /) por dia:"
ler | awk '$6=="\"GET" && ($7=="/" || $7=="/entrar") {print substr($4,2,11), $1}' | sort -u | awk '{print $1}' | uniq -c
