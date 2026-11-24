"""Vocabulário controlado do Acervo Psico: conceito -> termos equivalentes.

Serve para a busca entender que quem pesquisa "agressão" também quer as páginas
que dizem "violência". O primeiro termo de cada lista é o termo preferido.

Plural, acento e flexão já são resolvidos pelo radical (stem) do Postgres:
não precisa listar "mulher" e "mulheres". Aqui entram só sinônimos de verdade.

Para incluir um conceito: acrescente uma linha e rode `python migrar.py` na VM.
Revisar com quem é da Psicologia é o passo mais importante deste arquivo.
"""

CONCEITOS: dict[str, list[str]] = {
    # Violências
    "violência": ["violência", "agressão", "maus-tratos", "violento"],
    "violência contra a mulher": [
        "violência contra a mulher", "violência doméstica", "violência de gênero",
        "feminicídio", "Maria da Penha",
        # Como as pessoas perguntam pela lei sem saber o nome dela.
        "lei que protege a mulher", "lei de proteção à mulher", "Lei 11.340",
    ],
    "violência sexual": ["violência sexual", "abuso sexual", "estupro", "exploração sexual"],
    "racismo": ["racismo", "discriminação racial", "preconceito racial", "injúria racial"],
    "LGBTfobia": ["LGBTfobia", "homofobia", "transfobia", "lesbofobia"],
    "capacitismo": ["capacitismo", "discriminação da pessoa com deficiência"],
    # Ciclos de vida e populações
    "criança": ["criança", "infância", "infantil"],
    "adolescente": ["adolescente", "adolescência", "juventude", "jovem"],
    "pessoa idosa": ["pessoa idosa", "idoso", "velhice", "envelhecimento", "terceira idade"],
    "mulher": ["mulher", "feminino"],
    "pessoa com deficiência": ["pessoa com deficiência", "deficiência", "PCD"],
    "povos indígenas": ["povos indígenas", "indígena", "povos originários", "aldeia"],
    "população em situação de rua": [
        "população em situação de rua", "situação de rua", "morador de rua",
    ],
    "migração": ["migração", "migrante", "imigrante", "refugiado", "refúgio"],
    "diversidade sexual": [
        "diversidade sexual", "LGBT", "LGBTQIA", "orientação sexual", "identidade de gênero",
    ],
    "família": ["família", "familiar", "parentalidade"],
    # Saúde mental e sofrimento
    "saúde mental": ["saúde mental", "sofrimento psíquico", "transtorno mental", "adoecimento psíquico"],
    "suicídio": ["suicídio", "ideação suicida", "comportamento suicida", "autolesão", "automutilação"],
    "ansiedade": ["ansiedade", "angústia", "ansioso"],
    "depressão": ["depressão", "depressivo", "tristeza profunda"],
    "luto": ["luto", "perda", "morte", "óbito"],
    "álcool e drogas": [
        "álcool e drogas", "droga", "substância psicoativa", "dependência química",
        "alcoolismo", "uso abusivo",
    ],
    "trauma": ["trauma", "traumático", "estresse pós-traumático", "TEPT"],
    # Prática profissional
    "sigilo": ["sigilo", "confidencialidade", "segredo profissional", "sigilo profissional"],
    "ética profissional": ["ética profissional", "código de ética", "conduta ética"],
    "documentos psicológicos": [
        "documentos psicológicos", "laudo", "parecer", "relatório psicológico",
        "declaração", "atestado psicológico",
    ],
    "avaliação psicológica": [
        "avaliação psicológica", "psicodiagnóstico", "teste psicológico", "instrumento psicológico",
    ],
    "acolhimento": ["acolhimento", "escuta qualificada", "escuta", "atendimento"],
    "trabalho em rede": ["trabalho em rede", "intersetorialidade", "articulação da rede", "rede de proteção"],
    # Políticas e serviços
    # CRAS (proteção básica) e CREAS (proteção especial) NÃO são sinônimos: cada um no seu.
    "assistência social": ["assistência social", "SUAS", "proteção social", "política de assistência social"],
    "CRAS": ["CRAS", "centro de referência de assistência social", "proteção social básica", "PAIF"],
    "CREAS": ["CREAS", "centro de referência especializado de assistência social",
              "proteção social especial", "PAEFI"],
    "atenção básica": ["atenção básica", "atenção primária", "UBS", "unidade básica de saúde", "ESF"],
    "atenção psicossocial": [
        "atenção psicossocial", "CAPS", "RAPS", "rede de atenção psicossocial", "reforma psiquiátrica",
    ],
    "hospital": ["hospital", "hospitalar", "internação"],
    "sistema prisional": [
        "sistema prisional", "prisão", "encarceramento", "privação de liberdade", "presídio",
    ],
    "socioeducação": [
        "socioeducação", "medida socioeducativa", "ato infracional", "adolescente em conflito com a lei",
    ],
    "justiça": ["justiça", "judiciário", "vara de família", "poder judiciário", "tribunal"],
    "segurança pública": ["segurança pública", "polícia", "policial"],
    "educação": ["educação", "escola", "escolar", "educação básica", "ambiente escolar"],
    "emergências e desastres": ["emergências e desastres", "desastre", "catástrofe", "calamidade", "emergência"],
    "direitos sexuais e reprodutivos": [
        "direitos sexuais e reprodutivos", "saúde sexual", "saúde reprodutiva",
        "direitos reprodutivos", "planejamento reprodutivo",
    ],
    "IST/HIV": ["HIV", "aids", "IST", "infecção sexualmente transmissível"],
    "questão agrária": ["questão agrária", "reforma agrária", "rural", "camponês", "trabalhador rural"],
    "trânsito": ["trânsito", "mobilidade", "motorista", "condutor"],
    "esporte": ["esporte", "atividade física", "atleta", "esportivo"],
    "gênero": ["gênero", "machismo", "sexismo", "desigualdade de gênero", "patriarcado"],
}
