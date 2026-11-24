"""Medidor de uso: grava cada ação (sem IP nem texto) e resume para a página /uso.

Ações contadas: login, abrir a tela, busca, pergunta à IA e PDF aberto. O uso de
contas administradoras não é gravado, para os testes não inflarem a contagem.
"""
import hashlib
import json
import os
import shutil
import time
import traceback
from pathlib import Path

import ollama_client
from config import config
from db import pool

FUSO = "America/Sao_Paulo"
BACKUP_STATUS = "/opt/crepop/backup-status.json"  # escrito pelo deploy/backup.sh


def apelido(cookie: str | None) -> str | None:
    """12 letras do hash do cookie: distingue logins sem identificar a pessoa."""
    return hashlib.sha256(cookie.encode()).hexdigest()[:12] if cookie else None


def registrar(tipo: str, id_usuario: int | None, cookie: str | None,
              id_publicacao: int | None = None) -> None:
    """Conta uma ação. Se falhar, só vai para o log: o medidor nunca derruba o pedido."""
    try:
        with pool.connection() as conn:
            conn.execute(
                """INSERT INTO evento_uso (tipo, sessao, id_publicacao)
                   SELECT %s, %s, %s
                   WHERE NOT EXISTS (SELECT 1 FROM usuario WHERE id_usuario = %s AND admin)""",
                (tipo, apelido(cookie), id_publicacao, id_usuario),
            )
    except Exception:  # noqa: BLE001
        traceback.print_exc()


def eh_admin(id_usuario: int | None) -> bool:
    if id_usuario is None:
        return False
    with pool.connection() as conn:
        return conn.execute(
            "SELECT 1 FROM usuario WHERE id_usuario = %s AND ativo AND admin", (id_usuario,)
        ).fetchone() is not None


def _linhas(cur) -> list[dict]:
    nomes = [c.name for c in cur.description]
    return [dict(zip(nomes, linha)) for linha in cur.fetchall()]


def resumo() -> dict:
    with pool.connection() as conn:
        # Datas e horas no horário de Brasília (o servidor está em UTC).
        conn.execute(f"SET LOCAL TIME ZONE '{FUSO}'")
        periodos = _linhas(conn.execute(
            """WITH p(nome, ordem, desde) AS (VALUES
                   ('hoje', 1, current_date), ('7 dias', 2, current_date - 6),
                   ('30 dias', 3, current_date - 29), ('desde o início', 4, DATE '2000-01-01'))
               SELECT p.nome,
                      count(DISTINCT e.sessao)                        AS aparelhos,
                      count(e.tipo) FILTER (WHERE e.tipo = 'login')    AS logins,
                      count(e.tipo) FILTER (WHERE e.tipo = 'busca')    AS buscas,
                      count(e.tipo) FILTER (WHERE e.tipo = 'pergunta') AS perguntas,
                      count(e.tipo) FILTER (WHERE e.tipo = 'pdf')      AS pdfs,
                      count(DISTINCT e.criado_em::date)                AS dias_com_uso
               FROM p LEFT JOIN evento_uso e ON e.criado_em >= p.desde
               GROUP BY p.nome, p.ordem ORDER BY p.ordem"""
        ))
        por_dia = _linhas(conn.execute(
            """SELECT to_char(d, 'YYYY-MM-DD') AS dia,
                      count(DISTINCT e.sessao)                        AS aparelhos,
                      count(e.tipo) FILTER (WHERE e.tipo = 'login')    AS logins,
                      count(e.tipo) FILTER (WHERE e.tipo = 'busca')    AS buscas,
                      count(e.tipo) FILTER (WHERE e.tipo = 'pergunta') AS perguntas,
                      count(e.tipo) FILTER (WHERE e.tipo = 'pdf')      AS pdfs,
                      count(e.tipo) FILTER (WHERE e.tipo <> 'login')   AS acoes
               FROM generate_series(current_date - 29, current_date, interval '1 day') d
               LEFT JOIN evento_uso e ON e.criado_em >= d AND e.criado_em < d + interval '1 day'
               GROUP BY d ORDER BY d"""
        ))
        por_hora = [r[1] for r in conn.execute(
            """SELECT h, count(e.tipo)
               FROM generate_series(0, 23) h
               LEFT JOIN evento_uso e ON extract(hour FROM e.criado_em) = h
                    AND e.criado_em >= current_date - 29 AND e.tipo <> 'login'
               GROUP BY h ORDER BY h"""
        ).fetchall()]
        agora, ultimo = conn.execute(
            """SELECT count(DISTINCT sessao) FILTER (WHERE criado_em > now() - interval '15 minutes'),
                      to_char(max(criado_em), 'DD/MM/YYYY "às" HH24:MI')
               FROM evento_uso"""
        ).fetchone()
        # Só termos que se repetem: um termo digitado uma única vez não aparece.
        termos = _linhas(conn.execute(
            """SELECT lower(trim(r.pergunta)) AS termo, count(*) AS vezes
               FROM registro_consulta r JOIN usuario u USING (id_usuario)
               WHERE r.modo = 'buscar' AND NOT u.admin AND r.criado_em >= current_date - 29
               GROUP BY 1 HAVING count(*) >= 2
               ORDER BY vezes DESC, termo LIMIT 10"""
        ))
        publicacoes = _linhas(conn.execute(
            """SELECT p.titulo, count(*) AS vezes
               FROM evento_uso e JOIN publicacao p USING (id_publicacao)
               WHERE e.tipo = 'pdf' AND e.criado_em >= current_date - 29
               GROUP BY p.titulo ORDER BY vezes DESC, p.titulo LIMIT 8"""
        ))
        # 👍/👎 das respostas da Susmi (contas não-admin), últimos 30 dias.
        uteis, ruins = conn.execute(
            """SELECT count(*) FILTER (WHERE a.util), count(*) FILTER (WHERE NOT a.util)
               FROM avaliacao_resposta a JOIN registro_consulta r USING (id_consulta)
               JOIN usuario u USING (id_usuario)
               WHERE NOT u.admin AND a.criado_em >= current_date - 29"""
        ).fetchone()
        ultimas_ruins = _linhas(conn.execute(
            """SELECT to_char(a.criado_em, 'DD/MM HH24:MI') AS quando, r.pergunta,
                      a.comentario, left(r.resposta, 220) AS resposta
               FROM avaliacao_resposta a JOIN registro_consulta r USING (id_consulta)
               JOIN usuario u USING (id_usuario)
               WHERE NOT a.util AND NOT u.admin AND a.criado_em >= current_date - 29
               ORDER BY a.criado_em DESC LIMIT 10"""
        ))
        susmi = _desempenho_ia(conn)
        acervo = _linhas(conn.execute(
            """SELECT count(DISTINCT v.id_publicacao) AS publicacoes, count(p.id_pagina) AS paginas,
                      count(p.numero_pagina_impressa) AS com_pagina_impressa,
                      pg_size_pretty(pg_database_size(current_database())) AS tamanho_banco
               FROM versao_arquivo v LEFT JOIN pagina p USING (id_versao)
               WHERE v.situacao_vigencia"""
        ))[0]
    return {
        "agora": agora, "ultimo_uso": ultimo, "periodos": periodos, "por_dia": por_dia,
        "por_hora": por_hora, "termos": termos, "publicacoes": publicacoes,
        "avaliacoes": {"uteis": uteis, "ruins": ruins, "ultimas_ruins": ultimas_ruins},
        "susmi": susmi, "acervo": acervo, "sistema": _sistema(),
    }


