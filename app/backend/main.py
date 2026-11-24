"""API do Acervo Psico — login, busca híbrida, perguntas à IA local e a tela.

Proteções (ver docs/seguranca.md):
- tudo exige login, menos a tela de entrada e /saude;
- o banco é acessado por um papel que só lê o acervo e só acrescenta histórico;
- não existe envio de PDF pela web: o acervo só muda por script dentro da VM;
- limites por IP (login, buscas, perguntas), fila curta para a IA e tamanho máximo de texto;
- cookie assinado, HttpOnly e SameSite=Strict; cabeçalhos de segurança em toda resposta.
"""
import json
import threading
import time
import traceback
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import conversa
import db
import ollama_client
import rag
import uso
from config import config
from seguranca import (
    COOKIE, HASH_FALSO, conferir_senha, criar_sessao, falhas_login, fila_ia,
    ler_sessao, limite_buscas, limite_perguntas,
)

STATIC = Path(__file__).parent / "static"
PUBLICOS = {"/entrar", "/saude"}

app = FastAPI(title="Acervo Psico", docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
def _startup():
    db.init()
    threading.Thread(target=_aquecer_ia, daemon=True).start()


def _aquecer_ia():
    """Ao subir, a Susmi já lê as instruções fixas (Modelfile + começo do prompt) e os
    modelos ficam na memória. O Ollama guarda essa leitura (cache de prompt) e a 1ª
    pergunta do dia só lê as páginas, não as ~1.000 palavras de regras e exemplos."""
    for tentativa in range(10):
        try:
            ollama_client.embed(["aquecer"])
            # As duas vagas da IA (OLLAMA_NUM_PARALLEL=2) leem ao mesmo tempo: assim as duas
            # ficam com as instruções e o mapa do acervo no cache.
            prefixo = rag.prefixo_fixo()
            vagas = [threading.Thread(target=ollama_client.ler_antes, args=(prefixo,)) for _ in range(config.ia_paralelo)]
            for v in vagas:
                v.start()
            for v in vagas:
                v.join()
            print(f"[ia] aquecida: modelo carregado e instruções + mapa do acervo já lidos "
                  f"({len(prefixo)} caracteres)", flush=True)
            return
        except Exception as e:  # noqa: BLE001 — Ollama ainda subindo: tenta de novo
            print(f"[ia] aquecimento falhou ({e}); tentativa {tentativa + 1}", flush=True)
            time.sleep(30)


# ---------- Middleware: login obrigatório + cabeçalhos de segurança ----------

CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; "
    "frame-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
)


def ip_de(request: Request) -> str:
    # O uvicorn só escuta em 127.0.0.1: quem chega é o nginx, que põe o IP real aqui.
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "?")


def chave_uso(request: Request) -> str:
    """Limite de uso por sessão de login (cada aba logada conta separado), não só por IP:
    numa sala de aula todo mundo sai pelo mesmo IP do Wi-Fi."""
    return ip_de(request) + "|" + (request.cookies.get(COOKIE) or "")[-16:]


@app.middleware("http")
async def proteger(request: Request, call_next):
    caminho = request.url.path
    # Pedido que altera algo (POST) só vale vindo da própria página (contra CSRF).
    if request.method == "POST":
        origem = request.headers.get("origin")
        if origem and urlparse(origem).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Origem não permitida."}, status_code=403)

    request.state.id_usuario = ler_sessao(request.cookies.get(COOKIE))
    if caminho not in PUBLICOS and request.state.id_usuario is None:
        if request.method == "GET" and caminho == "/":
            resp = RedirectResponse("/entrar", status_code=303)
        else:
            resp = JSONResponse({"detail": "Faça login para continuar."}, status_code=401)
    else:
        resp = await call_next(request)

    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = CSP
    if caminho in ("/", "/entrar") or caminho.startswith(("/buscar", "/perguntar", "/eu", "/uso")):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ---------- Login ----------

class Login(BaseModel):
    login: str = Field(min_length=1, max_length=60)
    senha: str = Field(min_length=1, max_length=200)


@app.get("/entrar", include_in_schema=False)
def tela_entrar(request: Request):
    if request.state.id_usuario is not None:
        return RedirectResponse("/", status_code=303)
    return FileResponse(STATIC / "entrar.html")


