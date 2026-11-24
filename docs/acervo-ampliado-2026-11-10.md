# Acervo ampliado: leis, normas do CFP e manuais do governo (10/11/2026)

A ideia inicial era um "super treinamento" da Susmi para ela saber mais de Psicologia.
Em vez disso, **ampliamos a biblioteca que ela consulta**. Este documento explica por quê,
o que entrou, como foi feito e como desfazer.

## Por que não treinar o modelo

| | Treinar o modelo (fine-tuning) | Ampliar o acervo (o que fizemos) |
|---|---|---|
| Máquina | Precisa de placa de vídeo. Na VM (3 núcleos de 1,8 GHz, 5 GB de RAM livre) levaria dias por rodada e não cabe junto com a Susmi ligada | ~2 s por página, de uma vez só |
| Fatos | O modelo "lembra mais ou menos": é quando ele inventa lei, artigo ou resolução com confiança | A Susmi lê a página e cita `[p. N]`: dá para conferir no PDF |
| Atualizar | Treinar de novo | Pôr o PDF na pasta e rodar a ingestão |

O disco tem 80 GB livres; o acervo inteiro (banco) tinha 132 MB. Espaço não é o limite:
o limite é a CPU para indexar e o cuidado para não encher a busca de ruído.

## O que entrou (36 documentos, ~1.450 páginas)

**Normas do CFP (8)** — grupo "Ética e normas do CFP" na lista lateral:
Código de Ética Profissional (2005); Resolução 06/2019 comentada (documentos psicológicos);
Resolução 11/2018 (atendimento online); Resolução 01/2009 (registro documental);
Resolução 01/2018 (pessoas trans e travestis); Resolução 01/1999 (orientação sexual);
Resolução 08/2010 (perito e assistente técnico); Cartilha de Avaliação Psicológica (3. ed., 2022).
Fonte: site.cfp.org.br.

**Leis (19), texto integral compilado do Planalto** — grupo "Leis (texto integral)":
Maria da Penha (11.340/2006); ECA (8.069/1990); Reforma Psiquiátrica (10.216/2001);
Brasileira de Inclusão (13.146/2015); Estatuto da Pessoa Idosa (10.741/2003); LOAS (8.742/1993);
Orgânica da Saúde (8.080/1990); Escuta Protegida (13.431/2017); profissão de psicólogo (4.119/1962);
Conselhos de Psicologia (5.766/1971); notificação compulsória da violência contra a mulher
(10.778/2003); SINASE (12.594/2012); Drogas (11.343/2006); Marco Legal da Primeira Infância
(13.257/2016); Estatuto da Igualdade Racial (12.288/2010); Prevenção da Automutilação e do Suicídio
(13.819/2019); Berenice Piana — autismo (12.764/2012); Psicologia e Serviço Social nas escolas
(13.935/2019); Minuto Seguinte (12.845/2013).

**Manuais do governo federal (9), ~1.000 páginas** — entram nos grupos temáticos que já existiam
(Saúde e saúde mental, Assistência social (SUAS), Violências), com a categoria "Manual do governo":
Cadernos de Atenção Básica nº 34 — Saúde mental (MS, 2013); Prevenção do suicídio: manual para
equipes de saúde mental (MS, 2006); Linha de cuidado para crianças, adolescentes e famílias em
situação de violências (MS, 2010); Viva — instrutivo de notificação de violência interpessoal e
autoprovocada (MS, 2016); PNAS/2004 e NOB/SUAS (MDS, 2005); Tipificação nacional de serviços
socioassistenciais (MDS, 2014); Orientações técnicas do CREAS (MDS, 2011); Orientações técnicas
sobre o PAIF, v. 1 e 2 (MDS, 2012). Fontes: bvsms.saude.gov.br e mds.gov.br. Ficou de fora o
"Saúde mental no SUS: os CAPS" (2004): o endereço oficial deu 404.

Por que essas: as alunas perguntaram "qual a lei que protege as mulheres?", buscaram "Lei Maria
da Penha", "notificação compulsória", CAPS e SUAS (ver `relatorios/uso-2026-11-10.txt`, fora do git, e o painel de uso). Ficaram de
fora o Código Penal (grande demais e pouco específico) e tudo que tem direito autoral fechado
(DSM, livros).

