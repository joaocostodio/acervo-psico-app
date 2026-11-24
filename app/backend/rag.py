"""Busca híbrida + RAG estrito: acha as páginas mais relevantes e gera a resposta citando-as.

A busca junta dois jeitos de procurar e combina as duas listas (RRF):
  1. por SIGNIFICADO: embedding da consulta x embedding de cada página (pgvector/HNSW);
  2. por PALAVRA: busca textual em português (radicais, sem acento), expandida com o
     vocabulário controlado — "agressão" também procura "violência", "maus-tratos"...
Assim, quem digita com outras palavras ainda acha a página, e o que foi achado por
palavra vem com os termos grifados (no trecho e no PDF).
"""
import hashlib
import math
import re
import time
from pathlib import Path

from db import pool
import embeddings
import mapa
import ollama_client
import referencias
from config import config

# O jeito de responder (educada, só com o acervo, citando página) está fixo no modelo
# próprio "acervo-psico" (ia/Modelfile). Aqui vai só o material da pergunta — e um
# lembrete curto da regra principal, caso se use um modelo sem o Modelfile.
PROMPT_BASE = """{mapa}Use SOMENTE os trechos abaixo e cite as páginas no formato [p. N]. Se não
estiver nos trechos, diga: "Não encontrei isso nas páginas consultadas."

TRECHOS:
{contexto}

PERGUNTA: {pergunta}{pedido}
RESPOSTA:"""

# Pedido de TEXTO LONGO (artigo, resumo expandido...): conversas reais de 20/10/2026
# ("desenvolva um artigo sobre ansiedade na juventude", "resumo expandido sobre o crepop")
# recebiam o formato curto de pergunta. Agora a IA lê mais páginas e organiza em seções.
_LONGO = re.compile(
    # "artigo" só no sentido de redação: "o artigo 5 da lei" é pergunta curta.
    r"\b(?:um|uma|meu|minha)\s+(?:artigo|ensaio|redaç(?:ão|ao)|dissertaç(?:ão|ao)|texto)\s+(?:sobre|acerca|a respeito|com)"
    r"|\b(?:escrev|desenvolv|cri|faç|fac|elabor|redij|produz|mont|ger)\w*\s+(?:um|uma|o|a)?\s*"
    r"(?:artigo|ensaio|reda|dissert|texto|trabalho|resumo)"
    r"|\bresumo\s+(?:expandido|detalhado|completo)|\bfichamento\b|\btexto\s+(?:completo|longo|acad[êe]mico)",
    re.I,
)
PEDIDO_LONGO = ("\n(Pedido de texto longo: escreva um texto organizado, com uma introdução curta, "
                "seções com subtítulos em **negrito** e uma conclusão. Use TODOS os trechos que "
                "servirem e cite a página [p. N] depois de cada informação. Não invente nada que "
                "não esteja nos trechos.)")


def _mapa() -> str:
    """O mapa do acervo (mapa.py) vem antes de tudo: é sempre o mesmo texto, então fica no
    cache do Ollama e não custa tempo depois do aquecimento."""
    return mapa.texto() + "\n\n" if config.usar_mapa else ""


def prefixo_fixo() -> str:
    """Começo do prompt que é igual em toda pergunta (mapa + regra), para o aquecimento."""
    return PROMPT_BASE.split("{contexto}")[0].format(mapa=_mapa())


def eh_pedido_longo(pergunta: str) -> bool:
    return bool(_LONGO.search(pergunta))


def tokens_resposta(pergunta: str) -> int:
    return config.longo_tokens if eh_pedido_longo(pergunta) else config.max_tokens_resposta

CANDIDATOS = 40   # quantas páginas cada busca (significado e palavra) indica antes de combinar
RRF_K = 60        # constante padrão do Reciprocal Rank Fusion
MARCA_INI, MARCA_FIM = "⟦", "⟧"  # ⟦ ⟧ — marcadores do grifo vindos do Postgres
SEM_HIFEN = r"regexp_replace(p.conteudo_texto, '(\w)-\s*\n\s*(\w)', '\1\2', 'g')"
# Página do LIVRO (para citar em ABNT; curadoria/paginacao.py) e, em obra escaneada em
# página dupla, a segunda página impressa que está na mesma página do PDF.
IMPRESSA_SQL = """p.numero_pagina_impressa,
    (SELECT p.numero_pagina_impressa + 1 FROM pagina n
      WHERE n.id_versao = p.id_versao AND n.numero_pagina_pdf = p.numero_pagina_pdf + 1
        AND n.numero_pagina_impressa = p.numero_pagina_impressa + 2)"""


# ---------- Expansão da consulta pelo vocabulário controlado ----------

def _q(lexema: str) -> str:
    """Lexema entre aspas para montar um tsquery (escapa aspas e barra)."""
    return "'" + lexema.replace("\\", "\\\\").replace("'", "''") + "'"


# Palavras que o dicionário do Postgres não considera vazias, mas que numa busca
# deste acervo não carregam o assunto ("agressão CONTRA mulher", "papel do PSICÓLOGO").
# Elas ainda contam dentro de expressões ("violência contra a mulher"), só não são
# exigidas nem grifadas sozinhas.
VAZIAS_EXTRA = (
    "contra sobre entre durante após perante acerca respeito qual quais onde como quando "
    "porque sendo ser fazer deve devem pode podem papel psicólogo psicóloga psicólogos "
    "psicólogas psicologia "
    # "Como o psicólogo ATUA no CRAS?": exigir "atua" deixava de fora as páginas que
    # explicam o CRAS e trazia o currículo de uma autora ("Atuou no CRAS…").
    "atua atuar atuam atuando atuação diz dizer dizem acervo "
    # Palavras de pergunta: "EXISTE ALGUMA lei…", "O que HÁ sobre…", "me EXPLIQUE…".
    "existe existem existir algum alguma alguns algumas há tem têm "
    "explique explicar fale falar sabe saber gostaria quero preciso"
)
# Página com menos texto que isso é capa, título de seção ou página em branco: na busca
# por sentido ela "parece" a pergunta (só tem o título) e toma o lugar de quem tem conteúdo.
MIN_CARACTERES = 300
_lex_vazias: set[str] | None = None
VAZIO = {"lexemas": [], "soltos": set(), "tsquery_e": None, "tsquery_ou": None,
         "grupos": [], "equivalencias": []}


def _vazias(conn) -> set[str]:
    global _lex_vazias
    if _lex_vazias is None:
        _lex_vazias = set(conn.execute(
            "SELECT tsvector_to_array(to_tsvector('pt_sem_acento', %s))", (VAZIAS_EXTRA,)
        ).fetchone()[0])
    return _lex_vazias


