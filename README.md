# Acervo Psico

Pesquisa inteligente nas **Referências Técnicas do CREPOP/CFP**: 41 publicações e
5.551 páginas sobre a atuação da Psicologia nas políticas públicas. Funciona como um
"NotebookLM" próprio, **100% local**: a IA roda num servidor do LARCC/SETREM e nada sai
para a internet.

## Acesso para teste

| | |
|---|---|
| **Endereço** | http://138.94.76.170:22233 |
| **Usuário** | `acervo` |
| **Senha** | pedir ao autor (não fica no repositório) |

É a conta compartilhada de teste (a mesma das colegas da Psicologia). Depois de 10
senhas erradas em 15 minutos, quem errou fica bloqueado por 15 minutos naquele login (a
senha certa continua entrando, para um colega da mesma rede não trancar os outros).

| Faz | Como |
|---|---|
| **Buscar** pelo sentido, não só pela palavra | "agressão contra mulher" acha páginas que dizem "violência contra a mulher" |
| Mostrar **por que** achou | "Também busquei: violência, maus-tratos (para agressão)" |
| Abrir o PDF **na página certa, com as palavras grifadas** | Leitor PDF.js com ▲▼ para pular entre as ocorrências |
| **Perguntar à IA** | Ela lê as páginas mais relevantes e responde citando cada uma (`[p. 32]`), com o texto aparecendo enquanto é escrito |
| **Leis e normas** na íntegra | Código de Ética, resoluções do CFP e 19 leis da área (Maria da Penha, ECA, Reforma Psiquiátrica…), com referência ABNT pronta ([acervo ampliado](docs/acervo-ampliado-2026-11-10.md)) |
| Proteger o acervo | Login, limites, banco com privilégio mínimo, backup diário ([segurança](docs/seguranca.md)) |

Projeto da disciplina de Banco de Dados (SETREM), em parceria com a Psicologia. Este repositório traz só o código do app; a parte da disciplina (MER, modelo lógico, artigo e entregas) não está incluída.

## Documentação

| Para | Leia |
|---|---|
| **Como foi feito, passo a passo** (do zero ao sistema no ar, com checklist) | [docs/como-foi-feito.md](docs/como-foi-feito.md) |
| Entender como o sistema funciona por dentro | [docs/arquitetura.md](docs/arquitetura.md) |
| Segurança: camadas, prova de ataque, limites | [docs/seguranca.md](docs/seguranca.md) |
| O que entrou no acervo em 10/11/2026 (leis, normas do CFP, manuais do governo) e por que não "treinar" a IA | [docs/acervo-ampliado-2026-11-10.md](docs/acervo-ampliado-2026-11-10.md) |
| Rodar, instalar e operar o app | [app/README.md](app/README.md) |
| Como o NotebookLM funciona (inspiração) | [docs/notebooklm-engenharia-reversa.md](docs/notebooklm-engenharia-reversa.md) |

## Estrutura

```
acervo-psico-app/
  README.md              este arquivo (o mapa: comece por aqui)
  docs/                  documentação técnica (arquitetura, segurança, IA, atualizações)
  relatorios/            relatórios de uso puxados da VM (só local, fora do git)
  app/                   o sistema que roda na VM
    backend/             API FastAPI, busca híbrida, IA, tela (static/)
      ia/                modelo próprio da IA (Modelfile) e perguntas de avaliação
    deploy/              instalação na VM: serviço, nginx, backup, teste de ataque
```

## Tecnologias

PostgreSQL 16 + **pgvector** (vetores) + busca textual em português · **Ollama** (IA local:
`nomic-embed-text` para embeddings, modelo de linguagem para as respostas) · FastAPI
(Python) · PDF.js · nginx · Docker · VM Ubuntu do LARCC (3 vCPUs, 12 GB, sem GPU).