@app.post("/entrar")
def entrar(req: Login, request: Request):
    ip = ip_de(request)
    login = req.login.strip().lower()
    # Bloqueio por login + IP (não pelo IP todo): na sala, todos dividem o IP do Wi-Fi.
    chave = f"{ip}|{login}"
    bloqueado = falhas_login.bloqueado(chave)
    with db.pool.connection() as conn:
        linha = conn.execute(
            "SELECT id_usuario, hash_senha, admin FROM usuario WHERE login = %s AND ativo",
            (login,),
        ).fetchone()
    # Bloqueado: administrador (e login inexistente) não tenta mais. Conta comum
    # (a compartilhada da turma, de senha conhecida) ainda entra com a senha CERTA:
    # senão um aluno errando 10 vezes de propósito tranca a sala inteira, que divide o IP.
    if bloqueado and (linha is None or linha[2]):
        raise HTTPException(429, "Muitas tentativas erradas. Aguarde 15 minutos.")
    ok = conferir_senha(req.senha, linha[1] if linha else HASH_FALSO) and linha is not None
    if not ok:
        falhas_login.registrar(chave)
        print(f"[login] falha para '{req.login[:60]}' de {ip}", flush=True)
        if bloqueado:
            raise HTTPException(429, "Muitas tentativas erradas. Aguarde 15 minutos.")
        raise HTTPException(401, "Usuário ou senha incorretos.")
    falhas_login.zerar(chave)
    sessao = criar_sessao(linha[0])
    uso.registrar("login", linha[0], sessao)
    resp = JSONResponse({"ok": True})
    resp.set_cookie(
        COOKIE, sessao, max_age=config.sessao_horas * 3600,
        httponly=True, samesite="strict", path="/",
    )
    return resp


@app.post("/sair")
def sair():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE, path="/")
    return resp


@app.get("/eu")
def eu(request: Request):
    with db.pool.connection() as conn:
        linha = conn.execute(
            "SELECT login, nome, admin FROM usuario WHERE id_usuario = %s AND ativo",
            (request.state.id_usuario,),
        ).fetchone()
    if not linha:
        raise HTTPException(401, "Sessão inválida.")
    return {"login": linha[0], "nome": linha[1] or linha[0], "admin": linha[2]}


def contar(request: Request, tipo: str, id_publicacao: int | None = None) -> None:
    uso.registrar(tipo, request.state.id_usuario, request.cookies.get(COOKIE), id_publicacao)


# ---------- Tela e acervo ----------

@app.get("/", include_in_schema=False)
def tela(request: Request):
    contar(request, "tela")
    return FileResponse(STATIC / "index.html")


# ---------- Medidor de uso (só administrador; para os outros a rota "não existe") ----------

@app.get("/uso", include_in_schema=False)
def tela_uso(request: Request):
    if not uso.eh_admin(request.state.id_usuario):
        raise HTTPException(404, "Not Found")
    return FileResponse(STATIC / "uso.html")


@app.get("/uso/dados")
def uso_dados(request: Request):
    if not uso.eh_admin(request.state.id_usuario):
        raise HTTPException(404, "Not Found")
    return uso.resumo()


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/saude")
def saude():
    return {"status": "ok"}


@app.get("/estatisticas")
def estatisticas():
    with db.pool.connection() as conn:
        pubs, pags = conn.execute(
            """SELECT count(DISTINCT v.id_publicacao), count(p.id_pagina)
               FROM versao_arquivo v LEFT JOIN pagina p USING (id_versao)
               WHERE v.situacao_vigencia"""
        ).fetchone()
    return {"publicacoes": pubs, "paginas_no_acervo": pags, "fila_ia": fila_ia.tamanho}


@app.get("/publicacoes")
def publicacoes():
    return rag.listar_publicacoes()


@app.get("/pdf/{id_publicacao}")
def pdf(id_publicacao: int, request: Request):
    """Serve o PDF da publicação (o caminho vem do banco, nunca do cliente)."""
    caminho = rag.caminho_pdf(id_publicacao)
    if not caminho or not Path(caminho).is_file():
        raise HTTPException(404, "PDF não encontrado.")
    # O leitor pede o arquivo uma vez inteiro e depois aos pedaços (Range):
    # só o primeiro pedido conta como "PDF aberto".
    if "range" not in request.headers:
        contar(request, "pdf", id_publicacao)
    return FileResponse(caminho, media_type="application/pdf", headers={"Content-Disposition": "inline"})


