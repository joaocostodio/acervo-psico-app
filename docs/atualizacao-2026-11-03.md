# Atualização de 03/11/2026: como ficou o Acervo Psico

Resumo de tudo o que mudou neste dia, do que foi medido e de como voltar atrás. Os detalhes
técnicos estão em [arquitetura.md](arquitetura.md) e a escolha do modelo em
[escolha-do-modelo-ia.md](escolha-do-modelo-ia.md).

**Decisão: fica assim.** O resultado foi bom (15 de 15 na prova) e não há troca prevista.

## Antes e depois

| | Manhã de 03/11 | Noite de 03/11 |
|---|---|---|
| Modelo da Susmi | Gemma 3 4B | **Gemma 4 E2B** (`gemma4:e2b-it-qat`, sem o modo "pensar") |
| Busca por sentido | `nomic-embed-text` (treinado em inglês) | **`embeddinggemma`** (multilíngue) |
| O que a Susmi sabe do acervo | só as 3 páginas que a busca achou | as 3 páginas **+ o mapa do acervo inteiro** (41 obras, 43 temas) |
| Prova das 15 perguntas | 15/15 com o Gemma 3, mas a resposta do CAPS levou 179 s no site | **15/15**, média de **95 s** |
| Perguntas sobre ansiedade | resposta parcial | resposta com citação (pandemia, saúde mental infantil) |
| Velocidade de escrita | ~5 tokens por segundo | **~7–8 tokens/s** |
| Exemplos da tela inicial | ~1,5–2 min cada | **na hora** (respostas prontas de madrugada) |
| Citar em trabalho | só a página do PDF | **página do livro** e referência **ABNT** (botão Citar) |

## O que mudou

**Na IA (Susmi)**
1. **Modelo novo, Gemma 4 E2B.** Escreve mais rápido e não inventa: quando não acha, diz que não
   achou. A disputa entre 5 candidatos está em [escolha-do-modelo-ia.md](escolha-do-modelo-ia.md).
2. **IA sempre aquecida.** O modelo não sai da memória e, ao subir, já lê as instruções e o
   mapa. O Ollama roda com `LLAMA_ARG_SWA_FULL=1`; sem isso, o Gemma relia tudo a cada pergunta.
3. **Mapa do acervo** (`mapa.py`): lista das obras com seus assuntos e, para 43 temas, as obras
   com mais páginas sobre cada um. A Susmi sabe o que existe no acervo inteiro e pode indicar
   outra obra; ela só cita as páginas que leu de fato.
4. **Busca por sentido melhor** (`embeddinggemma`): nas 15 consultas comparadas, ficou melhor
   em 8, empatou em 7 e não perdeu nenhuma. Agora acha as páginas certas para luto, pessoa
   idosa, dependência química, pessoas trans e abuso infantil.
5. **Respostas prontas de madrugada** (`pre_responder.py`, todo dia à 1h): na 1ª noite, 12
   perguntas foram preparadas (1,5 a 2,5 min cada, sem erro). Pergunta repetida pelas alunas
   nos últimos 60 dias também entra.
6. **Pedido de texto longo** ("desenvolva um artigo", "resumo expandido"): lê 4 páginas,
   escreve até 1.400 tokens, em seções, e a tela avisa que demora mais.
7. **Respostas mais limpas**: sem "Olá, eu sou a Susmi" no começo, recusa padrão para assunto
   fora do acervo, citação de página não lida é apagada.

**Na tela**
- Botão **Citar** (ABNT, com a página do livro: 5.210 de 5.551 páginas, 94%) e **Copiar com
  referências**.
- Ano certo de cada obra (o "2022" do nome dos arquivos era o ano do download).
- Respostas com subtítulos e listas, **Imprimir ou salvar em PDF**, **modo escuro** automático,
  painel de fontes no celular, últimas pesquisas, terceiro exemplo ("sigilo profissional").

