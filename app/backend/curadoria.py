"""Fase 2 do modelo: categoria, eixo temático e leis citadas. Roda dentro do migrar.py.

Idempotente. A classificação feita aqui entra com origem_classificacao = 'IA': é uma
proposta para a curadoria (as colegas da Psicologia) revisar. Uma classificação que já
foi trocada para 'Curador' no banco nunca é sobrescrita.
"""
import re
from collections import Counter

import paginacao

# ---------- Categoria: o tipo de documento, tirado do título ----------
CATEGORIAS = [
    (r"^\d{4} - RT - |^Referencias Tecnicas", "Referência Técnica"),
    (r" - Seminario ", "Seminário"),
    (r" - Mostra - ", "Mostra de Práticas"),
    (r" - Gestores - ", "Guia para Gestores"),
    (r"^\d{4} - Lei - ", "Lei"),
    (r"^\d{4} - CFP - ", "Norma do CFP"),
    (r"^\d{4} - Gov - ", "Manual do governo"),
]

# ---------- Eixo temático: o campo de atuação (N:N — uma obra pode estar em dois) ----------
# Pedaço do título -> eixos. Proposta da IA para a curadoria revisar.
EIXOS = {
    "Saúde e saúde mental": ["Alcool e Drogas", "Atencao Basica", "CAPS", "Hospitais SUS",
                             "IST HIV Aids", "Praticas na RAPS", "Gestores - SUS",
                             "Saude do Trabalhador", "Gov - Prevencao do Suicidio"],
    "Assistência social (SUAS)": ["Gestores - SUAS", "CRAS SUAS", "CREAS", "Populacao de Rua",
                                  "Gov - PNAS", "Gov - Tipificacao", "Gov - Orientacoes Tecnicas PAIF"],
    "Justiça e segurança": ["Medidas Socioeducativas", "Seguranca Publica", "Sistema Prisional",
                            "Varas de Familia"],
    "Violências": ["Mulher em Violencia", "Mulheres em Violencia",
                   "Violencia Sexual Infantojuvenil", "CREAS",
                   "Gov - Linha de Cuidado Criancas e Adolescentes em Violencias",
                   "Gov - Instrutivo de Notificacao de Violencia"],
    "Diversidade e direitos": ["Relacoes Raciais", "LGBTQIA+", "Direitos Sexuais e Reprodutivos",
                               "Pessoas Idosas", "Migracao e Refugio"],
    "Povos e territórios": ["Povos Indigenas", "Povos Tradicionais", "Questoes da Terra",
                            "Quilombolas"],
    "Educação": ["Educacao Basica"],
    "Trabalho, esporte e trânsito": ["Saude do Trabalhador", "Esporte", "Mobilidade e Transito"],
    "Emergências e desastres": ["Emergencias e Desastres"],
    "Seminários regionais": ["Seminario IX"],
    # Acrescentados em 10/11/2026: texto integral das leis e as normas da profissão.
    "Ética e normas do CFP": [" - CFP - "],
    "Leis (texto integral)": [" - Lei - "],
}

