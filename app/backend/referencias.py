"""Referência ABNT (NBR 6023:2018) de cada publicação, para a pessoa citar no trabalho.

Montadas à mão a partir da ficha catalográfica (CIP) de cada PDF, em 03/11/2026.
As obras sem ficha usaram a folha de rosto. A chave é o título do arquivo no banco
(publicacao.titulo). O "2022" no nome dos arquivos é o ano do download, não o da
publicação: o ano certo está aqui.

Formato de cada item: (autor, título em negrito, complemento do título, edição,
publicação [local: editora], ano, eletrônico).
Na tela: referência completa + citação no texto "(CONSELHO FEDERAL DE PSICOLOGIA, 2019, p. 43)".
"""
CFP = "CONSELHO FEDERAL DE PSICOLOGIA (Brasil)"
CREPOP = "CENTRO DE REFERÊNCIA TÉCNICA EM PSICOLOGIA E POLÍTICAS PÚBLICAS (Brasil)"
BSB = "Brasília: CFP"
GM_LEME = "Leme: GM Editorial; Brasília: CFP"
GM_SP = "São Paulo: GM Editorial; Brasília: CFP"
RT = "Referências técnicas para atuação de psicólogas(os)"
SEM_IX = "IX Seminário Nacional Psicologia e Políticas Públicas"
MS = "BRASIL. Ministério da Saúde"
MDS = "BRASIL. Ministério do Desenvolvimento Social e Combate à Fome"
BSB_MS = "Brasília: Ministério da Saúde"
BSB_MDS = "Brasília: MDS"