## Como foi feito

1. **Leis**: `app/deploy/baixar_leis.py` limpa o HTML do Planalto — tira o texto revogado (que o
   site mostra riscado, com `<strike>` ou `line-through`) e o cabeçalho do site — e o Chrome
   imprime em PDF A4. Cada PDF começa com o nome da lei, o número, a data, a fonte e a data
   da consulta.
2. **Normas do CFP e manuais do governo**: os PDFs oficiais, sem mudança.
3. **Nomes dos arquivos** seguem o padrão do acervo: `2006 - Lei - Maria da Penha.pdf`,
   `2005 - CFP - Codigo de Etica.pdf`, `2013 - Gov - Caderno de Atencao Basica Saude Mental.pdf`.
   Desse nome saem:
   - tipo e fonte (`ingest_all.tipo_e_fonte`): Lei / Presidência da República, Norma do CFP / CFP,
     Manual do governo / Ministério da Saúde ou do Desenvolvimento Social;
   - categoria e eixo (`curadoria.py`): "Lei" / "Norma do CFP" / "Manual do governo", os eixos
     novos "Leis (texto integral)" e "Ética e normas do CFP", e os manuais nos eixos temáticos;
   - referência ABNT (`referencias.py`): leis no formato da NBR 6023 para legislação on-line
     (`BRASIL. Lei nº 11.340, de 7 de agosto de 2006. Ementa. Brasília, DF: Presidência da
     República, [2006]. Disponível em: … Acesso em: 10 nov. 2026.`), citação `(BRASIL, 2006)`;
   - nome curto (`mapa.OBRAS`), **sem número nem ano**: o modelo pequeno confunde número no
     cabeçalho do trecho com página e cita `[p. 2006]`.
4. **Mapa do acervo** (começo fixo de todo prompt): leis e normas entram numa linha por grupo,
   para não aumentar muito o prompt.
5. **Susmi** (`ia/Modelfile`): sabe que o acervo agora tem leis e normas, e diz a lei e o artigo
   quando a informação vem de uma delas.
6. **Prova**: `ia/perguntas-teste.json` ganhou 4 perguntas (violência psicológica na Maria da
   Penha, documentos da Res. 06/2019, sigilo no Código de Ética, internação involuntária na
   10.216). As 15 antigas continuam iguais, para comparar com a nota de antes (15/15).

Na VM: PDFs em `/opt/crepop/dados/leis-e-normas`; log em `/var/log/acervo-ingerir-leis.log`;
prova em `/var/log/acervo-avaliar-leis.json`.

## Resultado

**Fase 1+2 (leis e normas do CFP), 10/11/2026 11:24 UTC:** 25 dos 27 PDFs entraram (+445
páginas: 5.551 → 5.996). As resoluções 11/2018 e 01/2018 falharam porque o texto extraído tinha
o caractere nulo (`\x00`), que o Postgres recusa; `ingest.py` passou a tirá-lo e as duas entraram
na fase 3. A curadoria achou 1.076 citações de lei nas páginas.

Busca (5 primeiras páginas, mesmo caminho do site):

| Pergunta | Depois da fase 1+2 |
|---|---|
| qual a lei que protege as mulheres? | Lei Maria da Penha em 4 das 5 |
| internação involuntária | Lei da Reforma Psiquiátrica em 1º |
| documentos que o psicólogo pode emitir | Resolução 06/2019 comentada em 4 das 5 |
| notificação compulsória | a lei da notificação em 1º |
| papel do psicólogo no CAPS / SUAS / ansiedade | só Referências Técnicas do CREPOP (as leis não tomaram o lugar delas) |

Prova (`avaliar.py`, 19 perguntas): **17/19**, média 116 s. As **15 antigas: 15/15** (igual a
antes). Das 4 novas, 2 certas. As 2 que não passaram não inventaram nada:
- *internação involuntária*: respondeu certo ("sim, sob condições", citando a lei), mas não trouxe
  o detalhe cobrado (comunicar o Ministério Público em 72 horas);
