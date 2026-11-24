"""Leis do Planalto (texto compilado) -> HTML limpo, sem o texto revogado, para virar PDF.

Usado em 10/11/2026 para pôr o texto integral das leis no acervo (docs/acervo-ampliado-2026-11-10.md).
Roda no PC, não na VM. Passos:
  1. python baixar_leis.py <pasta>       (baixa e converte; gera <pasta>/html/*.html)
     O Planalto às vezes recusa o urllib do Python ("Remote end closed connection"). Se
     acontecer, baixe cada endereço de LEIS com o navegador ou com
     `Invoke-WebRequest <url> -OutFile "<pasta>/html-original/<arquivo>.htm"` e rode de novo:
     o que já está em html-original/ não é baixado outra vez.
  2. Para cada HTML, gere o PDF com o Chrome (mantém o texto selecionável):
     chrome --headless=new --no-pdf-header-footer --print-to-pdf="<arquivo>.pdf" "<arquivo>.html"
  3. Copie os PDFs para /opt/crepop/dados/leis-e-normas na VM e rode ingest_all.py e migrar.py.
Lei nova: acrescente aqui, em referencias.LEIS (ABNT) e em mapa.OBRAS (nome curto, sem números).
"""
import html
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

P = "https://www.planalto.gov.br/ccivil_03/"
# arquivo, número, data por extenso, nome popular, url
LEIS = [
    ("2006 - Lei - Maria da Penha", "11.340", "7 de agosto de 2006", "Lei Maria da Penha", P + "_ato2004-2006/2006/lei/l11340.htm"),
    ("1990 - Lei - ECA", "8.069", "13 de julho de 1990", "Estatuto da Criança e do Adolescente (ECA)", P + "leis/l8069.htm"),
    ("2001 - Lei - Reforma Psiquiatrica", "10.216", "6 de abril de 2001", "Lei da Reforma Psiquiátrica (Lei Paulo Delgado)", P + "leis/leis_2001/l10216.htm"),
    ("2015 - Lei - Brasileira de Inclusao", "13.146", "6 de julho de 2015", "Lei Brasileira de Inclusão (Estatuto da Pessoa com Deficiência)", P + "_ato2015-2018/2015/lei/l13146.htm"),
    ("2003 - Lei - Estatuto da Pessoa Idosa", "10.741", "1º de outubro de 2003", "Estatuto da Pessoa Idosa", P + "leis/2003/l10.741.htm"),
    ("1993 - Lei - LOAS", "8.742", "7 de dezembro de 1993", "Lei Orgânica da Assistência Social (LOAS)", P + "leis/l8742.htm"),
    ("1990 - Lei - Organica da Saude SUS", "8.080", "19 de setembro de 1990", "Lei Orgânica da Saúde (SUS)", P + "leis/l8080.htm"),
    ("2017 - Lei - Escuta Protegida", "13.431", "4 de abril de 2017", "Lei da Escuta Protegida (escuta especializada e depoimento especial)", P + "_ato2015-2018/2017/lei/l13431.htm"),
    ("1962 - Lei - Profissao de Psicologo", "4.119", "27 de agosto de 1962", "Lei da profissão de psicólogo", P + "leis/1950-1969/l4119.htm"),
    ("1971 - Lei - Conselhos de Psicologia", "5.766", "20 de dezembro de 1971", "Lei dos Conselhos de Psicologia", P + "leis/l5766.htm"),
    ("2003 - Lei - Notificacao Compulsoria Violencia contra a Mulher", "10.778", "24 de novembro de 2003", "Lei da notificação compulsória da violência contra a mulher", P + "leis/2003/l10.778.htm"),
    ("2012 - Lei - SINASE", "12.594", "18 de janeiro de 2012", "Lei do SINASE (atendimento socioeducativo)", P + "_ato2011-2014/2012/lei/l12594.htm"),
    ("2006 - Lei - Drogas", "11.343", "23 de agosto de 2006", "Lei de Drogas (Sisnad)", P + "_ato2004-2006/2006/lei/l11343.htm"),
    ("2016 - Lei - Marco Legal da Primeira Infancia", "13.257", "8 de março de 2016", "Marco Legal da Primeira Infância", P + "_ato2015-2018/2016/lei/l13257.htm"),
    ("2010 - Lei - Estatuto da Igualdade Racial", "12.288", "20 de julho de 2010", "Estatuto da Igualdade Racial", P + "_ato2007-2010/2010/lei/l12288.htm"),
    ("2019 - Lei - Prevencao da Automutilacao e do Suicidio", "13.819", "26 de abril de 2019", "Política Nacional de Prevenção da Automutilação e do Suicídio", P + "_ato2019-2022/2019/lei/l13819.htm"),
    ("2012 - Lei - Autismo TEA", "12.764", "27 de dezembro de 2012", "Lei Berenice Piana (Política Nacional da Pessoa com Transtorno do Espectro Autista)", P + "_ato2011-2014/2012/lei/l12764.htm"),
    ("2019 - Lei - Psicologia e Servico Social na Educacao Basica", "13.935", "11 de dezembro de 2019", "Lei da Psicologia e do Serviço Social nas escolas públicas", P + "_ato2019-2022/2019/lei/l13935.htm"),
    ("2013 - Lei - Minuto Seguinte", "12.845", "1º de agosto de 2013", "Lei do Minuto Seguinte (atendimento a pessoas em situação de violência sexual)", P + "_ato2011-2014/2013/lei/l12845.htm"),
]

