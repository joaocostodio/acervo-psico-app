# Como o Acervo Psico foi feito, do zero ao sistema no ar

Este é o caminho completo, na ordem em que as coisas foram feitas, com as decisões, os
erros e como cada um foi resolvido. Serve de roteiro para quem vai montar um sistema
parecido: **siga as etapas, mas faça o seu**. A modelagem do banco (MER e lógico) não está
aqui: é a parte da disciplina e cada um faz a própria.

Linha do tempo resumida:

| Data | Marco |
|---|---|
| até 19/10/2026 | Ideia, especificação, modelagem do banco, VM do LARCC |
| 19/10 | Primeira versão no ar: ingestão, busca híbrida, leitor com grifo, IA local, login |
| 20/10 | Primeiro uso real pelas colegas da Psicologia → correções da IA, medidor de uso |
| 03/11 | Troca do modelo de IA, citação ABNT, busca por sentido melhor, respostas prontas |
| 09/11 | Segurança para apresentar com a turma inteira no mesmo Wi-Fi |
| 10/11 | Acervo ampliado (leis e normas), caderno de pesquisa, linha do tempo, fichas |
| 17/11 | Aviso de crise (CVV 188 / SAMU 192) em perguntas sobre suicídio |

---

## Etapa 0 — Entender o problema antes de programar

1. **Quem vai usar e para quê.** Aqui: estudantes de Psicologia que precisam achar, nas
   Referências Técnicas do CREPOP/CFP (PDFs de 100+ páginas cada), o trecho que fala do
   assunto delas, e **citar a página certa**.
2. **Inspiração.** O NotebookLM do Google faz isso, mas manda tudo para a nuvem. A ideia
   foi fazer um "NotebookLM próprio", 100% local. O estudo de como ele funciona está em
   [notebooklm-engenharia-reversa.md](notebooklm-engenharia-reversa.md).
3. **Requisitos por escrito.** Antes de qualquer código, uma lista de requisitos
   funcionais (buscar, abrir na página, perguntar, citar) e não funcionais (local, LGPD,
   rodar sem placa de vídeo). Tudo o que veio depois foi conferido contra essa lista.
4. **Restrições reais.** O servidor disponível era uma VM do LARCC: Ubuntu, 3 vCPUs,
   12 GB de RAM, **sem GPU**. Essa restrição decidiu quase tudo (modelo de IA, tamanho do
   contexto, cache).

> Dica: anote a restrição de hardware logo no começo. "Dá para rodar IA aqui?" muda a
> resposta de tudo.

## Etapa 1 — Modelar o banco (a parte da disciplina)

Foi a primeira coisa feita, antes do app: **MER conceitual → modelo lógico em 3FN →
físico (`app/backend/schema.sql`)**. O que guiou a modelagem:

- **Uma página do PDF = uma linha.** É o que permite citar a página exata. O texto e o
  vetor (embedding) da página ficam na mesma linha.
- **Publicação ≠ arquivo.** A mesma publicação pode ganhar versão nova; o arquivo tem
  hash (para não ingerir duas vezes) e a versão vigente.
- **Auditoria de uso da IA**: cada pergunta é registrada com as páginas que a resposta
  citou, com **prazo de guarda** (LGPD).
- **Vocabulário controlado** (conceito → termos equivalentes) como tabela, não só no
  código.

O `schema.sql` deste repositório é o resultado *físico*. Faça o seu MER e o seu lógico a
partir dos seus requisitos; não copie a estrutura daqui.

## Etapa 2 — Preparar o servidor

Na VM (Ubuntu), como root:

1. **Docker** só para o banco: imagem `pgvector/pgvector:pg16`
   ([`app/docker-compose.yml`](../app/docker-compose.yml)). Porta publicada **só em
   `127.0.0.1`**: o banco nunca fica acessível de fora.
2. **Ollama** instalado nativo (não em container), escutando em `127.0.0.1:11434`.
3. **Python 3 + venv** para o backend (`app/backend/requirements.txt`: FastAPI, uvicorn,
   psycopg 3, pgvector, pdfplumber, httpx, pydantic-settings).
4. **nginx** na frente, única porta aberta para fora (80).

No projeto original, um script de instalação **idempotente** (pode rodar de novo sem
estragar nada) fazia tudo isso de uma vez. Ele não está neste repositório: escreva o seu.
Vale a pena desde cedo, porque toda mudança no servidor passa a ser "editar o script e
rodar de novo", em vez de comando solto que ninguém lembra depois.

## Etapa 3 — Criar o banco de verdade

[`schema.sql`](../app/backend/schema.sql) + [`migrar.py`](../app/backend/migrar.py):