OBRAS: dict[str, tuple[str, str, str, str, str, int, bool]] = {
    "Referencias Tecnicas para atuacao de psicologas(os) nos CAPS":
        (CFP, f"{RT} no CAPS", "Centro de Atenção Psicossocial", "ed. rev.", BSB, 2022, False),
    "2022 - Gestores - SUAS":
        (CFP, "Como os psicólogos e as psicólogas podem contribuir para avançar o Sistema Único de "
              "Assistência Social (SUAS)", "informações para gestoras e gestores", "", BSB, 2011, False),
    "2022 - Gestores - SUS":
        (CFP, "Senhoras e senhores gestores da Saúde, como a Psicologia pode contribuir para o avanço "
              "do SUS", "", "", BSB, 2011, False),
    "2022 - RT - Alcool e Drogas":
        (CFP, f"{RT} em políticas públicas de álcool e outras drogas", "", "2. ed.", BSB, 2019, True),
    "2022 - RT - Atencao Basica":
        (CFP, f"{RT} na atenção básica à saúde", "", "2. ed.", BSB, 2019, False),
    "2022 - RT - CAPS":
        (CFP, f"{RT} no CAPS", "Centro de Atenção Psicossocial", "", BSB, 2013, False),
    "2022 - RT - CRAS SUAS":
        (CFP, f"{RT} no CRAS/SUAS", "", "3. ed.", BSB, 2021, False),
    "2022 - RT - CREAS":
        (CFP, "Referências técnicas para prática de psicólogas(os) no Centro de Referência "
              "Especializado da Assistência Social", "CREAS", "", BSB, 2012, False),
    "2022 - RT - Educacao Basica":
        (CFP, f"{RT} na educação básica", "", "2. ed.", BSB, 2019, False),
    "2022 - RT - Emergencias e Desastres":
        (CFP, f"{RT} na gestão integral de riscos, emergências e desastres", "", "", BSB, 2021, False),
    "2022 - RT - Esporte":
        (CFP, f"{RT} em políticas públicas de esporte", "", "", BSB, 2019, False),
    "2022 - RT - Hospitais SUS":
        (CFP, f"{RT} nos serviços hospitalares do SUS", "", "", BSB, 2019, False),
    "2022 - RT - IST HIV Aids":
        (CFP, f"{RT} nos programas de IST/HIV/aids", "", "ed. rev.", BSB, 2020, False),
    "2022 - RT - Medidas Socioeducativas":
        (CFP, f"{RT} no âmbito das medidas socioeducativas", "", "", BSB, 2021, False),
    "2022 - RT - Mobilidade e Transito":
        (CREPOP, f"{RT} em políticas públicas de mobilidade humana e trânsito", "", "",
         "Brasília: Conselho Federal de Psicologia", 2018, False),
    "2022 - RT - Mulher em Violencia":
        (CFP, f"{RT} em programas de atenção à mulher em situação de violência", "", "", BSB, 2012, False),
    "2022 - RT - Povos Indigenas":
        (CFP, f"{RT} junto aos povos indígenas", "", "", BSB, 2022, False),
    "2022 - RT - Povos Tradicionais":
        (CFP, f"{RT} com povos tradicionais", "", "", BSB, 2019, False),
    "2022 - RT - Questoes da Terra":
        (CFP, f"{RT} em questões relativas à terra", "", "ed. rev.", BSB, 2019, False),
    "2022 - RT - Relacoes Raciais":
        (CFP, "Relações raciais", "referências técnicas para atuação de psicólogas/os", "", BSB, 2017, False),
    "2022 - RT - Saude do Trabalhador":
        (CFP, "Saúde do trabalhador no âmbito da saúde pública",
         "referências para atuação da(o) psicóloga(o)", "2. ed.", BSB, 2019, True),
    "2022 - RT - Seguranca Publica":
        (CFP, f"{RT} na política de segurança pública", "", "", BSB, 2020, False),
    "2022 - RT - Sistema Prisional":
        (CFP, f"{RT} no sistema prisional", "", "", BSB, 2021, False),
    "2022 - RT - Varas de Familia":
        (CFP, "Referências técnicas para a atuação de psicólogas(os) em varas de família", "",
         "ed. rev.", BSB, 2019, False),
    "2022 - RT - Violencia Sexual Infantojuvenil":
        (CFP, f"{RT} na rede de proteção às crianças e adolescentes em situação de violência sexual",
         "", "2. ed. rev.", BSB, 2020, False),
    "2022 - Seminario IX - Centro-Oeste":
        (CFP, SEM_IX, "etapa Centro-Oeste: psicologia e políticas públicas: a construção do trabalho "
                      "junto com os povos indígenas e quilombolas no Centro-Oeste", "", BSB, 2019, False),
    "2022 - Seminario IX - Geral":
        (CFP, SEM_IX, "etapa nacional: Psicologia na defesa das políticas públicas", "", BSB, 2019, False),
    "2022 - Seminario IX - Nordeste":
        (CFP, SEM_IX, "etapa Nordeste: seguridade social e processos de subjetivação em tempos de crise "
                      "e desmonte das políticas públicas", "", BSB, 2019, False),
    "2022 - Seminario IX - Norte":
        (CFP, SEM_IX, "etapa Norte: conjuntura política e a prática da psicologia em políticas públicas",
         "", BSB, 2019, False),
    "2022 - Seminario IX - Sudeste":
        (CFP, SEM_IX, "etapa Sudeste: diálogos em rede e desafios ético-políticos da Psicologia nas "
                      "políticas públicas: do desmonte à resistência", "", BSB, 2019, False),
    "2022 - Seminario IX - Sul":
        (CFP, SEM_IX, "etapa Sul: Psicologia, educação e laicidade: enfrentamentos ao conservadorismo",
         "", BSB, 2019, False),
    "2023 - RT - LGBTQIA+":
        (CFP, "Referências técnicas para atuação de psicólogas, psicólogos e psicólogues em políticas "
              "públicas para população LGBTQIA+", "", "", BSB, 2023, True),
    "2023 - Seminario XII - Migracao e Refugio":
        (CFP, "XII Seminário de Psicologia e Políticas Públicas",
         "interface entre psicologia e populações em situação de refúgio, migração e apatridia", "",
         "Brasília: Conselho Federal de Psicologia", 2024, False),
    "2024 - RT - Povos Indigenas 2a ed":
        (CFP, "Nota técnica sobre atuação de psicólogas(os) junto aos povos indígenas", "", "2. ed.",
         BSB, 2024, True),
    "2025 - Gestores - SUAS":
        (CFP, "Como as psicólogas e os psicólogos podem contribuir para avançar o Sistema Único de "
              "Assistência Social (SUAS)", "informações para gestoras e gestores", "2. ed.", GM_LEME, 2025, True),
    "2025 - Mostra - Praticas na RAPS":
        (CFP, "A Psicologia na luta pelo cuidado em liberdade",
         "ontem, hoje, sempre!: I Mostra Nacional de Práticas Profissionais na Rede de Atenção "
         "Psicossocial (RAPS)", "", GM_LEME, 2025, True),
    "2025 - RT - Direitos Sexuais e Reprodutivos":
        (CFP, f"{RT} em políticas públicas de direitos sexuais e direitos reprodutivos", "", "", GM_SP, 2025, True),
    "2025 - RT - Mulheres em Violencia":
        (CFP, f"{RT} no atendimento às mulheres em situação de violência", "", "2. ed.", GM_SP, 2024, False),
    "2025 - RT - Pessoas Idosas":
        (CFP, "Referências técnicas para a atuação de psicólogas(os) junto às pessoas idosas nas "
              "políticas públicas", "", "", "Brasília: Conselho Federal de Psicologia", 2025, True),
    "2025 - RT - Populacao de Rua":
        (CFP, f"{RT} em políticas públicas para a população em situação de rua", "", "", GM_SP, 2025, True),
    "2025 - RT - Quilombolas":
        (CFP, f"{RT} junto aos povos quilombolas", "", "", GM_LEME, 2025, True),
    # ---- Normas do CFP (acrescentadas em 10/11/2026) ----
    "2005 - CFP - Codigo de Etica":
        (CFP, "Código de ética profissional do psicólogo", "", "", BSB, 2005, True),
    "2019 - CFP - Resolucao Documentos Psicologicos":
        (CFP, "Resolução CFP nº 06/2019 comentada", "orientações sobre elaboração de documentos escritos "
              "produzidos pela(o) psicóloga(o) no exercício profissional", "", BSB, 2019, True),
    "2018 - CFP - Resolucao Atendimento Online":
        (CFP, "Resolução nº 11, de 11 de maio de 2018", "regulamenta a prestação de serviços psicológicos "
              "realizados por meios de tecnologias da informação e da comunicação", "", BSB, 2018, True),
    "2009 - CFP - Resolucao Registro Documental":
        (CFP, "Resolução CFP nº 001/2009", "dispõe sobre a obrigatoriedade do registro documental decorrente "
              "da prestação de serviços psicológicos", "", BSB, 2009, True),
    "2018 - CFP - Resolucao Pessoas Trans":
        (CFP, "Resolução nº 1, de 29 de janeiro de 2018", "estabelece normas de atuação para as psicólogas e "
              "os psicólogos em relação às pessoas transexuais e travestis", "", BSB, 2018, True),
    "1999 - CFP - Resolucao Orientacao Sexual":
        (CFP, "Resolução CFP nº 001/99, de 22 de março de 1999", "estabelece normas de atuação para os "
              "psicólogos em relação à questão da orientação sexual", "", BSB, 1999, True),
    "2010 - CFP - Resolucao Perito e Assistente Tecnico":
        (CFP, "Resolução CFP nº 008/2010", "dispõe sobre a atuação do psicólogo como perito e assistente "
              "técnico no Poder Judiciário", "", BSB, 2010, True),
    "2022 - CFP - Cartilha Avaliacao Psicologica":
        (CFP, "Cartilha avaliação psicológica", "", "3. ed.", BSB, 2022, True),
    # ---- Manuais do governo federal (Ministério da Saúde e MDS), 10/11/2026 ----
    "2013 - Gov - Caderno de Atencao Basica Saude Mental":
        (MS + ". Secretaria de Atenção à Saúde. Departamento de Atenção Básica", "Saúde mental", "",
         "", BSB_MS, 2013, True),
    "2006 - Gov - Prevencao do Suicidio Manual":
        (MS, "Prevenção do suicídio", "manual dirigido a profissionais das equipes de saúde mental", "",
         BSB_MS, 2006, True),
    "2010 - Gov - Linha de Cuidado Criancas e Adolescentes em Violencias":
        (MS + ". Secretaria de Atenção à Saúde", "Linha de cuidado para a atenção integral à saúde de "
         "crianças, adolescentes e suas famílias em situação de violências",
         "orientação para gestores e profissionais de saúde", "", BSB_MS, 2010, True),
    "2016 - Gov - Instrutivo de Notificacao de Violencia":
        (MS + ". Secretaria de Vigilância em Saúde", "Viva",
         "instrutivo notificação de violência interpessoal e autoprovocada", "2. ed.", BSB_MS, 2016, True),
    "2005 - Gov - PNAS e NOB SUAS":
        (MDS + ". Secretaria Nacional de Assistência Social", "Política Nacional de Assistência Social "
         "PNAS/2004", "Norma Operacional Básica NOB/SUAS", "", BSB_MDS, 2005, True),
    "2014 - Gov - Tipificacao dos Servicos Socioassistenciais":
        (MDS, "Tipificação nacional de serviços socioassistenciais", "", "Reimpr.", BSB_MDS, 2014, True),
    "2011 - Gov - Orientacoes Tecnicas CREAS":
        (MDS, "Orientações técnicas", "Centro de Referência Especializado de Assistência Social – CREAS",
         "", BSB_MDS, 2011, True),
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 1":
        (MDS, "Orientações técnicas sobre o PAIF", "o Serviço de Proteção e Atendimento Integral à "
         "Família – PAIF, segundo a Tipificação Nacional de Serviços Socioassistenciais", "",
         BSB_MDS, 2012, True),
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 2":
        (MDS, "Orientações técnicas sobre o PAIF", "trabalho social com famílias do Serviço de Proteção "
         "e Atendimento Integral à Família – PAIF", "", BSB_MDS, 2012, True),
}

