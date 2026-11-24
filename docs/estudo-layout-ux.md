# Estudo de layout e uso do Acervo Psico (03/11/2026)

O que a tela faz bem, onde atrapalha as estudantes de Psicologia e como aproveitar
melhor a VM do LARCC até o fim do empréstimo (10/12/2026). Feito lendo o código da tela
(`app/backend/static/*.html`) e usando-a num servidor de teste com dados de mentira.
A escolha do modelo da IA está em outro estudo: [escolha-do-modelo-ia.md](escolha-do-modelo-ia.md).

## 1. Para quem e em que momento

- **Quem usa**: estudantes de Psicologia da SETREM, no estágio e nas disciplinas. As
  perguntas reais de 20/10/2026 mostram para que elas usam: *"consegue criar um resumo
  expandido sobre o crepop"*, *"desenvolva um artigo sobre ansiedade na juventude"*,
  *"me explique ansiedade baseado nos pdf"*. **Elas estão escrevendo trabalhos.** A
  ferramenta precisa ajudar a juntar trechos, citar certo e levar isso para o Word.
- **Quando**: novembro e dezembro, ou seja, **fim de semestre e trabalhos finais**. A VM
  fica com o projeto até **10/12/2026**. O que a aluna juntar precisa sair do site e ficar
  com ela.
- **Onde**: no celular (entre aulas e no estágio) e no computador (escrevendo). Usam todas
  o mesmo login de teste, então o site não sabe quem é quem.
- **A VM**: 3 núcleos, 12 GB, **sem placa de vídeo**. A busca leva ~0,2 s e a IA leva de 1 a
  3 min por resposta, com 2 respostas por vez. **A IA é o recurso escasso**: toda melhoria
  que não gasta IA de dia sai de graça.

## 2. O que já funciona bem (manter)

| Ponto | Por que é bom |
|---|---|
| Dois modos claros (**Buscar** instantâneo × **Perguntar à Susmi** 1–3 min) com o tempo escrito no cartão | a pessoa sabe o que esperar antes de clicar |
| Resultado → PDF **na página**, com grifo amarelo/verde e ▲▼ | é o coração da ferramenta: vai direto à fonte |
| "Também busquei: …" e selo "mesmo assunto" | mostra por que cada página apareceu |
| Linha de pensamento com o trecho real sendo lido | a espera de 1 min deixa de parecer travamento |
| Citação `p. N` clicável, **Citar** (ABNT com página do livro) e **Copiar com referências** | resolve a maior dor de trabalho acadêmico |
| Marca d'água "GERADO POR IA" + aviso + 👍/👎 | uso responsável, e o 👎 vira pergunta-teste |
| Modo escuro, impressão, fontes no celular, últimas pesquisas | já entregues na atualização de 03/11 |

A identidade visual (verde-petróleo, papel creme, serifa nas respostas) é sóbria e
combina com material técnico. **Não recomendo trocar o visual**: o ganho está no fluxo.

## 3. Onde a tela atrapalha (por prioridade)

### P1. Nada do que a aluna acha fica guardado (alta)
Recarregou a página ou clicou em "Nova pesquisa", e a conversa some. Não há lugar para
**juntar** os trechos e as respostas que vão para o trabalho. Hoje ela precisaria copiar
um por um para outro documento, e a referência ABNT de cada um, à parte.
**Proposta:** um **Caderno de pesquisa** (fichamento). Um botão "Guardar" em cada
resultado, em cada resposta da Susmi e no leitor de PDF. O caderno junta tudo com a
citação e a referência ABNT de cada item, aceita uma anotação da aluna e exporta para o
Word ou o PDF com as referências no fim. Fica **só no aparelho** (navegador), coerente
com o login compartilhado e a LGPD: nada novo vai para o servidor.

### P2. Citação direta exige redigitar o trecho (alta)
Para citar entre aspas, a aluna lê no PDF e redigita o trecho, depois procura a página
impressa. **Proposta:** no leitor, selecionar o texto e clicar **"Guardar trecho
selecionado"** guarda as palavras exatas com a página (do livro, quando o sistema sabe).

### P3. A espera da IA prende a pessoa na aba (média)
Uma resposta leva 1 a 3 minutos. Quem troca de aba para escrever o trabalho não sabe
quando acabou. **Proposta:** o título da aba mostra o andamento ("⏳ Susmi escrevendo…")
e vira **"✓ Resposta pronta"** quando termina. Custo zero, nada no servidor.

