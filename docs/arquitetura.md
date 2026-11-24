# Arquitetura do Acervo Psico

## Visão geral

```
                         Navegador (tela: app/backend/static/index.html)
                                         │  HTTP
                                         ▼
  Internet ─► LARCC 138.94.76.170:22233 ─► VM :80  nginx (limites, cabeçalhos)
                                                     │
                                                     ▼  127.0.0.1:8000
                                     FastAPI (app/backend/main.py) — login, rotas
                                      │                │                  │
                         busca híbrida│      PDF + PDF.js│                  │ pergunta
                                      ▼                ▼                  ▼
                   PostgreSQL 16 + pgvector     /opt/crepop/dados    Ollama (IA local)
                   (Docker, 127.0.0.1:5432)      (41 PDFs)            embeddinggemma (vetores)
                   papel restrito acervo_app                          modelo de linguagem (respostas)
```

Tudo roda na mesma VM (Ubuntu, 3 vCPUs, 12 GB de RAM, **sem GPU**). Só a porta 80
fica aberta para fora; banco, IA e app escutam apenas em `127.0.0.1`.

## Ingestão (uma vez, pela linha de comando na VM)

```
PDF ─ pdfplumber ─► texto de cada página ─► embeddinggemma ─► vetor (768 números)
                                     └──────► INSERT em pagina (texto + vetor)
                                               └► o banco calcula busca_texto sozinho
```

`app/backend/ingest_all.py` lê a pasta do acervo. Uma página do PDF = uma linha em
`pagina`, o que permite citar a página exata. O hash do arquivo impede ingerir o mesmo
PDF duas vezes. Os 41 PDFs levaram cerca de 3 h (4 a 5 min por PDF, em CPU).

## Buscar (instantâneo, ~0,2 s)

A busca combina **dois jeitos de procurar** e junta as listas:

```
"agressão contra mulher"
   │
   ├─► 1. POR SENTIDO   embedding da frase ──► pgvector (HNSW, cosseno) ──► 40 páginas
   │
   ├─► 2. POR PALAVRA   vocabulário controlado expande a frase:
   │                    (agressão | violência | maus-tratos | violento) & (mulher | feminino)
   │                    ──► busca textual em português (GIN) ──► 40 páginas
   │
   └─► 3. JUNTA         Reciprocal Rank Fusion: nota = Σ 1/(60 + posição em cada lista)
                        ──► 10 melhores ──► ts_headline grifa os trechos
```

- **Por que dois jeitos?** O embedding entende o assunto ("agressão" fica perto de
  "violência"), mas não sabe dizer *quais palavras* da página casaram. A busca por
  palavra sabe grifar, mas não entende sinônimo sozinha. O vocabulário controlado faz a
  ponte e a fusão aproveita o melhor das duas.
- **Configuração `pt_sem_acento`** (no `schema.sql`): dicionário português do Postgres +
  `unaccent`. "violencia" acha "violência"; "mulheres" e "mulher" viram o mesmo radical.
- **Páginas "mesmo assunto"**: achadas só pelo sentido (não têm as palavras). A tela
  marca com esse selo, para a pessoa entender por que apareceram.
- **Limitação conhecida**: o radical do português junta palavras diferentes às vezes
  ("luto" e "luta" viram `lut`). O vocabulário controlado e a busca por sentido compensam
  em parte.

## Leitor com grifo

O clique abre o PDF no **PDF.js** (Mozilla, servido pela própria VM) dentro da página.
A tela comanda o leitor: vai para a página citada e manda grifar as palavras que a busca
achou **naquela página** (expressões inteiras, como "Lei Maria da Penha", e palavras
soltas). Amarelo é o que foi digitado, verde é o equivalente; ▲▼ passam pelas ocorrências.

## Perguntar à IA (RAG)

```
pergunta ─► mesma busca híbrida ─► 3 páginas ─► trecho relevante de cada (~1.500 caracteres)
        ─► prompt: "[p. N] (fonte)" trecho … + pergunta
        ─► já existe em resposta_guardada? sai na hora (78 s → 1 s), sem entrar na fila
        ─► senão: modelo "acervo-psico" (Ollama) ─► resposta em streaming, citando [p. N]
        ─► grava em registro_consulta + cita_pagina (auditoria)
        ─► na tela: marca d'água "GERADO POR IA", aviso para conferir na fonte e 👍/👎
```

