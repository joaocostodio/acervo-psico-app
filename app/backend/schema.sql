-- Schema do Acervo Psico (MVP "NotebookLM local").
-- Recorte do MER (../../README.md). Embeddings = 768 dim (vetor_conteudo: nomic-embed-text; vetor_conteudo_2: embeddinggemma, em uso).
--
-- Idempotente: o migrar.py roda este arquivo inteiro a cada atualização. Tudo é
-- "IF NOT EXISTS", então serve tanto para banco novo quanto para atualizar um antigo.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Busca textual em português que ignora acento: "violencia" acha "violência",
-- e o radical (stem) junta "mulher"/"mulheres", "agressão"/"agressões".
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_ts_config WHERE cfgname = 'pt_sem_acento') THEN
        CREATE TEXT SEARCH CONFIGURATION pt_sem_acento (COPY = portuguese);
        ALTER TEXT SEARCH CONFIGURATION pt_sem_acento
            ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;
    END IF;
END $$;

-- ============ ACERVO ============

CREATE TABLE IF NOT EXISTS fonte_emissora (
    id_fonte          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_fonte        VARCHAR(255) NOT NULL UNIQUE,
    url_oficial_fonte TEXT
);

CREATE TABLE IF NOT EXISTS publicacao (
    id_publicacao      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    titulo             VARCHAR(500) NOT NULL,
    tipo               VARCHAR(100),
    url_pagina_oficial TEXT,
    id_fonte           INT REFERENCES fonte_emissora(id_fonte)
);

CREATE TABLE IF NOT EXISTS versao_arquivo (
    id_versao         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_publicacao     INT NOT NULL REFERENCES publicacao(id_publicacao) ON DELETE CASCADE,
    numero_versao     INT NOT NULL DEFAULT 1,
    hash_arquivo      VARCHAR(64) NOT NULL,
    caminho_pdf       TEXT NOT NULL,
    situacao_vigencia BOOLEAN NOT NULL DEFAULT TRUE,
    data_upload       TIMESTAMPTZ DEFAULT now(),
    UNIQUE (hash_arquivo)
);

CREATE TABLE IF NOT EXISTS pagina (
    id_pagina              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_versao              INT NOT NULL REFERENCES versao_arquivo(id_versao) ON DELETE CASCADE,
    numero_pagina_pdf      INT NOT NULL,
    numero_pagina_impressa INT,
    conteudo_texto         TEXT NOT NULL,
    vetor_conteudo         VECTOR(768)
);

-- Coluna calculada pelo próprio banco: o texto da página já "picado" em radicais.
-- Antes, junta as palavras que o PDF quebrou no fim da linha ("vio-\nlência").
ALTER TABLE pagina ADD COLUMN IF NOT EXISTS busca_texto tsvector
    GENERATED ALWAYS AS (
        to_tsvector('pt_sem_acento',
                    regexp_replace(conteudo_texto, '(\w)-\s*\n\s*(\w)', '\1\2', 'g'))
    ) STORED;

-- Índice HNSW: busca por significado (similaridade de cosseno entre vetores).
CREATE INDEX IF NOT EXISTS idx_pagina_vetor
    ON pagina USING hnsw (vetor_conteudo vector_cosine_ops);
-- Segunda coluna de vetores: para trocar o modelo de embedding sem desligar a busca.
-- reindexar.py preenche; depois o .env aponta COLUNA_VETOR=vetor_conteudo_2.
ALTER TABLE pagina ADD COLUMN IF NOT EXISTS vetor_conteudo_2 VECTOR(768);
CREATE INDEX IF NOT EXISTS idx_pagina_vetor_2
    ON pagina USING hnsw (vetor_conteudo_2 vector_cosine_ops);
-- Índice GIN: busca por palavra (o "índice remissivo" do acervo).
CREATE INDEX IF NOT EXISTS idx_pagina_busca_texto
    ON pagina USING gin (busca_texto);
CREATE INDEX IF NOT EXISTS idx_pagina_versao ON pagina (id_versao);