### P4. O número da página confunde (média)
A etiqueta do resultado mostra `p. 20` (página do **PDF**), mas o "Citar" usa `p. 18`
(página do **livro**). Na mesma linha, dois números para a mesma página. **Proposta:**
manter `p. 20` (é o que abre o PDF) e o "Citar" explicar a diferença, como já faz. Mostrar
a página do livro no item guardado no caderno, que é para onde ela copia.

### P5. "Nada encontrado" sem saída (média)
Com fontes desmarcadas, a busca pode voltar vazia e a tela só diz "Nada encontrado nessas
fontes". **Proposta:** oferecer "Buscar no acervo todo" e "Perguntar à Susmi".

### P6. A tela diz "nada sai para a internet", mas as fontes de letra vêm do Google (média)
`index.html` e `entrar.html` carregam *Source Serif* e *IBM Plex Sans* de
`fonts.googleapis.com`. O navegador de cada aluna avisa o Google a cada acesso (IP e
horário). Não vaza pergunta, mas contradiz o selo da tela inicial. **Proposta:** baixar as
duas fontes (woff2, ~200 KB) para `static/fontes/` na instalação e tirar o Google do
CSP. Fica para quem mexer no deploy (ver seção 6).

### P7. Abrir uma obra pela lista lateral cai na capa (baixa)
O clique na lista lateral abre a página 1. Para quem quer **conhecer** a obra, seria melhor
ter a referência, o ano, os eixos e "buscar só nesta obra". Fica para depois do caderno.

### P8. Botões pequenos no celular (baixa)
`p. N` nas respostas tem ~20 px de altura e "Explicar"/"Citar" ficam lado a lado com a
etiqueta da página. No toque, o mínimo recomendado é 32–44 px. Melhorar junto com a
próxima rodada de celular.

## 4. Como aproveitar mais a VM

A CPU fica **parada de noite e nos fins de semana**, e a IA é a parte lenta de dia. A
estratégia é **adiantar de noite o que for previsível** e, de dia, usar só o que é barato
(banco e busca).

| # | Ideia | Gasta | Valor para as alunas | Quem faz |
|---|---|---|---|---|
| A | **Respostas prontas de madrugada**: rodar às 2h as perguntas dos botões da tela inicial e as mais feitas da semana. Com a `resposta_guardada`, saem em 1 s de dia | IA de madrugada (~3 min cada) | os exemplos da tela inicial respondem na hora, sem fila | backend (claude1) |
| B | **Ficha de leitura de cada obra** (resumo, pontos principais, leis citadas), gerada de madrugada, com marca de IA | ~41 × 3 min ≈ 2 h, uma vez | entender uma RT antes de ler as 200 páginas | backend + tela |
| C | **"Páginas parecidas"** em cada resultado (vizinhos no pgvector) | ~10 ms de banco | puxar o fio de um assunto entre obras diferentes | backend + tela |
| D | **Leis no acervo**: lista das leis (`lei` + `pagina_lei`, já existem) → páginas que citam cada uma | banco | "onde as RTs falam da Lei Maria da Penha / ECA / LBI" | backend + tela |
| E | **Glossário** a partir do vocabulário controlado (45 conceitos) | nada | ver os termos equivalentes da área e buscar por eles | tela |
| F | **Caderno de pesquisa** (P1, P2) | nada (fica no aparelho) | juntar, citar e exportar para o trabalho | **tela, feito neste estudo** |
| G | Comparar duas obras sobre um tema (IA lê 2 páginas de cada) | IA de dia, 2–3 min | bom, mas caro; só depois de A | backend |
| H | Questões de estudo / *flashcards* gerados pela IA | IA de madrugada | arriscado sem revisão de professora: IA pode errar. Só com revisão | depois |

**Não recomendo** aumentar o paralelismo da IA nem modelos maiores de dia: com 3 núcleos o
total não cai (medido em 20/10), e cada resposta fica mais lenta para todas.

**Até 10/12/2026**: o caderno exporta para Word/PDF justamente para a aluna não perder nada
quando a VM for devolvida.

## 5. O que foi implementado neste estudo

_(preenchido depois que a atualização do claude1 for commitada, para não editar o mesmo arquivo ao mesmo tempo)_

## 6. Divisão do trabalho

- **claude2 (este estudo)**: tela, caderno de pesquisa, título da aba, saídas da busca vazia.
- **claude1 (modelo e backend)**: escolha do modelo, respostas prontas de madrugada (A),
  fichas de leitura (B), páginas parecidas (C), leis (D), fontes de letra no deploy (P6).