- **Respostas guardadas** (`resposta_guardada`): a chave é o hash de modelo + instruções +
  prompt inteiro; mudou qualquer coisa, a resposta antiga deixa de valer. Não guarda a
  pergunta nem quem perguntou; o `backup.sh` apaga as de mais de 30 dias.
- **👍/👎** (`POST /avaliar` → `avaliacao_resposta`): uma avaliação por resposta, só de quem
  perguntou; o comentário passa pelo mesmo filtro de nome/CPF. O painel `/uso` mostra os
  últimos 👎, para saber **onde** a Susmi erra.
- **Marca d'água**: toda resposta escrita pela IA leva "GERADO POR IA" ao fundo e o aviso
  "Resposta gerada por inteligência artificial. Ela pode cometer erros: confira sempre nas
  páginas citadas antes de usar." (`static/index.html`).

Três jeitos de perguntar, do mais rápido ao mais amplo:

| Botão | A IA lê | Por quê é rápido |
|---|---|---|
| **Explicar** (em cada resultado da busca) | 1 página | contexto pequeno |
| **Perguntar à IA sobre estas páginas** (fim da busca) | as 3 primeiras | começa a ler **enquanto a pessoa digita** (`/preparar`) e, como o contexto é sempre o mesmo, o Ollama **reaproveita a leitura** nas perguntas seguintes |
| **Perguntar à IA** (livre) | as 3 páginas que a busca achar | — |

Medido (qwen2.5:3b, mesmas 3 páginas): 1ª pergunta leu em 40,6 s; a 2ª e a 3ª, em
**1,9 s** e **1,8 s** (resposta completa em 9 s e 3 s), graças ao cache de prompt do
Ollama/llama.cpp, que reaproveita o começo idêntico do texto.

### Atualização de 03/11/2026

Resumo para quem não é da área técnica, com antes e depois e como voltar atrás:
[atualizacao-2026-11-03.md](atualizacao-2026-11-03.md).

- **Modelo**: disputa entre Gemma 3 4B, Gemma 4 E4B/E2B e Qwen 3.5 4B (normal e MTP), com
  15 perguntas (4 delas reais das alunas). Todo o processo, os números e a decisão estão
  em [escolha-do-modelo-ia.md](escolha-do-modelo-ia.md). Partiu da ideia do Colibrì
  (modelos MoE lidos do disco), que não cabe nesta VM; o que se aproveitou foi escolher
  pelo número de parâmetros ativos.
- **IA aquecida**: ao subir, o app manda a IA ler as instruções fixas, e o modelo nunca sai
  da memória (`keep_alive = -1`). Antes, a 1ª pergunta pagava ~1 min só para ler as regras.
  Para o Gemma reaproveitar essa leitura entre perguntas diferentes, o Ollama roda com
  `LLAMA_ARG_SWA_FULL=1`: sem isso, a janela deslizante do modelo (512 tokens) fazia o
  llama.cpp reler tudo a cada pergunta. Resultado: "Qual o papel do psicólogo no CAPS?"
  passou de **179 s** (manhã de 03/11, Gemma 3) para **~100 s**.
- **Texto longo** (`rag.eh_pedido_longo`): "desenvolva um artigo", "resumo expandido",
  "escreva um texto sobre…" leem 4 páginas e podem escrever até 1.400 tokens, em seções.
- **Citar em ABNT**: cada página tem `numero_pagina_impressa`, calculada pelo
  `paginacao.py` a partir do número no rodapé (5.210 de 5.551 páginas, 94%; em obra
  escaneada em página dupla, "p. 36-37"). A referência de cada obra vem da ficha catalográfica
  (`referencias.py`). Na tela: botão **Citar** e **Copiar com referências (ABNT)**, que troca
  `[p. N]` por "(CONSELHO FEDERAL DE PSICOLOGIA, 2019, p. 43)" e lista as referências no fim.