- Extensões `vector` (pgvector) e `unaccent`.
- Configuração de busca textual **`pt_sem_acento`**: dicionário português do Postgres +
  `unaccent`. Assim "violencia" acha "violência" e "mulheres" acha "mulher".
- Coluna `busca_texto` **calculada pelo próprio banco** a partir do texto da página, com
  índice **GIN** (busca por palavra).
- Coluna de vetor com índice **HNSW** (cosseno) (busca por sentido).
- DDL **idempotente** (`CREATE ... IF NOT EXISTS`): o `migrar.py` pode rodar sempre que o
  schema mudar.
- **Dois papéis no banco**: um administrador (para scripts) e um `acervo_app` com
  privilégio mínimo, que é o único que a aplicação web usa. O app não consegue apagar
  tabela nem mexer no que não precisa. Prova: [`app/deploy/teste-ataque.sh`](../app/deploy/teste-ataque.sh).

## Etapa 4 — Ingerir os PDFs

[`ingest.py`](../app/backend/ingest.py) e [`ingest_all.py`](../app/backend/ingest_all.py):

```
PDF ─ pdfplumber ─► texto de cada página ─► modelo de embedding (Ollama) ─► vetor
                                       └──► INSERT em pagina (texto + vetor)
```

- O título vem do nome do arquivo (`2022 - RT - CAPS.pdf`).
- O **hash do arquivo** impede ingerir o mesmo PDF duas vezes.
- Em CPU, cada PDF levou 4 a 5 min (o embedding é a parte lenta). Os 41 primeiros PDFs
  (5.551 páginas) levaram cerca de 3 h. **Rode isso em segundo plano e cedo.**
- Páginas com menos de 300 caracteres (capa, título de capítulo) ficam fora da busca:
  elas "ganhavam" na busca por sentido sem ter conteúdo.

## Etapa 5 — A busca híbrida (o coração do sistema)

Detalhes em [arquitetura.md](arquitetura.md). Resumo:

1. **Por sentido**: o embedding da frase digitada → as 40 páginas mais próximas
   (pgvector).
2. **Por palavra**: o [vocabulário controlado](../app/backend/vocabulario.py) expande a
   frase ("agressão" → agressão | violência | maus-tratos) → busca textual em português
   → 40 páginas.
3. **Junta** as duas listas com *Reciprocal Rank Fusion* (nota = Σ 1/(60 + posição)) →
   10 melhores → `ts_headline` grifa os trechos.

Por que as duas: o embedding entende sinônimo mas não sabe dizer quais palavras casaram;
a busca por palavra sabe grifar mas não entende sinônimo. Juntas, cobrem uma a outra.

Erros que apareceram e como foram resolvidos:

- **Palavras de pergunta viravam obrigatórias** ("existe alguma lei que…"): lista de
  palavras ignoradas.
- **Pergunta longa** não casava com nenhuma página: nota por raridade da palavra (IDF²),
  "psicodrama" vale mais que "métodos".
- **Radical do português junta palavras diferentes** ("luto" e "luta" → `lut`): a busca
  por sentido compensa em parte.
- **Modelo de embedding treinado em inglês** (`nomic-embed-text`) entendia mal
  português. Trocado por `embeddinggemma` (multilíngue) **sem parar a busca**: vetores
  novos numa coluna separada ([`reindexar.py`](../app/backend/reindexar.py)), comparação
  das mesmas 15 consultas à mão (8 melhores, 7 empates, nenhuma pior), e só então a
  troca no `.env`.

## Etapa 6 — Leitor de PDF com grifo

- O PDF é servido pelo próprio app (`GET /pdf/{id}`, só com login), nunca direto da pasta.
- **PDF.js** (Mozilla), servido pela VM, aberto dentro da página.
- A tela manda o leitor ir à página e grifar as palavras que a busca achou **naquela
  página**: amarelo o que foi digitado, verde o equivalente; ▲▼ pulam entre as
  ocorrências.
- Depois: **página do livro ≠ página do PDF**. O [`paginacao.py`](../app/backend/paginacao.py)
  lê o número no rodapé para achar a página impressa (94% das páginas), necessária para
  citar em ABNT.

## Etapa 7 — A IA (RAG) que responde citando a página

Fluxo:

```
pergunta ─► mesma busca híbrida ─► 3 páginas ─► trecho relevante de cada
        ─► prompt "[p. N] (fonte) trecho…" + pergunta
        ─► modelo local no Ollama ─► resposta em streaming, citando [p. N]
        ─► grava a consulta e as páginas citadas (auditoria)
```

Decisões importantes:

1. **RAG estrito**: a IA só recebe as páginas do acervo e tem a instrução fixa de dizer
   "Não encontrei isso nas páginas consultadas" quando for o caso. As regras e os
   exemplos estão no [`ia/Modelfile`](../app/backend/ia/Modelfile).
2. **Escolha do modelo por medição, não por fama.** Foram testados qwen2.5 7B e 3B,
   Gemma 3 4B, Gemma 4 E4B/E2B e Qwen 3.5 4B, com as mesmas perguntas e o mesmo caminho do
   site. O 7B passava de 5 minutos por resposta nesta CPU. O processo inteiro e os números
   estão em [escolha-do-modelo-ia.md](escolha-do-modelo-ia.md).
3. **"Ensinar" sem GPU**: em vez de *fine-tuning* (que exige placa de vídeo e centenas
   de exemplos), regras + **exemplos de resposta** no Modelfile. Subiu a nota de 5 para
   7 de 8.
4. **O que é crítico vai no código, não no prompt.** Um modelo pequeno não segue regra de
   forma confiável. Por isso o código: apaga frase que cita página que não foi lida;
   mascara nome e CPF de paciente antes da busca, da IA e do histórico
   ([`conversa.py`](../app/backend/conversa.py)); responde "oi" e "quem é você" sem
   chamar a IA; mostra o aviso de crise (CVV 188 / SAMU 192) em perguntas sobre suicídio.
5. **Velocidade numa CPU fraca.** Quase todo o tempo vai em *ler* o prompt. O que ajudou:
   - 3 páginas em vez de 5, e só o trecho relevante de cada uma;
   - modelo sempre na memória (`keep_alive`) e "aquecido" ao subir o app;
   - cache de prompt do Ollama/llama.cpp: perguntas seguintes sobre as mesmas páginas
     saem em segundos (`LLAMA_ARG_SWA_FULL=1` para o Gemma reaproveitar a leitura);
   - **streaming**: o texto aparece enquanto é escrito;
   - **fila** com 2 perguntas em paralelo e posição na fila mostrada na tela;
   - **respostas guardadas**: pergunta repetida sobre as mesmas páginas sai na hora;
   - **respostas prontas de madrugada** para os exemplos e as perguntas mais repetidas
     ([`pre_responder.py`](../app/backend/pre_responder.py), cron às 1h).
6. **Cuidado com a memória**: o cache do llama-server, no padrão, ocupa até 8 GB; numa VM
   de 12 GB isso derrubou a IA no primeiro dia. Limite em 1,5 GB (`LLAMA_ARG_CACHE_RAM`).
7. **Transparência**: marca d'água "GERADO POR IA", aviso para conferir na fonte, 👍/👎
   em cada resposta, e a "linha de pensamento" mostra as páginas que a busca escolheu e
   por quê.

## Etapa 8 — Avaliar a IA com perguntas-teste

[`avaliar.py`](../app/backend/avaliar.py) + [`ia/perguntas-teste.json`](../app/backend/ia/perguntas-teste.json):

- Perguntas com resposta conhecida, incluindo as que **devem ser recusadas** (fora do
  acervo, pedido de remédio, dado de paciente).
- Confere: citou só páginas que leu? Trouxe os termos esperados? Recusou o que devia?
- **Ciclo de melhoria**: cada pergunta real que deu errado vira uma pergunta-teste; muda-se
  o Modelfile, o vocabulário ou a busca; roda-se o `avaliar.py`; **a nota não pode cair**.
  Assim a nota foi de 4/8 até 15/15.
- A nota automática é tolerante: as respostas também foram lidas uma a uma
  (`avaliar.py --saida`).

Lição do "caso do CRAS": a resposta ruim **não era culpa do modelo**, e sim da busca, que
trazia o currículo de uma autora em vez das páginas sobre o CRAS. Antes de culpar a IA,
olhe quais páginas ela recebeu.

## Etapa 9 — A tela

HTML/CSS/JS puro, sem framework ([`app/backend/static/`](../app/backend/static/)):
login, busca, resultados com grifo e selo "mesmo assunto", leitor, perguntar à IA,
**Citar** e **Copiar com referências (ABNT)** ([`referencias.py`](../app/backend/referencias.py),
a partir da ficha catalográfica de cada obra), modo escuro, celular, caderno de pesquisa,
linha do tempo e ficha de cada obra. O estudo de layout está em
[estudo-layout-ux.md](estudo-layout-ux.md).

## Etapa 10 — Segurança

Detalhes em [seguranca.md](seguranca.md). As camadas:

- **Firewall (ufw)**: só SSH e web. Banco, IA e app escutam só em `127.0.0.1`.
- **nginx**: limites de requisição e de tamanho, cabeçalhos de segurança.
- **Login**: senha com hash **scrypt** ([`seguranca.py`](../app/backend/seguranca.py)),
  cookie de sessão assinado, bloqueio após 10 erros em 15 min **por login** (e não por
  IP: a turma inteira sai pelo mesmo IP do Wi-Fi).
- **Banco com privilégio mínimo** (etapa 3) e **segredos só no `.env`**, gerado na
  instalação e que nunca vai para o git.
- **Sem upload pela web**: PDF novo só entra pela linha de comando na VM.
- **LGPD**: dado de paciente mascarado, prazo de guarda das consultas, medidor de uso sem
  IP nem texto.
- **SSH endurecido** depois de milhares de tentativas de senha vindas de robôs
  ([`endurecer-ssh.sh`](../app/deploy/endurecer-ssh.sh), com fail2ban).
- **Backup diário** do banco às 3h ([`backup.sh`](../app/deploy/backup.sh)).

## Etapa 11 — Colocar no ar e acompanhar o uso real

- Serviço **systemd** ([`acervo-psico.service`](../app/deploy/acervo-psico.service)): o
  app volta sozinho se cair ou se a VM reiniciar.
- **Medidor de uso** (`/uso`, só admin): buscas, perguntas, aparelhos, desempenho da IA e
  saúde do servidor ([`uso.py`](../app/backend/uso.py)).
- **Diagnóstico** só de leitura ([`diagnostico.sh`](../app/deploy/diagnostico.sh)).
- **Testar com usuários de verdade cedo.** As 11 primeiras perguntas das colegas
  mostraram mais problemas do que todos os testes anteriores (ver "O que as conversas
  reais ensinaram" em [arquitetura.md](arquitetura.md)).

## Etapa 12 — Crescer o acervo

Em 10/11, o acervo passou de 41 para 77 obras (leis, normas do CFP, manuais do governo),
com [`baixar_leis.py`](../app/deploy/baixar_leis.py) e a curadoria de categoria, eixo e
leis citadas ([`curadoria.py`](../app/backend/curadoria.py)). Obra nova precisa de: ingerir
o PDF, rodar o `migrar.py` (página impressa), referência ABNT em `referencias.py` e
entrada no mapa do acervo (`mapa.py`). Detalhes em
[acervo-ampliado-2026-11-10.md](acervo-ampliado-2026-11-10.md).

---

## Checklist para montar o seu

- [ ] Requisitos por escrito (quem usa, o que precisa, restrições de hardware e LGPD)
- [ ] **Seu** MER e **seu** lógico em 3FN, rastreados contra os requisitos
- [ ] `schema.sql` idempotente + script de migração + papel de banco restrito
- [ ] Banco em Docker, só em `127.0.0.1`
- [ ] Ollama local com um modelo de embedding **que entenda português**
- [ ] Ingestão página a página, com hash para não duplicar
- [ ] Busca por palavra (português + sem acento) **e** por sentido, juntas por RRF
- [ ] Leitor de PDF que abre na página e grifa
- [ ] RAG estrito com citação de página; o que é crítico garantido no código
- [ ] Modelo de IA escolhido por **medição** no seu hardware
- [ ] Perguntas-teste + `avaliar` antes de cada mudança
- [ ] Login com hash, limites, firewall, `.env` fora do git, backup
- [ ] Instalador idempotente; serviço systemd
- [ ] Usuários reais testando o quanto antes, e cada erro vira pergunta-teste

## Erros que custaram tempo (para você não repetir)

| Erro | O que aconteceu | Como evitar |
|---|---|---|
| Modelo grande demais | 7B passou de 5 min por resposta e estourou o tempo limite | Meça no seu hardware antes de escolher |
| Cache do llama-server sem limite | A IA caiu com a RAM cheia no 1º dia de uso | `LLAMA_ARG_CACHE_RAM` em VM pequena |
| Embedding em inglês | Busca por sentido fraca em português | Modelo multilíngue; compare com as mesmas consultas |
| Culpar a IA pela resposta ruim | Era a busca que trazia as páginas erradas | Sempre olhe o contexto que a IA recebeu |
| Regra só no prompt | Modelo pequeno inventava página e copiava os exemplos | Validar e limpar a resposta no código |
| Bloqueio de login por IP | A turma toda no mesmo Wi-Fi seria bloqueada junto | Limite por login |
| Comandos soltos no servidor | Ninguém lembrava o que tinha sido mudado | Tudo num instalador idempotente versionado |
| Senha e IPs no repositório | Vazamento ao deixar o repo público | `.env` e dados de acesso fora do git desde o 1º commit |