-- ============ FASE 2 DO MODELO LÓGICO: classificação e leis ============
-- Tabelas que estavam no MER/lógico da Entrega 2 e entraram no banco em 20/10/2026.
-- Nomes de chave no padrão do físico (id_<x>; no lógico, codigo_<x>).

-- Relacionamento "substitui" (PUBLICACAO 0,1 – 0,1): a edição nova aponta para a anterior.
-- UNIQUE garante o (0,1) do outro lado: uma edição só é substituída por uma.
ALTER TABLE publicacao ADD COLUMN IF NOT EXISTS id_publicacao_anterior INT
    UNIQUE REFERENCES publicacao(id_publicacao);

-- RF-N01 e datas da PUBLICACAO que estavam no lógico e faltavam aqui (09/11/2026).
--   data_apareceu_site: quando a obra apareceu no site do CFP (fecha o RF-N01)
--   data_obra: data da edição impressa na obra
--   data_conferencia_fonte: última vez que se conferiu a obra na fonte oficial
ALTER TABLE publicacao ADD COLUMN IF NOT EXISTS data_apareceu_site DATE;
ALTER TABLE publicacao ADD COLUMN IF NOT EXISTS data_obra DATE;
ALTER TABLE publicacao ADD COLUMN IF NOT EXISTS data_conferencia_fonte TIMESTAMPTZ;
-- Até hoje a única conferência foi baixar o PDF do site oficial: vale a data do upload.
UPDATE publicacao p
   SET data_conferencia_fonte = COALESCE(
        (SELECT min(v.data_upload) FROM versao_arquivo v WHERE v.id_publicacao = p.id_publicacao), now())
 WHERE p.data_conferencia_fonte IS NULL;
ALTER TABLE publicacao ALTER COLUMN data_conferencia_fonte SET DEFAULT now();
ALTER TABLE publicacao ALTER COLUMN data_conferencia_fonte SET NOT NULL;

