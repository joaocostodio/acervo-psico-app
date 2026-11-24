"""Conversa simples com a Susmi: "oi", "quem é você?", "qual meu nome?", "obrigado".

Essas mensagens não são perguntas sobre o acervo. Mandá-las para a busca fazia a Susmi
ler 3 páginas sem relação e responder "Não encontrei isso nas páginas consultadas"
(visto nas conversas reais de 20/10/2026). Aqui elas ganham resposta na hora, sem IA.

Só responde quando a mensagem é SÓ isso: em "oi, como acolher uma vítima de violência?"
sobra uma pergunta de verdade, e ela segue para a busca normalmente.
"""
import re
import unicodedata

EXEMPLOS = (
    "\n\nPara uma boa resposta, pergunte sobre um tema da atuação da Psicologia, por exemplo:\n"
    "• Qual o papel do psicólogo no CAPS?\n"
    "• Como acolher uma mulher em situação de violência?\n"
    "• O que o acervo diz sobre sigilo profissional?"
)
QUEM_SOU = (
    "Eu sou a Susmi — Somente Um Sistema Muito Inteligente —, a assistente do Acervo Psico. "
    "Eu leio as Referências Técnicas do CREPOP/CFP, o Código de Ética e as resoluções do CFP "
    "o texto integral das leis da área (Maria da Penha, ECA, Reforma Psiquiátrica e outras) e manuais do Ministério da Saúde e da Assistência Social, "
    "e respondo citando a página de onde tirei "
    "cada informação, para você conferir no PDF. Não respondo de memória: se o acervo não "
    "trata do assunto, eu aviso. E rodo num servidor próprio, então suas perguntas não saem "
    "para a internet."
)

# (padrão, resposta). Os padrões olham o texto sem acento, em minúsculas e sem pontuação.
RESPOSTAS = [
    (r"\b(qual (e )?(o )?meu nome|(voce|vc) sabe (o )?meu nome|sabe quem eu sou|quem sou eu)\b",
     "Não sei o seu nome: eu não guardo dados pessoais de quem conversa comigo." + EXEMPLOS),
    (r"\b(quem (e|eh|es) (voce|vc|tu)|quem (e|eh) (a )?susmi|qual (e )?(o )?seu nome"
     r"|como (voce|vc) se chama|o que (e|eh|significa) (a )?susmi|(voce|vc) (e|eh) (uma )?(ia|robo|pessoa|humana?))\b",
     QUEM_SOU + EXEMPLOS),
    (r"\b(o que (voce|vc) (faz|sabe fazer|pode fazer)|como (voce|vc) funciona|como (eu )?(te )?uso"
     r"|como usar|para que (voce|vc) serve)\b",
     QUEM_SOU + EXEMPLOS),
    (r"^(obrigad[oa]|brigad[oa]|valeu|vlw|thanks|thank you)\b",
     "Por nada! Quando quiser, é só perguntar." + EXEMPLOS),
    (r"\b(nice to meet|prazer em|muito prazer|prazer)\b",
     "O prazer é meu! Eu sou a Susmi, a assistente do Acervo Psico." + EXEMPLOS),
    (r"^(oi+|ola|opa|bom dia|boa tarde|boa noite|hello|hi|hey|e ai|eai)\b",
     "Oi! Eu sou a Susmi, a assistente do Acervo Psico. Leio as Referências Técnicas do "
     "CREPOP/CFP, as normas do CFP e as leis da área, e respondo citando a página." + EXEMPLOS),
]
# Palavras que podem sobrar sem que a mensagem vire uma pergunta sobre o acervo.
SOBRAS = set(
    "e a o oi ola tudo bem bom boa susmi voce vc tu por favor aqui entao ok okay sim "
    "oh great you friend too me te muito obrigado obrigada amiga amigo querida legal "
    "como vai esta".split()
)


# ---------- Dados pessoais na pergunta (LGPD) ----------
# O modelo pequeno nem sempre lembra de pedir para tirar o nome/CPF do paciente. Aqui é
# garantido no código: o aviso sai sempre e os dados são mascarados ANTES de a pergunta
# ir para a busca, para a IA e para o histórico.
AVISO_DADOS = ("Por favor, não inclua nome nem documentos de pacientes aqui: tirei esses dados "
               "da sua pergunta antes de guardá-la. O acervo traz referências gerais, não "
               "orienta casos individuais; para o caso, procure supervisão profissional.")
_DOCUMENTO = re.compile(r"\b(CPF|RG|CNS|cart[aã]o do SUS|prontu[aá]rio)\b[\s:nNº°.-]*[\d.\-/]+", re.I)
_NUMERO_LONGO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")  # CPF sem rótulo
_MAIUSC = r"[A-ZÁÉÍÓÚÂÊÔÃÕÇ][a-záéíóúâêôãõç]+"
_NOME = re.compile(r"\b(paciente|cliente|usu[aá]ri[oa]|atendid[oa]|filh[oa]|menin[oa])\s+"
                   rf"({_MAIUSC}(?:\s+(?:(?:da|de|do|dos|das|e)\s+)?{_MAIUSC}){{0,3}})")


_AVISO_DA_IA = re.compile(r"\s*Por favor, n[ãa]o inclua nome[^.]*\.", re.I)


def com_aviso(resposta: str) -> str:
    """Aviso de dados pessoais no começo, sem repetir o aviso que a IA às vezes escreve."""
    return AVISO_DADOS + "\n\n" + _AVISO_DA_IA.sub("", resposta, count=1).strip()


def dados_pessoais(pergunta: str) -> tuple[bool, str]:
    """(tinha dados?, pergunta com os dados trocados por [CPF]/[nome])."""
    p = _DOCUMENTO.sub(lambda m: f"{m.group(1)} [número]", pergunta)
    p = _NUMERO_LONGO.sub("[número]", p)
    p = _NOME.sub(lambda m: f"{m.group(1)} [nome]", p)
    p = " ".join(p.split())
    return p != " ".join(pergunta.split()), p


def _normalizar(texto: str) -> str:
    sem_acento = "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                         if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^\w\s]", " ", sem_acento).split())


def responder(mensagem: str) -> str | None:
    """A resposta pronta, se a mensagem for só conversa; None se for pergunta do acervo."""
    n = _normalizar(mensagem)
    if not n or len(n.split()) > 8:
        return None
    for padrao, resposta in RESPOSTAS:
        m = re.search(padrao, n)
        if m:
            resto = [w for w in (n[:m.start()] + " " + n[m.end():]).split() if w not in SOBRAS]
            if len(resto) <= 1:
                return resposta
    return None
