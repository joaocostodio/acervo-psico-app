# Segurança do Acervo Psico

O portal fica aberto na internet (http://138.94.76.170:22233) para as colegas da
Psicologia testarem. A proteção é em **camadas**: se uma falhar, a próxima segura.
A ideia central é o **privilégio mínimo**: cada parte do sistema só consegue fazer o
que precisa, e nada além.

```
Internet ──► LARCC (porta 22233) ──► VM: firewall ──► nginx ──► app (FastAPI) ──► Postgres
                                      só 22 e 80     limites     login, limites    papel restrito
                                                     por IP      por sessão        (só lê o acervo)
```

## As camadas

| Camada | O que faz | Onde está |
|---|---|---|
| **Firewall (ufw)** | Só entram SSH (22) e web (80). Banco (5432), IA (11434) e app (8000) escutam só em `127.0.0.1`: nem existem para quem está fora da VM | configuração da VM |
| **nginx** | Limita requisições **por pessoa** (IP + cookie de sessão: 40/s e 60 conexões), porque numa sala todos saem pelo mesmo IP e um aluno com script não pode esgotar a cota da turma; e **por IP** só contra enxurrada (300/s, 1.000 conexões). Cookie inventado não dá cota nova útil: sem sessão válida o app responde 401 na hora. Tentativas de login: 120/min por IP. Corpo de até 64 KB (não há upload) e timeouts curtos contra conexões "penduradas" | `app/deploy/nginx-acervo-psico.conf` |
| **Login** | Tudo exige login, menos a tela de entrada. Senha guardada só como hash **scrypt** com sal. Login inexistente gasta o mesmo tempo que login errado, para não revelar quais existem. 10 erros em 15 min bloqueiam **aquele login vindo daquele IP** por 15 min (não o IP inteiro: numa sala todos saem pelo mesmo IP, e um aluno chutando senhas trancaria a turma e quem apresenta). Durante o bloqueio, conta de administrador não tenta mais; conta comum (a da turma, de senha conhecida) ainda entra com a senha certa, para um aluno não trancar os colegas de propósito | `app/backend/seguranca.py`, `main.py` |
| **Fila da IA com prioridade** | A conta administradora passa na frente da fila e tem uma das 2 vagas da IA guardada (`IA_VAGAS_RESERVADAS_ADMIN=1`): as outras contas respondem uma por vez, e a pergunta de quem apresenta sai na hora mesmo com a sala inteira perguntando. `0` no `.env` devolve as 2 vagas para todos | `seguranca.py` (`Vagas`), `config.py` |
| **Sessão** | Cookie assinado (HMAC-SHA256), `HttpOnly` (JavaScript não lê), `SameSite=Strict` (outro site não usa), expira em 12 h. POST de outra origem é recusado (contra CSRF) | `seguranca.py`, `main.py` |
| **Limites de uso** | 30 buscas/min e 3 perguntas/min **por sessão**; a IA aceita no máximo 4 perguntas na fila e recusa o resto com aviso (não deixa a VM travar). Texto da busca até 300 caracteres, pergunta até 1.000 | `config.py`, `main.py` |
| **Sem upload pela web** | Não existe rota para enviar PDF. O acervo só muda por script **dentro da VM** (`ingest_all.py`), com o papel administrador | `main.py`, `ingest.py` |
| **Banco: papel restrito** | O app conecta como `acervo_app`, que só tem `SELECT` no acervo e `INSERT` no histórico. **Não tem `DELETE`, `UPDATE`, `DROP`, `TRUNCATE`, `ALTER` nem `CREATE`.** Cada comando tem no máximo 20 s; no máximo 10 conexões | `app/backend/migrar.py` |
| **Consultas parametrizadas** | Todo texto do usuário vai ao banco como parâmetro (`%s`), nunca colado no SQL: não há como injetar comando | `rag.py` |
| **Serviço endurecido** | O app roda com o usuário de sistema `acervo`, sem shell, sem poder escrever em disco (`ProtectSystem=strict`), sem ganhar privilégio. Não é dono do código nem dos PDFs | `app/deploy/acervo-psico.service` |
| **Cabeçalhos** | CSP (só carrega script/estilo do próprio site e do Google Fonts), `X-Frame-Options`, `nosniff`, `Referrer-Policy`; páginas sem cache; `/docs` da API desligado | `main.py` |
| **Backup diário** | `pg_dump` às 3h, guarda 14 dias. Se algo der muito errado, volta-se ao dia anterior | `app/deploy/backup.sh` |
| **LGPD** | Cada consulta grava finalidade e prazo de guarda (12 meses); a rotina diária apaga o que venceu. A busca simples não guarda quais páginas a pessoa viu | `schema.sql`, `backup.sh` |

## Prova: tentativas de ataque com o papel do app

Teste feito em 19/10/2026, conectando no banco **com a mesma credencial que o app usa**
(o pior caso: alguém que tivesse achado uma brecha e conseguido mandar SQL):

| Tentativa | Resultado |
|---|---|
| `DROP TABLE pagina` | `ERROR: must be owner of table pagina` |
| `DELETE FROM publicacao` | `ERROR: permission denied for table publicacao` |
| `UPDATE pagina SET conteudo_texto='x'` | `ERROR: permission denied for table pagina` |
| `TRUNCATE registro_consulta` | `ERROR: permission denied for table registro_consulta` |
| `INSERT INTO publicacao (titulo) VALUES ('lixo')` | `ERROR: permission denied for table publicacao` |
| `CREATE TABLE lixo (x int)` | `ERROR: permission denied for schema public` |
| `DELETE FROM registro_consulta` | `ERROR: permission denied for table registro_consulta` |
| `ALTER TABLE usuario ADD COLUMN x int` | `ERROR: must be owner of table usuario` |

E pela web, sem login: `GET /` → 303 (vai para a tela de login), `POST /buscar` → 401,
`/docs` → 401, `POST /ingerir` → 401 (a rota nem existe mais).

Para repetir o teste, rode na VM o bloco "ataque" de [`app/deploy/teste-ataque.sh`](../app/deploy/teste-ataque.sh).

## Tentativas de invasão no SSH (30/10 a 09/11/2026)

Levantado em 09/11/2026 no log do SSH da VM (`journalctl -u ssh`):

| Origem | Senhas erradas | Como | Acertos |
|---|---|---|---|
| 209.99.188.168 (provedor no exterior, SKN Subnet & Telecom) | 6.551 | Robô de força bruta por dicionário: 128 tentativas/hora, dia e noite, em 2 ondas (30–31/10 e 05–06/11); 2.720 vezes como `root`, o resto com nomes de lista pronta (`ubuntu`, `admin`, `oracle`, `postgres`, `nvidia`, `hadoop`…). Nunca abriu o site | 0 |
| 45.173.166.132 e 177.129.8.112 (provedores brasileiros) | 64 e 77 | Usuário em português `suporte`, `root`, `ubuntu`; o primeiro também abriu o site 2 vezes | 0 |

Todos os logins aceitos vieram do salto do LARCC (máquina da rede interna). Não entrou porque a
senha do `root` não está em lista nenhuma, e banco, IA e app nem escutam fora da VM.
Reforço preparado em [`app/deploy/endurecer-ssh.sh`](../app/deploy/endurecer-ssh.sh) (SSH só pela
rede do LARCC, sem `root`/senha para quem vem de fora, fail2ban); aplicar com o OK do responsável.

## O que ainda NÃO está protegido (limites conhecidos)

- **Sem HTTPS.** O LARCC encaminha só HTTP. A senha viaja sem criptografia entre o
  navegador e o servidor: quem estiver na mesma rede Wi-Fi pode interceptá-la. Por isso
  a senha de teste é **descartável** e não deve ser reaproveitada em lugar nenhum.
  Para produção: pedir ao LARCC um domínio + certificado (Let's Encrypt) no nginx.
- **Usuário compartilhado.** Todas as colegas entram com o mesmo `acervo`. O histórico
  não distingue quem perguntou o quê (o que, para a LGPD, até ajuda). Para produção:
  um usuário por pessoa (`criar_usuario.py`).
- **Senha fraca de teste** (a senha não fica no repositório; o João passa às colegas). Trocar depois do período de testes:
  `NOVA_SENHA=... .venv/bin/python criar_usuario.py acervo`.
- **Limites em memória.** Os contadores de limite zeram se o app reiniciar. Suficiente
  para um protótipo com um servidor só.
- **Prompt injection.** Os PDFs são do CFP (fonte confiável) e a IA só lê, não executa
  nada nem tem acesso a ferramentas — o pior caso é uma resposta errada, por isso a tela
  sempre mostra a página de origem para conferir.

## Operação

```bash
# na VM (root)
systemctl status acervo-psico          # o app
journalctl -u acervo-psico -f          # log do app (inclui logins que falharam)
tail -f /var/log/nginx/access.log      # quem acessou
ls -la /opt/crepop/backups             # backups
cat /var/log/acervo-backup.log         # resultado do backup + limpeza LGPD

# restaurar um backup (sobrescreve o banco!)
docker exec -i crepop-pg pg_restore -U postgres -d crepop --clean < /opt/crepop/backups/ARQUIVO.dump
```
