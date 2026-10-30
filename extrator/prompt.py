"""Prompt de extração (o mesmo para o Gemini e para o Qwen) e leitura da resposta do modelo."""
import json
import re
import unicodedata
from datetime import date

from extrator.dados import CAMPOS, hoje_extenso

SISTEMA = """Você lê mensagens de WhatsApp que clientes mandam para um negócio e extrai o pedido de agendamento.
Responda só com um objeto JSON, sem texto antes ou depois, com estas chaves:
- "intencao": "agendar", "remarcar", "cancelar", "consultar" (pergunta se tem horário livre) ou "outro"
- "servico": o nome exato de um serviço da lista abaixo, ou null se a mensagem não citar nenhum
- "profissional": o nome exato de um profissional da lista abaixo, ou null
- "data": a data no formato AAAA-MM-DD, ou null. Resolva datas relativas a partir de hoje. Dia da semana sozinho é a próxima ocorrência depois de hoje; "dia N" é o próximo dia N depois de hoje
- "hora": horário no formato HH:MM (24 horas), ou null
- "periodo": "manha", "tarde" ou "noite" quando o cliente citar só o período, sem horário; senão null
Em "remarcar", data e hora são as do novo horário. Não invente: campo que a mensagem não traz fica null.

Hoje é {hoje}.
Negócio: {tipo}
Serviços: {servicos}
Profissionais: {profissionais}"""


def mensagens_extracao(ex: dict) -> list[dict]:
    """Conversa no formato de chat: sistema com o catálogo, usuário com a mensagem do cliente."""
    n = ex["negocio"]
    sistema = SISTEMA.format(hoje=hoje_extenso(date.fromisoformat(ex["hoje"])), tipo=n["tipo"],
                             servicos=", ".join(n["servicos"]), profissionais=", ".join(n["profissionais"]))
    return [{"role": "system", "content": sistema}, {"role": "user", "content": ex["mensagem"]}]


def resposta_esperada(rotulo: dict) -> str:
    return json.dumps({k: rotulo[k] for k in CAMPOS}, ensure_ascii=False)


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def ler_resposta(texto: str) -> dict | None:
    """Extrai o JSON da resposta do modelo e normaliza os campos. None se não houver JSON válido."""
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio < 0 or fim < inicio:
        return None
    try:
        bruto = json.loads(texto[inicio:fim + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(bruto, dict):
        return None
    saida = {}
    for campo in CAMPOS:
        v = bruto.get(campo)
        v = v.strip() if isinstance(v, str) else v
        if v in ("", "null", "None") or not isinstance(v, str):
            v = None
        if v and campo in ("intencao", "periodo"):
            v = _sem_acento(v.lower())
        if v and campo == "hora":
            m = re.fullmatch(r"(\d{1,2})(?::|h)?(\d{2})?", v)
            v = f"{int(m.group(1)):02d}:{m.group(2) or '00'}" if m else v
        saida[campo] = v
    return saida