BLOCO = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "table", "blockquote", "center"}
VAZIOS = {"br", "img", "hr", "meta", "link", "input", "col", "area", "base", "wbr"}


class Limpa(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.linhas, self.atual = [], []
        self.prof: dict[str, int] = {}
        self.pular: list[tuple[str, int]] = []  # (tag, profundidade) onde começou o trecho riscado

    def _quebra(self):
        t = " ".join("".join(self.atual).split())
        if t:
            self.linhas.append(t)
        self.atual = []

    def handle_starttag(self, tag, attrs):
        if tag in BLOCO:
            self._quebra()
        if tag in VAZIOS:
            return
        self.prof[tag] = self.prof.get(tag, 0) + 1
        estilo = (dict(attrs).get("style") or "").replace(" ", "").lower()
        if tag in ("strike", "s", "del", "script", "style", "head") or "line-through" in estilo:
            self.pular.append((tag, self.prof[tag]))

    def handle_endtag(self, tag):
        if tag in VAZIOS:
            return
        if self.pular and self.pular[-1] == (tag, self.prof.get(tag, 0)):
            self.pular.pop()
        if self.prof.get(tag):
            self.prof[tag] -= 1
        if tag in BLOCO:
            self._quebra()

    def handle_data(self, data):
        if not self.pular:
            self.atual.append(data)


def decodificar(b: bytes) -> str:
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b[: len(b) // 2 * 2].decode("utf-16", "replace")
    try:  # o meta charset do Planalto às vezes mente: tenta UTF-8 de verdade, senão 1252
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("windows-1252", "replace")


def converter(arquivo, numero, data, nome, url, saida: Path) -> dict:
    bruto = saida / "html-original" / (arquivo + ".htm")
    if not bruto.exists():
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        bruto.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    texto = decodificar(bruto.read_bytes())
    p = Limpa()
    p.feed(texto)
    p._quebra()
    linhas = p.linhas
    # Começa no título da lei ("LEI Nº 11.340, DE 7 DE AGOSTO DE 2006"): o que vem antes é o cabeçalho do site.
    num_sem_ponto = numero.replace(".", r"\.?")
    ini = next((i for i, l in enumerate(linhas)
                if re.search(rf"^LEI\s+N[ºo°.]*\s*{num_sem_ponto}", l, re.I)), 0)
    linhas = linhas[ini:]
    # Rodapé do site
    fim = next((i for i, l in enumerate(linhas) if l.startswith("Este texto não substitui")), len(linhas))
    linhas = linhas[:fim]
    corpo = "\n".join(f"<p>{html.escape(l)}</p>" for l in linhas)
    pagina = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>{html.escape(nome)}</title>
<style>
 @page {{ size: A4; margin: 2cm 2cm 2.2cm 2cm; }}
 body {{ font-family: "Times New Roman", serif; font-size: 11.5pt; line-height: 1.38; color: #000; }}
 h1 {{ font-size: 16pt; margin: 0 0 4pt; }} .sub {{ font-size: 10pt; color: #333; margin: 0 0 14pt; border-bottom: 1px solid #999; padding-bottom: 8pt; }}
 p {{ margin: 0 0 5pt; text-align: justify; }}
</style></head><body>
<h1>{html.escape(nome)}</h1>
<p class="sub">Lei nº {numero}, de {data}. Texto compilado da Presidência da República (planalto.gov.br), consultado em 10/11/2026. Os trechos revogados (riscados no site oficial) foram omitidos. Fonte: {html.escape(url)}</p>
{corpo}
</body></html>"""
    destino = saida / "html" / (arquivo + ".html")
    destino.write_text(pagina, encoding="utf-8")
    return {"arquivo": arquivo, "linhas": len(linhas), "caracteres": sum(map(len, linhas)),
            "inicio": linhas[0][:70] if linhas else "(vazio)", "corte_inicio": ini}


if __name__ == "__main__":
    saida = Path(sys.argv[1])
    (saida / "html-original").mkdir(parents=True, exist_ok=True)
    (saida / "html").mkdir(parents=True, exist_ok=True)
    for lei in LEIS:
        try:
            r = converter(*lei, saida)
            print(f"{r['arquivo'][:48]:48} {r['linhas']:5} linhas {r['caracteres']:7} car. | {r['inicio']}")
        except Exception as e:  # noqa: BLE001
            print(f"{lei[0]}: ERRO {e}")