- *documentos da Resolução 06/2019*: a busca trouxe as páginas de abertura da resolução (que
  repetem "Resolução 06/2019"), não a que lista declaração, atestado, relatório, laudo e parecer;
  a Susmi disse que as páginas lidas não traziam a lista. Perguntando "que documentos o psicólogo
  pode emitir", a busca acha a página certa. Melhoria possível: dar menos peso a páginas de capa
  e sumário.

**Fase 3 (manuais do governo), 10/11/2026 12:40 UTC:** os 9 manuais (+969 páginas) e as 2
resoluções que tinham falhado entraram. Acervo final: **77 publicações, 6.965 páginas** (eram 41 e
5.551). Curadoria: 1.315 citações de lei em páginas.

| Pergunta | 5 primeiras páginas |
|---|---|
| como notificar um caso de violência autoprovocada | Instrutivo VIVA nas 5 |
| como identificar risco de suicídio | Prevenção do suicídio (MS) nas 5 |
| o que é o PAIF e como funciona o trabalho com famílias | Orientações técnicas do PAIF nas 4 primeiras |
| ansiedade na juventude | Caderno de Atenção Básica: saúde mental em 4 das 5 |
| papel do psicólogo no CAPS | só as RTs do CAPS e da RAPS (igual à fase 1) |

Prova: **17/19** de novo, média 118 s. As 15 antigas, 15/15; as mesmas 2 novas não passaram, pelos
mesmos motivos da fase 1. Os manuais não pioraram nada.

## Como desfazer

O script de instalação guardou o banco e o código de antes:

```bash
# na VM (root). Voltar só a fase 3 (manuais): antes-gov-20261110-120523 / backend-antes-20261110-120523.
# Voltar tudo (como era antes de 10/11): os de baixo.
docker exec -i crepop-pg pg_restore -U postgres -d crepop --clean < /opt/crepop/backups/antes-leis-20261110-110303.dump
cp -a /opt/crepop/backend-antes-20261110-110303/. /opt/crepop/backend/
ollama create acervo-psico -f /opt/crepop/backend/ia/Modelfile
systemctl restart acervo-psico
```

Para tirar só uma obra: `DELETE FROM publicacao WHERE titulo = '…'` (apaga as páginas junto)
com o papel administrador, e reiniciar o app.

## Também nesta atualização (tela)

- **Título da aba avisa** quando a Susmi termina: "⏳ Susmi escrevendo…" e, se a pessoa estiver em
  outra aba, "✓ Resposta pronta". Uma resposta leva 1 a 3 minutos; agora dá para escrever o
  trabalho em outra aba e voltar quando ficar pronta.
- **Busca vazia com saída**: em vez de só "Nada encontrado nessas fontes", oferece "Buscar no
  acervo todo" (quando há fontes desmarcadas) e "Perguntar à Susmi".

### Segunda rodada da tela (10/11/2026, à tarde)

Feita depois de usar o site como uma aluna, no computador e no celular:

| | O que mudou | Por quê |
|---|---|---|
| A | No celular, o nome da obra fica sozinho na 1ª linha; selo, botões e página na de baixo. No toque, "Explicar"/"Citar" sempre visíveis e maiores | o nome quebrava uma palavra por linha ("IST / HIV / Aids") e os botões eram cortados |
| B | Selo colorido por tipo: Lei (roxo), Norma do CFP (verde), Manual do governo (azul); obras do CREPOP seguem em cinza. Também nas "páginas que a Susmi lê" | o Código de Ética aparecia com a mesma cara de qualquer RT |
| C | Botões "CREPOP · Leis · Normas do CFP · Manuais" na lista de fontes, com "Pesquisar só nestas"; nomes em até duas linhas | 77 obras; nomes cortados ("Caderno de Atenção Básic…") |
| D | Tela inicial: aviso "Novo: Código de Ética, resoluções, 19 leis e manuais…" com "Ver as leis / ver as normas", e exemplos novos (Lei Maria da Penha, documentos psicológicos, risco de suicídio…) | nada mostrava que o acervo tinha crescido |
| E | A conversa volta depois de recarregar a página (F5). Fica só nesta aba (`sessionStorage`): some ao fechar a aba, e "Nova pesquisa" apaga | num computador de laboratório, a próxima pessoa não vê o que a anterior pesquisou |