- **Ano certo**: o "2022" do nome dos arquivos era o ano do download; a tela mostra o ano de
  publicação da ficha (ex.: CAPS 2013 e CAPS 2022, ed. rev.).
- **Métricas** (`metrica_resposta`): tempo na fila, até a 1ª palavra e total, velocidade de
  leitura e de escrita de cada resposta. O painel `/uso` mostra isso e a saúde do servidor.
- **Busca por sentido com `embeddinggemma`** (multilíngue, no lugar do `nomic-embed-text`,
  treinado em inglês). Detalhes e a comparação logo abaixo.
- **Mapa do acervo** (`mapa.py`): ver a seção própria, abaixo.
- **Respostas prontas de madrugada** (`pre_responder.py`): ver abaixo.

#### Busca por sentido: `nomic-embed-text` → `embeddinggemma` (03/11/2026)

Os vetores novos foram calculados na coluna `vetor_conteudo_2` com a busca no ar
(`reindexar.py`, 5.551 páginas em 175 min de CPU). Antes de trocar, as mesmas 15 consultas
rodaram nos dois modelos e as 6 primeiras páginas de cada um foram comparadas à mão:

| Consulta | Melhor | Por quê |
|---|---|---|
| ansiedade na juventude | **novo** | traz adolescência e saúde mental infantojuvenil; o antigo, esporte e quilombolas |
| me explique ansiedade | empate | os dois fracos: o acervo quase não fala de ansiedade em si |
| como lidar com o luto | **novo** | 6 de 6 páginas sobre luto (Emergências, Direitos Sexuais, Idosos); o antigo, 3 |
| agressão contra mulher | empate | os dois só com Mulheres em Violência |
| pessoa idosa abandonada pela família | **novo** | 5 de 6 de Pessoas Idosas; o antigo, nenhuma |
| criança vítima de abuso | **novo** | 6 de 6 de Violência Sexual Infantojuvenil; o antigo misturou Varas de Família |
| sofrimento no trabalho | **novo** | 4 páginas de Saúde do Trabalhador; o antigo, 1 |
| risco de suicídio | empate | os dois acham a página de fatores de risco em idosos |
| dependência química | **novo** | Álcool e Drogas e CAPS; o antigo trouxe glossário previdenciário e quilombolas |
| preconceito racial | empate | os dois só com Relações Raciais |
| atendimento a pessoas trans | **novo** | 5 de 6 do LGBTQIA+ (processo transexualizador, documentos) |
| acolhimento depois de enchente | empate | os dois falham: nenhum acha Emergências e Desastres (a busca por palavra compensa) |
| bullying na escola | empate | os dois com Educação Básica |
| pessoas morando na rua | empate | os dois com População de Rua |
| objetivo do crepop | empate | os dois com as apresentações do CREPOP |

Placar: **8 melhores, 7 empates, nenhuma pior**. A troca está no `config.py` e no `.env` da VM
(`EMBED_MODEL=embeddinggemma`, `COLUNA_VETOR=vetor_conteudo_2`). A coluna antiga continua no
banco: para voltar, ponha `EMBED_MODEL=nomic-embed-text` e `COLUNA_VETOR=vetor_conteudo` no
`.env` e reinicie o app. O
`embeddinggemma` ocupa 0,65 GB de memória (o `nomic`, 0,3 GB) e saiu da memória.

#### Mapa do acervo (sempre na "ponta da língua")

Não dá para a Susmi ler o acervo inteiro a cada pergunta: são ~3 milhões de tokens, a janela
dela é de 8 mil e, nesta CPU, ler tudo levaria ~36 h. O que dá é deixar **sempre lido** um
resumo do acervo inteiro: o `mapa.py` monta (uma vez, ao subir o app, ~5 s) a lista das 41
obras com o ano e os assuntos de cada uma, e, para 43 temas (ansiedade, luto, suicídio,
violência sexual, racismo…), as 3 obras com mais páginas sobre o tema. São ~9 mil caracteres
(~2.500 tokens) que entram no **começo fixo** de todo prompt, junto das instruções; como esse
começo é sempre igual, a IA o lê uma vez só ao iniciar (aquecimento) e reaproveita em todas
as perguntas. Com isso a janela passou de 4.096 para 8.192 tokens.

