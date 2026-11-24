"""Mapa do acervo: o que cada obra trata e em que obras aparecem os temas mais procurados.

Vai no começo de TODO prompt da Susmi. Como é sempre o mesmo texto, a IA lê uma vez (no
aquecimento) e o Ollama guarda essa leitura no cache: nas perguntas seguintes, o mapa não
custa tempo. Serve para a Susmi saber o que existe no acervo inteiro ("o tema aparece mais
em tal obra") sem precisar ler as 5.551 páginas, o que não caberia na memória nem no tempo.

Parte 1 (OBRAS) foi escrita à mão a partir do sumário de cada PDF (03/11/2026).
Parte 2 (TEMAS) é calculada pelo banco quando o app sobe: para cada tema, as obras com mais
páginas que falam dele. Obra nova entra sozinha na parte 2; na parte 1, acrescentar aqui.
O mapa NÃO é fonte de resposta: a Susmi só cita as páginas que leu.
"""
import re

import referencias
from db import pool

# titulo do arquivo -> (nome curto, do que trata)
OBRAS: dict[str, tuple[str, str]] = {
    "Referencias Tecnicas para atuacao de psicologas(os) nos CAPS":
        ("CAPS (ed. rev.)", "saúde mental no CAPS: cidadania, desinstitucionalização, RAPS, clínica ampliada, atuação da(o) psicóloga(o) e gestão"),
    "2022 - RT - CAPS":
        ("CAPS (1ª ed.)", "saúde mental no CAPS: reforma psiquiátrica, teorias em Psicologia, prática no CAPS"),
    "2022 - Gestores - SUAS":
        ("Guia SUAS para gestores (2011)", "por que contratar psicólogas(os) na Assistência Social: campos de atuação, contratação, concurso"),
    "2022 - Gestores - SUS":
        ("Guia SUS para gestores", "contribuição da Psicologia ao SUS: campos de atuação, contratação, concurso"),
    "2022 - RT - Alcool e Drogas":
        ("Álcool e outras drogas", "uso de drogas, redução de danos, rede psicossocial, política de drogas centrada no usuário"),
    "2022 - RT - Atencao Basica":
        ("Atenção Básica", "Psicologia na UBS/ESF/NASF, apoio matricial, gestão do trabalho no SUS"),
    "2022 - RT - CRAS SUAS":
        ("CRAS/SUAS", "proteção social básica, trabalho com famílias (PAIF), território, vínculos, gestão do SUAS"),
    "2022 - RT - CREAS":
        ("CREAS", "proteção social especial, famílias e pessoas com direitos violados, violências"),
    "2022 - RT - Educacao Basica":
        ("Educação Básica", "Psicologia na escola: comunidade escolar, queixa escolar, medicalização, desafios"),
    "2022 - RT - Emergencias e Desastres":
        ("Emergências e desastres", "gestão de riscos, emergências e desastres, cuidado com afetados"),
    "2022 - RT - Esporte":
        ("Esporte", "Psicologia social do esporte, políticas públicas de esporte e lazer"),
    "2022 - RT - Hospitais SUS":
        ("Hospitais do SUS", "Psicologia hospitalar: atuação nos hospitais, equipe, gestão"),
    "2022 - RT - IST HIV Aids":
        ("IST/HIV/aids", "prevenção, pessoas que vivem com HIV, sigilo, integralidade, controle social"),
    "2022 - RT - Medidas Socioeducativas":
        ("Medidas socioeducativas", "adolescentes em conflito com a lei, socioeducação, SINASE"),
    "2022 - RT - Mobilidade e Transito":
        ("Mobilidade humana e trânsito", "avaliação psicológica de condutores, educação para o trânsito"),
    "2022 - RT - Mulher em Violencia":
        ("Mulher em violência (2012)", "gênero, consequências da violência, rede de atenção, atendimento e grupos de mulheres"),
    "2022 - RT - Povos Indigenas":
        ("Povos indígenas (2022)", "movimento indígena, cuidado e saúde indígena, educação indígena, matriciamento"),
    "2022 - RT - Povos Tradicionais":
        ("Povos e comunidades tradicionais", "reconhecimento, direitos e atuação junto a comunidades tradicionais"),
    "2022 - RT - Questoes da Terra":
        ("Questões da terra", "conflitos agrários, movimentos do campo, atuação emancipadora"),
    "2022 - RT - Relacoes Raciais":
        ("Relações raciais", "racismo institucional, interpessoal e internalizado, movimento negro, promoção da igualdade"),
    "2022 - RT - Saude do Trabalhador":
        ("Saúde do trabalhador", "adoecimento no trabalho, nexo causal, notificação de agravos, vigilância, álcool no trabalho"),
    "2022 - RT - Seguranca Publica":
        ("Segurança pública", "Psicologia na segurança pública, saúde dos profissionais de segurança, direitos humanos"),
    "2022 - RT - Sistema Prisional":
        ("Sistema prisional", "prisões, exames criminológicos, saúde das pessoas privadas de liberdade"),
    "2022 - RT - Varas de Familia":
        ("Varas de família", "Psicologia jurídica: guarda, separação, perícia e ações de família"),
    "2022 - RT - Violencia Sexual Infantojuvenil":
        ("Violência sexual infantojuvenil", "rede de proteção a crianças e adolescentes, escuta, atuação nos serviços"),
    "2022 - Seminario IX - Centro-Oeste":
        ("IX Seminário – Centro-Oeste", "povos indígenas e quilombolas, enfrentamento ao racismo"),
    "2022 - Seminario IX - Geral":
        ("IX Seminário – Nacional", "Psicologia na defesa das políticas públicas"),
    "2022 - Seminario IX - Nordeste":
        ("IX Seminário – Nordeste", "seguridade social, desmonte das políticas e subjetividade"),
    "2022 - Seminario IX - Norte":
        ("IX Seminário – Norte", "atuação na Amazônia, impactos ambientais, formação"),
    "2022 - Seminario IX - Sudeste":
        ("IX Seminário – Sudeste", "direitos humanos, subjetividades violadas, protagonismo de usuárias(os)"),
    "2022 - Seminario IX - Sul":
        ("IX Seminário – Sul", "educação, gênero, laicidade, medicalização na escola"),
    "2023 - RT - LGBTQIA+":
        ("LGBTQIA+", "diversidade sexual e de gênero, intersexualidade, despatologização, resoluções do CFP"),
    "2023 - Seminario XII - Migracao e Refugio":
        ("XII Seminário – Migração e refúgio", "migrantes, refugiados, apatridia, acolhimento, interseccionalidade"),
    "2024 - RT - Povos Indigenas 2a ed":
        ("Povos indígenas (2ª ed., 2024)", "nota técnica sobre a atuação junto aos povos indígenas"),
    "2025 - Gestores - SUAS":
        ("Guia SUAS para gestores (2025)", "Psicologia no SUAS: proteção básica e especial, condições de trabalho, sistema de justiça"),
    "2025 - Mostra - Praticas na RAPS":
        ("Mostra de práticas na RAPS", "experiências premiadas de cuidado em liberdade nos CAPS e na RAPS"),
    "2025 - RT - Direitos Sexuais e Reprodutivos":
        ("Direitos sexuais e reprodutivos", "saúde da população negra, maternidade, aleitamento, gravidez na adolescência, aborto"),
    "2025 - RT - Mulheres em Violencia":
        ("Mulheres em violência (2024)", "atendimento às mulheres em situação de violência, rede, Lei Maria da Penha"),
    "2025 - RT - Pessoas Idosas":
        ("Pessoas idosas", "envelhecimento, ILPIs, Estatuto da Pessoa Idosa, violência contra a pessoa idosa"),
    "2025 - RT - Populacao de Rua":
        ("População em situação de rua", "acesso a direitos, SUS e SUAS, demandas específicas"),
    "2025 - RT - Quilombolas":
        ("Povos quilombolas", "território, ancestralidade, saúde da população negra, formação antirracista"),
    # ---- Normas do CFP e leis (10/11/2026). Nomes sem número nem ano: o modelo pequeno
    # confunde número no cabeçalho com página. No mapa, cada grupo vai numa linha só.
    "2005 - CFP - Codigo de Etica": ("Código de Ética Profissional do Psicólogo", ""),
    "2019 - CFP - Resolucao Documentos Psicologicos": ("Resolução do CFP sobre documentos psicológicos (comentada)", ""),
    "2018 - CFP - Resolucao Atendimento Online": ("Resolução do CFP sobre atendimento online (TICs)", ""),
    "2009 - CFP - Resolucao Registro Documental": ("Resolução do CFP sobre registro documental", ""),
    "2018 - CFP - Resolucao Pessoas Trans": ("Resolução do CFP sobre pessoas trans e travestis", ""),
    "1999 - CFP - Resolucao Orientacao Sexual": ("Resolução do CFP sobre orientação sexual", ""),
    "2010 - CFP - Resolucao Perito e Assistente Tecnico": ("Resolução do CFP sobre perito e assistente técnico", ""),
    "2022 - CFP - Cartilha Avaliacao Psicologica": ("Cartilha de Avaliação Psicológica do CFP", ""),
    "2006 - Lei - Maria da Penha": ("Lei Maria da Penha", ""),
    "1990 - Lei - ECA": ("Estatuto da Criança e do Adolescente (ECA)", ""),
    "2001 - Lei - Reforma Psiquiatrica": ("Lei da Reforma Psiquiátrica", ""),
    "2015 - Lei - Brasileira de Inclusao": ("Lei Brasileira de Inclusão", ""),
    "2003 - Lei - Estatuto da Pessoa Idosa": ("Estatuto da Pessoa Idosa", ""),
    "1993 - Lei - LOAS": ("Lei Orgânica da Assistência Social (LOAS)", ""),
    "1990 - Lei - Organica da Saude SUS": ("Lei Orgânica da Saúde (SUS)", ""),
    "2017 - Lei - Escuta Protegida": ("Lei da Escuta Protegida", ""),
    "1962 - Lei - Profissao de Psicologo": ("Lei da profissão de psicólogo", ""),
    "1971 - Lei - Conselhos de Psicologia": ("Lei dos Conselhos de Psicologia", ""),
    "2003 - Lei - Notificacao Compulsoria Violencia contra a Mulher": ("Lei da notificação compulsória da violência contra a mulher", ""),
    "2012 - Lei - SINASE": ("Lei do SINASE", ""),
    "2006 - Lei - Drogas": ("Lei de Drogas", ""),
    "2016 - Lei - Marco Legal da Primeira Infancia": ("Marco Legal da Primeira Infância", ""),
    "2010 - Lei - Estatuto da Igualdade Racial": ("Estatuto da Igualdade Racial", ""),
    "2019 - Lei - Prevencao da Automutilacao e do Suicidio": ("Lei de Prevenção da Automutilação e do Suicídio", ""),
    "2012 - Lei - Autismo TEA": ("Lei Berenice Piana (autismo)", ""),
    "2019 - Lei - Psicologia e Servico Social na Educacao Basica": ("Lei da Psicologia e do Serviço Social nas escolas", ""),
    "2013 - Lei - Minuto Seguinte": ("Lei do Minuto Seguinte", ""),
    "2013 - Gov - Caderno de Atencao Basica Saude Mental": ("Caderno de Atenção Básica: saúde mental", ""),
    "2006 - Gov - Prevencao do Suicidio Manual": ("Prevenção do suicídio: manual para equipes de saúde mental", ""),
    "2010 - Gov - Linha de Cuidado Criancas e Adolescentes em Violencias": ("Linha de cuidado de crianças e adolescentes em situação de violências", ""),
    "2016 - Gov - Instrutivo de Notificacao de Violencia": ("Instrutivo de notificação de violência (VIVA)", ""),
    "2005 - Gov - PNAS e NOB SUAS": ("Política Nacional de Assistência Social (PNAS) e NOB/SUAS", ""),
    "2014 - Gov - Tipificacao dos Servicos Socioassistenciais": ("Tipificação nacional dos serviços socioassistenciais", ""),
    "2011 - Gov - Orientacoes Tecnicas CREAS": ("Orientações técnicas do CREAS", ""),
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 1": ("Orientações técnicas do PAIF (vol. I)", ""),
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 2": ("Orientações técnicas do PAIF (vol. II)", ""),
}

