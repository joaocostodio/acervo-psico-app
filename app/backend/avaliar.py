"""Avalia a IA com perguntas de resposta conhecida (ia/perguntas-teste.json).

Rodar DENTRO da VM:   .venv/bin/python avaliar.py [modelo] [--saida arquivo.json]
Para cada pergunta: busca as páginas como o app faz, gera a resposta e confere
(1) se citou página quando devia (e se a página citada estava entre as lidas) e
(2) se a resposta contém algum dos termos esperados. Mostra tempo e nota final.
Com --saida, grava as respostas inteiras e os tempos (para comparar modelos lendo
o que cada um escreveu, não só a nota).
Usar antes de trocar de modelo: o modelo novo tem que acertar pelo menos o mesmo.
"""
import json
import re
import sys
import time
from pathlib import Path

import conversa
import ollama_client
import rag
from config import config
from db import pool

args = sys.argv[1:]
saida_json = None
if "--saida" in args:
    i = args.index("--saida")
    saida_json = args[i + 1]
    del args[i:i + 2]
if args:
    config.chat_model = args[0]
casos = json.loads((Path(__file__).parent / "ia" / "perguntas-teste.json").read_text(encoding="utf-8"))
pool.open()

acertos, total_s, registros = 0, 0.0, []
for i, c in enumerate(casos["perguntas"], start=1):
    t0 = time.time()
    # O mesmo caminho do site (main.py): dados pessoais mascarados, conversa simples
    # respondida sem IA, resposta limpa do "Não encontrei" indevido.
    tinha_dados, pergunta = conversa.dados_pessoais(c["pergunta"])
    pronta = conversa.responder(pergunta)
    bruto = None
    if pronta:
        paginas, saida, texto = [], {"leitura_s": 0}, pronta
    else:
        paginas, _ = rag.recuperar(pergunta, None, None)
        saida = ollama_client.gerar(rag.montar_prompt(pergunta, paginas),
                                    max_tokens=rag.tokens_resposta(pergunta))
        bruto = saida["texto"]
        lidas_ = {p["pagina"] for p in paginas}
        texto = rag.limpar_resposta(rag.tirar_paginas_inventadas(bruto, lidas_))
        if texto != bruto.strip():
            print("       (a limpeza do servidor mexeu nesta resposta)")
    if tinha_dados:
        texto = conversa.com_aviso(texto)
    dt = time.time() - t0
    total_s += dt
    citadas = {int(n) for n in re.findall(r"p\.\s*(\d+)", texto)}
    lidas = {p["pagina"] for p in paginas}
    citou_ok = (bool(citadas) and citadas <= lidas) if c["deve_citar"] else True
    conteudo_ok = any(t.lower() in texto.lower() for t in c["deve_conter_algum"])
    ok = citou_ok and conteudo_ok
    acertos += ok
    print(f"[{'OK ' if ok else 'ERRO'}] {i}. {c['pergunta']}  ({dt:.0f}s, leitura {saida['leitura_s']}s)", flush=True)
    if not citou_ok:
        print(f"       citação: citou {sorted(citadas) or 'nada'}; páginas lidas {sorted(lidas)}")
    if not conteudo_ok:
        print(f"       faltou algum de: {c['deve_conter_algum']}")
    print("       " + " ".join(texto.split())[:260], flush=True)
    registros.append({
        "pergunta": c["pergunta"], "ok": ok, "citou_ok": citou_ok, "conteudo_ok": conteudo_ok,
        "tempo_s": round(dt, 1), "leitura_s": saida.get("leitura_s"),
        "tokens": saida.get("tokens"), "tokens_por_segundo": saida.get("tokens_por_segundo"),
        "paginas_lidas": [f"{rag._nome_fonte(p['titulo'])} p. {p['pagina']}" for p in paginas],
        "resposta": texto, "bruto": bruto,
    })

n = len(casos["perguntas"])
print(f"\nMODELO {config.chat_model}: {acertos}/{n} certas · média {total_s / n:.0f}s por pergunta")
if saida_json:
    Path(saida_json).write_text(json.dumps({
        "modelo": config.chat_model, "acertos": acertos, "total": n,
        "media_s": round(total_s / n, 1), "casos": registros,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
