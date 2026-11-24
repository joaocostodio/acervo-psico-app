# Acervo Psico — o app

Assistente de pesquisa **100% local** sobre o acervo do CREPOP/CFP: busca híbrida
(sentido + palavra), leitor de PDF com grifo e perguntas à IA com citação de página.
Como funciona por dentro: [../docs/arquitetura.md](../docs/arquitetura.md).
Segurança: [../docs/seguranca.md](../docs/seguranca.md).

## Onde roda

VM do LARCC (Ubuntu, 3 vCPUs, 12 GB, sem GPU), cedida até 10/12/2026.

| Peça | Onde | Acesso |
|---|---|---|
| Tela + API (FastAPI/uvicorn) | serviço `acervo-psico`, `/opt/crepop/backend` | `127.0.0.1:8000` |
| nginx | porta 80 da VM | público: **http://138.94.76.170:22233** |
| PostgreSQL 16 + pgvector | container `crepop-pg` | `127.0.0.1:5432` |
| Ollama (IA) | serviço `ollama` | `127.0.0.1:11434` |
| PDFs | `/opt/crepop/dados/acervo` | servidos pelo app, nunca direto |
| Backups | `/opt/crepop/backups` | cron diário às 3h |

O caminho `/opt/crepop` ficou do nome antigo do projeto: o banco guarda o caminho de
cada PDF, então renomear a pasta exigiria atualizar o banco. Não vale o risco.

## Instalar ou atualizar (na VM, como root)

```bash
# 1. banco (só na primeira vez)
cd app && POSTGRES_PASSWORD=<senha> docker compose up -d

# 2. copiar app/backend para /opt/crepop/backend e app/deploy para /opt/crepop/deploy
#    (primeira vez: python3 -m venv /opt/crepop/backend/.venv)

# 3. montar o resto à mão: dependências Python (requirements.txt), PDF.js em static/,
#    .env a partir do .env.example, migrar.py, modelo da IA (ollama create acervo-psico
#    -f ia/Modelfile), serviço systemd, nginx, firewall e backup (ver docs/como-foi-feito.md)

# 4. usuário de acesso
cd /opt/crepop/backend && .venv/bin/python criar_usuario.py acervo "Psicologia SETREM"

systemctl restart acervo-psico
```

O `.env` (em `/opt/crepop/backend/.env`) é criado na instalação; o modelo de
referência é [`.env.example`](.env.example). Ele **não vai para o git**.

## Ingerir PDFs novos

Não existe upload pela web, de propósito. Na VM:

```bash
cp novos/*.pdf /opt/crepop/dados/acervo/
cd /opt/crepop/backend && .venv/bin/python ingest_all.py /opt/crepop/dados/acervo
```

O título vem do nome do arquivo (`2022 - RT - CAPS.pdf`). PDF já ingerido (mesmo hash)
é pulado. Leva cerca de 4 a 5 min por PDF, por causa dos embeddings em CPU.

## Comandos do dia a dia

```bash
systemctl status acervo-psico            # o app está de pé?
journalctl -u acervo-psico -f            # log (inclui login que falhou)
ollama ps                                # modelos carregados na memória
.venv/bin/python avaliar.py              # nota da IA nas perguntas-teste
.venv/bin/python migrar.py               # depois de mudar schema.sql ou vocabulario.py
NOVA_SENHA=... .venv/bin/python criar_usuario.py acervo   # trocar a senha
NOVA_SENHA=... .venv/bin/python criar_usuario.py joaoadm "João (admin)" --admin   # conta que vê /uso
bash /opt/crepop/teste-ataque.sh         # prova de privilégio mínimo do banco
bash app/deploy/diagnostico.sh           # só leitura: serviços, SSH, nginx, uso, backup, ollama
.venv/bin/python avaliar.py <modelo> --saida r.json   # grava as respostas inteiras para comparar modelos
.venv/bin/python reindexar.py <modelo> <coluna>   # vetores com outro modelo numa coluna livre, sem parar a busca
.venv/bin/python pre_responder.py        # respostas prontas (o cron já roda às 1h; log em /var/log/acervo-prontas.log)
```

Se mudar as obras do acervo (PDF novo), o mapa do acervo (`mapa.py`) se refaz sozinho ao
reiniciar o app; obra nova também precisa entrar no dicionário `OBRAS` do `mapa.py`, com
um nome curto e os assuntos.

Depois de ingerir PDFs novos, rode `migrar.py`: ele calcula a página impressa das páginas
novas. Obra nova também precisa da referência ABNT em `referencias.py` (copiada da ficha
catalográfica do PDF); sem ela, a tela monta uma referência provisória e avisa.

## API