# Frases de crise em 1ª pessoa viram "suicídio" na busca por palavra. Sem isso, "quero me
# matar" vira o radical "mat" e traz "MATO Grosso", "MATE Masie" e "MATÉRIA-prima".
CRISE = re.compile(
    r"\b(?:me|se|te|nos)\s+matar\b|\bmatar-(?:me|se)\b|\bme\s+suicidar\b|\bquero\s+morrer\b"
    r"|\b(?:tirar|acabar\s+com)\s+(?:a\s+)?(?:minha|pr[óo]pria)\s+vida\b",
    re.IGNORECASE,
)


def expandir(conn, consulta: str) -> dict:
    """Quebra a consulta em grupos de sentido e troca cada grupo por seus equivalentes.

    "agressão contra mulher" vira  (agress | violenc | maus-trat <-> …) & (mulh | feminin)
    — "contra" sai. Termo de várias palavras entra como expressão (<-> = "seguida de"),
    para "Maria da Penha" não grifar todo "Maria" da página. Devolve o tsquery "E"
    (todas as ideias), o "OU" (qualquer uma, para grifar) e as equivalências da tela.
    """
    consulta = CRISE.sub(" suicídio ", consulta)
    lex_q = conn.execute(
        "SELECT tsvector_to_array(to_tsvector('pt_sem_acento', %s))", (consulta,)
    ).fetchone()[0] or []
    if not lex_q:
        return VAZIO

    linhas = conn.execute(
        """SELECT t.id_conceito, c.termo_preferido, t.texto, tsvector_to_array(t.lexemas),
                  phraseto_tsquery('pt_sem_acento', t.texto)::text
           FROM termo t JOIN conceito c USING (id_conceito)
           WHERE t.id_conceito IN (
               SELECT id_conceito FROM termo
               WHERE lexemas <> ''::tsvector AND tsvector_to_array(lexemas) <@ %s::text[])""",
        (lex_q,),
    ).fetchall()

    conceitos: dict[int, dict] = {}
    for id_c, preferido, texto, lx, tq in linhas:
        c = conceitos.setdefault(id_c, {"preferido": preferido, "termos": [], "cobre": set(), "digitados": []})
        if lx and tq:
            c["termos"].append((texto, tq))
        if lx and set(lx) <= set(lex_q):
            c["cobre"] |= set(lx)
            c["digitados"].append(texto)

    # Escolhe primeiro os conceitos que cobrem mais palavras da consulta
    # ("violência contra a mulher" ganha de "violência" + "mulher" separados).
    cobertos: set[str] = set()
    grupos, equivalencias = [], []
    for c in sorted(conceitos.values(), key=lambda c: -len(c["cobre"])):
        if not c["cobre"] or c["cobre"] <= cobertos:
            continue
        cobertos |= c["cobre"]
        grupos.append([tq for _, tq in c["termos"]])
        outros = [t for t, _ in c["termos"] if t not in c["digitados"]]
        equivalencias.append({"conceito": c["preferido"], "digitado": c["digitados"], "equivalentes": outros})
    vazias = _vazias(conn)
    for lx in lex_q:
        if lx not in cobertos and lx not in vazias:
            grupos.append([_q(lx)])
    if not grupos:
        return VAZIO

    por_grupo = ["(" + " | ".join(f"({a})" for a in g) + ")" for g in grupos]
    tsquery_e = " & ".join(por_grupo)
    tsquery_ou = " | ".join(f"({a})" for g in grupos for a in g)
    lex_uteis = [x for x in lex_q if x not in vazias or x in cobertos]
    # Lexemas que valem sozinhos (termo de uma palavra); os outros só valem em expressão.
    soltos = {a[1:-1] for g in grupos for a in g if re.fullmatch(r"'[^']+'", a)}
    return {"lexemas": lex_uteis, "soltos": soltos, "tsquery_e": tsquery_e,
            "tsquery_ou": tsquery_ou, "grupos": por_grupo, "equivalencias": equivalencias}


# ---------- Busca híbrida ----------

# Obras que a pessoa NOMEIA na pergunta ("o que a Lei Maria da Penha diz…", "a Resolução
# 06/2019…", "o Código de Ética…"). As páginas dessa obra entram como candidatas, ordenadas
# pelo sentido da pergunta, e ganham peso. Sem isso, o nome da obra puxava só as páginas
# que repetem o nome (capa, apresentação) e não a que responde (prova de 10/11/2026).
# Só leis, normas e manuais: um tema como "CAPS" ou "reforma psiquiátrica" não é nome de obra.
OBRAS_NOMEADAS: dict[str, list[str]] = {
    "2006 - Lei - Maria da Penha": [r"maria da penha", r"\b11\.?340\b"],
    "1990 - Lei - ECA": [r"\beca\b", r"estatuto da crian[çc]a", r"\b8\.?069\b"],
    "2001 - Lei - Reforma Psiquiatrica": [r"\blei (da )?reforma psiqui[áa]trica", r"paulo delgado", r"\b10\.?216\b"],
    "2015 - Lei - Brasileira de Inclusao": [r"\blbi\b", r"lei brasileira de inclus", r"estatuto da pessoa com defici", r"\b13\.?146\b"],
    "2003 - Lei - Estatuto da Pessoa Idosa": [r"estatuto d[oa] (pessoa )?idos[oa]", r"\b10\.?741\b"],
    "1993 - Lei - LOAS": [r"\bloas\b", r"lei org[âa]nica da assist[êe]ncia", r"\b8\.?742\b"],
    "1990 - Lei - Organica da Saude SUS": [r"lei org[âa]nica da sa[úu]de", r"\b8\.?080\b"],
    "2017 - Lei - Escuta Protegida": [r"lei da escuta", r"\b13\.?431\b"],
    "1962 - Lei - Profissao de Psicologo": [r"\b4\.?119\b", r"lei (que regulamenta |da )?profiss[ãa]o d[eo] psic[óo]log"],
    "1971 - Lei - Conselhos de Psicologia": [r"\b5\.?766\b"],
    "2003 - Lei - Notificacao Compulsoria Violencia contra a Mulher": [r"\b10\.?778\b"],
    "2012 - Lei - SINASE": [r"lei do sinase", r"\b12\.?594\b"],
    "2006 - Lei - Drogas": [r"lei de drogas", r"\bsisnad\b", r"\b11\.?343\b"],
    "2016 - Lei - Marco Legal da Primeira Infancia": [r"marco legal da primeira inf[âa]ncia", r"\b13\.?257\b"],
    "2010 - Lei - Estatuto da Igualdade Racial": [r"estatuto da igualdade racial", r"\b12\.?288\b"],
    "2019 - Lei - Prevencao da Automutilacao e do Suicidio": [r"\b13\.?819\b", r"pol[íi]tica nacional de preven[çc][ãa]o da automutila"],
    "2012 - Lei - Autismo TEA": [r"berenice piana", r"\b12\.?764\b"],
    "2019 - Lei - Psicologia e Servico Social na Educacao Basica": [r"\b13\.?935\b"],
    "2013 - Lei - Minuto Seguinte": [r"minuto seguinte", r"\b12\.?845\b"],
    "2005 - CFP - Codigo de Etica": [r"c[óo]digo de [ée]tica"],
    "2019 - CFP - Resolucao Documentos Psicologicos": [r"\b0?6/2019\b", r"resolu[çc][ãa]o (do )?(cfp )?(n[º°o.]*\s*)?0?6\b"],
    "2018 - CFP - Resolucao Atendimento Online": [r"\b11/2018\b"],
    "2009 - CFP - Resolucao Registro Documental": [r"\b0{0,2}1/2009\b"],
    "2018 - CFP - Resolucao Pessoas Trans": [r"\b0?1/2018\b"],
    "1999 - CFP - Resolucao Orientacao Sexual": [r"\b0{0,2}1/(19)?99\b"],
    "2010 - CFP - Resolucao Perito e Assistente Tecnico": [r"\b0{0,2}8/2010\b"],
    "2022 - CFP - Cartilha Avaliacao Psicologica": [r"cartilha (de )?avalia[çc][ãa]o"],
}
_NOMEADAS = [(t, re.compile("|".join(ps), re.I)) for t, ps in OBRAS_NOMEADAS.items()]
_ids_por_titulo: dict[str, int] = {}


