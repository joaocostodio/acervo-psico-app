"""Ficha de cada obra do acervo, feita de madrugada (cron, 2h30), quando a CPU está parada.

A ficha tem duas partes:
  1. DADOS (sem IA, segundos): as leis que a obra cita (tabela pagina_lei), as obras do
     acervo mais parecidas com ela (média dos vetores das páginas) e, numa lei, as obras
     que a citam. É refeita toda noite: acompanha o acervo.
  2. RESUMO (IA, ~2 min por obra): a Susmi lê a abertura e as páginas mais centrais da obra
     e escreve um resumo, os pontos principais (cada um com a página) e como a obra serve
     ao estágio. Só faz o que falta; com --refazer, refaz tudo. Para antes de --ate (para
     não pegar o horário de uso) e continua na noite seguinte.

Cada ficha é um JSON em config.fichas_dir/<id_publicacao>.json; o site só lê (GET /ficha/N).
Rodar na VM:
    .venv/bin/python gerar_fichas.py --so-dados          # parte 1, todas as obras
    .venv/bin/python gerar_fichas.py --ate 06:45         # parte 1 + resumos que faltam
    .venv/bin/python gerar_fichas.py --obras 51,53 --refazer
"""
import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import httpx

import rag
from config import config
from db import pool

PASTA = Path(config.fichas_dir)
COL = config.coluna_vetor          # nome de coluna vem da configuração, não de quem usa o site
PAGINAS_LIDAS = 5                  # páginas que a IA lê por obra
CHARS_POR_PAGINA = 1100
VERSAO_RESUMO = 1                  # mudou o jeito de fazer o resumo: suba para refazer todos

SISTEMA = """Você é a Susmi, assistente do Acervo Psico, para estudantes de Psicologia.
Vai escrever a FICHA de leitura de uma obra, usando SOMENTE os trechos dela que vêm abaixo.
Regras:
- Português do Brasil, claro e direto, sem floreio. Não invente nada que não esteja nos trechos.
- "resumo": 3 ou 4 frases dizendo do que a obra trata, para quem foi feita e com que objetivo.
- "pontos": de 4 a 6 ideias principais do CONTEÚDO (o que a obra orienta, define ou garante),
  não sobre o próprio documento ou como ele foi feito. Cada uma numa frase curta, sem [p. N]
  no texto, e com a "pagina": o número que vem em [p. N] no trecho de onde ela saiu. No máximo
  2 pontos da mesma página.
- "estagio": 2 frases sobre como uma estudante de Psicologia pode usar a obra no estágio ou na prática.
- "temas": de 3 a 6 palavras-chave curtas."""

FORMATO = {
    "type": "object",
    "properties": {
        "resumo": {"type": "string"},
        "pontos": {"type": "array", "items": {
            "type": "object",
            "properties": {"texto": {"type": "string"}, "pagina": {"type": "integer"}},
            "required": ["texto", "pagina"]}},
        "estagio": {"type": "string"},
        "temas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo", "pontos", "estagio", "temas"],
}

ABERTURA = re.compile(r"apresenta[çc][ãa]o|introdu[çc][ãa]o|pref[áa]cio|considera[çc][õo]es iniciais", re.I)
CAPA = re.compile(rag.CAPA_RE.replace(r"\misbn\M", r"\bisbn\b"), re.I)


def _limpo(texto: str) -> str:
    return re.sub(r"(\w)-\s+(\w)", r"\1\2", " ".join(texto.split()))


def _obras(conn) -> list[dict]:
    return [{"id": r[0], "titulo": r[1], "tipo": r[2], "id_versao": r[3]} for r in conn.execute(
        """SELECT pub.id_publicacao, pub.titulo, pub.tipo, v.id_versao
           FROM publicacao pub JOIN versao_arquivo v ON v.id_publicacao = pub.id_publicacao AND v.situacao_vigencia
           ORDER BY pub.id_publicacao""").fetchall()]