_GRUPOS_MAPA = [  # (pedaço do título, rótulo da linha única no mapa)
    (" - CFP - ", "NORMAS DO CFP (texto integral)"),
    (" - Lei - ", "LEIS (texto integral, versão compilada do Planalto)"),
    (" - Gov - ", "MANUAIS DO GOVERNO FEDERAL (Ministério da Saúde e MDS)"),
]
# Obras com nome de catálogo e sem "assunto" (leis, normas do CFP, manuais do governo).
EXTRAS = re.compile(r"^\d{4} - (Lei|CFP|Gov) - ")


def nome_curto(titulo: str) -> str | None:
    """Nome para mostrar (tela e cabeçalho do trecho), só das obras que têm um no catálogo."""
    item = OBRAS.get(titulo)
    return item[0] if item else None

# Temas que as pessoas procuram: (rótulo, expressão regular do Postgres, sem diferenciar
# maiúsculas). Por palavra inteira (\m … \M), e não pelo radical: o radical junta "luto" e
# "luta", e "luto" apontava para as obras sobre povos indígenas e questões da terra.
TEMAS = [
    ("ansiedade", r"\mansiedade|\mansios[oa]"), ("depressão", r"\mdepress[ãa]o|\mdepressiv"),
    ("suicídio", r"\msuic[ií]di|\msuicida"), ("autolesão", r"\mautoles|\mautomutila"),
    ("luto", r"\mluto\M|\menlutad|\mprocesso de luto"), ("trauma", r"\mtrauma|\mtraum[áa]tic"),
    ("medicalização", r"\mmedicaliza"), ("autismo", r"\mautis|\mTEA\M"),
    ("deficiência", r"\mdefici[êe]ncia"), ("álcool e drogas", r"\m[áa]lcool\M|\mdrogas\M"),
    ("redução de danos", r"redu[çc][ãa]o de danos"), ("comunidades terapêuticas", r"comunidades? terap[êe]uticas?"),
    ("internação", r"\minterna[çc][ãa]o"), ("violência doméstica", r"viol[êe]ncia dom[ée]stica"),
    ("violência sexual", r"viol[êe]ncia sexual|\mestupro"), ("feminicídio", r"\mfeminic[ií]dio"),
    ("abuso infantil", r"abuso sexual|maus-tratos"), ("bullying", r"\mbullying"),
    ("racismo", r"\mracismo|\mracista"), ("pessoas trans", r"\mtrans\M|\mtransexua|\mtravesti|\mtransg[êe]ner"),
    ("gênero", r"\mg[êe]nero\M"), ("adolescência", r"\madolescen"),
    ("juventude", r"\mjuventude|\mjovens?\M"), ("infância", r"\mcrian[çc]a|\minf[âa]ncia"),
    ("família", r"\mfam[ií]lia"), ("gravidez e maternidade", r"\mgravidez|\mgestante|\mmaternidade"),
    ("aborto", r"\maborto|\mabortamento"), ("envelhecimento", r"\menvelhec|\midos[oa]s?\M"),
    ("trabalho e adoecimento", r"\madoecimento|\mass[ée]dio|\mburnout"),
    ("avaliação psicológica", r"avalia[çc][ãa]o psicol[óo]gica"),
    ("laudos e documentos", r"\mlaudos?\M|documentos? psicol[óo]gicos?|relat[óo]rios? psicol[óo]gicos?"),
    ("sigilo", r"\msigilo|\mconfidencialidade"), ("ética profissional", r"c[óo]digo de [ée]tica"),
    ("supervisão", r"\msupervis[ãa]o"), ("acolhimento", r"\macolhimento"), ("escuta", r"\mescuta\M"),
    ("grupos", r"grupos? terap[êe]utic|\moficinas?\M"), ("visita domiciliar", r"visitas? domiciliar"),
    ("matriciamento", r"\mmatriciamento|apoio matricial"), ("notificação compulsória", r"notifica[çc][ãa]o compuls[óo]ria"),
    ("reforma psiquiátrica", r"reforma psiqui[áa]trica|\mantimanicomial"),
    ("migração e refúgio", r"\mmigrante|\mrefugiad|\mrefúgio"), ("pandemia", r"\mpandemia|\mcovid"),
]
POR_TEMA = 3  # obras listadas por tema