@app.get("/ficha/{id_publicacao}")
def ficha(id_publicacao: int):
    """Ficha da obra (gerar_fichas.py, de madrugada): leis citadas, obras parecidas e o
    resumo da Susmi. O caminho é montado aqui com o id inteiro, nunca vem do cliente."""
    caminho = Path(config.fichas_dir) / f"{id_publicacao}.json"
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise HTTPException(404, "Ficha ainda não gerada.") from None


@app.get("/pagina-impressa/{id_publicacao}/{numero_pdf}")
def pagina_impressa(id_publicacao: int, numero_pdf: int):
    """Página do livro de uma página do PDF (para citar um trecho selecionado no leitor)."""
    if not 1 <= numero_pdf <= 5000:
        raise HTTPException(404, "Página não encontrada.")
    r = rag.pagina_impressa(id_publicacao, numero_pdf)
    if r is None:
        raise HTTPException(404, "Página não encontrada.")
    return r


# ---------- Busca e pergunta ----------

class Busca(BaseModel):
    termo: str = Field(min_length=1, max_length=300)
    k: int | None = Field(default=None, ge=1, le=20)
    ids_publicacao: list[int] | None = Field(default=None, max_length=500)


@app.post("/buscar")
def buscar(req: Busca, request: Request):
    """Modo rápido: acha as páginas (por sentido e por palavra), sem gerar texto."""
    if not req.termo.strip():
        raise HTTPException(400, "Termo vazio.")
    if not limite_buscas.permitir(chave_uso(request)):
        raise HTTPException(429, "Muitas buscas em pouco tempo. Espere um minuto.")
    resultado = rag.buscar(req.termo.strip(), req.k, req.ids_publicacao, request.state.id_usuario)
    contar(request, "busca")
    return resultado


class Pergunta(BaseModel):
    pergunta: str = Field(min_length=1, max_length=1000)
    k: int | None = Field(default=None, ge=1, le=8)
    ids_publicacao: list[int] | None = Field(default=None, max_length=500)
    # Pergunta sobre páginas já escolhidas na busca (em vez de buscar de novo):
    ids_pagina: list[int] | None = Field(default=None, min_length=1, max_length=5)
    termo_busca: str | None = Field(default=None, max_length=300)


class Preparo(BaseModel):
    ids_pagina: list[int] = Field(min_length=1, max_length=5)
    termo_busca: str | None = Field(default=None, max_length=300)


@app.post("/preparar")
def preparar(req: Preparo, request: Request):
    """Lê as páginas escolhidas antes de a pergunta chegar, se a IA estiver livre.

    A tela chama isto quando a pessoa clica em "Perguntar sobre estas páginas"; enquanto
    ela digita, a IA já leu. Se a IA estiver ocupada, não faz nada (não fura a fila)."""
    if not limite_buscas.permitir(chave_uso(request)):
        raise HTTPException(429, "Muitas ações em pouco tempo. Espere um minuto.")
    if fila_ia.tamanho >= fila_ia.paralelo or not fila_ia.entrar():
        return {"preparado": False}
    try:
        if not fila_ia.vez.acquire(blocking=False):
            return {"preparado": False}
        try:
            paginas, _ = rag.carregar_paginas(req.ids_pagina, req.termo_busca)
            rag.preparar(paginas)
        finally:
            fila_ia.vez.release()
    finally:
        fila_ia.sair()
    return {"preparado": True}


class Avaliacao(BaseModel):
    id_consulta: int
    util: bool
    comentario: str | None = Field(default=None, max_length=500)


@app.post("/avaliar")
def avaliar(req: Avaliacao, request: Request):
    """👍/👎 numa resposta da Susmi. Só quem perguntou avalia, e uma vez só."""
    if not limite_buscas.permitir(chave_uso(request)):
        raise HTTPException(429, "Muitas ações em pouco tempo. Espere um minuto.")
    comentario = None
    if req.comentario and req.comentario.strip():
        _, comentario = conversa.dados_pessoais(req.comentario.strip())  # LGPD também aqui
    with db.pool.connection() as conn:
        dono = conn.execute(
            "SELECT 1 FROM registro_consulta WHERE id_consulta = %s AND id_usuario = %s AND modo = 'perguntar'",
            (req.id_consulta, request.state.id_usuario),
        ).fetchone()
        if not dono:
            raise HTTPException(404, "Resposta não encontrada.")
        conn.execute(
            """INSERT INTO avaliacao_resposta (id_consulta, util, comentario) VALUES (%s, %s, %s)
               ON CONFLICT (id_consulta) DO NOTHING""",
            (req.id_consulta, req.util, comentario),
        )
    return {"ok": True}