# ---------- Leis mais citadas: número, ano, nome popular, ementa resumida ----------
# "apelidos" acham a lei quando o texto cita só o nome ("Lei Maria da Penha", "ECA").
LEIS = [
    ("11.340", 2006, "Lei Maria da Penha",
     "Cria mecanismos para coibir a violência doméstica e familiar contra a mulher.",
     [r"Lei Maria da Penha"]),
    ("8.069", 1990, "Estatuto da Criança e do Adolescente (ECA)",
     "Dispõe sobre a proteção integral à criança e ao adolescente.",
     [r"Estatuto da Criança e do Adolescente", r"\bECA\b"]),
    ("8.742", 1993, "Lei Orgânica da Assistência Social (LOAS)",
     "Dispõe sobre a organização da Assistência Social.",
     [r"Lei Orgânica da Assistência Social", r"\bLOAS\b"]),
    ("8.080", 1990, "Lei Orgânica da Saúde",
     "Dispõe sobre a promoção, proteção e recuperação da saúde e o funcionamento do SUS.",
     [r"Lei Orgânica da Saúde"]),
    ("10.216", 2001, "Lei da Reforma Psiquiátrica (Lei Paulo Delgado)",
     "Dispõe sobre os direitos das pessoas com transtornos mentais e redireciona o modelo "
     "assistencial em saúde mental.",
     [r"Lei Paulo Delgado", r"Lei da Reforma Psiquiátrica"]),
    ("10.741", 2003, "Estatuto da Pessoa Idosa",
     "Dispõe sobre os direitos da pessoa idosa.",
     [r"Estatuto do Idoso", r"Estatuto da Pessoa Idosa"]),
    ("2.848", 1940, "Código Penal", "Decreto-Lei que institui o Código Penal.",
     [r"Código Penal\b(?! Militar)"]),
    ("6.001", 1973, "Estatuto do Índio", "Dispõe sobre o Estatuto do Índio.",
     [r"Estatuto do Índio"]),
    ("12.435", 2011, "Lei do SUAS",
     "Altera a LOAS e organiza o Sistema Único de Assistência Social.", []),
    ("11.343", 2006, "Lei de Drogas",
     "Institui o Sistema Nacional de Políticas Públicas sobre Drogas (Sisnad).",
     [r"Lei de Drogas"]),
    ("5.766", 1971, "Lei dos Conselhos de Psicologia",
     "Cria o Conselho Federal e os Conselhos Regionais de Psicologia.", []),
    ("13.431", 2017, "Lei da Escuta Protegida",
     "Sistema de garantia de direitos da criança e do adolescente vítima ou testemunha de "
     "violência (escuta especializada e depoimento especial).", []),
    ("9.836", 1999, "Lei Arouca",
     "Institui o Subsistema de Atenção à Saúde Indígena no SUS.", [r"Lei Arouca"]),
    ("9.394", 1996, "Lei de Diretrizes e Bases da Educação (LDB)",
     "Estabelece as diretrizes e bases da educação nacional.",
     [r"Lei de Diretrizes e Bases", r"\bLDB\b"]),
    ("4.119", 1962, "Lei da profissão de psicólogo",
     "Dispõe sobre os cursos de formação em Psicologia e regulamenta a profissão.", []),
    ("9.503", 1997, "Código de Trânsito Brasileiro",
     "Institui o Código de Trânsito Brasileiro.", [r"Código de Trânsito Brasileiro"]),
    ("10.639", 2003, "Lei da história e cultura afro-brasileira",
     "Inclui no currículo oficial a temática História e Cultura Afro-Brasileira.", []),
    ("11.645", 2008, "Lei da história e cultura afro-brasileira e indígena",
     "Inclui no currículo a temática História e Cultura Afro-Brasileira e Indígena.", []),
    ("7.210", 1984, "Lei de Execução Penal", "Institui a Lei de Execução Penal.",
     [r"Lei de Execução Penal"]),
    ("7.716", 1989, "Lei do crime racial (Lei Caó)",
     "Define os crimes resultantes de preconceito de raça ou de cor.", [r"Lei Caó"]),
    ("8.072", 1990, "Lei dos Crimes Hediondos", "Dispõe sobre os crimes hediondos.",
     [r"Lei dos Crimes Hediondos"]),
    ("10.257", 2001, "Estatuto da Cidade", "Regulamenta a política urbana.",
     [r"Estatuto da Cidade"]),
    ("10.778", 2003, "Lei da notificação compulsória da violência contra a mulher",
     "Estabelece a notificação compulsória do caso de violência contra a mulher atendida "
     "em serviços de saúde.", []),
    ("12.594", 2012, "Lei do SINASE",
     "Institui o Sistema Nacional de Atendimento Socioeducativo.", []),
    ("13.257", 2016, "Marco Legal da Primeira Infância",
     "Dispõe sobre as políticas públicas para a primeira infância.",
     [r"Marco Legal da Primeira Infância"]),
    ("13.146", 2015, "Lei Brasileira de Inclusão (Estatuto da Pessoa com Deficiência)",
     "Institui a Lei Brasileira de Inclusão da Pessoa com Deficiência.",
     [r"Lei Brasileira de Inclusão", r"Estatuto da Pessoa com Deficiência"]),
    ("12.288", 2010, "Estatuto da Igualdade Racial", "Institui o Estatuto da Igualdade Racial.",
     [r"Estatuto da Igualdade Racial"]),
    ("13.104", 2015, "Lei do Feminicídio",
     "Prevê o feminicídio como circunstância qualificadora do homicídio.",
     [r"Lei do Feminicídio"]),
    ("12.845", 2013, "Lei do Minuto Seguinte",
     "Atendimento obrigatório e integral de pessoas em situação de violência sexual.",
     [r"Lei do Minuto Seguinte"]),
    ("12.711", 2012, "Lei de Cotas", "Ingresso nas universidades e institutos federais.",
     [r"Lei de Cotas"]),
    ("13.819", 2019, "Política Nacional de Prevenção da Automutilação e do Suicídio",
     "Institui a Política Nacional de Prevenção da Automutilação e do Suicídio.", []),
    ("12.764", 2012, "Lei Berenice Piana (autismo)",
     "Institui a Política Nacional de Proteção dos Direitos da Pessoa com Transtorno do Espectro Autista.",
     [r"Lei Berenice Piana"]),
    ("13.935", 2019, "Lei da Psicologia e do Serviço Social nas escolas",
     "Dispõe sobre a prestação de serviços de psicologia e de serviço social nas redes públicas de "
     "educação básica.", []),
]