def obras_citadas(conn, consulta: str) -> tuple[list[int], str]:
    """ids das obras que a pergunta nomeia (versão vigente) e a pergunta SEM o nome delas.
    Dentro da obra, quem acha a página certa é o resto da pergunta: com o nome junto, o
    sentido puxava as páginas que falam da obra em si (abertura, créditos)."""
    titulos, resto = [], consulta
    for t, rx in _NOMEADAS:
        if rx.search(consulta):
            titulos.append(t)
            resto = rx.sub(" ", resto)
    if not titulos:
        return [], consulta
    faltam = [t for t in titulos if t not in _ids_por_titulo]
    if faltam:
        for t, i in conn.execute("SELECT titulo, id_publicacao FROM publicacao WHERE titulo = ANY(%s)", (faltam,)).fetchall():
            _ids_por_titulo[t] = i
    resto = re.sub(r"\b(a|o|na|no|da|do|de|pela|pelo)\s+(lei|resolu[çc][ãa]o|cfp|n[º°o.]*)\b", " ", resto, flags=re.I)
    resto = re.sub(r"\b(lei|resolu[çc][ãa]o|cfp)\b|/\d{2,4}\b|\bn[º°]\s*", " ", resto, flags=re.I)
    return [_ids_por_titulo[t] for t in titulos if t in _ids_por_titulo], " ".join(resto.split())


# Capa, créditos, expediente e sumário: nas 8 primeiras páginas, com cara de capa (curta)
# ou com estas palavras. Leis ficam de fora: "expediente" e "diretoria" são termos jurídicos.
CAPA_RE = (r"sum[áa]rio|[íi]ndice|lista de (quadros|tabelas|figuras)|dados internacionais de cataloga"
           r"|ficha catalogr|\misbn\M|todos os direitos reservados|permitida a reprodu[çc][ãa]o"
           r"|plen[áa]rio|conselheir[oa]s|diretoria|grupo de trabalho|composto por|cr[ée]ditos"
           r"|expediente|projeto gr[áa]fico|diagrama[çc][ãa]o|\.{8,}")
# Peso final = nota da combinação (RRF) × estes fatores.
_AJUSTE = """
      (CASE WHEN pub.id_publicacao = ANY(%(citadas)s::int[]) THEN 1.25 ELSE 1 END)
    * (CASE WHEN pub.tipo IN ('Lei', 'Norma do CFP') AND f.por_palavra AND f.por_sentido THEN 1.15 ELSE 1 END)
    * (CASE WHEN p.numero_pagina_pdf <= 8 AND pub.tipo IS DISTINCT FROM 'Lei'
             AND (length(p.conteudo_texto) < 700 OR p.conteudo_texto ~* %(capa)s) THEN 0.6 ELSE 1 END)"""

def _nota_por_raridade(conn, grupos: list[str]) -> tuple[str, dict]:
    """Nota de uma página = soma do peso de cada ideia da pergunta que ela contém, com
    peso maior para a ideia rara: IDF ao quadrado (IDF = log de páginas totais / páginas
    com a ideia). Ao quadrado porque, somadas, várias palavras comuns ("aplica", "serve",
    "métodos") passavam "psicodrama" (10 páginas) com o IDF simples.
    Devolve o trecho de SQL e os parâmetros dele."""
    total = conn.execute("SELECT count(*) FROM pagina").fetchone()[0] or 1
    partes, params = [], {}
    for i, g in enumerate(grupos):
        n = conn.execute("SELECT count(*) FROM pagina WHERE busca_texto @@ %s::tsquery", (g,)).fetchone()[0]
        if not n:
            continue
        params[f"g{i}"] = g
        params[f"w{i}"] = math.log(total / n) ** 2
        partes.append(f"CASE WHEN p.busca_texto @@ %(g{i})s::tsquery THEN %(w{i})s ELSE 0 END")
    if not partes:
        return "ts_rank_cd(p.busca_texto, %(q)s::tsquery)", {}
    # O ts_rank_cd só desempata entre páginas com as mesmas ideias.
    return "(" + " + ".join(partes) + ") + ts_rank_cd(p.busca_texto, %(q)s::tsquery)", params