CREATE TABLE IF NOT EXISTS categoria_fonte (
    id_categoria   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_categoria VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS eixo_tematico (
    id_eixo   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nome_eixo VARCHAR(80) NOT NULL UNIQUE
);

-- classifica (PUBLICACAO N:N CATEGORIA_FONTE)
CREATE TABLE IF NOT EXISTS publicacao_categoria (
    id_publicacao INT REFERENCES publicacao(id_publicacao) ON DELETE CASCADE,
    id_categoria  INT REFERENCES categoria_fonte(id_categoria),
    PRIMARY KEY (id_publicacao, id_categoria)
);

-- aborda (PUBLICACAO N:N EIXO_TEMATICO): quem classificou é atributo do VÍNCULO.
CREATE TABLE IF NOT EXISTS publicacao_eixo (
    id_publicacao        INT REFERENCES publicacao(id_publicacao) ON DELETE CASCADE,
    id_eixo              INT REFERENCES eixo_tematico(id_eixo),
    origem_classificacao VARCHAR(10) NOT NULL DEFAULT 'IA'
                         CHECK (origem_classificacao IN ('IA', 'Curador')),
    PRIMARY KEY (id_publicacao, id_eixo)
);

CREATE TABLE IF NOT EXISTS lei (
    id_lei            INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_lei        VARCHAR(12) NOT NULL UNIQUE,   -- "11.340"
    ano               SMALLINT,
    nome_popular      VARCHAR(120),                  -- "Lei Maria da Penha" (físico: ajuda a busca)
    ementa            TEXT,
    situacao_vigencia BOOLEAN NOT NULL DEFAULT TRUE,
    url_fonte_oficial TEXT
);

-- citada_em (PAGINA N:N LEI): preenchida lendo o texto das páginas (curadoria.py).
CREATE TABLE IF NOT EXISTS pagina_lei (
    id_pagina INT REFERENCES pagina(id_pagina) ON DELETE CASCADE,
    id_lei    INT REFERENCES lei(id_lei) ON DELETE CASCADE,
    PRIMARY KEY (id_pagina, id_lei)
);
CREATE INDEX IF NOT EXISTS idx_pagina_lei_lei ON pagina_lei (id_lei);

-- ============ VOCABULÁRIO CONTROLADO ============
-- Um CONCEITO (ex.: "violência") reúne TERMOs equivalentes ("agressão",
-- "maus-tratos"). Quem pesquisa "agressão" também acha páginas que dizem "violência".

CREATE TABLE IF NOT EXISTS conceito (
    id_conceito      INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    termo_preferido  VARCHAR(120) NOT NULL UNIQUE,
    nota             TEXT
);

CREATE TABLE IF NOT EXISTS termo (
    id_termo     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_conceito  INT NOT NULL REFERENCES conceito(id_conceito) ON DELETE CASCADE,
    texto        VARCHAR(120) NOT NULL UNIQUE,
    -- Radicais do termo, para casar com a consulta sem depender de acento/plural.
    lexemas      tsvector GENERATED ALWAYS AS (to_tsvector('pt_sem_acento', texto)) STORED
);

-- ============ USO ============

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario  INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    login       VARCHAR(60) NOT NULL UNIQUE,
    nome        VARCHAR(120),
    hash_senha  TEXT NOT NULL,          -- scrypt com sal; a senha em si nunca é gravada
    ativo       BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Administrador vê o medidor de uso (/uso). O uso dele não entra na contagem.
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS admin BOOLEAN NOT NULL DEFAULT FALSE;

-- Atributos do USUARIO no lógico (RF-N09: perfil) que faltavam aqui (09/11/2026).
-- No lógico a chave de negócio é o e-mail; no físico a pessoa entra com um login, e o
-- e-mail fica UNIQUE mas opcional (a conta de teste compartilhada não tem e-mail).
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE;
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS perfil VARCHAR(50) NOT NULL DEFAULT 'Estudante'
    CHECK (perfil IN ('Estudante', 'Profissional', 'Curador', 'Gestor', 'Encarregado_LGPD'));
ALTER TABLE usuario ADD COLUMN IF NOT EXISTS municipio VARCHAR(255);
UPDATE usuario SET perfil = 'Gestor' WHERE admin AND perfil = 'Estudante';

CREATE TABLE IF NOT EXISTS registro_consulta (
    id_consulta INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pergunta    TEXT NOT NULL,
    resposta    TEXT,
    criado_em   TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE registro_consulta
    ADD COLUMN IF NOT EXISTS id_usuario INT REFERENCES usuario(id_usuario);
ALTER TABLE registro_consulta
    ADD COLUMN IF NOT EXISTS modo VARCHAR(10) NOT NULL DEFAULT 'perguntar';
-- LGPD (RN-N05 / Decisão 1 da Entrega 2): a busca de uma pessoa é dado pessoal, então
-- o registro declara para que serve e até quando fica. Passado o prazo, a rotina
-- diária (deploy/backup.sh) apaga.
ALTER TABLE registro_consulta
    ADD COLUMN IF NOT EXISTS finalidade VARCHAR(60) NOT NULL DEFAULT 'métrica de uso';
ALTER TABLE registro_consulta
    ADD COLUMN IF NOT EXISTS prazo_guarda DATE NOT NULL
        DEFAULT (CURRENT_DATE + INTERVAL '12 months')::date;
CREATE INDEX IF NOT EXISTS idx_consulta_prazo ON registro_consulta (prazo_guarda);

-- Nomes que mudaram do lógico para o físico (o banco guarda a correspondência).
COMMENT ON COLUMN registro_consulta.pergunta IS
    'Lógico: termo_buscado. Guarda o termo da busca ou a pergunta à IA (ver modo).';
COMMENT ON COLUMN registro_consulta.criado_em IS 'Lógico: data_hora.';
COMMENT ON COLUMN registro_consulta.modo IS
    'Só no físico: buscar (busca por palavra) ou perguntar (pergunta à IA).';
COMMENT ON COLUMN registro_consulta.resposta IS 'Só no físico: texto da resposta da IA.';
COMMENT ON COLUMN usuario.login IS 'Só no físico: nome de entrada (o lógico identifica por email).';
COMMENT ON COLUMN versao_arquivo.caminho_pdf IS
    'Só no físico: onde o PDF está no disco (saiu do conceitual na devolutiva).';

-- Liga cada RESPOSTA DA IA às páginas que a fundamentaram (auditoria da resposta).
-- Busca simples não grava aqui: métrica de uso se faz por contagem, sem o rastro de
-- quais páginas cada pessoa viu (Decisão 1 da Entrega 2).
CREATE TABLE IF NOT EXISTS cita_pagina (
    id_consulta  INT REFERENCES registro_consulta(id_consulta) ON DELETE CASCADE,
    id_pagina    INT REFERENCES pagina(id_pagina),
    similaridade REAL,
    PRIMARY KEY (id_consulta, id_pagina)
);

-- ============ AVALIAÇÃO DAS RESPOSTAS (👍/👎) ============
-- Uma por resposta da IA. Mostra ONDE a Susmi erra, em vez de "tive reclamação".
-- Some junto com a consulta quando o prazo de guarda dela vence (LGPD, ON DELETE CASCADE).
CREATE TABLE IF NOT EXISTS avaliacao_resposta (
    id_consulta INT PRIMARY KEY REFERENCES registro_consulta(id_consulta) ON DELETE CASCADE,
    util        BOOLEAN NOT NULL,
    comentario  VARCHAR(500),
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ DESEMPENHO DA IA ============
-- Tempo e velocidade de cada resposta da Susmi, para o painel do administrador (/uso):
-- quanto esperou na fila, quando apareceu a 1ª palavra, quanto levou ao todo. Sem texto
-- e sem pessoa; some junto com a consulta quando o prazo de guarda dela vence.
CREATE TABLE IF NOT EXISTS metrica_resposta (
    id_consulta        INT PRIMARY KEY REFERENCES registro_consulta(id_consulta) ON DELETE CASCADE,
    modelo             VARCHAR(80),
    guardada           BOOLEAN NOT NULL DEFAULT FALSE,  -- saiu de resposta_guardada (sem IA)
    espera_ms          INT,     -- na fila, esperando vaga na IA
    primeira_ms        INT,     -- do pedido até a 1ª palavra na tela
    total_ms           INT,     -- do pedido até o fim
    tokens_lidos       INT,     -- tamanho do contexto que a IA leu
    leitura_ms         INT,     -- tempo que a IA levou lendo
    tokens             INT,     -- tamanho da resposta
    tokens_por_segundo REAL,    -- velocidade de escrita
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_metrica_resposta_data ON metrica_resposta (criado_em);

-- ============ RESPOSTAS GUARDADAS ============
-- Mesma pergunta sobre as mesmas páginas, com o mesmo modelo, sai na hora em vez de ~90 s.
-- A chave é o hash (modelo + instruções + texto inteiro do prompt): mudou qualquer coisa,
-- vira outra chave. Não guarda a pergunta nem quem perguntou. Vale 30 dias (backup.sh).
CREATE TABLE IF NOT EXISTS resposta_guardada (
    chave     CHAR(64) PRIMARY KEY,
    resposta  TEXT NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============ MEDIDOR DE USO ============
-- Uma linha por ação, para saber SE e QUANTO o portal é usado. Não guarda IP nem
-- texto. "sessao" é um apelido anônimo de cada login (12 letras do hash do cookie):
-- serve só para contar aparelhos distintos, não identifica a pessoa.
CREATE TABLE IF NOT EXISTS evento_uso (
    id_evento     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    tipo          VARCHAR(12) NOT NULL
                  CHECK (tipo IN ('login', 'tela', 'busca', 'pergunta', 'pdf')),
    sessao        CHAR(12),
    id_publicacao INT REFERENCES publicacao(id_publicacao) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_evento_uso_data ON evento_uso (criado_em);

-- Primeira vez: traz as buscas e perguntas que já estavam no histórico (sem sessão).
INSERT INTO evento_uso (criado_em, tipo)
SELECT r.criado_em, CASE r.modo WHEN 'buscar' THEN 'busca' ELSE 'pergunta' END
FROM registro_consulta r JOIN usuario u USING (id_usuario)
WHERE r.criado_em IS NOT NULL AND NOT u.admin
  AND NOT EXISTS (SELECT 1 FROM evento_uso);
