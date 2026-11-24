"""Configuração lida do ambiente (.env). Nenhum segredo fica no código."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # O servidor web usa um papel RESTRITO do banco (só lê o acervo e grava o histórico).
    database_url: str
    # Papel dono das tabelas: só os scripts de linha de comando (migrar, ingerir,
    # criar usuário, backup) usam. O servidor web nunca abre conexão com ele.
    database_url_admin: str | None = None

    ollama_url: str = "http://localhost:11434"
    chat_model: str = "acervo-psico"  # Gemma 4 E2B + regras e exemplos (ia/Modelfile)
    # Busca por sentido (03/11/2026: embeddinggemma, multilíngue, no lugar do nomic-embed-text;
    # os vetores antigos continuam em vetor_conteudo para voltar, se preciso).
    embed_model: str = "embeddinggemma"
    coluna_vetor: str = "vetor_conteudo_2"  # coluna de pagina com os vetores do embed_model
    top_k: int = 3                    # páginas que a IA lê para responder
    contexto_chars: int = 1500        # quanto de cada página entra no contexto da IA
    max_tokens_resposta: int = 900    # teto do tamanho da resposta (completa, em tópicos)
    num_ctx: int = 8192               # janela de contexto do modelo (tokens), por vaga da IA
    usar_mapa: bool = True            # mapa do acervo no começo de todo prompt (mapa.py)
    # Pedido de texto longo ("desenvolva um artigo", "resumo expandido"): lê mais páginas
    # e pode escrever mais. Custa mais tempo; a tela avisa.
    # A janela (num_ctx) é a mesma de sempre: trocar num_ctx entre pedidos faz o Ollama
    # recarregar o modelo. Mapa + instruções + 4 páginas × 1.500 caracteres + 1.400 tokens cabem em 8.192.
    # Ajustes da ordem da busca (10/11/2026, rag._AJUSTE): obra citada na pergunta, peso a
    # lei/norma do CFP achada pelas duas buscas e menos peso a capa/créditos/sumário.
    # False volta à ordem só pela combinação das duas buscas (RRF), como era antes.
    ajustar_busca: bool = True
    longo_k: int = 4
    longo_tokens: int = 1400
    # Modelos que "pensam" antes de responder (Qwen 3.5...): em CPU isso custa minutos.
    # False manda think=false ao Ollama; None não manda nada (modelos sem esse modo).
    ia_pensar: bool | None = None

    # Fichas das obras (gerar_fichas.py, de madrugada): um JSON por obra; o site só lê.
    fichas_dir: str = "/opt/crepop/dados/fichas"

    # Sessão: chave que assina o cookie de login (longa e aleatória, só no .env).
    secret_key: str
    sessao_horas: int = 12

    # Limites contra abuso.
    # Login: 10 falhas em 15 min bloqueiam aquele LOGIN vindo daquele IP por 15 min. Não
    # bloqueia o IP inteiro: numa sala todos saem pelo mesmo IP do Wi-Fi, e um aluno
    # chutando senhas trancaria a turma (e quem apresenta) do lado de fora.
    limite_login_falhas: int = 10
    limite_buscas_min: int = 30       # buscas por minuto, por sessão de login
    limite_perguntas_min: int = 3     # perguntas à IA por minuto, por sessão de login
    fila_ia_max: int = 6              # perguntas com a IA ou esperando por ela (todas as pessoas)
    ia_paralelo: int = 2              # respondidas ao mesmo tempo (= OLLAMA_NUM_PARALLEL na VM)
    # Vagas da IA guardadas para o administrador (seguranca.Vagas). 1 = as outras contas
    # usam uma vaga por vez e a pergunta do administrador sai na hora (bom em apresentação).
    # 0 = todas as vagas para todos (o administrador só passa na frente da fila).
    ia_vagas_reservadas_admin: int = 1


config = Config()