# "Lei nº 11.340/2006", "Lei 8080/90", "Lei n.º 10.216, de 6 de abril de 2001",
# "Decreto-Lei nº 2.848". O número precisa vir com ano (/2006 ou "de ... de 2006"), ou ser
# uma lei do catálogo: "Lei 1234" solta no texto costuma ser outra coisa.
_LEI = re.compile(
    r"\bLei\s+(?:Federal\s+|Complementar\s+|Estadual\s+|Municipal\s+)?(?:n\s*[º°o.]*\s*)?"
    r"(\d{1,2}\.?\d{3})(?:\s*/\s*(\d{4}|\d{2})\b|,?\s*de\s+\d{1,2}\s*(?:º|°|o)?\s+de\s+[a-zç]+\s+de\s+(\d{4}))?",
    re.I,
)
_LOCAL = re.compile(r"\b(Estadual|Municipal)\b", re.I)


def _numero(bruto: str) -> str:
    n = bruto.replace(".", "")
    return f"{int(n[:-3])}.{n[-3:]}"


def _ano(curto: str | None, longo: str | None) -> int | None:
    a = longo or curto
    if not a:
        return None
    a = int(a)
    return a if a > 999 else (1900 + a if a >= 30 else 2000 + a)


def leis_no_texto(texto: str, catalogo: set[str], apelidos: list[tuple[str, re.Pattern]]) -> dict[str, int | None]:
    """{número: ano} das leis federais citadas no texto (por número ou por nome)."""
    achadas: dict[str, int | None] = {}
    for m in _LEI.finditer(texto):
        if _LOCAL.search(m.group(0)):
            continue  # lei estadual/municipal: outro número, outro ente
        num, ano = _numero(m.group(1)), _ano(m.group(2), m.group(3))
        if ano or num in catalogo:
            achadas.setdefault(num, ano)
    for num, padrao in apelidos:
        if padrao.search(texto):
            achadas.setdefault(num, None)
    return achadas


def paginas_impressas(conn) -> None:
    """Preenche pagina.numero_pagina_impressa (a página do livro, para citar em ABNT).
    Recalcula tudo a cada migração: depende só do texto das páginas (paginacao.py)."""
    versoes = conn.execute("SELECT DISTINCT id_versao FROM pagina").fetchall()
    total = achadas = 0
    with conn.cursor() as cur:
        for (id_versao,) in versoes:
            linhas = conn.execute(
                "SELECT id_pagina, numero_pagina_pdf, conteudo_texto FROM pagina WHERE id_versao = %s",
                (id_versao,)).fetchall()
            mapa, _ = paginacao.paginas_impressas([(pdf, t) for _, pdf, t in linhas])
            # Só grava o que mudou: regravar a linha recalcula a busca_texto da página.
            cur.executemany(
                """UPDATE pagina SET numero_pagina_impressa = %s
                   WHERE id_pagina = %s AND numero_pagina_impressa IS DISTINCT FROM %s""",
                [(mapa.get(pdf), id_p, mapa.get(pdf)) for id_p, pdf, _ in linhas])
            total += len(linhas)
            achadas += sum(1 for v in mapa.values() if v)
    print(f"páginas impressas: {achadas} de {total} páginas com o número do livro")


