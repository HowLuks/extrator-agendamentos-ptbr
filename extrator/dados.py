"""Catálogos de negócios, sorteio dos rótulos e leitura/escrita dos arquivos .jsonl.

O rótulo é sorteado primeiro e a mensagem é escrita depois a partir dele (pelo Gemini ou à mão),
então o gabarito fica correto por construção e não há dado de cliente real.
"""
import json
import os
import random
from datetime import date, timedelta
from pathlib import Path

CAMPOS = ["intencao", "servico", "profissional", "data", "hora", "periodo"]
INTENCOES = ["agendar", "remarcar", "cancelar", "consultar", "outro"]
PERIODOS = ["manha", "tarde", "noite"]
DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
         "setembro", "outubro", "novembro", "dezembro"]

NEGOCIOS = [
    {"tipo": "barbearia", "servicos": ["corte", "barba", "corte e barba", "pigmentação", "sobrancelha"],
     "profissionais": ["Rafael", "Diego", "Thiago"]},
    {"tipo": "salão de beleza", "servicos": ["corte feminino", "escova", "coloração", "hidratação", "manicure", "pedicure"],
     "profissionais": ["Juliana", "Camila", "Patrícia", "Fernanda"]},
    {"tipo": "estúdio de unhas", "servicos": ["alongamento em gel", "manutenção", "esmaltação em gel", "spa dos pés"],
     "profissionais": ["Bianca", "Larissa"]},
    {"tipo": "clínica de estética", "servicos": ["limpeza de pele", "drenagem linfática", "massagem relaxante", "depilação a laser"],
     "profissionais": ["Dra. Renata", "Aline", "Marcos"]},
    {"tipo": "pet shop", "servicos": ["banho", "tosa", "banho e tosa", "hidratação de pelo"],
     "profissionais": ["Vanessa", "Bruno"]},
    {"tipo": "consultório de psicologia", "servicos": ["sessão individual", "sessão de casal", "primeira consulta"],
     "profissionais": ["Dra. Helena", "Dr. Paulo"]},
    {"tipo": "estúdio de tatuagem", "servicos": ["orçamento", "sessão de tatuagem", "piercing"],
     "profissionais": ["Caio", "Mariana"]},
    {"tipo": "personal trainer", "servicos": ["avaliação física", "treino individual", "treino em dupla"],
     "profissionais": ["Leo", "Priscila"]},
]

# Probabilidade de cada campo aparecer na mensagem, por intenção: servico, profissional, data, hora
CHANCES = {
    "agendar": (0.85, 0.4, 0.85, 0.6),
    "remarcar": (0.5, 0.3, 0.9, 0.6),
    "cancelar": (0.5, 0.2, 0.6, 0.4),
    "consultar": (0.7, 0.3, 0.7, 0.3),
    "outro": (0.4, 0.1, 0.0, 0.0),
}
PESOS_INTENCAO = [50, 15, 12, 13, 10]
TEMAS_OUTRO = ["preço", "endereço", "formas de pagamento", "agradecimento", "estacionamento", "saudação", "elogio",
               "se aceita cartão", "tempo de duração do serviço"]


def hoje_extenso(hoje: date) -> str:
    return f"{DIAS_SEMANA[hoje.weekday()]}, {hoje.day} de {MESES[hoje.month - 1]} de {hoje.year}"


def _sortear_data(rng: random.Random, hoje: date) -> tuple[date, str]:
    """Devolve a data alvo e como a mensagem deve se referir a ela."""
    tipo = rng.choices(["hoje", "amanha", "depois", "semana", "dia", "barra"], [8, 22, 6, 34, 15, 15])[0]
    if tipo == "hoje":
        return hoje, "hoje"
    if tipo == "amanha":
        return hoje + timedelta(days=1), "amanhã"
    if tipo == "depois":
        return hoje + timedelta(days=2), "depois de amanhã"
    if tipo == "semana":
        # Dia da semana sem outra indicação = próxima ocorrência depois de hoje (1 a 7 dias)
        alvo = hoje + timedelta(days=rng.randint(1, 7))
        return alvo, DIAS_SEMANA[alvo.weekday()]
    alvo = hoje + timedelta(days=rng.randint(3, 25))  # até 25 dias: "dia N" nunca cai no dia de hoje
    return alvo, f"dia {alvo.day}" if tipo == "dia" else f"{alvo.day:02d}/{alvo.month:02d}"


def sortear_exemplo(rng: random.Random, id_: str) -> dict:
    negocio = rng.choice(NEGOCIOS)
    hoje = date(2026, 11, 1) + timedelta(days=rng.randint(0, 150))
    intencao = rng.choices(INTENCOES, PESOS_INTENCAO)[0]
    p_serv, p_prof, p_data, p_hora = CHANCES[intencao]
    rotulo = dict.fromkeys(CAMPOS)
    rotulo["intencao"] = intencao
    dica = {"data": None, "tema": rng.choice(TEMAS_OUTRO) if intencao == "outro" else None}
    if rng.random() < p_serv:
        rotulo["servico"] = rng.choice(negocio["servicos"])
    if rng.random() < p_prof:
        rotulo["profissional"] = rng.choice(negocio["profissionais"])
    if rng.random() < p_data:
        alvo, dica["data"] = _sortear_data(rng, hoje)
        rotulo["data"] = alvo.isoformat()
    if rng.random() < p_hora:
        rotulo["hora"] = f"{rng.randint(8, 19):02d}:{rng.choice(['00', '00', '30']):s}"
    elif intencao != "outro" and rng.random() < 0.4:
        rotulo["periodo"] = rng.choice(PERIODOS)
    return {"id": id_, "hoje": hoje.isoformat(), "negocio": negocio, "rotulo": rotulo, "dica": dica,
            "mensagem": None, "autor": None}


def sortear_conjunto(nome: str, n: int, semente: int) -> list[dict]:
    rng = random.Random(semente)
    return [sortear_exemplo(rng, f"{nome}-{i:04d}") for i in range(1, n + 1)]


def ler_jsonl(caminho: str | Path) -> list[dict]:
    with open(caminho, encoding="utf-8") as f:
        return [json.loads(linha) for linha in f if linha.strip()]


def salvar_jsonl(caminho: str | Path, linhas: list[dict]) -> None:
    # Grava num temporário e troca, para não corromper o arquivo se o processo cair no meio
    tmp = f"{caminho}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for linha in linhas:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    os.replace(tmp, caminho)
