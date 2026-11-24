"""Ingere todos os PDFs de uma pasta (o acervo). Uso: python ingest_all.py <pasta>.

Deriva o título do nome do arquivo. Pula PDFs já ingeridos (hash igual).
Pensado para rodar como job de fundo; imprime progresso linha a linha.
Usa o papel administrador do banco (DATABASE_URL_ADMIN no .env).

Tipo e fonte saem do nome do arquivo:
  "2006 - Lei - Maria da Penha.pdf"      -> Lei, Presidência da República
  "2005 - CFP - Codigo de Etica.pdf"     -> Norma do CFP, CFP
  "2013 - Gov - Caderno ... .pdf"        -> Manual do governo, Ministério da Saúde (ou MDS, se SUAS)
  qualquer outro (as RTs do CREPOP)      -> Referência Técnica, CREPOP/CFP
"""
import re
import sys
import time
from pathlib import Path

import ingest


def tipo_e_fonte(titulo: str) -> tuple[str, str]:
    if re.match(r"^\d{4} - Lei - ", titulo):
        return "Lei", "Presidência da República"
    if re.match(r"^\d{4} - CFP - ", titulo):
        return "Norma do CFP", "CFP"
    if re.match(r"^\d{4} - Gov - ", titulo):
        suas = re.search(r"PNAS|Tipificacao|PAIF|CREAS", titulo)
        return "Manual do governo", ("Ministério do Desenvolvimento Social" if suas else "Ministério da Saúde")
    return "Referência Técnica", "CREPOP/CFP"


if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    pdfs = sorted(pasta.glob("*.pdf"))
    print(f"{len(pdfs)} PDFs em {pasta}", flush=True)

    for i, p in enumerate(pdfs, start=1):
        titulo = p.stem
        t0 = time.time()
        try:
            r = ingest.ingerir_pdf(str(p), titulo, *tipo_e_fonte(titulo))
            print(
                f"[{i}/{len(pdfs)}] {p.name}: {r.get('status')} "
                f"paginas={r.get('paginas_com_texto', '-')} ({round(time.time() - t0, 1)}s)",
                flush=True,
            )
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(pdfs)}] {p.name}: ERRO {e}", flush=True)

    print("FIM_INGEST_ALL", flush=True)
