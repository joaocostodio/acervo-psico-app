#!/bin/bash
# Rotina diária (cron, 3h): backup do banco (guarda 14 dias) + limpeza LGPD.
# Restaurar um backup:
#   docker exec -i crepop-pg pg_restore -U postgres -d crepop --clean < ARQUIVO.dump
set -euo pipefail
PASTA=/opt/crepop/backups
mkdir -p "$PASTA"
chmod 700 "$PASTA"

# 1. Backup
ARQ="$PASTA/crepop-$(date +%F-%H%M).dump"
docker exec crepop-pg pg_dump -U postgres -Fc crepop > "$ARQ.tmp"
mv "$ARQ.tmp" "$ARQ"
find "$PASTA" -name 'crepop-*.dump' -mtime +14 -delete
echo "$(date +%F\ %T) backup ok: $ARQ ($(du -h "$ARQ" | cut -f1))"
# Resumo para o painel /uso: a pasta de backups é só do root; o app lê só este arquivo
# (quando e quanto, sem o conteúdo).
printf '{"quando": %s, "bytes": %s}\n' "$(date +%s)" "$(stat -c %s "$ARQ")" > /opt/crepop/backup-status.json
chmod 644 /opt/crepop/backup-status.json

# 2. LGPD: apaga as consultas cujo prazo de guarda venceu (o app não consegue apagar;
#    só esta rotina, com o papel administrador, faz isso).
apagadas=$(docker exec crepop-pg psql -U postgres -d crepop -Atc \
    "WITH d AS (DELETE FROM registro_consulta WHERE prazo_guarda < CURRENT_DATE RETURNING 1)
     SELECT count(*) FROM d")
echo "$(date +%F\ %T) LGPD: $apagadas consulta(s) vencida(s) apagada(s)"

# 3. Medidor de uso: guarda 12 meses.
eventos=$(docker exec crepop-pg psql -U postgres -d crepop -Atc \
    "WITH d AS (DELETE FROM evento_uso WHERE criado_em < now() - interval '12 months' RETURNING 1)
     SELECT count(*) FROM d")
echo "$(date +%F\ %T) medidor: $eventos evento(s) com mais de 12 meses apagado(s)"

# 4. Respostas guardadas da Susmi: valem 30 dias (depois a pergunta volta a ir para a IA).
#    As avaliações 👍/👎 somem junto com a consulta (passo 2, ON DELETE CASCADE).
guardadas=$(docker exec crepop-pg psql -U postgres -d crepop -Atc \
    "WITH d AS (DELETE FROM resposta_guardada WHERE criado_em < now() - interval '30 days' RETURNING 1)
     SELECT count(*) FROM d")
echo "$(date +%F\ %T) respostas guardadas: $guardadas com mais de 30 dias apagada(s)"
