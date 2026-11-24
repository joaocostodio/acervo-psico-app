"""Descobre a página IMPRESSA de cada página do PDF (a que vale para citar em ABNT).

A página 45 do PDF pode ser a página 43 do livro: capa, ficha e sumário não são
numerados. O número impresso aparece no texto da página, sozinho numa linha ou no
rodapé ("10 Conselho Federal de Psicologia"). Aqui cada número "solto" vota num
deslocamento (página do PDF − número); o deslocamento mais votado vale para a obra.

Há obras escaneadas em página dupla (duas páginas do livro em uma do PDF): nelas o
número impresso cresce de 2 em 2 (impressa = 2 × pdf − k), e a página do PDF corresponde
a "p. N–N+1".

Só marca a página se o número previsto aparece nela ou se as vizinhas confirmam a
sequência; capa e páginas antes da numeração ficam sem página impressa (None).
"""
import re
from collections import Counter

# Número "solto": sozinho na linha, ou na ponta de uma linha curta (rodapé/cabeçalho).
_LINHA = re.compile(r"^\s*(\d{1,3})\s*$|^\s*(\d{1,3})\s+\S.{0,60}$|^.{0,60}\S\s+(\d{1,3})\s*$", re.M)
_PONTA = re.compile(r"(?<![\d.,/])(\d{1,3})(?![\d.,/%º°])")
APOIO_MINIMO = 0.6  # fração das páginas que precisa confirmar o deslocamento


def _numeros(texto: str) -> set[int]:
    c = {int(next(g for g in m.groups() if g)) for m in _LINHA.finditer(texto)}
    for parte in (texto[:25], texto[-25:]):  # o extrator às vezes cola o número no texto
        c |= {int(m.group(1)) for m in _PONTA.finditer(parte)}
    c.discard(0)
    return c


def paginas_impressas(paginas: list[tuple[int, str]]) -> tuple[dict[int, int | None], dict]:
    """[(página do PDF, texto)] de UMA obra -> ({página do PDF: impressa ou None}, resumo).

    O resumo diz se a obra é de página dupla ("dupla": True) e quanto apoio o deslocamento teve.
    """
    nums = {pdf: _numeros(t) for pdf, t in paginas}
    simples, dupla = Counter(), Counter()
    for pdf, ns in nums.items():
        for n in ns:
            simples[pdf - n] += 1
            dupla[2 * pdf - n] += 1
    ks, cs = (simples.most_common(1) or [(0, 0)])[0]
    kd, cd = (dupla.most_common(1) or [(0, 0)])[0]
    eh_dupla = cd > cs * 1.5
    k, apoio = (kd, cd) if eh_dupla else (ks, cs)
    resumo = {"dupla": eh_dupla, "deslocamento": k, "apoio": round(apoio / max(1, len(paginas)), 2)}
    if apoio < APOIO_MINIMO * len(paginas):
        return {pdf: None for pdf in nums}, resumo

    prever = (lambda pdf: 2 * pdf - k) if eh_dupla else (lambda pdf: pdf - k)
    confirmada = {pdf: prever(pdf) >= 1 and prever(pdf) in ns for pdf, ns in nums.items()}
    ordem = sorted(nums)
    primeira = next((p for p in ordem if confirmada[p]), None)
    resultado: dict[int, int | None] = {}
    for i, pdf in enumerate(ordem):
        n = prever(pdf)
        if primeira is None or pdf < primeira or n < 1:
            resultado[pdf] = None
        elif confirmada[pdf]:
            resultado[pdf] = n
        else:
            # Página sem número visível (abertura de capítulo, figura): vale se alguma
            # vizinha próxima, antes e depois, confirma a sequência.
            antes = any(confirmada.get(p) for p in ordem[max(0, i - 3):i])
            depois = any(confirmada.get(p) for p in ordem[i + 1:i + 4])
            resultado[pdf] = n if antes and depois else None
    return resultado, resumo
