"""Segurança do portal: senha com hash, cookie de sessão assinado, limites por IP e fila da IA.

Tudo com a biblioteca padrão do Python (hashlib/hmac), sem dependência nova.
"""
import base64
import hashlib
import hmac
import secrets
import threading
import time
from collections import defaultdict, deque

from config import config

# ---------- Senha ----------
# scrypt é um hash "caro de propósito": testar milhões de senhas fica inviável.
_N, _R, _P = 2**14, 8, 1


def gerar_hash(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _N, _R, _P, base64.b64encode(sal).decode(), base64.b64encode(h).decode()
    )


def conferir_senha(senha: str, guardado: str) -> bool:
    try:
        _, n, r, p, sal, h = guardado.split("$")
        calc = hashlib.scrypt(
            senha.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32
        )
        return hmac.compare_digest(calc, base64.b64decode(h))
    except (ValueError, TypeError):
        return False


# Hash de uma senha qualquer: quando o login não existe, ainda gastamos o mesmo tempo
# conferindo, para não revelar pelo tempo de resposta quais logins existem.
HASH_FALSO = gerar_hash(secrets.token_hex(8))


# ---------- Sessão (cookie assinado) ----------
COOKIE = "acervo_sessao"


def _assinar(dados: str) -> str:
    return hmac.new(config.secret_key.encode(), dados.encode(), hashlib.sha256).hexdigest()


def criar_sessao(id_usuario: int) -> str:
    expira = int(time.time()) + config.sessao_horas * 3600
    dados = f"{id_usuario}.{expira}"
    return f"{dados}.{_assinar(dados)}"


def ler_sessao(valor: str | None) -> int | None:
    """Devolve o id do usuário se o cookie for autêntico e não tiver expirado."""
    if not valor or valor.count(".") != 2:
        return None
    id_usuario, expira, assinatura = valor.split(".")
    if not hmac.compare_digest(assinatura, _assinar(f"{id_usuario}.{expira}")):
        return None
    if not expira.isdigit() or int(expira) < time.time() or not id_usuario.isdigit():
        return None
    return int(id_usuario)


# ---------- Limite de requisições por IP (janela deslizante, em memória) ----------
class Limitador:
    def __init__(self, maximo: int, janela_s: int):
        self.maximo, self.janela = maximo, janela_s
        self._eventos: dict[str, deque] = defaultdict(deque)
        self._trava = threading.Lock()

    def _limpar(self, fila: deque, agora: float) -> None:
        while fila and fila[0] <= agora - self.janela:
            fila.popleft()

    def permitir(self, chave: str) -> bool:
        """Conta uma tentativa; False se a chave já estourou o limite na janela."""
        agora = time.time()
        with self._trava:
            fila = self._eventos[chave]
            self._limpar(fila, agora)
            if len(fila) >= self.maximo:
                return False
            fila.append(agora)
            return True

    def bloqueado(self, chave: str) -> bool:
        agora = time.time()
        with self._trava:
            fila = self._eventos.get(chave)
            if not fila:
                return False
            self._limpar(fila, agora)
            return len(fila) >= self.maximo

    def registrar(self, chave: str) -> None:
        with self._trava:
            self._eventos[chave].append(time.time())

    def zerar(self, chave: str) -> None:
        with self._trava:
            self._eventos.pop(chave, None)


falhas_login = Limitador(config.limite_login_falhas, 15 * 60)
limite_buscas = Limitador(config.limite_buscas_min, 60)
limite_perguntas = Limitador(config.limite_perguntas_min, 60)


# ---------- Fila da IA ----------
# A IA roda em CPU e responde até `paralelo` perguntas ao mesmo tempo (o Ollama precisa
# de OLLAMA_NUM_PARALLEL igual). Em vez de deixar acumular pedidos até travar a VM,
# aceitamos poucos na fila e recusamos o resto com aviso.
class Vagas:
    """As vagas da IA (como um semáforo), com prioridade para o administrador.

    - `reserva` vagas ficam guardadas para quem tem prioridade: com 2 vagas e reserva 1,
      as outras contas usam uma vaga por vez e a outra fica livre para o administrador
      (numa apresentação, a pergunta de quem apresenta sai na hora, mesmo com a sala
      inteira perguntando).
    - Com administrador esperando, uma vaga que se solta vai para ele primeiro."""

    def __init__(self, total: int, reserva: int = 0):
        self._livres = total
        self.reserva = max(0, min(reserva, total - 1))
        self._prio_esperando = 0
        self._cond = threading.Condition()

    def _pode(self, prioridade: bool) -> bool:
        if prioridade:
            return self._livres > 0
        return self._livres > self.reserva and self._prio_esperando == 0

    def acquire(self, blocking: bool = True, timeout: float | None = None,
                prioridade: bool = False) -> bool:
        with self._cond:
            if self._pode(prioridade):
                self._livres -= 1
                return True
            if not blocking:
                return False
            if prioridade:
                self._prio_esperando += 1
            try:
                ok = self._cond.wait_for(lambda: self._pode(prioridade), timeout)
                if ok:
                    self._livres -= 1
                return ok
            finally:
                if prioridade:
                    self._prio_esperando -= 1

    def release(self) -> None:
        with self._cond:
            self._livres += 1
            self._cond.notify_all()


class FilaIA:
    def __init__(self, maximo: int, paralelo: int, reserva: int = 0):
        self.maximo, self.paralelo = maximo, paralelo
        self._n = 0
        self._trava = threading.Lock()
        self._vagas = Vagas(paralelo, reserva)

    def entrar(self, prioridade: bool = False) -> bool:
        """Entra na fila; o administrador tem lugar mesmo com a fila cheia."""
        with self._trava:
            if self._n >= self.maximo + (self.paralelo if prioridade else 0):
                return False
            self._n += 1
            return True

    def sair(self) -> None:
        with self._trava:
            self._n -= 1

    @property
    def tamanho(self) -> int:
        return self._n

    @property
    def vez(self) -> Vagas:
        return self._vagas


fila_ia = FilaIA(config.fila_ia_max, config.ia_paralelo, config.ia_vagas_reservadas_admin)