def _buscar_paginas(conn, consulta: str, k: int, ids_publicacao: list[int] | None) -> tuple[list[dict], dict]:
    exp = expandir(conn, consulta)
    vetor = embeddings.consulta(consulta)
    col = embeddings.coluna()  # nome fixo validado (vetor_conteudo ou vetor_conteudo_2)
    filtro = ("AND length(p.conteudo_texto) >= %(min)s"
              + (" AND va.id_publicacao = ANY(%(ids)s)" if ids_publicacao else ""))
    # Se nenhuma página tem TODAS as ideias, aceita páginas com qualquer uma delas — mas a
    # nota passa a valorizar as ideias RARAS: em "me fale do psicodrama, quem criou, métodos
    # mais efetivos", "psicodrama" carrega o assunto; "métodos" está em centenas de páginas.
    tsq = exp["tsquery_e"]
    nota_sql = "ts_rank_cd(p.busca_texto, %(q)s::tsquery)"
    extras: dict = {}
    if tsq:
        tem = conn.execute(
            f"""SELECT 1 FROM pagina p JOIN versao_arquivo va USING (id_versao)
                WHERE va.situacao_vigencia AND p.busca_texto @@ %(q)s::tsquery {filtro} LIMIT 1""",
            {"q": tsq, "ids": ids_publicacao, "min": MIN_CARACTERES},
        ).fetchone()
        if not tem:
            tsq = exp["tsquery_ou"]
            nota_sql, extras = _nota_por_raridade(conn, exp["grupos"])

    ajustar = config.ajustar_busca
    citadas, sem_nome = obras_citadas(conn, consulta) if ajustar else ([], consulta)
    exp["obras_citadas"] = citadas
    exp["pergunta_sem_obra"] = sem_nome if citadas else None
    # Vetor da pergunta sem o nome da obra, para achar a página certa dentro dela.
    vetor_w = embeddings.consulta(sem_nome) if citadas and len(sem_nome) >= 8 and sem_nome != consulta else vetor
    # 3ª lista de candidatas: as páginas das obras nomeadas, pelo sentido da pergunta. O "+ 0"
    # impede o índice HNSW (são poucas centenas de páginas; com o índice e o filtro por obra,
    # a varredura iterativa percorreria o acervo inteiro procurando 12 páginas de uma lei de 3).
    lista_w = f"""
        ), w AS (
            SELECT id_pagina, row_number() OVER (ORDER BY d) AS r FROM (
                SELECT p.id_pagina, (p.{col} <=> %(vetw)s::vector) + 0 AS d
                FROM pagina p JOIN versao_arquivo va USING (id_versao)
                WHERE va.situacao_vigencia AND p.{col} IS NOT NULL
                  AND va.id_publicacao = ANY(%(citadas)s::int[]) {filtro}
                ORDER BY d LIMIT 12) s""" if citadas else ""
    uniao_w = " UNION ALL SELECT id_pagina, r, 'w' FROM w" if citadas else ""
    ordem = f"f.nota_final * {_AJUSTE}" if ajustar else "f.nota_final"

    conn.execute("SET LOCAL hnsw.ef_search = 100")
    conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
    linhas = conn.execute(
        f"""
        WITH v AS (
            SELECT id_pagina, row_number() OVER (ORDER BY d) AS r FROM (
                SELECT p.id_pagina, p.{col} <=> %(vet)s::vector AS d
                FROM pagina p JOIN versao_arquivo va USING (id_versao)
                WHERE va.situacao_vigencia AND p.{col} IS NOT NULL {filtro}
                ORDER BY d LIMIT %(n)s) s
        ), t AS (
            SELECT id_pagina, row_number() OVER (ORDER BY nota DESC) AS r FROM (
                SELECT p.id_pagina, {nota_sql} AS nota
                FROM pagina p JOIN versao_arquivo va USING (id_versao)
                WHERE %(q)s::text IS NOT NULL AND va.situacao_vigencia
                  AND p.busca_texto @@ %(q)s::tsquery {filtro}
                ORDER BY nota DESC LIMIT %(n)s) s{lista_w}
        ), f AS (
            SELECT id_pagina, sum(1.0 / (%(rrf)s + r)) AS nota_final,
                   bool_or(origem = 't') AS por_palavra, bool_or(origem IN ('v', 'w')) AS por_sentido
            FROM (SELECT id_pagina, r, 'v' AS origem FROM v
                  UNION ALL SELECT id_pagina, r, 't' FROM t{uniao_w}) x
            GROUP BY id_pagina
        )
        SELECT p.id_pagina, p.numero_pagina_pdf, p.conteudo_texto, pub.titulo, pub.id_publicacao,
               coalesce(1 - (p.{col} <=> %(vet)s::vector), 0) AS similaridade,
               f.por_palavra, f.por_sentido,
               CASE WHEN %(ou)s::text IS NULL THEN NULL ELSE
                 ts_headline('pt_sem_acento', {SEM_HIFEN}, %(ou)s::tsquery,
                   'StartSel={MARCA_INI}, StopSel={MARCA_FIM}, MaxWords=48, MinWords=24, MaxFragments=2, FragmentDelimiter=" … "')
               END AS trecho,
               CASE WHEN %(ou)s::text IS NULL THEN NULL ELSE
                 ts_headline('pt_sem_acento', {SEM_HIFEN}, %(ou)s::tsquery,
                   'StartSel={MARCA_INI}, StopSel={MARCA_FIM}, HighlightAll=true')
               END AS pagina_grifada,
               {IMPRESSA_SQL}
        FROM f
        JOIN pagina p USING (id_pagina)
        JOIN versao_arquivo va USING (id_versao)
        JOIN publicacao pub USING (id_publicacao)
        ORDER BY {ordem} DESC
        LIMIT %(k)s""",
        {"vet": vetor, "q": tsq, "ou": exp["tsquery_ou"], "n": CANDIDATOS, "rrf": RRF_K,
         "k": k, "ids": ids_publicacao, "min": MIN_CARACTERES, "citadas": citadas, "capa": CAPA_RE,
         "vetw": vetor_w,
         **extras},
    ).fetchall()

    paginas = [{
        "id_pagina": r[0], "pagina": r[1], "texto": r[2], "titulo": r[3], "id_publicacao": r[4],
        "similaridade": round(float(r[5]), 3), "por_palavra": r[6], "por_sentido": r[7],
        "trecho_marcado": r[8], "pagina_grifada": r[9],
        "pagina_impressa": r[10], "pagina_impressa_fim": r[11],
    } for r in linhas]
    _processar_grifos(conn, paginas, exp)
    _anexar_leis(conn, paginas)
    return paginas, exp


def _nome_lei(numero: str, ano: int | None, popular: str | None) -> str:
    base = f"Lei nº {numero}" + (f"/{ano}" if ano else "")
    return f"{base} ({popular})" if popular else base


def _anexar_leis(conn, paginas: list[dict]) -> None:
    """p['leis']: as leis que cada página cita (tabela pagina_lei, preenchida pela curadoria)."""
    ids = [p["id_pagina"] for p in paginas]
    leis: dict[int, list[str]] = {}
    if ids:
        for id_pagina, numero, ano, popular in conn.execute(
            """SELECT pl.id_pagina, l.numero_lei, l.ano, l.nome_popular
               FROM pagina_lei pl JOIN lei l USING (id_lei)
               WHERE pl.id_pagina = ANY(%s)
               ORDER BY l.nome_popular IS NULL, l.numero_lei""", (ids,)
        ):
            leis.setdefault(id_pagina, []).append(_nome_lei(numero, ano, popular))
    for p in paginas:
        p["leis"] = leis.get(p["id_pagina"], [])