Para que serve: a Susmi sabe **quais obras** existem e onde cada assunto está, e pode
indicar "veja também a Referência Técnica de Pessoas Idosas" quando as 3 páginas lidas não
bastam. O mapa avisa que **não é fonte**: ela só cita as páginas que leu.
Liga/desliga: `USAR_MAPA=false` no `.env`.

**Prova com mapa + `embeddinggemma`** (as mesmas 15 perguntas, `avaliar.py`, 03/11/2026):
**15/15** certas, média de **95 s** por pergunta (antes: 13/15 e 84 s). As duas perguntas de
ansiedade, que antes davam "Não encontrei", agora respondem com dados do acervo (pandemia,
saúde mental infantil), porque a busca nova acha as páginas certas. O custo: ~10 s a mais por
pergunta, porque as 3 páginas lidas agora vêm depois de ~2.500 tokens de mapa.

#### Respostas prontas de madrugada

Todo dia às 1h (cron em `/etc/cron.d/acervo-psico`), com a CPU parada, o `pre_responder.py`
faz as perguntas dos exemplos da tela e as perguntas reais que se repetiram nos últimos 60
dias, pelo mesmo caminho do site, e guarda as respostas em `resposta_guardada`. Quem clica
num exemplo recebe a resposta na hora. Só gera o que falta: mudou modelo, instruções, mapa ou
acervo, a chave muda e a resposta é refeita. Não entra no histórico de consultas. Log em
`/var/log/acervo-prontas.log`.

### O modelo: Gemma 3 4B "ensinado" por regras e exemplos (até 03/11/2026)

O modelo `acervo-psico` ([`ia/Modelfile`](../app/backend/ia/Modelfile)) é o **Gemma 3 4B**
(Google, aberto) com regras fixas e **três exemplos de resposta**: citar a página,
recusar o que não está no acervo e tratar dado de paciente. É o que dá para fazer numa VM
sem GPU; *fine-tuning* de verdade exigiria placa de vídeo e centenas de exemplos revisados.

Escolha feita com as 8 perguntas-teste ([`avaliar.py`](../app/backend/avaliar.py)), em 19/10/2026:

| Modelo base | Acertos | Tempo médio (sem cache) | Observação |
|---|---|---|---|
| qwen2.5:7b | — | > 5 min com 5 páginas | lento demais nesta CPU; removido |
| qwen2.5:3b | 4/8 | 69 s | citou o ano do título como página (`[p. 2025]`) |
| **gemma3:4b** | **5/8** | 84 s | melhor português e citações → **escolhido** |
| gemma3:4b + exemplos (19/10) | 7/8 | 99 s | acertou o caso do paciente e as citações; falta a pergunta do CRAS |
| gemma3:4b + exemplos + resposta completa + busca corrigida (20/10, tarde) | 8/8 | 114 s | respostas mais longas; CRAS resolvido na busca (ver abaixo) |
| + correções das conversas reais (20/10, noite) | 11/11 | 93 s | 3 perguntas novas tiradas das reclamações (lei das mulheres, psicodrama, "Quem é susmi?") |
| gemma3:4b, 15 perguntas (03/11) | 15/15 | 92 s | respostas curtas (mediana 168 tokens), escreve 5,3 tokens/s |
| **gemma4:e2b + correções (03/11, o de hoje)** | **13/15** | **84 s** | escreve 8 tokens/s, respostas completas; erra por cautela nas 2 de ansiedade ([escolha-do-modelo-ia.md](escolha-do-modelo-ia.md)) |

**O caso do CRAS** não era culpa do modelo, e sim da busca: ela exigia a palavra
"atua" e só achava o currículo de uma autora ("Atuou no CRAS…"), e páginas que eram
só um título ("EIXO 3: Atuação da Psicóloga no CREAS") ganhavam na busca por sentido.
Hoje "atua", "atuação" e "diz" não são exigidas e páginas com menos de 300 caracteres
(145 de 5.551) ficam fora da busca; as 3 páginas lidas passaram a ser do CRAS/SUAS.