def _linha(evento: dict) -> bytes:
    return (json.dumps(evento, ensure_ascii=False) + "\n").encode()


@app.post("/perguntar")
def perguntar(req: Pergunta, request: Request):
    """Modo IA, em streaming (NDJSON: um evento JSON por linha).

    1. {'tipo':'fontes'}     — as páginas que a IA vai ler (a tela já mostra);
    2. {'tipo':'pensamento'} — os passos da busca e o trecho de cada página que a IA lê,
                               para a tela mostrar enquanto ela lê;
    3. {'tipo':'fila'}       — enquanto as vagas da IA estão ocupadas (CPU, poucas por vez);
    4. {'tipo':'texto'}      — a resposta, pedaço a pedaço, conforme é escrita;
    5. {'tipo':'fim'}        — resposta completa + métricas (ou {'tipo':'erro'}).
    """
    t0 = time.monotonic()
    pergunta = req.pergunta.strip()
    if not pergunta:
        raise HTTPException(400, "Pergunta vazia.")
    if not limite_perguntas.permitir(chave_uso(request)):
        raise HTTPException(429, "Muitas perguntas em pouco tempo. Espere um minuto.")
    # Nome/CPF de paciente: sai da pergunta antes da busca, da IA e do histórico (LGPD).
    tinha_dados, pergunta = conversa.dados_pessoais(pergunta)
    pronta = conversa.responder(pergunta)
    if pronta:  # "oi", "quem é você?": responde na hora, sem buscar nem usar a IA
        contar(request, "pergunta")
        corpo = [_linha({"tipo": "fontes", "fontes": [], "equivalencias": []}),
                 _linha({"tipo": "texto", "delta": pronta}),
                 _linha({"tipo": "fim", "resposta": pronta, "metricas": None})]
        return StreamingResponse(iter(corpo), media_type="application/x-ndjson",
                                 headers={"Cache-Control": "no-store"})
    # O administrador passa na frente e tem vaga guardada (ver seguranca.Vagas).
    admin = uso.eh_admin(request.state.id_usuario)
    if not fila_ia.entrar(prioridade=admin):
        raise HTTPException(503, "A Susmi está ocupada com outras perguntas. Tente de novo em alguns minutos.")
    contar(request, "pergunta")
    try:
        if req.ids_pagina:
            paginas, exp = rag.carregar_paginas(req.ids_pagina, req.termo_busca)
        else:
            paginas, exp = rag.recuperar(pergunta, req.k, req.ids_publicacao)
    except Exception:
        fila_ia.sair()
        raise
    id_usuario = request.state.id_usuario

    def eventos():
        tem_vez = False
        espera_ms = 0
        try:
            yield _linha({"tipo": "fontes", **rag.fontes_publicas(paginas, exp),
                          "longo": rag.eh_pedido_longo(pergunta)})
            yield _linha({"tipo": "pensamento", **rag.pensamento(paginas, exp, bool(req.ids_pagina))})
            # Resposta já guardada (mesma pergunta e páginas) não ocupa vaga da IA.
            if not rag.tem_resposta_guardada(pergunta, paginas):
                t_fila = time.monotonic()
                while not fila_ia.vez.acquire(timeout=2, prioridade=admin):
                    yield _linha({"tipo": "fila", "na_frente": max(1, fila_ia.tamanho - fila_ia.paralelo)})
                espera_ms = int((time.monotonic() - t_fila) * 1000)
                tem_vez = True
                yield _linha({"tipo": "lendo"})
            for ev in rag.responder_stream(pergunta, paginas, id_usuario, t0, espera_ms):
                if tinha_dados and ev["tipo"] == "fim":  # o aviso não depende da IA lembrar
                    ev["resposta"] = conversa.com_aviso(ev["resposta"])
                yield _linha(ev)
        except Exception:  # noqa: BLE001 — o erro vai para o log; a tela recebe aviso curto
            traceback.print_exc()
            yield _linha({"tipo": "erro", "detalhe": "Falha ao gerar a resposta. Tente de novo."})
        finally:
            if tem_vez:
                fila_ia.vez.release()
            fila_ia.sair()

    return StreamingResponse(
        eventos(), media_type="application/x-ndjson",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-store"},
    )