# ---------- Parte 1: dados (sem IA) ----------

def _parecidas(conn) -> dict[int, list[tuple[int, float]]]:
    """Para cada obra, as outras mais parecidas (cosseno entre as médias dos vetores das páginas)."""
    linhas = conn.execute(f"""
        WITH c AS (SELECT v.id_publicacao, avg(p.{COL}) AS centro
                     FROM pagina p JOIN versao_arquivo v USING (id_versao)
                    WHERE v.situacao_vigencia AND p.{COL} IS NOT NULL AND length(p.conteudo_texto) >= 300
                    GROUP BY 1)
        SELECT a.id_publicacao, b.id_publicacao, 1 - (a.centro <=> b.centro)
          FROM c a JOIN c b ON a.id_publicacao <> b.id_publicacao""").fetchall()
    por: dict[int, list[tuple[int, float]]] = {}
    for a, b, s in linhas:
        por.setdefault(a, []).append((b, float(s)))
    return {a: sorted(l, key=lambda x: -x[1]) for a, l in por.items()}


def _leis_por_obra(conn) -> dict[int, list[dict]]:
    por: dict[int, list[dict]] = {}
    for id_pub, id_lei, numero, ano, popular, n in conn.execute(
        """SELECT v.id_publicacao, l.id_lei, l.numero_lei, l.ano, l.nome_popular, count(DISTINCT pl.id_pagina)
             FROM pagina_lei pl JOIN lei l USING (id_lei)
             JOIN pagina p USING (id_pagina) JOIN versao_arquivo v USING (id_versao)
            WHERE v.situacao_vigencia
            GROUP BY 1, 2, 3, 4, 5
            ORDER BY 1, 6 DESC, l.nome_popular IS NULL, 3"""):
        base = f"Lei nº {numero}" + (f"/{ano}" if ano else "")
        por.setdefault(id_pub, []).append(  # "Código Penal (Lei nº 2.848/1940)"
            {"id_lei": id_lei, "nome": f"{popular} ({base})" if popular else base, "paginas": n})
    return por


def _obra_da_lei(nome: str, id_por_titulo: dict[str, int]) -> int | None:
    """A lei está no acervo como obra própria? ('Lei nº 11.340/2006 (...)' -> id da Maria da Penha)."""
    for titulo, rx in rag._NOMEADAS:
        if " - Lei - " in titulo and rx.search(nome):
            return id_por_titulo.get(titulo)
    return None


def dados(conn) -> dict[int, dict]:
    obras = _obras(conn)
    id_por_titulo = {o["titulo"]: o["id"] for o in obras}
    titulo_de = {o["id"]: o["titulo"] for o in obras}
    parecidas = _parecidas(conn)
    leis = _leis_por_obra(conn)
    # Lei no acervo -> as obras que a citam (para a ficha da lei).
    citada_por: dict[int, list[dict]] = {}
    for id_pub, lista in leis.items():
        for l in lista:
            l["id_publicacao"] = _obra_da_lei(l["nome"], id_por_titulo)
            if l["id_publicacao"] and l["id_publicacao"] != id_pub:
                citada_por.setdefault(l["id_publicacao"], []).append(
                    {"id_publicacao": id_pub, "titulo": titulo_de[id_pub], "paginas": l["paginas"]})
    saida = {}
    for o in obras:
        i = o["id"]
        saida[i] = {
            "id_publicacao": i,
            "titulo": o["titulo"],
            "leis": [{k: l[k] for k in ("nome", "paginas", "id_publicacao")}
                     for l in leis.get(i, []) if l["id_publicacao"] != i][:8],
            "parecidas": [{"id_publicacao": b, "titulo": titulo_de[b], "semelhanca": round(s, 3)}
                          for b, s in parecidas.get(i, [])[:4] if b in titulo_de],
            "citada_por": sorted(citada_por.get(i, []), key=lambda x: -x["paginas"])[:12],
        }
    return saida