# ---- Leis (texto compilado do Planalto, baixado em 10/11/2026) ----
# título do arquivo -> (número, data por extenso, ano, ementa, endereço)
_P = "https://www.planalto.gov.br/ccivil_03/"
LEIS: dict[str, tuple[str, str, int, str, str]] = {
    "2006 - Lei - Maria da Penha": ("11.340", "7 de agosto de 2006", 2006,
        "Cria mecanismos para coibir a violência doméstica e familiar contra a mulher", _P + "_ato2004-2006/2006/lei/l11340.htm"),
    "1990 - Lei - ECA": ("8.069", "13 de julho de 1990", 1990,
        "Dispõe sobre o Estatuto da Criança e do Adolescente e dá outras providências", _P + "leis/l8069.htm"),
    "2001 - Lei - Reforma Psiquiatrica": ("10.216", "6 de abril de 2001", 2001,
        "Dispõe sobre a proteção e os direitos das pessoas portadoras de transtornos mentais e redireciona "
        "o modelo assistencial em saúde mental", _P + "leis/leis_2001/l10216.htm"),
    "2015 - Lei - Brasileira de Inclusao": ("13.146", "6 de julho de 2015", 2015,
        "Institui a Lei Brasileira de Inclusão da Pessoa com Deficiência (Estatuto da Pessoa com Deficiência)",
        _P + "_ato2015-2018/2015/lei/l13146.htm"),
    "2003 - Lei - Estatuto da Pessoa Idosa": ("10.741", "1º de outubro de 2003", 2003,
        "Dispõe sobre o Estatuto da Pessoa Idosa e dá outras providências", _P + "leis/2003/l10.741.htm"),
    "1993 - Lei - LOAS": ("8.742", "7 de dezembro de 1993", 1993,
        "Dispõe sobre a organização da Assistência Social e dá outras providências", _P + "leis/l8742.htm"),
    "1990 - Lei - Organica da Saude SUS": ("8.080", "19 de setembro de 1990", 1990,
        "Dispõe sobre as condições para a promoção, proteção e recuperação da saúde, a organização e o "
        "funcionamento dos serviços correspondentes e dá outras providências", _P + "leis/l8080.htm"),
    "2017 - Lei - Escuta Protegida": ("13.431", "4 de abril de 2017", 2017,
        "Estabelece o sistema de garantia de direitos da criança e do adolescente vítima ou testemunha de "
        "violência", _P + "_ato2015-2018/2017/lei/l13431.htm"),
    "1962 - Lei - Profissao de Psicologo": ("4.119", "27 de agosto de 1962", 1962,
        "Dispõe sobre os cursos de formação em psicologia e regulamenta a profissão de psicólogo",
        _P + "leis/1950-1969/l4119.htm"),
    "1971 - Lei - Conselhos de Psicologia": ("5.766", "20 de dezembro de 1971", 1971,
        "Cria o Conselho Federal e os Conselhos Regionais de Psicologia e dá outras providências",
        _P + "leis/l5766.htm"),
    "2003 - Lei - Notificacao Compulsoria Violencia contra a Mulher": ("10.778", "24 de novembro de 2003", 2003,
        "Estabelece a notificação compulsória, no território nacional, do caso de violência contra a mulher "
        "que for atendida em serviços de saúde públicos ou privados", _P + "leis/2003/l10.778.htm"),
    "2012 - Lei - SINASE": ("12.594", "18 de janeiro de 2012", 2012,
        "Institui o Sistema Nacional de Atendimento Socioeducativo (Sinase) e regulamenta a execução das "
        "medidas socioeducativas destinadas a adolescente que pratique ato infracional",
        _P + "_ato2011-2014/2012/lei/l12594.htm"),
    "2006 - Lei - Drogas": ("11.343", "23 de agosto de 2006", 2006,
        "Institui o Sistema Nacional de Políticas Públicas sobre Drogas - Sisnad", _P + "_ato2004-2006/2006/lei/l11343.htm"),
    "2016 - Lei - Marco Legal da Primeira Infancia": ("13.257", "8 de março de 2016", 2016,
        "Dispõe sobre as políticas públicas para a primeira infância", _P + "_ato2015-2018/2016/lei/l13257.htm"),
    "2010 - Lei - Estatuto da Igualdade Racial": ("12.288", "20 de julho de 2010", 2010,
        "Institui o Estatuto da Igualdade Racial", _P + "_ato2007-2010/2010/lei/l12288.htm"),
    "2019 - Lei - Prevencao da Automutilacao e do Suicidio": ("13.819", "26 de abril de 2019", 2019,
        "Institui a Política Nacional de Prevenção da Automutilação e do Suicídio",
        _P + "_ato2019-2022/2019/lei/l13819.htm"),
    "2012 - Lei - Autismo TEA": ("12.764", "27 de dezembro de 2012", 2012,
        "Institui a Política Nacional de Proteção dos Direitos da Pessoa com Transtorno do Espectro Autista",
        _P + "_ato2011-2014/2012/lei/l12764.htm"),
    "2019 - Lei - Psicologia e Servico Social na Educacao Basica": ("13.935", "11 de dezembro de 2019", 2019,
        "Dispõe sobre a prestação de serviços de psicologia e de serviço social nas redes públicas de "
        "educação básica", _P + "_ato2019-2022/2019/lei/l13935.htm"),
    "2013 - Lei - Minuto Seguinte": ("12.845", "1º de agosto de 2013", 2013,
        "Dispõe sobre o atendimento obrigatório e integral de pessoas em situação de violência sexual",
        _P + "_ato2011-2014/2013/lei/l12845.htm"),
}
ACESSO = "10 nov. 2026"