_mapa: str | None = None


def _nome(titulo: str) -> str:
    return OBRAS.get(titulo, (titulo, ""))[0]


def gerar(conn) -> str:
    """Monta o texto do mapa (ordem fixa: o texto sai igual a cada vez, para o cache)."""
    titulos = [t for (t,) in conn.execute(
        """SELECT pub.titulo FROM publicacao pub
           JOIN versao_arquivo v ON v.id_publicacao = pub.id_publicacao AND v.situacao_vigencia
           ORDER BY pub.titulo""").fetchall()]
    obras = []
    for pedaco, rotulo in _GRUPOS_MAPA:
        do_grupo = sorted((t for t in titulos if pedaco in t), key=_nome)
        if do_grupo:
            obras.append(f"- {rotulo}: " + "; ".join(_nome(t) for t in do_grupo))
        titulos = [t for t in titulos if pedaco not in t]
    for t in sorted(titulos, key=_nome):
        nome, assunto = OBRAS.get(t, (t, ""))
        ref = referencias.de(t)
        obras.append(f"- {nome}{f' ({ref['ano']})' if ref and str(ref['ano']) not in nome else ''}"
                     + (f": {assunto}" if assunto else ""))
    temas = []
    for rotulo, busca in TEMAS:
        linhas = conn.execute(
            """SELECT pub.titulo, count(*) AS n
               FROM pagina p JOIN versao_arquivo va USING (id_versao) JOIN publicacao pub USING (id_publicacao)
               WHERE va.situacao_vigencia AND p.conteudo_texto ~* %s
               GROUP BY pub.titulo ORDER BY n DESC, pub.titulo LIMIT %s""",
            (busca, POR_TEMA)).fetchall()
        if linhas:
            temas.append(f"- {rotulo}: " + "; ".join(f"{_nome(t)} ({n} p.)" for t, n in linhas))
    return ("MAPA DO ACERVO (as obras que existem e onde cada tema mais aparece). Serve só para "
            "você saber o que há no acervo e sugerir onde procurar. NÃO é fonte: não cite o mapa "
            "nem tire dele informações para a resposta; responda só com os TRECHOS.\n"
            "OBRAS:\n" + "\n".join(obras)
            + "\nTEMAS (obras com mais páginas sobre cada um):\n" + "\n".join(temas))


def texto() -> str:
    """O mapa, calculado uma vez por processo (o acervo só muda por script, com reinício)."""
    global _mapa
    if _mapa is None:
        with pool.connection() as conn:
            _mapa = gerar(conn)
    return _mapa