# ---------- Parte 2: resumo (IA) ----------

def paginas_para_ler(conn, obra: dict) -> list[tuple[int, str]]:
    """A abertura (apresentação/introdução; numa lei, as 2 primeiras páginas) + as páginas mais
    centrais da obra (as mais perto da média dos vetores). Até PAGINAS_LIDAS, em ordem."""
    linhas = conn.execute(f"""
        WITH c AS (SELECT avg({COL}) AS centro FROM pagina
                    WHERE id_versao = %(v)s AND {COL} IS NOT NULL AND length(conteudo_texto) >= 700)
        SELECT p.numero_pagina_pdf, p.conteudo_texto, p.{COL} <=> c.centro
          FROM pagina p, c
         WHERE p.id_versao = %(v)s AND length(p.conteudo_texto) >= 300
         ORDER BY p.numero_pagina_pdf""", {"v": obra["id_versao"]}).fetchall()
    if not linhas:
        return []
    lei = obra["tipo"] == "Lei"
    def capa(n, t):
        return not lei and n <= 8 and (len(t) < 700 or CAPA.search(t))
    escolha: list[int] = []
    if lei:  # o começo da lei diz o que ela é e define os termos (ex.: Art. 7º da Maria da Penha)
        escolha += [n for n, _, _ in linhas[:2]]
    elif obra["tipo"] in ("Norma do CFP", "Manual do governo"):
        # Nas Referências Técnicas a apresentação é um texto padrão do CREPOP (a metodologia),
        # igual em todas: lá a ficha sai só das páginas centrais.
        abertura = [n for n, t, _ in linhas if n <= 14 and len(t) >= 700 and ABERTURA.search(t[:400]) and not CAPA.search(t)]
        escolha += abertura[:1]
    centrais = sorted((d if d is not None else 9, n) for n, t, d in linhas if not capa(n, t))
    for _, n in centrais:
        if len(escolha) >= PAGINAS_LIDAS:
            break
        if n not in escolha:
            escolha.append(n)
    texto = {n: t for n, t, _ in linhas}
    return [(n, _limpo(texto[n])[:CHARS_POR_PAGINA]) for n in sorted(escolha)]


def resumir(obra: dict, paginas: list[tuple[int, str]]) -> dict:
    nome = rag._nome_fonte(obra["titulo"])
    trechos = "\n\n".join(f"[p. {n}]\n{t}" for n, t in paginas)
    prompt = f"OBRA: {nome} ({obra['tipo'] or 'Referência do CREPOP/CFP'})\n\nTRECHOS:\n{trechos}\n\nFICHA (JSON):"
    corpo = {"model": config.chat_model, "system": SISTEMA, "prompt": prompt, "stream": False,
             "format": FORMATO, "keep_alive": -1,
             # num_ctx igual ao do site: se mudar, o Ollama recarrega o modelo
             "options": {"temperature": 0.2, "num_predict": 700, "num_ctx": config.num_ctx}}
    if config.ia_pensar is not None:
        corpo["think"] = config.ia_pensar
    t0 = time.time()
    r = httpx.post(f"{config.ollama_url}/api/generate", json=corpo, timeout=900)
    r.raise_for_status()
    d = json.loads(r.json()["response"])
    lidas = {n for n, _ in paginas}
    pontos, por_pagina = [], {}
    for p in d.get("pontos", []):
        if not isinstance(p, dict) or not str(p.get("pagina", "")).isdigit():
            continue
        n = int(p["pagina"])
        texto = " ".join(re.sub(r"\s*\[p\.\s*[\d,\s]+\]\s*", " ", str(p.get("texto", ""))).split())
        # Página que a IA não leu é página inventada: o ponto sai (pode ter vindo da
        # memória do modelo, e não dá para conferir). Até 2 pontos por página.
        if texto and n in lidas and por_pagina.get(n, 0) < 2:
            por_pagina[n] = por_pagina.get(n, 0) + 1
            pontos.append({"texto": texto, "pagina": n})
    return {
        "resumo": " ".join(str(d.get("resumo", "")).split()),
        "pontos": pontos[:6],
        "estagio": " ".join(str(d.get("estagio", "")).split()),
        "temas": [" ".join(str(t).split()) for t in d.get("temas", []) if str(t).strip()][:6],
        "paginas_lidas": sorted(lidas),
        "modelo": config.chat_model,
        "versao_resumo": VERSAO_RESUMO,
        "gerada_em": datetime.now().isoformat(timespec="minutes"),
        "segundos": round(time.time() - t0),
    }