def _de_lei(titulo_arquivo: str) -> dict | None:
    """ABNT NBR 6023:2018, legislação em meio eletrônico:
    BRASIL. Lei nº 11.340, de 7 de agosto de 2006. Ementa. Brasília, DF: Presidência da
    República, [2006]. Disponível em: URL. Acesso em: 10 nov. 2026."""
    item = LEIS.get(titulo_arquivo)
    if not item:
        return None
    numero, data, ano, ementa, url = item
    # Na legislação a NBR 6023 não põe negrito no título da lei (o destaque vai no Diário
    # Oficial, que aqui não entra: a fonte é o texto compilado do Planalto).
    abnt = (f"BRASIL. Lei nº {numero}, de {data}. {ementa}. Brasília, DF: Presidência da República, "
            f"[{ano}]. Disponível em: {url}. Acesso em: {ACESSO}.")
    return {"autor": "BRASIL", "autor_citacao": "BRASIL", "ano": ano,
            "abnt": abnt, "abnt_texto": abnt.replace("**", "")}


# O que vem DEPOIS do ano na referência (série, volume): "…, 2013. (Cadernos de Atenção Básica, n. 34)."
DEPOIS_DO_ANO = {
    "2013 - Gov - Caderno de Atencao Basica Saude Mental": "(Cadernos de Atenção Básica, n. 34).",
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 1": "v. 1.",
    "2012 - Gov - Orientacoes Tecnicas PAIF vol 2": "v. 2.",
}