Testado num servidor local com dados reais do site (Playwright, 1366 px e 390 px) antes de
instalar; o `index.html` anterior ficou em `/opt/crepop/index-antes-*.html` na VM.

### Caderno de pesquisa (10/11/2026, à tarde)

Botão **Caderno** no topo (com contador). Guarda trechos da busca (**Guardar**), respostas da
Susmi (**Guardar no caderno**) e trechos selecionados no PDF (**Guardar seleção**, no leitor:
palavras exatas + página do livro, via `/pagina-impressa`). Cada item mostra a citação ABNT
pronta e aceita uma anotação. **Baixar para o Word** gera um `.doc` (HTML que o Word abre, sem
biblioteca externa — a CSP só permite scripts do próprio site): citação direta curta entre aspas,
longa (mais de ~3 linhas) recuada 4 cm em letra menor, e as referências (NBR 6023) de todas as
obras, sem repetir, em ordem alfabética. Também **Copiar tudo**, **Imprimir/PDF** e **Apagar**
(com segundo clique). Fica no `localStorage` do navegador: nada vai para o servidor.

## Ajustes da ordem da busca (10/11/2026, à tarde)

Depois da prova de 17/19, a busca ganhou três ajustes (`rag._AJUSTE`, desligáveis com
`AJUSTAR_BUSCA=false` no `.env`):

1. **Obra nomeada na pergunta** (`rag.OBRAS_NOMEADAS`: "Lei Maria da Penha", "Resolução 06/2019",
   "Código de Ética", "ECA", "10.216"…). As páginas dela entram como 3ª lista de candidatas,
   ordenadas pelo sentido da pergunta **sem o nome da obra**, e valem ×1,25. Só leis, normas e
   manuais: "CAPS" ou "reforma psiquiátrica" (tema) não contam como nome de obra.
2. **Lei ou norma do CFP achada pelas duas buscas** (sentido e palavra): ×1,15.
3. **Capa, créditos, expediente e sumário** (8 primeiras páginas, curtas ou com essas palavras;
   leis ficam de fora, porque "expediente" e "diretoria" são termos jurídicos): ×0,6.

Comparação na VM (5 primeiras páginas, mesma pergunta, ajustes desligados → ligados):

| Pergunta | Antes | Depois |
|---|---|---|
| Lei da Reforma Psiquiátrica permite internação involuntária? | p. 2 da lei (a das 72 h) em 4º — a Susmi lê 3 | p. 1 e p. 2 da lei em 1º e 2º |
| O que o Código de Ética diz sobre o sigilo? | nenhuma página do Código | as 5 do Código, art. 9º (p. 13) em 1º |
| sigilo profissional | Código de Ética em 5º | em 1º |
| avaliação psicológica | sumário da cartilha em 1º | sumário fora; páginas de conteúdo |
| O que a Lei Maria da Penha considera violência psicológica? | lei em 1º, depois RTs | as 5 da lei (art. 7º em 1º) |
| papel do psicólogo no CAPS, CRAS, SUAS, objetivo do CREPOP, ansiedade | — | **iguais** |
| documentos da Resolução 06/2019 | abertura e créditos da resolução | mais páginas da resolução, mas a p. 9 (art. 8º, a lista) ainda fica fora das 5 primeiras |

O tempo da busca não mudou (~0,25 s; +0,1 s quando a pergunta nomeia uma obra).

Prova com a busca nova (numa cópia do backend em `/tmp`, sem mexer no site), 10/11/2026 14:29 UTC:
**18/19** (antes, 17/19), média 110 s. As 15 antigas, 15/15. Passou a acertar a da internação
involuntária (agora a Susmi lê a p. 2 da Lei 10.216, a das 72 horas). Continua errando só a dos
documentos da Resolução 06/2019: a p. 9 (art. 8º, a lista das modalidades) é uma página longa,
com vários assuntos, e não chega às 3 que a Susmi lê. Próximo passo possível: dividir páginas
longas em pedaços para a busca (cada pedaço com o seu vetor), ou um "resumo do artigo" por página.

