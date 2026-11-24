"""Conexões com o Postgres e registro do tipo vector (pgvector).

São dois papéis de banco, de propósito:
- `pool` (DATABASE_URL): papel restrito `acervo_app`, o único que o servidor web usa.
  Só tem SELECT no acervo e INSERT no histórico de consultas. Não apaga, não altera,
  não cria nem derruba tabela: mesmo que alguém achasse uma brecha na API, o próprio
  banco recusaria o DROP/DELETE.
- `conectar_admin()` (DATABASE_URL_ADMIN): dono das tabelas. Só os scripts de linha
  de comando, rodados dentro da VM, usam.
"""
import psycopg
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from config import config


def _configure(conn):
    register_vector(conn)
    conn.commit()


pool = ConnectionPool(
    config.database_url, min_size=1, max_size=5, open=False, configure=_configure
)


def init() -> None:
    pool.open()


def conectar_admin() -> psycopg.Connection:
    if not config.database_url_admin:
        raise SystemExit("Defina DATABASE_URL_ADMIN no .env para rodar este script.")
    conn = psycopg.connect(config.database_url_admin)
    try:
        register_vector(conn)
    except psycopg.ProgrammingError:
        conn.rollback()  # banco novo: a extensão vector ainda não existe (migrar.py cria)
    return conn