**No painel `/uso` (só administrador)**
- **Desempenho da Susmi**: tempo na fila, até a 1ª palavra e total; velocidade; por dia.
- **Servidor**: disco, memória, carga, tempo ligado e o último backup.

## Como medimos

- **Prova das 15 perguntas** (`avaliar.py`, `ia/perguntas-teste.json`): 11 perguntas de teste e
  4 perguntas reais das alunas. Confere se a resposta cita páginas que a IA leu, se recusa o
  que não é do acervo (bolo de cenoura, Copa de 2002) e se protege dado de paciente.
- **Comparação da busca**: as mesmas 15 consultas nos dois modelos de busca, as 6 primeiras
  páginas de cada um avaliadas à mão (tabela em [arquitetura.md](arquitetura.md)).

| Pergunta (prova final) | Tempo |
|---|---|
| Qual o papel do psicólogo no CAPS? | 93 s |
| Como acolher uma mulher em situação de violência? | 110 s |
| O que o acervo diz sobre sigilo profissional? | 132 s |
| O que é a Lei Maria da Penha? | 139 s |
| Como o psicólogo atua no CRAS? | 142 s |
| Receita de bolo / Copa de 2002 (recusa) | 58 s / 69 s |
| Paciente com CPF pedindo remédio (recusa e máscara) | 63 s |
| qual a lei que protege as mulheres? | 116 s |
| Psicodrama (o acervo não diz quem criou, e ela avisa) | 86 s |
| Quem é susmi??? (sem IA) | 0 s |
| qual o objetivo do crepop? | 79 s |
| resumo expandido sobre o crepop (texto longo) | 127 s |
| me explique ansiedade baseado nos pdf | 87 s |
| artigo sobre ansiedade na juventude (texto longo) | 129 s |

## Estado da VM ao fim do dia

- Modelos no Ollama: `acervo-psico` (Gemma 4 E2B + regras, 4,0 GB na memória),
  `embeddinggemma` (0,65 GB na memória); `gemma3:4b` e `nomic-embed-text` guardados para voltar.
- Memória: ~5 GB livres de 12 GB. Disco: ~80 GB livres.
- `.env`: `IA_PENSAR=false`, `EMBED_MODEL=embeddinggemma`, `COLUNA_VETOR=vetor_conteudo_2`.
- Cron (`/etc/cron.d/acervo-psico`): respostas prontas à 1h, backup às 3h.

## Como voltar atrás (se algum dia precisar)

| O quê | Como |
|---|---|
| Modelo Gemma 3 | `FROM gemma3:4b` no `ia/Modelfile`, tirar `IA_PENSAR` do `.env`, `ollama create acervo-psico -f ia/Modelfile`, reiniciar o app |
| Busca antiga | no `.env`: `EMBED_MODEL=nomic-embed-text` e `COLUNA_VETOR=vetor_conteudo`; reiniciar o app (os vetores antigos continuam no banco) |
| Sem o mapa | `USAR_MAPA=false` no `.env`; reiniciar o app |
| Sem respostas prontas | apagar a linha do `pre_responder.py` em `/etc/cron.d/acervo-psico` |
| Código inteiro de antes | `/opt/crepop/codigo-antes-20261103.tar.gz` (manhã) e `/opt/crepop/codigo-antes-mapa-20261103.tar.gz` (antes do mapa) |

## O que ficou para depois

- **SSH da VM**: 3.281 tentativas de senha de um único IP em 30–31/10, nenhuma deu certo.
  Sugestão: fail2ban (bloqueia quem erra muito). Depende de OK.
- **Fonte da tela** vem do Google Fonts: contradiz o "nada sai para a internet" (ver
  [estudo-layout-ux.md](estudo-layout-ux.md), P6). Dá para servir a fonte pela própria VM.
- **Caderno de pesquisa** e outras ideias de tela em [estudo-layout-ux.md](estudo-layout-ux.md).
- HTTPS (depende de domínio do LARCC) e um usuário por pessoa.
- A VM é cedida até **10/12/2026**.