# Uma "cadeia" é uma sequência de palavras grifadas ligadas só por espaço, hífen ou
# palavrinhas ("Lei ⟦Maria⟧ da ⟦Penha⟧", "⟦maus⟧-⟦tratos⟧") = uma expressão achada inteira.
_MARCA = re.compile(f"{MARCA_INI}([^{MARCA_FIM}]+){MARCA_FIM}")
_LIGA = r"(?:a|as|o|os|à|às|ao|aos|de|da|das|do|dos|em|na|nas|no|nos|com)"
_CADEIA = re.compile(
    f"{MARCA_INI}[^{MARCA_FIM}]+{MARCA_FIM}"
    f"(?:(?:[ \\-]+{_LIGA})*[ \\-]+{MARCA_INI}[^{MARCA_FIM}]+{MARCA_FIM})*"
)
EQUIV_INI, EQUIV_FIM = "⟪", "⟫"  # ⟪ ⟫ — grifo de termo equivalente, no trecho


def _processar_grifos(conn, paginas: list[dict], exp: dict) -> None:
    """Limpa os grifos do Postgres e monta a lista do que grifar no PDF.

    O ts_headline grifa cada palavra da consulta onde quer que apareça; aqui fica só
    o que faz sentido: expressões inteiras e palavras que são termo por si mesmas.
    Cada destaque vira {texto, tipo}: 'digitado' (o que a pessoa escreveu, em qualquer
    flexão) ou 'equivalente' (veio do vocabulário controlado).
    """
    textos = [t for p in paginas for t in (p["trecho_marcado"], p["pagina_grifada"]) if t]
    palavras = sorted({w.lower() for t in textos for w in _MARCA.findall(t)})
    lex = dict(conn.execute(
        "SELECT w, tsvector_to_array(to_tsvector('pt_sem_acento', w)) FROM unnest(%s::text[]) w",
        (palavras,),
    ).fetchall()) if palavras else {}
    soltos, digitados = exp["soltos"], set(exp["lexemas"])

    def lx(w: str) -> set[str]:
        return set(lex.get(w.lower()) or [])

    def tipo(ws: list[str]) -> str:
        return "digitado" if any(lx(w) & digitados for w in ws) else "equivalente"

    def limpar(texto: str, coleta: list | None) -> str:
        def marca_solta(mm: re.Match) -> str:
            w = mm.group(1)
            if not lx(w) & soltos:  # pedaço de expressão, sozinho: tira o grifo
                return w
            t = tipo([w])
            if coleta is not None:
                coleta.append((w, t))
            return f"{MARCA_INI}{w}{MARCA_FIM}" if t == "digitado" else f"{EQUIV_INI}{w}{EQUIV_FIM}"

        def troca(m: re.Match) -> str:
            bloco, ws = m.group(0), _MARCA.findall(m.group(0))
            if len({w.lower() for w in ws}) < 2:  # uma palavra só (ou repetida: "RAPS RAPS")
                return _MARCA.sub(marca_solta, bloco)
            t = tipo(ws)  # expressão inteira
            if coleta is not None:
                coleta.append((_MARCA.sub(r"\1", bloco), t))
                coleta.extend((w, tipo([w])) for w in ws if lx(w) & soltos)
            return bloco if t == "digitado" else _MARCA.sub(f"{EQUIV_INI}\\1{EQUIV_FIM}", bloco)
        return _CADEIA.sub(troca, texto)

    for p in paginas:
        coleta: list[tuple[str, str]] = []
        grifada = p.pop("pagina_grifada")
        if grifada:
            limpar(grifada, coleta)
        if p["trecho_marcado"]:
            p["trecho_marcado"] = limpar(p["trecho_marcado"], None)
        vistos, destaques = set(), []
        for texto, t in coleta:
            texto = " ".join(texto.split())
            if texto.lower() not in vistos:
                vistos.add(texto.lower())
                destaques.append({"texto": texto, "tipo": t})
        p["destaques"] = destaques


def _trecho_simples(texto: str, tamanho: int = 360) -> str:
    limpo = re.sub(r"(\w)- (\w)", r"\1\2", " ".join(texto.split()))
    return limpo[:tamanho]


def _trecho(p: dict) -> str:
    """Trecho para a lista de resultados: ⟦digitado⟧ e ⟪equivalente⟫ viram <mark> no front."""
    t = p.get("trecho_marcado")
    if t and (MARCA_INI in t or EQUIV_INI in t):
        return " ".join(t.split())
    return _trecho_simples(p["texto"])


# ---------- Registro (histórico) ----------

FINALIDADE = {"buscar": "métrica de uso", "perguntar": "auditoria da resposta da IA"}


def _registrar(conn, id_usuario: int | None, modo: str, pergunta: str,
               resposta: str | None, paginas: list[dict]) -> int:
    """Grava a consulta com finalidade e prazo de guarda (LGPD). Só a resposta da IA
    guarda as páginas citadas; a busca simples guarda só o termo e a hora."""
    id_consulta = conn.execute(
        """INSERT INTO registro_consulta (id_usuario, modo, pergunta, resposta, finalidade)
           VALUES (%s, %s, %s, %s, %s) RETURNING id_consulta""",
        (id_usuario, modo, pergunta, resposta, FINALIDADE[modo]),
    ).fetchone()[0]
    if modo != "perguntar":
        return id_consulta
    for p in paginas:
        conn.execute(
            """INSERT INTO cita_pagina (id_consulta, id_pagina, similaridade)
               VALUES (%s, %s, %s) ON CONFLICT DO NOTHING""",
            (id_consulta, p["id_pagina"], p["similaridade"]),
        )
    return id_consulta


def _publico(p: dict) -> dict:
    return {
        "id_pagina": p["id_pagina"],
        "titulo": p["titulo"], "id_publicacao": p["id_publicacao"], "pagina": p["pagina"],
        "similaridade": p["similaridade"], "por_palavra": p["por_palavra"],
        "por_sentido": p["por_sentido"], "destaques": p["destaques"],
        "leis": p.get("leis", []),
        "pagina_impressa": p.get("pagina_impressa"), "pagina_impressa_fim": p.get("pagina_impressa_fim"),
    }


# ---------- API ----------

