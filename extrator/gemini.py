"""Chamada ao Gemini, usada para escrever as mensagens sintéticas e como modelo de comparação."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _carregar_env() -> None:
    env = RAIZ / ".env"
    if env.exists():
        for linha in env.read_text().splitlines():
            if "=" in linha and not linha.lstrip().startswith("#"):
                chave, valor = linha.split("=", 1)
                os.environ.setdefault(chave.strip(), valor.strip().strip('"'))


def gerar(conteudo: str, sistema: str | None = None, json: bool = False, temperatura: float = 0.0) -> str:
    from google import genai
    from google.genai import types

    _carregar_env()
    cliente = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=sistema, temperature=temperatura,
        response_mime_type="application/json" if json else None,
    )
    resposta = cliente.models.generate_content(
        model=os.environ.get("GEMINI_MODELO", "gemini-2.5-flash"), contents=conteudo, config=config)
    return resposta.text or ""


def cota_esgotada(erro: Exception) -> bool:
    return getattr(erro, "code", None) == 429