| Rota | O que faz | Login |
|---|---|---|
| `GET /entrar`, `POST /entrar`, `POST /sair` | tela de login, entrar, sair | — |
| `GET /saude` | o servidor está de pé? | — |
| `GET /` | a tela | ✔ |
| `GET /eu`, `GET /estatisticas` | usuário logado; números do acervo e fila da IA | ✔ |
| `GET /publicacoes` | as fontes (painel da esquerda), com o ano certo e a referência ABNT de cada uma (`referencias.py`) | ✔ |
| `GET /pdf/{id}` | o PDF da versão vigente | ✔ |
| `GET /pagina-impressa/{id}/{pagina_pdf}` | a página do livro de uma página do PDF (`pagina_impressa`, `pagina_impressa_fim` em página dupla; `null` se não achada). 404 se a página não tem texto | ✔ |
| `POST /buscar` `{termo, k?, ids_publicacao?}` | busca híbrida com grifos e equivalências | ✔ |
| `POST /preparar` `{ids_pagina, termo_busca?}` | a IA começa a ler as páginas escolhidas enquanto a pessoa digita | ✔ |
| `POST /perguntar` `{pergunta, k?, ids_publicacao?, ids_pagina?, termo_busca?}` | resposta da IA em streaming (NDJSON); pergunta repetida sobre as mesmas páginas sai da tabela `resposta_guardada` na hora | ✔ |
| `POST /avaliar` `{id_consulta, util, comentario?}` | 👍/👎 numa resposta da IA (só quem perguntou, uma vez; comentário com nome/CPF mascarado) | ✔ |
| `GET /uso`, `GET /uso/dados` | medidor de uso: aparelhos, buscas, perguntas, PDFs, por dia e por hora; desempenho da Susmi (tempo até a 1ª palavra, tempo total, velocidade); saúde do servidor (disco, memória, carga, último backup) | só admin (para os outros, 404) |
| `POST /buscar`, `POST /perguntar` (resultados) | cada página vem com `pagina_impressa` (o número do livro, para citar em ABNT) além da página do PDF | ✔ |

O medidor grava cada ação na tabela `evento_uso` (tipo e hora, sem IP nem texto; um apelido
anônimo do login conta aparelhos distintos). Contas `--admin` não entram na contagem. O
`backup.sh` apaga eventos com mais de 12 meses.

## Status

- [x] Fundação na VM (Ollama, Postgres + pgvector, Docker)
- [x] Ingestão do acervo: 41 PDFs, 5.551 páginas
- [x] Busca híbrida (sentido + palavra) com vocabulário controlado
- [x] Leitor PDF.js com grifo e navegação entre ocorrências
- [x] IA com citação de página, streaming e fila
- [x] Login, limites, papel de banco restrito, firewall, backup, LGPD (prazo de guarda)
- [x] Medidor de uso (`/uso`, só admin) e script de diagnóstico (`deploy/diagnostico.sh`)
- [x] Susmi: conversa simples sem IA, nome/CPF de paciente mascarado, avaliação com perguntas-teste
- [x] Curadoria (fase 2, 20/10/2026): categoria, eixo temático e leis — fecha as 12 tabelas do lógico
- [x] 👍/👎 nas respostas, respostas guardadas para pergunta repetida
- [x] Respostas da IA com marca d'água "GERADO POR IA" e aviso para conferir na fonte
- [x] Atualização de 03/11/2026: "Citar" em ABNT com a página do livro (94% das páginas), ano
      certo das obras, modo texto longo (artigo, resumo expandido), respostas com subtítulos e
      listas, "Copiar com referências", impressão, modo escuro, fontes no celular, últimas
      pesquisas, painel com desempenho da IA e saúde do servidor, IA aquecida ao iniciar
- [x] 03/11/2026 (noite): busca por sentido com `embeddinggemma` (8 consultas melhores, 7
      empates em 15), mapa do acervo sempre lido pela Susmi, respostas prontas de madrugada;
      prova das 15 perguntas: 15/15, média de 95 s
      ([resumo do dia](../docs/atualizacao-2026-11-03.md))
- [x] 10/11/2026: leis, normas do CFP e manuais do governo (77 obras), caderno de pesquisa,
      busca que acha a obra citada; à noite, **trecho grifado** ("de onde veio" a frase da
      resposta), **linha do tempo** e **ficha de cada obra** (resumo da Susmi feito de madrugada,
      `gerar_fichas.py`) ([detalhes](../docs/acervo-ampliado-2026-11-10.md))
- [ ] HTTPS (depende de domínio do LARCC)
- [ ] Um usuário por pessoa (hoje: usuário de teste compartilhado)
- [ ] Revisão dos eixos e sinônimos pelas colegas da Psicologia ([planilha](../docs/revisao-vocabulario-e-eixos.xlsx))