def listar_publicacoes() -> list[dict]:
    """Fontes do acervo (versão vigente) com a contagem de páginas pesquisáveis."""
    with pool.connection() as conn:
        linhas = conn.execute(
            """SELECT pub.id_publicacao, pub.titulo, pub.tipo,
                      (SELECT count(*) FROM pagina p WHERE p.id_versao = v.id_versao),
                      (SELECT min(c.nome_categoria) FROM publicacao_categoria pc
                         JOIN categoria_fonte c USING (id_categoria)
                        WHERE pc.id_publicacao = pub.id_publicacao),
                      ARRAY(SELECT e.nome_eixo FROM publicacao_eixo pe
                              JOIN eixo_tematico e USING (id_eixo)
                             WHERE pe.id_publicacao = pub.id_publicacao ORDER BY e.nome_eixo)
               FROM publicacao pub
               JOIN versao_arquivo v ON v.id_publicacao = pub.id_publicacao AND v.situacao_vigencia
               ORDER BY pub.titulo"""
        ).fetchall()
    return [{"id_publicacao": r[0], "titulo": r[1], "tipo": r[2], "paginas": r[3],
             "categoria": r[4], "eixos": list(r[5]), "referencia": referencias.de(r[1]),
             # leis e normas do CFP: o nome vem do catálogo (a tela não deduz do arquivo)
             "nome_curto": mapa.nome_curto(r[1]) if mapa.EXTRAS.match(r[1]) else None}
            for r in linhas]


def pagina_impressa(id_publicacao: int, numero_pdf: int) -> dict | None:
    """Página do LIVRO para uma página qualquer do PDF (versão vigente), para citar um
    trecho que a pessoa selecionou no leitor. None se a página não existe."""
    with pool.connection() as conn:
        linha = conn.execute(
            f"""SELECT {IMPRESSA_SQL}
                FROM pagina p JOIN versao_arquivo va USING (id_versao)
                WHERE va.id_publicacao = %s AND va.situacao_vigencia AND p.numero_pagina_pdf = %s
                LIMIT 1""",
            (id_publicacao, numero_pdf),
        ).fetchone()
    if not linha:
        return None
    return {"pagina": numero_pdf, "pagina_impressa": linha[0], "pagina_impressa_fim": linha[1]}


def caminho_pdf(id_publicacao: int) -> str | None:
    """Caminho do PDF da versão vigente da publicação (None se não existir)."""
    with pool.connection() as conn:
        linha = conn.execute(
            """SELECT caminho_pdf FROM versao_arquivo
               WHERE id_publicacao = %s AND situacao_vigencia
               ORDER BY numero_versao DESC LIMIT 1""",
            (id_publicacao,),
        ).fetchone()
    return linha[0] if linha else None


def buscar(termo: str, k: int | None, ids_publicacao: list[int] | None, id_usuario: int | None) -> dict:
    """Modo RÁPIDO: só a busca híbrida, sem gerar texto. Devolve os trechos grifados."""
    k = k or 10
    with pool.connection() as conn:
        paginas, exp = _buscar_paginas(conn, termo, k, ids_publicacao)
        _registrar(conn, id_usuario, "buscar", termo, None, paginas)
    return {
        "termo": termo,
        "equivalencias": exp["equivalencias"],
        "resultados": [{**_publico(p), "trecho": _trecho(p)} for p in paginas],
    }


def recuperar(pergunta: str, k: int | None, ids_publicacao: list[int] | None) -> tuple[list[dict], dict]:
    k = k or (config.longo_k if eh_pedido_longo(pergunta) else config.top_k)
    with pool.connection() as conn:
        return _buscar_paginas(conn, pergunta, k, ids_publicacao)


def carregar_paginas(ids_pagina: list[int], termo_busca: str | None) -> tuple[list[dict], dict]:
    """As páginas que a pessoa escolheu na busca, NA MESMA ORDEM, com os grifos do termo
    da busca original. Sempre o mesmo texto para o mesmo conjunto: assim o contexto da IA
    fica idêntico entre perguntas seguidas e o Ollama reaproveita a leitura já feita."""
    with pool.connection() as conn:
        exp = expandir(conn, termo_busca) if termo_busca else VAZIO
        linhas = conn.execute(
            f"""SELECT p.id_pagina, p.numero_pagina_pdf, p.conteudo_texto, pub.titulo, pub.id_publicacao,
                       CASE WHEN %(ou)s::text IS NULL THEN NULL ELSE
                         ts_headline('pt_sem_acento', {SEM_HIFEN}, %(ou)s::tsquery,
                           'StartSel={MARCA_INI}, StopSel={MARCA_FIM}, HighlightAll=true') END,
                       {IMPRESSA_SQL}
                FROM unnest(%(ids)s::int[]) WITH ORDINALITY AS escolha(id_pagina, ordem)
                JOIN pagina p USING (id_pagina)
                JOIN versao_arquivo va USING (id_versao)
                JOIN publicacao pub USING (id_publicacao)
                WHERE va.situacao_vigencia
                ORDER BY escolha.ordem""",
            {"ids": ids_pagina, "ou": exp["tsquery_ou"]},
        ).fetchall()
        paginas = [{
            "id_pagina": r[0], "pagina": r[1], "texto": r[2], "titulo": r[3], "id_publicacao": r[4],
            "similaridade": 1.0, "por_palavra": True, "por_sentido": False, "escolhida": True,
            "trecho_marcado": None, "pagina_grifada": r[5],
            "pagina_impressa": r[6], "pagina_impressa_fim": r[7],
        } for r in linhas]
        _processar_grifos(conn, paginas, exp)
        _anexar_leis(conn, paginas)
    return paginas, exp


def preparar(paginas: list[dict]) -> None:
    """Faz a IA ler as páginas antes de a pergunta chegar (enquanto a pessoa digita).
    Gera 1 token só; o que importa é a leitura ficar guardada no cache do Ollama."""
    if paginas:
        prefixo = montar_prompt("", paginas).rsplit("\nPERGUNTA:", 1)[0] + "\nPERGUNTA:"  # sem o pedido
        ollama_client.ler_antes(prefixo)