def _desempenho_ia(conn) -> dict:
    """Quanto a Susmi demora, nos últimos 30 dias (tabela metrica_resposta)."""
    try:
        with conn.transaction():
            geral = _linhas(conn.execute(
                """SELECT count(*) AS respostas,
                          count(*) FILTER (WHERE guardada) AS guardadas,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY primeira_ms)
                              FILTER (WHERE NOT guardada) AS primeira_ms,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY total_ms)
                              FILTER (WHERE NOT guardada) AS total_ms,
                          percentile_cont(0.9) WITHIN GROUP (ORDER BY total_ms)
                              FILTER (WHERE NOT guardada) AS total_p90_ms,
                          avg(espera_ms) FILTER (WHERE NOT guardada) AS espera_ms,
                          avg(tokens_por_segundo) FILTER (WHERE NOT guardada) AS tokens_por_segundo,
                          sum(tokens_lidos) FILTER (WHERE NOT guardada)::float
                              / NULLIF(sum(leitura_ms) FILTER (WHERE NOT guardada), 0) * 1000 AS leitura_tps
                   FROM metrica_resposta WHERE criado_em >= current_date - 29"""
            ))[0]
            por_modelo = _linhas(conn.execute(
                """SELECT modelo, count(*) AS respostas,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY total_ms) AS total_ms
                   FROM metrica_resposta WHERE NOT guardada AND criado_em >= current_date - 29
                   GROUP BY modelo ORDER BY max(criado_em) DESC"""
            ))
            por_dia = _linhas(conn.execute(
                """SELECT to_char(d, 'YYYY-MM-DD') AS dia, count(m.id_consulta) AS respostas,
                          percentile_cont(0.5) WITHIN GROUP (ORDER BY m.total_ms) AS total_ms
                   FROM generate_series(current_date - 29, current_date, interval '1 day') d
                   LEFT JOIN metrica_resposta m ON m.criado_em >= d AND m.criado_em < d + interval '1 day'
                        AND NOT m.guardada
                   GROUP BY d ORDER BY d"""
            ))
    except Exception:  # noqa: BLE001 — tabela ainda não migrada: o painel continua
        traceback.print_exc()
        geral, por_modelo, por_dia = {}, [], []
    return {"modelo": config.chat_model, "na_memoria": ollama_client.modelos_carregados(),
            "geral": geral, "por_modelo": por_modelo, "por_dia": por_dia}


def _sistema() -> dict:
    """Saúde da VM vista de dentro do app: disco, memória, carga, último backup."""
    info: dict = {}
    try:
        uso = shutil.disk_usage("/")
        info["disco_livre_gb"] = round(uso.free / 1e9, 1)
        info["disco_total_gb"] = round(uso.total / 1e9, 1)
    except OSError:
        pass
    try:
        mem = dict(linha.split(":", 1) for linha in Path("/proc/meminfo").read_text().splitlines())
        kb = lambda k: int(mem[k].split()[0])  # noqa: E731
        info["memoria_total_gb"] = round(kb("MemTotal") / 1e6, 1)
        info["memoria_livre_gb"] = round(kb("MemAvailable") / 1e6, 1)
    except (OSError, KeyError, ValueError):
        pass
    try:
        info["carga"] = round(os.getloadavg()[0], 2)
        info["nucleos"] = os.cpu_count()
        info["ligada_ha_dias"] = round(float(Path("/proc/uptime").read_text().split()[0]) / 86400, 1)
    except (OSError, AttributeError, ValueError):
        pass
    try:
        # A pasta de backups é só do root; o backup.sh deixa este resumo legível.
        b = json.loads(Path(BACKUP_STATUS).read_text())
        info["backup_horas"] = round((time.time() - b["quando"]) / 3600, 1)
        info["backup_mb"] = round(b["bytes"] / 1e6)
    except (OSError, ValueError, KeyError):
        pass
    return info
