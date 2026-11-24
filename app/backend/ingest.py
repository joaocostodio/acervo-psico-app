"""Ingestão de PDF: extrai texto por página, gera embeddings e grava no banco.

Uma página do PDF = uma linha em `pagina` = um embedding. Isso casa com o MER
(PAGINA.vetor_conteudo) e permite citar a página exata na resposta.

Só roda pela linha de comando, dentro da VM (ingest_all.py), com o papel
administrador do banco. O servidor web não tem permissão de gravar no acervo.
"""
import hashlib
from pathlib import Path

import pdfplumber

import db
import embeddings

LOTE_EMBED = 16  # páginas por chamada de embedding


def _hash_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(8192), b""):
            h.update(bloco)
    return h.hexdigest()


def ingerir_pdf(
    caminho_pdf: str,
    titulo: str,
    tipo: str = "Documento",
    fonte: str = "CREPOP/CFP",
    url_oficial: str | None = None,
) -> dict:
    caminho = Path(caminho_pdf)
    hash_arq = _hash_arquivo(caminho)

    with db.conectar_admin() as conn:
        # Evita reingerir o mesmo arquivo.
        existe = conn.execute(
            "SELECT id_versao FROM versao_arquivo WHERE hash_arquivo = %s", (hash_arq,)
        ).fetchone()
        if existe:
            return {"status": "ja_ingerido", "id_versao": existe[0]}

        id_fonte = conn.execute(
            """INSERT INTO fonte_emissora (nome_fonte) VALUES (%s)
               ON CONFLICT (nome_fonte) DO UPDATE SET nome_fonte = EXCLUDED.nome_fonte
               RETURNING id_fonte""",
            (fonte,),
        ).fetchone()[0]

        id_pub = conn.execute(
            """INSERT INTO publicacao (titulo, tipo, url_pagina_oficial, id_fonte)
               VALUES (%s, %s, %s, %s) RETURNING id_publicacao""",
            (titulo, tipo, url_oficial, id_fonte),
        ).fetchone()[0]

        id_versao = conn.execute(
            """INSERT INTO versao_arquivo (id_publicacao, hash_arquivo, caminho_pdf)
               VALUES (%s, %s, %s) RETURNING id_versao""",
            (id_pub, hash_arq, str(caminho)),
        ).fetchone()[0]

        # Extrai o texto de cada página.
        paginas: list[tuple[int, str]] = []
        with pdfplumber.open(caminho) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                # Alguns PDFs (ex.: resoluções do CFP geradas pelo SEI) trazem o caractere
                # nulo no texto, que o Postgres recusa ("cannot contain NUL"): sai aqui.
                texto = (page.extract_text() or "").replace("\x00", "").strip()
                if texto:
                    paginas.append((i, texto))

        # Gera embeddings em lotes (modelo e coluna do .env) e grava.
        col = embeddings.coluna()
        total = 0
        for ini in range(0, len(paginas), LOTE_EMBED):
            lote = paginas[ini : ini + LOTE_EMBED]
            vetores = embeddings.documentos([t for _, t in lote])
            for (num_pdf, texto), vetor in zip(lote, vetores):
                conn.execute(
                    f"""INSERT INTO pagina
                        (id_versao, numero_pagina_pdf, conteudo_texto, {col})
                        VALUES (%s, %s, %s, %s)""",
                    (id_versao, num_pdf, texto, vetor),
                )
                total += 1
        conn.commit()

    return {
        "status": "ok",
        "id_versao": id_versao,
        "titulo": titulo,
        "paginas_com_texto": total,
    }