def _janela(p: dict, tamanho: int) -> str:
    """O pedaço da página que interessa: começa um pouco antes da 1ª palavra achada.

    A IA roda em CPU e o tempo de "ler" cresce com o tamanho do contexto; mandar a
    janela certa (e não o começo cego da página) deixa a resposta mais rápida e melhor.
    """
    limpo = re.sub(r"(\w)-\s+(\w)", r"\1\2", " ".join(p["texto"].split()))
    if len(limpo) <= tamanho:
        return limpo
    baixo = limpo.lower()
    pos = [baixo.find(d["texto"].lower()) for d in p.get("destaques", [])]
    pos = [x for x in pos if x >= 0]
    ini = max(0, min(pos) - tamanho // 4) if pos else 0
    ini = min(ini, len(limpo) - tamanho)
    if ini:
        ini = limpo.find(" ", ini) + 1
    return ("…" if ini else "") + limpo[ini : ini + tamanho] + "…"


def _nome_fonte(titulo: str) -> str:
    """'2025 - RT - Mulheres em Violencia' -> 'Mulheres em Violencia'. Sem o ano no
    cabeçalho: senão o modelo pequeno cita '[p. 2025]' em vez da página. Leis e normas do
    CFP usam o nome do catálogo ('Lei Maria da Penha'), também sem número nem ano."""
    if mapa.EXTRAS.match(titulo):
        return mapa.nome_curto(titulo) or mapa.EXTRAS.sub("", titulo)
    return re.sub(r"^\d{4}\s*-\s*(RT|Seminario [IVXL]+|Mostra|Gestores)\s*-\s*", "", titulo)


# Páginas que a PESSOA escolheu ("Explicar", "Perguntar sobre estas páginas") são lidas
# quase inteiras: a pergunta seguinte pode ser sobre outro trecho da página (ex.: a
# notificação compulsória, no fim da p. 117). A leitura é feita enquanto ela digita
# (/preparar) e fica no cache, então o custo não aparece. Mediana de uma página: 1.900.
LEITURA_ESCOLHIDA_MAX = 3000    # caracteres por página
LEITURA_ESCOLHIDA_TOTAL = 6000  # somando todas (cabe no contexto de 4.096 tokens)


def _tamanho_janela(paginas: list[dict]) -> int:
    if paginas and all(p.get("escolhida") for p in paginas):
        return min(LEITURA_ESCOLHIDA_MAX, LEITURA_ESCOLHIDA_TOTAL // len(paginas))
    return config.contexto_chars


def montar_prompt(pergunta: str, paginas: list[dict]) -> str:
    # Cada trecho começa com a citação pronta ("[p. 45]"): o modelo só precisa copiá-la.
    tamanho = _tamanho_janela(paginas)
    # As leis citadas em cada página vêm da tabela pagina_lei: o modelo não precisa achar
    # o número da lei no meio do texto (e não inventa um).
    # Vai DEPOIS do texto: antes, o modelo achava que a lista era a resposta e parava nela.
    contexto = "\n\n".join(
        f"[p. {p['pagina']}] ({_nome_fonte(p['titulo'])})\n"
        + _janela(p, tamanho)
        + (f"\n(Leis citadas nesta página: {'; '.join(p['leis'][:4])}.)" if p.get("leis") else "")
        for p in paginas
    )
    pedido = PEDIDO_LONGO if eh_pedido_longo(pergunta) else ""
    return PROMPT_BASE.format(mapa=_mapa(), contexto=contexto, pergunta=pergunta, pedido=pedido)


def fontes_publicas(paginas: list[dict], exp: dict) -> dict:
    return {"fontes": [_publico(p) for p in paginas], "equivalencias": exp["equivalencias"]}


def _lista(itens: list[str]) -> str:
    itens = [f"“{i}”" for i in itens]
    return itens[0] if len(itens) == 1 else ", ".join(itens[:-1]) + " e " + itens[-1]


def pensamento(paginas: list[dict], exp: dict, escolhidas: bool) -> dict:
    """A "linha de pensamento" que a tela mostra enquanto a IA lê: os passos que de fato
    aconteceram (equivalências usadas, por que cada página foi escolhida) e o MESMO
    trecho de cada página que vai no prompt. Nada aqui é inventado pelo modelo."""
    passos = []
    for e in exp["equivalencias"]:
        if e["equivalentes"]:
            passos.append(f"Você escreveu {_lista(e['digitado'])}; também considerei "
                          f"{_lista(e['equivalentes'][:4])}, que no acervo querem dizer o mesmo.")
    n = len(paginas)
    if escolhidas:
        passos.append("Vou ler só a página que você escolheu." if n == 1
                      else "Vou ler só as páginas que você escolheu.")
    elif paginas:
        passos.append("Procurei de dois jeitos: pelo sentido da pergunta e pelas palavras. "
                      "Juntei as duas listas e fiquei com "
                      + ("a melhor página." if n == 1 else f"as {n} melhores páginas."))
    leituras = []
    for p in paginas:
        fonte = _nome_fonte(p["titulo"])
        if escolhidas:
            motivo = "escolhida por você"
        elif p["por_palavra"] and p["por_sentido"]:
            motivo = "tem as palavras da pergunta e trata do mesmo assunto"
        elif p["por_palavra"]:
            motivo = "tem as palavras da pergunta"
        else:
            motivo = "fala do mesmo assunto com outras palavras"
        achou = [d["texto"] for d in p.get("destaques", [])[:3]]
        passos.append(f"p. {p['pagina']} de “{fonte}”: {motivo}"
                      + (f" ({'aparece' if len(achou) == 1 else 'aparecem'} {_lista(achou)})."
                         if achou else ".")
                      + (f" Cita: {'; '.join(p['leis'][:3])}." if p.get("leis") else ""))
        leituras.append({"pagina": p["pagina"], "fonte": fonte,
                         "texto": _janela(p, _tamanho_janela(paginas)),
                         "destaques": p.get("destaques", [])})
    return {"passos": passos, "leituras": leituras}


# "Não encontrei isso nas páginas consultadas." + a sugestão que costuma vir depois.
_NAO_ACHEI = re.compile(
    r"\s*N[ãa]o encontrei isso nas p[áa]ginas consultadas\.?"
    r"(?:\s*(?:Tente|Para|Sugiro|Caso|Se precisar|Recomendo)[^.\n]*\.)?(?:\s*\[p\.[^\]]*\])?",
    re.I,
)


_CITACAO = re.compile(r"\[p\.\s*([\d\s,e\-–]+)\]")
_FRASE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ\[•*-])")


def tirar_paginas_inventadas(texto: str, lidas: set[int]) -> str:
    """Apaga a frase cuja citação aponta só para páginas que a IA NÃO leu. Pega número de
    página inventado e cópia dos exemplos do Modelfile (que usam as páginas 997-999)."""
    def citadas(frase: str) -> set[int]:
        return {int(n) for m in _CITACAO.finditer(frase) for n in re.findall(r"\d+", m.group(1))}
    paragrafos = []
    for par in texto.split("\n"):
        frases = [f for f in _FRASE.split(par) if not (citadas(f) and not citadas(f) & lidas)]
        if frases or not par.strip():  # linha que ficou vazia (tópico apagado) some
            paragrafos.append(" ".join(frases))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(paragrafos)).strip()


