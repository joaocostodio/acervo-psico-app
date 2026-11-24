"""Cliente do Ollama local: embeddings e geração de texto (inteira ou em streaming)."""
import json
from collections.abc import Iterator

import httpx

from config import config

_client = httpx.Client(base_url=config.ollama_url, timeout=600.0)

# Mantém os modelos na memória para sempre (-1): sem isso o Ollama descarrega o modelo
# depois de um tempo parado, e a 1ª pergunta seguinte paga a recarga do disco E a leitura
# das instruções da Susmi de novo (~1.000 tokens, ~1 min nesta CPU).
MANTER = -1


# num_ctx é sempre o mesmo: se mudar entre pedidos, o Ollama recarrega o modelo.
def _opcoes(temperatura: float, max_tokens: int | None = None) -> dict:
    return {"temperature": temperatura, "num_predict": max_tokens or config.max_tokens_resposta,
            "num_ctx": config.num_ctx}


def _corpo(prompt: str, stream: bool, opcoes: dict) -> dict:
    corpo = {"model": config.chat_model, "prompt": prompt, "stream": stream,
             "keep_alive": MANTER, "options": opcoes}
    if config.ia_pensar is not None:
        corpo["think"] = config.ia_pensar
    return corpo


def embed(textos: list[str], modelo: str | None = None) -> list[list[float]]:
    """Gera embeddings para uma lista de textos (modelo de config.embed_model, ou o indicado).
    Use embeddings.py: ele põe o prefixo certo de pergunta/página para cada modelo."""
    resp = _client.post(
        "/api/embed", json={"model": modelo or config.embed_model, "input": textos, "keep_alive": MANTER}
    )
    resp.raise_for_status()
    return resp.json()["embeddings"]


def _metricas(d: dict) -> dict:
    eval_count = d.get("eval_count", 0) or 0
    eval_dur = d.get("eval_duration", 1) or 1
    prompt_dur = d.get("prompt_eval_duration", 0) or 0
    return {
        "tokens": eval_count,
        "tokens_por_segundo": round(eval_count / (eval_dur / 1e9), 2),
        "tokens_lidos": d.get("prompt_eval_count", 0) or 0,
        "leitura_s": round(prompt_dur / 1e9, 1),
        "tempo_total_s": round((d.get("total_duration", 0) or 0) / 1e9, 2),
        "modelo": config.chat_model,
    }


def modelos_carregados() -> list[dict]:
    """O que está na memória do Ollama agora (para o painel do administrador)."""
    try:
        r = _client.get("/api/ps", timeout=3)
        r.raise_for_status()
        return [{"nome": m.get("name"), "tamanho_gb": round((m.get("size") or 0) / 1e9, 1)}
                for m in r.json().get("models", [])]
    except Exception:  # noqa: BLE001 — painel: Ollama fora do ar aparece como lista vazia
        return []


def gerar(prompt: str, temperatura: float = 0.2, max_tokens: int | None = None) -> dict:
    """Gera a resposta inteira de uma vez e devolve texto + métricas."""
    resp = _client.post("/api/generate", json=_corpo(prompt, False, _opcoes(temperatura, max_tokens)))
    resp.raise_for_status()
    d = resp.json()
    return {"texto": d.get("response", ""), **_metricas(d)}


def ler_antes(prefixo: str) -> None:
    """Lê um contexto sem responder (1 token), só para deixá-lo no cache do Ollama.
    Pergunta seguinte que comece com o mesmo texto pula essa leitura."""
    _client.post("/api/generate", json=_corpo(prefixo, False, {**_opcoes(0.2), "num_predict": 1})).raise_for_status()


def gerar_stream(prompt: str, temperatura: float = 0.2, max_tokens: int | None = None) -> Iterator[dict]:
    """Gera em streaming: devolve {'delta': '...'} a cada pedaço e, no fim,
    {'fim': True, 'metricas': {...}}. Se quem pediu desistir, fechar o iterador
    fecha a conexão e o Ollama para de gerar."""
    with _client.stream("POST", "/api/generate",
                        json=_corpo(prompt, True, _opcoes(temperatura, max_tokens))) as resp:
        resp.raise_for_status()
        for linha in resp.iter_lines():
            if not linha:
                continue
            d = json.loads(linha)
            if d.get("response"):
                yield {"delta": d["response"]}
            if d.get("done"):
                yield {"fim": True, "metricas": _metricas(d)}