### O que as conversas reais ensinaram (20/10/2026)

As 11 primeiras perguntas das colegas mostraram onde a Susmi errava. O que é crítico
foi garantido **no código**, porque um modelo de 4B não segue regra de forma confiável:

| Problema visto | Correção | Onde |
|---|---|---|
| A IA caiu às 15:01: o cache de leituras do `llama-server` (padrão 8 GB) estourou a RAM | `LLAMA_ARG_CACHE_RAM=1536` no serviço do Ollama | serviço do Ollama |
| "oi", "Quem é susmi?", "Qual meu nome?" viravam busca → "Não encontrei" | Conversa simples respondida na hora, sem IA | `conversa.py` |
| Pergunta longa: nenhuma página tem todas as palavras e a busca pegava qualquer uma | Nota por raridade (IDF²): "psicodrama" vale mais que "métodos" | `rag._nota_por_raridade` |
| "Lei que protege as mulheres", "existe alguma…": palavras de pergunta viravam obrigatórias | Mais palavras ignoradas + termos novos no vocabulário | `rag.VAZIAS_EXTRA`, `vocabulario.py` |
| Copiava os exemplos do Modelfile ("risco de suicídio [p. 88]") | Exemplos com rótulo próprio e páginas 997–999; frase que cita página não lida é apagada | `ia/Modelfile`, `rag.tirar_paginas_inventadas` |
| "Não encontrei…" grudado em resposta que tinha informação | Removido quando sobra conteúdo; recusa legítima fica | `rag.limpar_resposta` |
| Páginas escolhidas lidas só em parte (a resposta estava no fim da p. 117) | Página escolhida lida quase inteira (até 3.000 caracteres) | `rag._tamanho_janela` |
| Nome/CPF de paciente na pergunta | Mascarados antes da busca, da IA e do histórico; aviso sempre | `conversa.dados_pessoais` |
| Pergunta presa a 3 páginas sem relação | Botões "Usar acervo todo" e "Perguntar no acervo todo" | `static/index.html` |

Os exemplos subiram a nota de 5 para 7 e custaram ~15 s na 1ª pergunta (mais texto para
ler); perguntas seguintes sobre as mesmas páginas continuam saindo em segundos.

**Ciclo de melhoria:** cada dúvida real das colegas da Psicologia vira uma pergunta em
`ia/perguntas-teste.json`; muda-se o Modelfile, o vocabulário ou o contexto; roda-se
`avaliar.py`; a nota não pode cair. Dois erros achados assim no primeiro dia: o ano no
cabeçalho do trecho (agora o trecho começa com `[p. N]`, pronto para copiar) e CRAS/CREAS
tratados como sinônimos no vocabulário (agora são conceitos separados).

- **RAG estrito**: a IA só recebe as páginas do acervo e tem instrução fixa de não usar
  nada de fora e dizer "Não encontrei isso nas páginas consultadas" quando for o caso
  ([`ia/Modelfile`](../app/backend/ia/Modelfile)).
- **Streaming**: a tela recebe a resposta aos pedaços (NDJSON) e mostra enquanto a IA
  escreve, em vez de esperar tudo.
- **Duas por vez + fila**: a IA responde até 2 perguntas ao mesmo tempo
  (`IA_PARALELO` no app, `OLLAMA_NUM_PARALLEL=2` no Ollama). A API aceita até 6 entre
  respondendo e esperando, avisa a posição na tela e recusa o excesso com mensagem.
  Medido em 20/10/2026 com 2 perguntas simultâneas: na fila (1 por vez) a 1ª terminou
  em 87 s e a 2ª esperou parada até 152 s para começar; em paralelo as duas começaram
  em 116 s e terminaram em 145 s e 177 s. Com 3 núcleos o total não cai: o ganho é
  ninguém ficar parado sem ver nada.