# Apresentação que o modelo cola no começo ("Olá! Eu sou a Susmi e estou aqui para
# ajudar…"): visto em 03/11/2026 com o Gemma 4, em quase toda resposta.
_SAUDACAO = re.compile(
    r"^\s*(?:Olá[!.,]?\s*)?(?:(?:Eu sou a Susmi|A Susmi é|Sou a Susmi|Como a Susmi|Aqui é a Susmi)"
    r"[^.!?\n]*[.!?]\s*|(?:Estou aqui para|Posso te ajudar|Farei o meu melhor)[^.!?\n]*[.!?]\s*)+"
    r"|^\s*Olá[!.,]\s*",
    re.I,
)
RECUSA = ("Não encontrei isso nas páginas consultadas. Tente buscar com outras palavras "
          "ligadas à atuação da Psicologia.")


def tirar_saudacao(texto: str) -> str:
    return _SAUDACAO.sub("", texto, count=1).lstrip()


def limpar_resposta(texto: str) -> str:
    """O modelo pequeno às vezes cola "Não encontrei isso nas páginas consultadas" numa
    resposta que TEM informação (no começo ou no fim). Se, sem a frase, sobra conteúdo de
    verdade, ela sai; numa recusa legítima ("Quem ganhou a Copa?"), fica como está.
    Também tira a saudação do começo; se sem ela não sobra nada (o modelo só se
    apresentou, sem citar nada), a resposta vira a recusa padrão."""
    texto = tirar_saudacao(texto)
    if len(re.sub(r"\s+", " ", texto).strip()) < 40 and not _CITACAO.search(texto):
        return RECUSA
    limpo = _NAO_ACHEI.sub(" ", texto).strip()
    conteudo = re.sub(r"\[p\.[^\]]*\]", "", limpo).strip()
    final = limpo if len(conteudo) >= 80 else texto
    # "O acervo consultado não traz." sozinha, sem dizer O QUE não traz: não informa nada.
    return re.sub(r"\s*O acervo consultado não traz\s*[.:]?\s*$", "", final).strip() or final


def _gravar_metrica(conn, id_consulta: int, guardada: bool, t0: float | None, espera_ms: int | None,
                    primeira: float | None, m: dict | None) -> None:
    """Tempo e velocidade de cada resposta da IA (tabela metrica_resposta), para o painel
    do administrador saber se a Susmi está rápida. Não guarda texto nem quem perguntou."""
    agora = time.monotonic()
    ms = lambda t: int((t - t0) * 1000) if (t is not None and t0 is not None) else None  # noqa: E731
    m = m or {}
    try:
        with conn.transaction():  # savepoint: se falhar, a resposta e o histórico ficam
            conn.execute(
                """INSERT INTO metrica_resposta (id_consulta, modelo, guardada, espera_ms, primeira_ms,
                                                 total_ms, tokens_lidos, leitura_ms, tokens, tokens_por_segundo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING""",
                (id_consulta, config.chat_model, guardada, espera_ms, ms(primeira), ms(agora),
                 m.get("tokens_lidos"),
                 int(m["leitura_s"] * 1000) if m.get("leitura_s") is not None else None,
                 m.get("tokens"), m.get("tokens_por_segundo")),
            )
    except Exception:  # noqa: BLE001 — métrica nunca derruba a resposta
        import traceback
        traceback.print_exc()


def responder_stream(pergunta: str, paginas: list[dict], id_usuario: int | None,
                     t0: float | None = None, espera_ms: int | None = None):
    """Modo IA em streaming: devolve o texto aos pedaços, conforme a IA escreve.

    Eventos: {'tipo': 'texto', 'delta': '...'} … e no fim {'tipo': 'fim', ...}.
    Só grava no histórico se a resposta terminar. t0 (time.monotonic do pedido) e
    espera_ms (tempo na fila) entram na métrica de tempo.
    """
    if not paginas:
        yield {"tipo": "fim", "resposta": "Não encontrei páginas sobre isso nas fontes marcadas.",
               "metricas": None}
        return
    prompt = montar_prompt(pergunta, paginas)
    chave = _chave_resposta(prompt)
    guardada = _resposta_guardada(chave)
    if guardada:  # mesma pergunta, mesmas páginas, mesmo modelo: sai na hora
        yield {"tipo": "texto", "delta": guardada}
        with pool.connection() as conn:
            id_consulta = _registrar(conn, id_usuario, "perguntar", pergunta, guardada, paginas)
            _gravar_metrica(conn, id_consulta, True, t0, espera_ms, time.monotonic(), None)
        yield {"tipo": "fim", "id_consulta": id_consulta, "resposta": guardada,
               "metricas": {"guardada": True, "modelo": config.chat_model}}
        return
    partes, metricas, primeira = [], None, None
    for ev in ollama_client.gerar_stream(prompt, max_tokens=tokens_resposta(pergunta)):
        if "delta" in ev:
            if primeira is None:
                primeira = time.monotonic()
            partes.append(ev["delta"])
            yield {"tipo": "texto", "delta": ev["delta"]}
        else:
            metricas = ev["metricas"]
    # A tela troca o texto pelo final, já limpo.
    lidas = {p["pagina"] for p in paginas}
    texto = limpar_resposta(tirar_paginas_inventadas("".join(partes), lidas))
    with pool.connection() as conn:
        id_consulta = _registrar(conn, id_usuario, "perguntar", pergunta, texto, paginas)
        _gravar_metrica(conn, id_consulta, False, t0, espera_ms, primeira, metricas)
        if texto.strip():
            conn.execute("INSERT INTO resposta_guardada (chave, resposta) VALUES (%s, %s) "
                         "ON CONFLICT DO NOTHING", (chave, texto))
    yield {"tipo": "fim", "id_consulta": id_consulta, "resposta": texto, "metricas": metricas}


# ---------- Respostas guardadas ----------
# As instruções da Susmi entram na chave: mudou o Modelfile, nenhuma resposta antiga vale.
_MODELFILE = Path(__file__).parent / "ia" / "Modelfile"
_INSTRUCOES = hashlib.sha256(
    _MODELFILE.read_bytes().replace(b"\r", b"") if _MODELFILE.is_file() else b""
).hexdigest()
GUARDA_DIAS = 30


def _chave_resposta(prompt: str) -> str:
    return hashlib.sha256(f"{config.chat_model}\n{_INSTRUCOES}\n{prompt}".encode()).hexdigest()


def _resposta_guardada(chave: str) -> str | None:
    with pool.connection() as conn:
        linha = conn.execute(
            "SELECT resposta FROM resposta_guardada WHERE chave = %s AND criado_em > now() - %s * interval '1 day'",
            (chave, GUARDA_DIAS),
        ).fetchone()
    return linha[0] if linha else None


def tem_resposta_guardada(pergunta: str, paginas: list[dict]) -> bool:
    """Para o main.py não pôr na fila da IA uma pergunta que já tem resposta pronta."""
    return bool(paginas) and _resposta_guardada(_chave_resposta(montar_prompt(pergunta, paginas))) is not None
