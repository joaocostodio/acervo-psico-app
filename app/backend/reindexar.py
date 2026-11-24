"""Recalcula os vetores de todas as páginas com OUTRO modelo de embedding, numa coluna
separada, sem parar a busca que está no ar.

Rodar DENTRO da VM (papel administrador), de preferência à noite:
    .venv/bin/python reindexar.py embeddinggemma vetor_conteudo_2
Pode parar e rodar de novo: continua de onde parou (só pega páginas sem vetor).
Com --refazer, apaga a coluna antes e recomeça.
Quando terminar, no .env:  EMBED_MODEL=embeddinggemma  e  COLUNA_VETOR=vetor_conteudo_2
e reinicie o serviço. Para voltar atrás, basta o .env antigo: a coluna velha fica intacta.
"""
import sys
import time

import db
import embeddings
from config import config

LOTE = 8


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2 or args[1] not in embeddings.COLUNAS:
        sys.exit(__doc__)
    modelo, col = args
    if col == config.coluna_vetor:
        sys.exit(f"{col} é a coluna que a busca usa agora: escolha a outra.")
    with db.conectar_admin() as conn:
        if "--refazer" in sys.argv:
            conn.execute(f"UPDATE pagina SET {col} = NULL")
            conn.commit()
        faltam = conn.execute(f"SELECT count(*) FROM pagina WHERE {col} IS NULL").fetchone()[0]
        print(f"{faltam} páginas para calcular com {modelo} -> {col}", flush=True)
        feitas, t0 = 0, time.time()
        while True:
            lote = conn.execute(
                f"SELECT id_pagina, conteudo_texto FROM pagina WHERE {col} IS NULL ORDER BY id_pagina LIMIT %s",
                (LOTE,)).fetchall()
            if not lote:
                break
            vetores = embeddings.documentos([t for _, t in lote], modelo)
            with conn.cursor() as cur:
                cur.executemany(f"UPDATE pagina SET {col} = %s WHERE id_pagina = %s",
                                [(v, i) for (i, _), v in zip(lote, vetores)])
            conn.commit()
            feitas += len(lote)
            if feitas % 200 < LOTE:
                passo = (time.time() - t0) / feitas
                print(f"  {feitas}/{faltam} · {passo:.2f} s/página · faltam ~{(faltam - feitas) * passo / 60:.0f} min",
                      flush=True)
    print(f"FIM: {feitas} páginas em {(time.time() - t0) / 60:.0f} min")


if __name__ == "__main__":
    main()