- **Linha de pensamento**: enquanto a IA lê, a tela mostra os passos reais da busca
  (equivalências usadas, por que cada página foi escolhida) e o mesmo trecho que vai
  no prompt, "lido" palavra por palavra com os grifos. Nada é inventado pelo modelo
  (o Gemma 3 4B não tem modo de raciocínio): é o caminho que o sistema de fato fez.
  Quando a resposta começa, o painel se recolhe e fica para consulta.
- **Resposta completa**: o Modelfile pede uma frase direta e depois tópicos, cada um
  com a sua citação; teto de 900 tokens.
- **Modelo sempre carregado** (`keep_alive` 24 h): evita ~13 s de recarga do disco.
- **Avaliação**: [`avaliar.py`](../app/backend/avaliar.py) roda perguntas com resposta
  conhecida ([`ia/perguntas-teste.json`](../app/backend/ia/perguntas-teste.json)) e
  confere se a IA citou páginas que leu e se recusou o que está fora do acervo.

### Onde vai o tempo da IA (CPU, sem GPU)

| Etapa | Quanto | O que fizemos |
|---|---|---|
| Carregar o modelo do disco | ~6–13 s | Modelo fica na memória (`keep_alive` 24 h) |
| **Ler** o contexto (prompt) | **a maior parte** (~20 tokens/s) | 3 páginas em vez de 5; só o trecho relevante (1.500 caracteres); leitura antecipada; cache entre perguntas; linha de pensamento na tela |
| **Escrever** a resposta | ~5 tokens/s | Teto de 900 tokens; streaming, para a pessoa ler enquanto sai |

Antes de tudo isso, uma pergunta com o 7B e 5 páginas passou de 5 minutos e estourou o
tempo limite. Hoje: a 1ª pergunta começa a aparecer em ~40–60 s; perguntas seguintes
sobre as mesmas páginas, em poucos segundos.

## Arquivos do backend

| Arquivo | Papel |
|---|---|
| `main.py` | Rotas, login, middleware de segurança, streaming da pergunta |
| `rag.py` | Busca híbrida, vocabulário, grifos, montagem do prompt, histórico |
| `seguranca.py` | Hash de senha, cookie assinado, limites, fila da IA |
| `ollama_client.py` | Conversa com o Ollama (embeddings e geração) |
| `db.py` | Conexões: papel restrito (web) e administrador (scripts) |
| `schema.sql` | DDL idempotente (tabelas, índices, colunas calculadas) |
| `migrar.py` | Aplica o schema, o vocabulário e os privilégios |
| `vocabulario.py` | Os 45 conceitos e seus termos equivalentes |
| `ingest.py`, `ingest_all.py` | Ingestão dos PDFs |
| `criar_usuario.py` | Cria usuário / troca senha |
| `avaliar.py` | Avaliação da IA |
| `conversa.py` | Conversa simples sem IA ("oi", "quem é a Susmi?") e máscara de nome/CPF de paciente |
| `curadoria.py` | Fase 2: categoria, eixo temático, leis citadas e página impressa de cada página (roda no `migrar.py`) |
| `paginacao.py` | Descobre a página do LIVRO de cada página do PDF (número no rodapé; obras em página dupla) |
| `referencias.py` | Referência ABNT e ano de publicação de cada obra (das fichas catalográficas) |
| `embeddings.py` | Prefixo certo de pergunta/página para cada modelo de embedding; coluna de vetores em uso |
| `reindexar.py` | Recalcula os vetores com outro modelo de embedding numa coluna separada, sem parar a busca |
| `mapa.py` | Mapa do acervo (obras, assuntos e onde está cada tema) que fica sempre lido no começo do prompt |
| `pre_responder.py` | Respostas prontas de madrugada para os exemplos e as perguntas repetidas (cron, 1h) |
| `uso.py` | Medidor de uso, avaliações, desempenho da IA e saúde do servidor para o painel `/uso` |
| `config.py` | Parâmetros (limites, fila da IA, tamanhos de contexto) |
| `static/index.html`, `static/entrar.html` | A tela (HTML/CSS/JS puro, sem framework) |
| `static/uso.html` | Painel de uso (só admin) |
