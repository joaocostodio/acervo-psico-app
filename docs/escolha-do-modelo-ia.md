# Escolha do modelo da Susmi (03/11/2026)

Como escolhemos o modelo de linguagem que escreve as respostas da Susmi, o que foi
testado, o que ficou de fora e por quê. Para repetir a disputa com modelos novos, veja
[Como repetir](#como-repetir).

## 1. O problema

Em 03/11/2026, a Susmi levou **3 minutos** para responder "Qual o papel do psicólogo no
CAPS?" (1ª palavra na tela aos 2 min 29 s). Numa VM com 3 núcleos e sem placa de vídeo
(Xeon Silver 4108, 1,8 GHz, 12 GB de RAM), quase todo o tempo vai em duas etapas:

| Etapa | Velocidade medida (Gemma 3 4B) | O que pesa |
|---|---|---|
| **Ler** as instruções e as páginas | ~17 tokens/s | ~1.000 tokens de regras e exemplos + ~1.200 das 3 páginas |
| **Escrever** a resposta | ~4 tokens/s | 300 a 900 tokens |

## 2. A ideia de partida: o Colibrì

O ponto de partida foi um post do Instagram (@fabianocarvalhojr) sobre o
**Colibrì** ([JustVugg/colibri](https://github.com/JustVugg/colibri)), que roda um modelo
de 744 bilhões de parâmetros (GLM-5.2) num notebook sem placa de vídeo. O truque: é um
modelo **MoE** (*mixture of experts*), que usa só uma pequena parte dos parâmetros a
cada palavra. O Colibrì deixa na RAM só a parte comum (~10 GB) e lê do disco, sob
demanda, os "especialistas" que cada palavra pede.

**Por que não serve do jeito que está:**

| | Colibrì pede | A VM tem |
|---|---|---|
| RAM | ~25 GB | 12 GB (o banco e o app também usam) |
| Disco | ~370 GB em NVMe rápido | 85 GB livres |
| Leitura do disco, salteada | vários GB/s (NVMe) | **51 MB/s** (medido com leituras de 2 MB em posições aleatórias) |

O Colibrì lê cerca de 11 GB do disco **por palavra** quando os especialistas não estão
na memória. A 51 MB/s, isso daria minutos por palavra. Mesmo um MoE bem menor, como o
Gemma 4 26B-A4B (16 GB), não cabe nos 12 GB: a parte que sobra viria do disco a cada
palavra, a vários segundos por palavra. Uma resposta de 400 palavras levaria horas.

**O que aproveitamos da ideia:** escolher pelo número de parâmetros **ativos** (o que a
CPU calcula por palavra), não pelo tamanho total, e só considerar modelos que **cabem
inteiros na RAM**. Daí os candidatos abaixo.

## 3. Candidatos

| Modelo | Tamanho | Por que entrou |
|---|---|---|
| **Gemma 3 4B** (o atual, `acervo-psico`) | 3,4 GB | base de comparação |
| Gemma 4 E4B (QAT) | 6,1 GB | sucessor do atual; ~4,5 bi de parâmetros "efetivos" (8 bi com as tabelas de embedding) |
| Gemma 4 E2B (QAT) | 4,3 GB | ~2,3 bi efetivos: metade da conta por palavra |
| Qwen 3.5 4B MTP | 4,1 GB | "MTP" = prevê várias palavras de uma vez (deveria escrever mais rápido) |
| Qwen 3.5 4B | 3,3 GB | o mesmo sem MTP |

Ficaram de fora sem teste: Gemma 4 26B-A4B (16 GB) e Qwen 3.5 35B-A3B (22 GB), MoE que
não cabem na RAM; e os modelos de 9 bi ou mais, densos e lentos demais nesta CPU.

Todos receberam **as mesmas instruções** da Susmi (`ia/Modelfile`, só trocando o
`FROM`). Os modelos que "pensam antes de responder" (Gemma 4, Qwen 3.5) rodaram com o
pensamento desligado (`think: false`); com ele ligado, cada resposta levaria minutos a mais.

## 4. Como testamos

- **15 perguntas** de `ia/perguntas-teste.json`: as 11 de antes + 4 perguntas reais das
  alunas de 20/10/2026 ("qual o objetivo do crepop?", "consegue criar um resumo
  expandido sobre o crepop", "me explique ansiedade baseado nos pdf", "desenvolva um
  artigo sobre ansiedade na juventude").
- **Mesmo caminho do site**: a mesma busca acha as mesmas páginas para todos os
  modelos; a resposta passa pela mesma limpeza (`avaliar.py`).
- **Nota automática**: citou só páginas que leu? Trouxe algum dos termos esperados? Recusou
  o que está fora do acervo?
- **Leitura humana**: `avaliar.py --saida` grava a resposta inteira de cada modelo, e
  as respostas foram lidas uma a uma (seção 6). A nota automática é tolerante (basta uma
  palavra-chave), então sozinha não decide.
- Na própria VM, um modelo por vez, com a memória limpa entre um e outro
  (`app/deploy/bench-modelos.sh`).

## 5. Resultados

| Modelo | Acertos | Tempo médio | Mediana | Leitura (mediana) | Escrita |
|---|---|---|---|---|---|
| Gemma 4 E4B | 2/2 (interrompido) | ~5 min | — | ~200 s | — |
| **Gemma 4 E2B** | **12/15** | **93 s** | 85 s | 55 s | **7,8 tokens/s** |
| Qwen 3.5 4B MTP | 13/15 | 185 s | 203 s | 119 s | 3,6 tokens/s |
| Qwen 3.5 4B | — (pulado) | — | — | — | — |
| Gemma 3 4B (atual) | 15/15 | 92 s | 95 s | 60 s | 5,3 tokens/s |

Tamanho das respostas (mediana): Gemma 3, **168 tokens**; Gemma 4 E2B, **294**; Qwen 3.5,
292. Com o mesmo tempo total do Gemma 3, o E2B escreve cerca de 75% mais.

- **Gemma 4 E4B**: as duas primeiras respostas estavam certas, mas só a leitura levou
  200 a 230 s por pergunta. Interrompemos para não gastar 1 hora num modelo que
  ninguém esperaria.
- **Qwen 3.5 4B sem MTP**: pulado. A versão MTP, que deveria ser a mais rápida das
  duas, já levava o dobro do tempo do E2B.

## 6. O que as respostas mostraram (leitura humana)

**Gemma 4 E2B**: conteúdo correto e bem organizado, com tópicos e citações, e escreve
duas vezes mais rápido que o Gemma 3. Dois defeitos repetidos:
1. começava quase toda resposta com "Olá! Eu sou a Susmi e estou aqui para ajudar…";
2. nas perguntas fora do acervo (bolo de cenoura, Copa de 2002), **só se apresentava**,
   sem dizer que não encontrou. A nota automática pegou isso como erro.

O terceiro "erro" ("me explique ansiedade") foi uma resposta honesta: as páginas que a
busca achou não explicam ansiedade, e ele disse isso.

**Qwen 3.5 4B MTP**: o melhor texto. Não se apresenta, recusa certo, diz com precisão
o que falta ("o acervo menciona o psicodrama no esporte, mas não traz quem o criou"),
traz mais leis ("Disque 180, Lei 10.714/03"). Mas escreve a 3,6 tokens/s e lê devagar:
**mais de 3 minutos por resposta**. O MTP não ajudou nesta CPU.

**Gemma 4 E4B**: respostas boas nas duas perguntas que chegou a fazer, mas lento demais.

**Gemma 3 4B (atual)**: acertou as 15 pela nota automática, mas com respostas curtas
(metade do tamanho), às vezes sem os tópicos pedidos nas instruções, e com citação fora do
lugar ("Conforme [p. 51], …"; "[p. 18]" colado numa recusa). No pedido de artigo, colou os
trechos com o cabeçalho "[p. 64] (Violencia Sexual Infantojuvenil)" em vez de escrever.

## 7. Decisão: Gemma 4 E2B

Antes de decidir, o E2B rodou de novo as 15 perguntas **com as correções da seção 8**
(sem saudação, recusa garantida, modo texto longo):

| Modelo | Acertos | Tempo médio | Mediana | Leitura (mediana) | Escrita | Tamanho (mediana) |
|---|---|---|---|---|---|---|
| Gemma 3 4B (o anterior) | 15/15 | 92 s | 95 s | 60 s | 5,3 tokens/s | 168 tokens |
| **Gemma 4 E2B + correções** | **13/15** | **84 s** | 89 s | 58 s | **8,0 tokens/s** | 262 tokens |

A saudação sumiu e as recusas (bolo, Copa) saíram certas. **Ficamos com o Gemma 4 E2B**:

- **mais rápido no total** (84 s contra 92 s), e **escreve 50% mais rápido**. No texto
  longo (até 1.400 tokens), são ~3 min em vez de ~4,5. Como a resposta aparece enquanto é
  escrita, a pessoa lê mais cedo;
- **respostas mais completas e organizadas**, com frase direta, subtítulos e um tópico por
  ponto, cada um com a sua citação, como as instruções pedem. O Gemma 3 respondia com a
  metade do tamanho e às vezes colava os trechos crus;
- quando erra, **erra por cautela**: diz "Não encontrei" em vez de inventar.

**O que perdemos (e fica de olho):** as 2 perguntas que o E2B errou são as de **ansiedade**
("me explique ansiedade baseado nos pdf", "desenvolva um artigo sobre ansiedade na
juventude"). As páginas que a busca achou só citam ansiedade de passagem (em segurança
pública, em violência sexual infantojuvenil), e o E2B respondeu "Não encontrei". O Gemma 3
juntou essas menções numa resposta parcial. As duas atitudes são defensáveis, porque o acervo
não tem um texto sobre ansiedade. Mas as alunas perguntaram isso de verdade, então é o
primeiro ponto a acompanhar pelo 👎 no painel `/uso`.

**Resolvido na mesma noite (03/11/2026):** com a busca por sentido trocada para o
`embeddinggemma` e o mapa do acervo no prompt ([arquitetura.md](arquitetura.md)), a busca
passou a achar páginas que falam de ansiedade de fato (pandemia, saúde mental infantil), e o
E2B respondeu as duas com citação. Prova: **15/15**, média de 95 s.

**Descartados:** Gemma 4 E4B (~5 min por resposta) e Qwen 3.5 4B, com e sem MTP (o melhor
texto, mas mais de 3 min por resposta nesta CPU).

**Para voltar ao Gemma 3**: `FROM gemma3:4b` no `ia/Modelfile`, tirar `IA_PENSAR` do `.env`,
`ollama create acervo-psico -f ia/Modelfile` e reiniciar o serviço. O `gemma3:4b` continua
baixado na VM.

## 8. O que mudou no código por causa do teste

Os dois defeitos do Gemma 4 E2B foram corrigidos **no código**, não só nas instruções,
seguindo a regra do projeto: um modelo pequeno não segue regra de forma confiável.

| Defeito | Correção | Onde |
|---|---|---|
| Saudação "Olá! Eu sou a Susmi…" | apagada do começo da resposta | `rag.tirar_saudacao` |
| Só se apresenta e não recusa | se, sem a saudação, não sobra conteúdo nem citação, vira "Não encontrei isso nas páginas consultadas…" | `rag.limpar_resposta` |
| (os dois) | regra nova: "Não cumprimente nem se apresente" | `ia/Modelfile`, regra 4 |

Mudanças que valem para qualquer modelo e saíram das medições:
- **IA aquecida ao iniciar** (`main._aquecer_ia`): o app manda a IA ler as instruções fixas
  assim que sobe, e o modelo fica sempre na memória (`keep_alive = -1`). Na medição, a 1ª
  pergunta pagava ~1 minuto só para ler as regras e os exemplos.
- **Cache completo da janela deslizante** (`LLAMA_ARG_SWA_FULL=1` no serviço do Ollama).
  Depois de publicar, o aquecimento não fazia efeito: o log mostrava *"forcing full prompt
  re-processing due to lack of cache data (likely due to SWA…)"*. O Gemma usa atenção em
  janela deslizante (512 tokens), e o llama.cpp jogava fora a leitura das instruções a cada
  pergunta. Com o cache completo (+96 MB de RAM), duas perguntas diferentes seguidas:

  | | Leitura | Resposta inteira |
  |---|---|---|
  | sem o cache completo | 95–98 s | 146–162 s |
  | **com o cache completo** | **60 s** | **101–105 s** |

  Para comparar: a mesma pergunta levou **179 s** de manhã, com o Gemma 3 sem aquecimento.
- **Tempo de cada resposta registrado** (`metrica_resposta`), mostrado no painel `/uso`:
  dá para ver se a troca de modelo melhorou a experiência de verdade, com as perguntas
  reais, e não só no teste.

## Como repetir

Na VM, como root (o teste roda numa pasta separada e não mexe no app no ar):

```bash
mkdir -p /root/bench/backend && cd /opt/crepop/backend && \
  tar --exclude=.venv -cf - . | tar -xf - -C /root/bench/backend
# candidatos no formato modelo|pensar (false = desliga o "pensar"; none = não manda)
CANDIDATOS="gemma4:e2b-it-qat|false atual|none" bash /opt/crepop/deploy/bench-modelos.sh > /root/bench/log.txt
grep MODELO /root/bench/log.txt          # nota e tempo médio de cada um
ls /root/bench/res-*.json                # respostas inteiras, para ler
```

Cada modelo leva de 25 a 50 minutos nesta VM. A Susmi fica lenta para quem estiver
usando durante o teste.
