"""Cria/atualiza o banco: schema, vocabulário controlado e papéis com privilégio mínimo.

Rodar DENTRO da VM, como administrador (usa DATABASE_URL_ADMIN):
    APP_DB_PASSWORD=<senha do papel acervo_app> python migrar.py

Pode rodar quantas vezes quiser: tudo é idempotente.
"""
import os
import sys
from pathlib import Path

from psycopg import sql

import curadoria
import db
from vocabulario import CONCEITOS

PAPEL_APP = "acervo_app"

# O que o servidor web pode fazer em cada tabela. Nada além disso.
#   - acervo e vocabulário: só ler
#   - histórico: só acrescentar (nunca editar nem apagar o que já foi registrado)
PERMISSOES = {
    "fonte_emissora": "SELECT",
    "publicacao": "SELECT",
    "versao_arquivo": "SELECT",
    "pagina": "SELECT",
    "conceito": "SELECT",
    "termo": "SELECT",
    "usuario": "SELECT",
    "registro_consulta": "SELECT, INSERT",
    "cita_pagina": "SELECT, INSERT",
    "evento_uso": "SELECT, INSERT",
    # Fase 2 do modelo: classificação e leis (curadoria.py preenche, como administrador).
    "categoria_fonte": "SELECT",
    "eixo_tematico": "SELECT",
    "publicacao_categoria": "SELECT",
    "publicacao_eixo": "SELECT",
    "lei": "SELECT",
    "pagina_lei": "SELECT",
    # 👍/👎 e respostas guardadas: só acrescentar.
    "avaliacao_resposta": "SELECT, INSERT",
    "resposta_guardada": "SELECT, INSERT",
    # Tempo de cada resposta da IA (painel do administrador): só acrescentar.
    "metrica_resposta": "SELECT, INSERT",
}


def aplicar_schema(conn) -> None:
    conn.execute((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    print("schema ok")


def carregar_vocabulario(conn) -> None:
    vistos: dict[str, str] = {}
    for preferido, termos in CONCEITOS.items():
        for t in termos:
            if t.lower() in vistos and vistos[t.lower()] != preferido:
                sys.exit(f"Termo '{t}' está em dois conceitos: '{vistos[t.lower()]}' e '{preferido}'.")
            vistos[t.lower()] = preferido
    for preferido, termos in CONCEITOS.items():
        id_conceito = conn.execute(
            """INSERT INTO conceito (termo_preferido) VALUES (%s)
               ON CONFLICT (termo_preferido) DO UPDATE SET termo_preferido = EXCLUDED.termo_preferido
               RETURNING id_conceito""",
            (preferido,),
        ).fetchone()[0]
        for t in termos:
            conn.execute(
                """INSERT INTO termo (id_conceito, texto) VALUES (%s, %s)
                   ON CONFLICT (texto) DO UPDATE SET id_conceito = EXCLUDED.id_conceito""",
                (id_conceito, t),
            )
    n = conn.execute("SELECT count(*) FROM conceito").fetchone()[0]
    m = conn.execute("SELECT count(*) FROM termo").fetchone()[0]
    print(f"vocabulário ok: {n} conceitos, {m} termos")


def configurar_papel_app(conn) -> None:
    senha = os.environ.get("APP_DB_PASSWORD")
    existe = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (PAPEL_APP,)).fetchone()
    if not existe:
        if not senha:
            sys.exit("Primeira vez: defina APP_DB_PASSWORD para criar o papel acervo_app.")
        conn.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
            sql.Identifier(PAPEL_APP), sql.Literal(senha)))
    elif senha:
        conn.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
            sql.Identifier(PAPEL_APP), sql.Literal(senha)))

    papel = sql.Identifier(PAPEL_APP)
    banco = conn.execute("SELECT current_database()").fetchone()[0]
    # Começa do zero e dá só o necessário.
    conn.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(papel))
    conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
    conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(papel))
    conn.execute(sql.SQL("REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(banco)))
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(banco), papel))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(papel))
    for tabela, privs in PERMISSOES.items():
        conn.execute(sql.SQL("GRANT {} ON {} TO {}").format(sql.SQL(privs), sql.Identifier(tabela), papel))
    # Identidades (ids automáticos) das duas tabelas em que o app insere.
    conn.execute(sql.SQL("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO {}").format(papel))
    # Freios: nenhuma consulta do app passa de 20 s; no máximo 10 conexões.
    conn.execute(sql.SQL("ALTER ROLE {} SET statement_timeout = '20s'").format(papel))
    conn.execute(sql.SQL("ALTER ROLE {} SET idle_in_transaction_session_timeout = '60s'").format(papel))
    conn.execute(sql.SQL("ALTER ROLE {} CONNECTION LIMIT 10").format(papel))
    conn.execute(sql.SQL("ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION").format(papel))
    print(f"papel {PAPEL_APP} ok (só leitura no acervo; só inserção no histórico)")


if __name__ == "__main__":
    with db.conectar_admin() as conn:
        aplicar_schema(conn)
        carregar_vocabulario(conn)
        curadoria.aplicar(conn)
        configurar_papel_app(conn)
        conn.commit()
    print("FIM_MIGRAR")