def aplicar(conn) -> None:
    pubs = conn.execute("SELECT id_publicacao, titulo FROM publicacao").fetchall()

    # Categorias
    for _, nome in CATEGORIAS:
        conn.execute("INSERT INTO categoria_fonte (nome_categoria) VALUES (%s) ON CONFLICT DO NOTHING", (nome,))
    cat_id = dict(conn.execute("SELECT nome_categoria, id_categoria FROM categoria_fonte").fetchall())
    for id_pub, titulo in pubs:
        for padrao, nome in CATEGORIAS:
            if re.search(padrao, titulo):
                conn.execute("INSERT INTO publicacao_categoria VALUES (%s, %s) ON CONFLICT DO NOTHING",
                             (id_pub, cat_id[nome]))
                break

    # Eixos (só acrescenta; o que a curadoria marcou fica)
    for nome in EIXOS:
        conn.execute("INSERT INTO eixo_tematico (nome_eixo) VALUES (%s) ON CONFLICT DO NOTHING", (nome,))
    eixo_id = dict(conn.execute("SELECT nome_eixo, id_eixo FROM eixo_tematico").fetchall())
    sem_eixo = []
    for id_pub, titulo in pubs:
        achou = False
        for nome, pedacos in EIXOS.items():
            if any(p in titulo for p in pedacos):
                achou = True
                conn.execute(
                    """INSERT INTO publicacao_eixo (id_publicacao, id_eixo, origem_classificacao)
                       VALUES (%s, %s, 'IA') ON CONFLICT DO NOTHING""",
                    (id_pub, eixo_id[nome]))
        if not achou:
            sem_eixo.append(titulo)

    # Leis: catálogo (atualiza nome/ementa) + as que aparecem por número nas páginas
    for num, ano, nome, ementa, _ in LEIS:
        conn.execute(
            """INSERT INTO lei (numero_lei, ano, nome_popular, ementa) VALUES (%s, %s, %s, %s)
               ON CONFLICT (numero_lei) DO UPDATE
               SET ano = EXCLUDED.ano, nome_popular = EXCLUDED.nome_popular, ementa = EXCLUDED.ementa""",
            (num, ano, nome, ementa))
    catalogo = {num for num, *_ in LEIS}
    apelidos = [(num, re.compile(p)) for num, _, _, _, ps in LEIS for p in ps]
    paginas = conn.execute(
        r"SELECT id_pagina, regexp_replace(conteudo_texto, '(\w)-\s*\n\s*(\w)', '\1\2', 'g') FROM pagina"
    ).fetchall()
    citacoes, anos = [], {}
    for id_pagina, texto in paginas:
        for num, ano in leis_no_texto(texto, catalogo, apelidos).items():
            citacoes.append((id_pagina, num))
            if ano:
                anos.setdefault(num, Counter())[ano] += 1
    for num in {n for _, n in citacoes} - catalogo:
        ano = anos[num].most_common(1)[0][0] if num in anos else None
        conn.execute("INSERT INTO lei (numero_lei, ano) VALUES (%s, %s) ON CONFLICT DO NOTHING", (num, ano))
    lei_id = dict(conn.execute("SELECT numero_lei, id_lei FROM lei").fetchall())
    conn.execute("DELETE FROM pagina_lei")  # recalculada inteira a cada migração
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO pagina_lei VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        [(p, lei_id[n]) for p, n in citacoes])

    paginas_impressas(conn)

    n_cat = conn.execute("SELECT count(*) FROM publicacao_categoria").fetchone()[0]
    n_eixo = conn.execute("SELECT count(*) FROM publicacao_eixo").fetchone()[0]
    n_lei, n_pl = conn.execute("SELECT (SELECT count(*) FROM lei), (SELECT count(*) FROM pagina_lei)").fetchone()
    print(f"curadoria ok: {n_cat} publicações com categoria, {n_eixo} vínculos publicação–eixo, "
          f"{n_lei} leis, {n_pl} citações de lei em páginas")
    if sem_eixo:
        print("  sem eixo (classificar à mão):", "; ".join(sem_eixo))
