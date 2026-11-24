# Engenharia reversa do NotebookLM → Portal CREPOP

> Objetivo: entender **como o NotebookLM funciona** (produto, UX e arquitetura) para
> construir o nosso sistema com a **nossa cara**, o nosso domínio (acervo de Psicologia
> do CREPOP) e as **nossas funcionalidades** — sem copiar, e rodando **100% local**.

---

## 1. A essência (o que o NotebookLM realmente é)

NotebookLM (Google Labs, movido a Gemini) não é um chatbot genérico. É um
**assistente de pesquisa ancorado em fontes** (*source-grounded*). A regra de ouro:

> A IA responde **somente** com base nas fontes que você forneceu, e **cita de onde
> tirou cada afirmação**. Se não está nas fontes, ela não inventa.

Isso é exatamente o pilar 1 da nossa especificação ("RAG estrito, citando edição e
página"). Ou seja: o NotebookLM é a prova de produto de que a nossa ideia funciona —
só que genérico e na nuvem. O nosso é especializado e privado.

---

## 2. Modelo conceitual do NotebookLM

| Entidade | O que é | Equivalente no nosso modelo |
|---|---|---|
| **Notebook** | Espaço de trabalho que agrupa fontes sobre um tema | (novo) `CADERNO`/coleção — hoje temos o acervo único; vira recorte por usuário/tema na fase 2 |
| **Source** (fonte) | Documento ingerido (PDF, Doc, URL, YouTube, texto colado) | `PUBLICACAO` + `VERSAO_ARQUIVO` |
| **Chunk** | Pedaço do documento, vetorizado para busca | `PAGINA` (no nosso caso, 1 página = 1 chunk) |
| **Chat / resposta** | Pergunta e resposta ancorada | `REGISTRO_CONSULTA` |
| **Citation** (citação) | Link da afirmação → trecho exato da fonte | `cita_pagina` (consulta N:N página) |
| **Note** | Resposta salva / anotação do usuário | (fase 2) `AVISO_CURADORIA` / notas |
| **Studio output** | Áudio, resumo, mapa mental gerados | (fase 2+) saídas derivadas |

**Leitura importante:** o nosso MER enxuto **já cobre o núcleo** do NotebookLM
(fonte → página → citação). O que o NotebookLM tem a mais são as *saídas de estúdio*
e os tipos variados de fonte — tudo fase 2+.

---

## 3. As três camadas de UX (o layout que faz sentido copiar na ESTRUTURA, não no visual)

O NotebookLM organiza a tela em **três painéis**, e essa divisão é ótima porque separa
"o que eu li", "a conversa" e "o que eu produzi":

```
┌─────────────┬────────────────────────┬─────────────────┐
│   FONTES    │        CHAT            │   ESTÚDIO/NOTAS │
│ (esquerda)  │      (centro)          │   (direita)     │
│             │                        │                 │
│ lista de    │ perguntas e respostas  │ saídas geradas  │
│ documentos, │ com citações clicáveis │ (resumo, áudio, │
│ seleção de  │ [1][2] → abre a fonte  │ guia, mapa) e   │
│ quais usar  │ na passagem exata      │ notas salvas    │
└─────────────┴────────────────────────┴─────────────────┘
```

**O que adotamos da estrutura:** os três painéis. **O que é nossa cara:** no nosso, o
painel direito não é "estúdio de podcast" — é o **leitor de PDF** que abre na página
citada (split-screen pergunta↔documento), que é o coração acadêmico do nosso produto.

---

## 4. O pipeline RAG por dentro (inferido, e como fazemos o nosso)

O NotebookLM não publica a arquitetura, mas o fluxo é o padrão de um RAG maduro. Abaixo,
o deles (inferido) e o **nosso já implementado** na fatia 1:

**Ingestão (quando você adiciona uma fonte):**
1. Parse do documento → texto + estrutura (páginas). → *nós: `pdfplumber`, texto por página*
2. Chunking (quebra em pedaços com sobreposição). → *nós: 1 página = 1 chunk (casa com citação por página)*
3. Embedding de cada chunk. → *nós: `nomic-embed-text`, vetor 768*
4. Armazenar no índice vetorial. → *nós: Postgres + pgvector (HNSW, cosseno)*

**Consulta (quando você pergunta):**
5. Embedding da pergunta. → *nós: idem*
6. Busca dos k trechos mais próximos (+ rerank no NotebookLM). → *nós: `ORDER BY vetor <=> pergunta LIMIT k`*
7. Montar prompt: instrução + trechos + pergunta. → *nós: `rag.PROMPT_BASE`, estrito*
8. LLM gera a resposta **marcando quais trechos usou**. → *nós: `qwen2.5:7b` local*
9. Renderizar com citações clicáveis. → *nós: `cita_pagina` + (fase front) link para a página*

**Diferença-chave de infra:** NotebookLM = Gemini na nuvem (rápido, mas manda seus
dados para fora). Nós = Ollama na VM do LARCC (privado/LGPD, porém **~4,3 tokens/s** em
CPU — ver seção 11).

---

## 5. O recurso que faz tudo funcionar: a citação rastreável

É o detalhe que separa "chatbot que alucina" de "assistente confiável". No NotebookLM,
cada afirmação tem um número `[1]` que abre o trecho exato. Para reproduzir:

- Guardar, para cada resposta, **quais chunks** entraram no contexto (nós: `cita_pagina`).
- Pedir ao modelo, no prompt, que **cite a origem** (nós: formato `[p. N]`).
- No front, transformar `[p. N]` em link → **abrir o PDF naquela página**.

**Nossa vantagem sobre o NotebookLM aqui:** além da página do PDF, modelamos a
**página impressa** (`numero_pagina_impressa`) — citação acadêmica correta — e o
**link para a fonte oficial** (CFP/Planalto). O NotebookLM não faz citação acadêmica
formal nem distingue edição vigente.

---

## 6. As "saídas de estúdio" do NotebookLM (o que é e o que faremos)

| Saída do NotebookLM | O que é | Nossa decisão |
|---|---|---|
| **Audio Overview** | "Podcast" com 2 vozes de IA discutindo as fontes | Adiar (fase 3). Chamativo, mas secundário para estudo técnico |
| **Video Overview** | Vídeo-resumo narrado | Adiar / provavelmente não |
| **Mind map** | Mapa mental dos temas das fontes | Fase 2 — útil para navegar o acervo por eixo temático |
| **Study guide** | Guia de estudo (perguntas, termos) | Fase 2 — ótimo para alunos de Psicologia |
| **Briefing / Report** | Resumo executivo das fontes | Fase 2 |
| **FAQ / Timeline** | Perguntas frequentes / linha do tempo | Avaliar |

Nenhuma dessas é necessária para o MVP. O MVP é **perguntar e receber resposta citada**.

---

## 7. NotebookLM → Portal CREPOP: manter / mudar / adicionar / adiar

| Aspecto | NotebookLM | Portal CREPOP (nosso) |
|---|---|---|
| Ancoragem em fontes | ✅ núcleo | ✅ **manter** (é a razão de existir) |
| Citação clicável | ✅ trecho | ✅ **manter e melhorar**: página PDF **+ página impressa** + link oficial |
| Layout 3 painéis | ✅ | ✅ **manter a estrutura**, visual nosso; painel direito = **leitor de PDF** |
| Onde roda | ☁️ nuvem (Gemini) | 🔒 **mudar**: 100% local (Ollama/VM), privacidade e LGPD |
| Domínio | genérico | 🎯 **mudar**: acervo técnico de Psicologia (CREPOP/CFP) |
| Versionamento de edição | ❌ não tem | ➕ **adicionar**: estilo GitHub (CAPS 2013 → 2022), "qual é a vigente" |
| Citação acadêmica | ❌ informal | ➕ **adicionar**: página impressa para referência |
| Auditoria / LGPD | ❌ | ➕ **adicionar**: log de consultas, bloqueio de dado de paciente |
| Coleções/eixos temáticos | notebooks | ➕ **adaptar**: eixos (CAPS, CRAS, Sistema Prisional...) sobre um acervo comum |
| Audio/Video Overview | ✅ | ⏳ **adiar** (fase 3) |
| Tipos de fonte (YouTube, URL...) | ✅ muitos | ⏳ só PDF no MVP; URL/colar depois |

---

## 8. Nossas funcionalidades próprias (os diferenciais que o NotebookLM não tem)

1. **Privacidade institucional (LGPD):** roda na infraestrutura do LARCC/SETREM, nada
   sai para a nuvem; validação que **bloqueia dados de pacientes** na pergunta.
2. **Versionamento de edições (releases):** o acervo evolui; a edição antiga não some,
   é marcada como não-vigente e vinculada à nova. "Mostre-me a versão vigente."
3. **Dupla paginação:** página do PDF (para o leitor) e página impressa (para citar em
   trabalho acadêmico).
4. **Links para a fonte oficial:** toda publicação aponta para o CFP/CREPOP ou Planalto.
5. **Navegação por eixo temático:** o acervo CREPOP já é organizado por tema (CAPS,
   CRAS/SUAS, Sistema Prisional, Álcool e Drogas, Povos Indígenas, etc.) — vira filtro.
6. **Auditabilidade:** toda consulta registrada (quem, quando, quais páginas) — pesquisa
   e prestação de contas.

---

## 9. Blueprint de UX/IA do nosso portal (a nossa cara)

Estrutura de telas (identidade visual — cores/tipografia — a definir num passo de design):

- **Tela principal (3 painéis):**
  - *Esquerda — Acervo:* busca + lista por eixo temático; selo de **edição vigente**;
    filtro por ano/tipo (RT, Seminário, Lei).
  - *Centro — Consulta:* campo de pergunta, histórico, respostas com citações `[p. N]`
    clicáveis; aviso de privacidade (não insira dados de paciente).
  - *Direita — Leitor:* PDF.js abrindo **na página citada**, com a página impressa
    destacada para citação.
- **Tela de ingestão/curadoria (restrita):** subir PDF, preencher metadados (título,
  tipo, fonte, edição, link oficial), marcar substituição de edição.
- **Identidade:** sóbria e acadêmica, acessível (WCAG AA), responsiva. Definir paleta,
  logotipo e tom — "portal de referência técnica", não "produto de startup".

---

## 10. Arquitetura técnica do nosso sistema (local)

```
Navegador (React + Tailwind, split-screen, PDF.js)
        │  HTTP/JSON (+ SSE para streaming da resposta)
        ▼
FastAPI (Python)  ── ingest.py / rag.py
        │                     │
        ▼                     ▼
Postgres + pgvector     Ollama (local, CPU)
 (páginas + vetores)     qwen2.5:7b  +  nomic-embed-text
```

Tudo na VM do LARCC. O front pode ser servido pela porta 80 → acessível em
`http://138.94.76.170:22233`. Já implementado: ingestão e `/perguntar` com citação.
Falta: streaming (SSE), front-end, versionamento na UI, auth/auditoria.

---

## 11. Riscos e limitações honestas

- **Velocidade:** ~4,3 tokens/s em CPU. Resposta de um parágrafo ≈ 45s. O NotebookLM
  responde em segundos porque usa GPU na nuvem. Mitigações: streaming (a resposta vai
  aparecendo), modelo 3B para fluidez, respostas mais curtas, cache de perguntas comuns.
- **Qualidade do modelo local < Gemini:** o 7B erra mais que o Gemini. O RAG estrito
  (responder só do acervo) reduz muito a alucinação, que é o risco maior.
- **Sem GPU:** embeddings de milhares de páginas levam tempo (ingestão é um job de
  fundo, não interativo).
- **Disco da VM pode falhar** (aviso do LARCC): backup do banco e dos PDFs.

---

## 12. Roadmap sugerido

- **Fase 1 (MVP — em andamento):** ingestão dos 41 PDFs + `/perguntar` com citação. *(feito o backend; ingerindo o acervo)*
- **Fase 2 (produto usável):** front 3 painéis + leitor de PDF na página citada +
  streaming + filtro por eixo temático + login e auditoria.
- **Fase 3 (diferenciais):** versionamento de edições na UI, página impressa nas
  citações, saídas de estúdio (resumo/guia/mapa), e só então avaliar áudio.
