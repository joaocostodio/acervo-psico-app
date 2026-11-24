"""Embeddings (vetores de sentido) da pergunta e das páginas, com o "jeito" de cada modelo.

Modelos de embedding modernos esperam um prefixo diferente para a PERGUNTA e para o
DOCUMENTO: é assim que foram treinados para busca. O nomic-embed-text do acervo foi
gravado sem prefixo (ingestão de 10/2026), então continua sem: misturar mudaria os vetores.

Trocar de modelo exige recalcular os vetores de todas as páginas (reindexar.py) numa
coluna nova e só então apontar EMBED_MODEL e COLUNA_VETOR para ela no .env.
"""
from config import config
import ollama_client

PERFIS = {
    # modelo: (prefixo da pergunta, prefixo da página)
    "nomic-embed-text": ("", ""),
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "granite-embedding:278m": ("", ""),
    "qwen3-embedding:0.6b": ("Instruct: Dada uma pergunta, encontre trechos que a respondem\nQuery: ", ""),
}
# Só estas colunas existem (nome vai direto no SQL: nunca vem do usuário).
COLUNAS = {"vetor_conteudo", "vetor_conteudo_2"}


def _perfil(modelo: str) -> tuple[str, str]:
    return PERFIS.get(modelo) or PERFIS.get(modelo.split(":")[0]) or ("", "")


def coluna() -> str:
    if config.coluna_vetor not in COLUNAS:
        raise ValueError(f"COLUNA_VETOR inválida: {config.coluna_vetor}")
    return config.coluna_vetor


def consulta(texto: str, modelo: str | None = None) -> list[float]:
    modelo = modelo or config.embed_model
    return ollama_client.embed([_perfil(modelo)[0] + texto], modelo)[0]


def documentos(textos: list[str], modelo: str | None = None) -> list[list[float]]:
    modelo = modelo or config.embed_model
    prefixo = _perfil(modelo)[1]
    return ollama_client.embed([prefixo + t for t in textos], modelo)