def _autor_citacao(autor: str) -> str:
    """'CONSELHO FEDERAL DE PSICOLOGIA (Brasil)' -> 'CONSELHO FEDERAL DE PSICOLOGIA';
    'BRASIL. Ministério da Saúde. …' -> 'BRASIL' (citação no texto: (BRASIL, 2013))."""
    if autor.startswith("BRASIL"):
        return "BRASIL"
    return autor.split(" (")[0]


def de(titulo_arquivo: str) -> dict | None:
    """Referência da obra: {'autor', 'ano', 'abnt' (com **negrito**), 'abnt_texto' (sem marcação),
    'autor_citacao'}. None se a obra não estiver no catálogo (obra nova: acrescentar aqui)."""
    if titulo_arquivo in LEIS:
        return _de_lei(titulo_arquivo)
    item = OBRAS.get(titulo_arquivo)
    if not item:
        return None
    autor, titulo, complemento, edicao, publicacao, ano, eletronico = item
    partes_titulo = f"**{titulo}**" + (f": {complemento}" if complemento else "")
    edicao = edicao if not edicao or edicao.endswith(".") else edicao + "."  # "2. ed." já termina em ponto
    pedacos = [f"{autor}.", f"{partes_titulo}.", edicao, f"{publicacao}, {ano}.",
               DEPOIS_DO_ANO.get(titulo_arquivo, "")]
    if eletronico:
        pedacos.append("E-book.")
    abnt = " ".join(p for p in pedacos if p)
    return {"autor": autor, "autor_citacao": _autor_citacao(autor), "ano": ano,
            "abnt": abnt, "abnt_texto": abnt.replace("**", "")}