# ---------- Gravação ----------

def ler(i: int) -> dict:
    try:
        return json.loads((PASTA / f"{i}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def gravar(i: int, ficha: dict) -> None:
    PASTA.mkdir(parents=True, exist_ok=True)
    tmp = PASTA / f".{i}.json.tmp"
    tmp.write_text(json.dumps(ficha, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o644)  # o site (usuário acervo) só lê
    tmp.replace(PASTA / f"{i}.json")


def _prazo(ate: str | None) -> datetime | None:
    """'--ate 09:30': a próxima vez que o relógio (da VM, em UTC) marcar 09:30 a partir de agora."""
    if not ate:
        return None
    h, m = map(int, ate.split(":"))
    agora = datetime.now()
    prazo = agora.replace(hour=h, minute=m, second=0, microsecond=0)
    return prazo if prazo > agora else prazo + timedelta(days=1)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-dados", action="store_true", help="só a parte sem IA")
    ap.add_argument("--ate", help="HH:MM: não começa resumo novo depois desse horário")
    ap.add_argument("--obras", help="ids separados por vírgula (padrão: todas)")
    ap.add_argument("--refazer", action="store_true", help="refaz os resumos que já existem")
    a = ap.parse_args()
    prazo = _prazo(a.ate)
    pool.open()
    t0 = time.strftime("%F %T")
    with pool.connection() as conn:
        base = dados(conn)
        obras = {o["id"]: o for o in _obras(conn)}
    so = {int(x) for x in a.obras.split(",")} if a.obras else None
    for i, d in base.items():  # parte 1: sempre, mantendo o resumo que já existe
        velha = ler(i)
        gravar(i, {**velha, **d})
    print(f"{t0} fichas: dados de {len(base)} obras", flush=True)
    if a.so_dados:
        pool.close()
        return
    feitas = erros = 0
    # Obras menores primeiro: leis e normas saem logo na 1ª noite.
    with pool.connection() as conn:
        tamanho = dict(conn.execute(
            "SELECT id_versao, count(*) FROM pagina GROUP BY 1").fetchall())
    fila = sorted((o for o in obras.values() if not so or o["id"] in so),
                  key=lambda o: tamanho.get(o["id_versao"], 0))
    for o in fila:
        atual = ler(o["id"])
        if not a.refazer and atual.get("resumo") and atual.get("versao_resumo") == VERSAO_RESUMO:
            continue
        if prazo and datetime.now() >= prazo:
            print(f"  parei: passou de {a.ate}", flush=True)
            break
        try:
            with pool.connection() as conn:
                paginas = paginas_para_ler(conn, o)
            if not paginas:
                continue
            r = resumir(o, paginas)
            gravar(o["id"], {**ler(o["id"]), **r})
            feitas += 1
            print(f"  {o['titulo']}: {r['segundos']} s, páginas {r['paginas_lidas']}", flush=True)
        except Exception as e:  # noqa: BLE001 — uma obra com problema não para as outras
            erros += 1
            print(f"  erro em {o['titulo']}: {e}", flush=True)
    print(f"{time.strftime('%F %T')} fichas: {feitas} resumos feitos, {erros} erros", flush=True)
    pool.close()


if __name__ == "__main__":
    main()