## Trecho grifado, linha do tempo e ficha da obra (10/11/2026, noite)

### 1. "De onde veio": o trecho grifado no PDF

Clicar numa citação da resposta ("p. 13") abre o PDF na página **com o trecho grifado em
amarelo**: a frase (ou o inciso, o artigo) da página que mais se parece com a frase da resposta
que terminava naquela citação. A barra do leitor mostra "De onde veio". Vale também para um
resultado da busca (o trecho mostrado), um item do caderno e os pontos da ficha da obra.

Roda todo no navegador, sobre o texto que o próprio PDF.js extrai da página (nada vai à VM):
palavras sem acento e cortadas em 6 letras, peso menor para as que aparecem a página inteira;
procura a janela de palavras que cobre a frase, abre até o começo e o fim da frase ("Art." e
"nº" não terminam frase) e tira a frase da ponta que quase nada acrescenta (o inciso vizinho que
repete "violência, entendida como qualquer conduta"). Se nada na página se parece o bastante
(cobertura < 30%), não grifa nada: fica só o grifo das palavras da busca, como antes.

Testado com o PDF.js 4.10.38 da VM: 4 citações de uma resposta sobre o Código de Ética e 4
paráfrases da Lei Maria da Penha caíram no artigo/inciso certo; frases sem relação ("O CAPS
atende…" na Maria da Penha, "receita de bolo") não grifaram nada.

### 2. Linha do tempo

Botão **Linha do tempo** no topo (e "ver tudo na linha do tempo" no aviso da tela inicial): as 77
obras em ordem de ano de publicação, por década, de 1962 (lei da profissão) a 2025, com o selo do
tipo e o filtro CREPOP · Leis · Normas · Manuais. Cada obra abre a ficha.

### 3. Ficha da obra

Botão de ficha em cada fonte da lista, no leitor ("Ficha") e na linha do tempo. A ficha mostra:

- **Resumo, pontos principais (cada um com a página, que abre com o trecho grifado), "No estágio"
  e temas**, escritos pela Susmi de madrugada (`gerar_fichas.py`, cron às 4h UTC = 1h em Brasília;
  não começa ficha nova depois das 9h30 UTC). Ela lê 5 páginas por obra: numa lei, as 2 primeiras
  + as mais centrais; numa norma ou manual, a apresentação + as centrais; numa RT, só as centrais
  (a apresentação das RTs é o texto padrão do CREPOP). "Centrais" = as mais perto da média dos
  vetores das páginas da obra. Resposta em JSON com formato fixo (Ollama `format`); ponto com
  página que ela não leu sai da ficha. ~2 min por obra: as 77 cabem numa noite.
- **Leis que a obra cita** (tabela `pagina_lei`), com link para a ficha da lei quando ela está no
  acervo; numa lei, **as obras que a citam** (ex.: Maria da Penha → RT Mulheres em Violência, 18
  páginas); e **obras parecidas** (cosseno entre as médias dos vetores). Sem IA, refeitas toda noite.
- Referência ABNT, **Abrir o PDF**, **Perguntar à Susmi só nesta obra** e **Guardar a ficha no caderno**.

Cada ficha é um JSON em `/opt/crepop/dados/fichas/<id>.json` (`FICHAS_DIR`); o site só lê
(`GET /ficha/{id}`, com login). Comandos: `gerar_fichas.py --so-dados` (sem IA),
`--obras 51,53 --refazer`, `--ate HH:MM`. Log em `/var/log/acervo-fichas.log`.

Desfazer: voltar `main.py`, `config.py` e `static/index.html` do backup
`/opt/crepop/backend-antes-<data>` e tirar a linha `gerar_fichas` de `/etc/cron.d/acervo-psico`.

## Próximos passos possíveis

- **Artigos de acesso aberto** (SciELO, CC-BY; ex.: *Psicologia: Ciência e Profissão*, do CFP):
  10 a 30 mil páginas, 1–2 noites. Mostrar "artigo científico" na fonte e dar preferência às
  normas e leis.
- A VM é devolvida em **10/12/2026**: o banco (`pg_dump`) e estes scripts levam tudo para outro servidor.
