"""Respostas prontas, feitas de madrugada (cron, 1h), quando a CPU da VM está parada.

Para cada pergunta da lista (exemplos da tela inicial + perguntas reais que se repetiram),
faz o mesmo caminho do site (busca as páginas, monta o prompt, a IA escreve, a resposta é
limpa) e guarda em resposta_guardada. Quem clicar no exemplo ou repetir a pergunta recebe a
resposta na hora, em vez de esperar ~1,5 min. Só gera o que ainda não está guardado: depois
da 1ª noite, roda em segundos, a não ser que o modelo, as instruções, o mapa ou o acervo
mudem (a chave da resposta guardada muda junto e ela é refeita).

Não grava no histórico de consultas (não é uso de ninguém). Rodar na VM:
    .venv/bin/python pre_responder.py
"""
import time

import conversa
import ollama_client
import rag
from db import pool

# Os exemplos da tela inicial (static/index.html, botões "exemplo") e perguntas reais.
PERGUNTAS = [
    "Qual o papel do psicólogo no CAPS?",
    "Como atender uma vítima de violência sexual?",
    "O que o acervo diz sobre sigilo profissional?",
    "Como acolher uma mulher em situação de violência?",
    "O que é a Lei Maria da Penha?",
    "qual a lei que protege as mulheres?",
    "Como o psicólogo atua no CRAS?",
    "qual o objetivo do crepop?",
    "Qual o papel do psicólogo no CRAS?",
    "Como a Psicologia atua com a população em situação de rua?",
    "Como a Psicologia atua com pessoas idosas?",
    "O que é redução de danos?",
]
REPETIDAS_DIAS = 60  # perguntas reais feitas 2+ vezes nesse período também entram


def perguntas_repetidas() -> list[str]:
    with pool.connection() as conn:
        return [p for (p,) in conn.execute(
            """SELECT max(r.pergunta) FROM registro_consulta r JOIN usuario u USING (id_usuario)
               WHERE r.modo = 'perguntar' AND NOT u.admin
                 AND r.criado_em > now() - %s * interval '1 day'
               GROUP BY lower(trim(r.pergunta)) HAVING count(*) >= 2""", (REPETIDAS_DIAS,)).fetchall()]


def preparar(pergunta: str) -> str:
    """'pronta' (já guardada), 'feita' (gerada agora), 'pulada' (não vai para a IA)."""
    _, pergunta = conversa.dados_pessoais(pergunta)
    if conversa.responder(pergunta):
        return "pulada"
    paginas, _ = rag.recuperar(pergunta, None, None)
    if not paginas:
        return "pulada"
    prompt = rag.montar_prompt(pergunta, paginas)
    chave = rag._chave_resposta(prompt)
    if rag._resposta_guardada(chave):
        return "pronta"
    saida = ollama_client.gerar(prompt, max_tokens=rag.tokens_resposta(pergunta))
    texto = rag.limpar_resposta(rag.tirar_paginas_inventadas(saida["texto"], {p["pagina"] for p in paginas}))
    if texto.strip():
        with pool.connection() as conn:
            conn.execute("INSERT INTO resposta_guardada (chave, resposta) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                         (chave, texto))
    return "feita"


def main() -> None:
    pool.open()
    lista = list(dict.fromkeys(PERGUNTAS + perguntas_repetidas()))  # sem repetir, na ordem
    t0 = time.strftime("%F %T")
    contagem: dict[str, int] = {}
    for p in lista:
        t = time.time()
        try:
            r = preparar(p)
        except Exception as e:  # noqa: BLE001 — uma pergunta com problema não para as outras
            r = "erro"
            print(f"  erro em {p!r}: {e}", flush=True)
        contagem[r] = contagem.get(r, 0) + 1
        if r == "feita":
            print(f"  feita em {time.time() - t:.0f} s: {p}", flush=True)
    print(f"{t0} respostas prontas: {len(lista)} perguntas · {contagem}", flush=True)
    pool.close()


if __name__ == "__main__":
    main()
