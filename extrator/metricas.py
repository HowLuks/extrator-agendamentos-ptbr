"""Métricas da extração: JSON válido, acerto por campo e acerto exato (todos os campos certos)."""
from extrator.dados import CAMPOS


def _igual(a, b) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip().casefold() == b.strip().casefold()
    return a == b


def avaliar(exemplos: list[dict], previsoes: list[dict | None]) -> dict:
    """exemplos com "rotulo"; previsoes na mesma ordem (None = resposta sem JSON válido, conta como erro)."""
    n = len(exemplos)
    if n == 0:
        return {"n": 0}
    acertos = dict.fromkeys(CAMPOS, 0)
    exatas = validas = 0
    for ex, prev in zip(exemplos, previsoes, strict=True):
        if prev is None:
            continue
        validas += 1
        certos = [c for c in CAMPOS if _igual(prev.get(c), ex["rotulo"][c])]
        for c in certos:
            acertos[c] += 1
        exatas += len(certos) == len(CAMPOS)
    return {"n": n, "json_valido": validas / n, "exata": exatas / n, **{c: acertos[c] / n for c in CAMPOS}}


def relatorio(exemplos: list[dict], previsoes: list[dict | None]) -> dict:
    """Métricas gerais e separadas por autor da mensagem (mede se o Gemini vai melhor no que ele mesmo escreveu)."""
    saida = {"geral": avaliar(exemplos, previsoes)}
    for autor in sorted({ex["autor"] for ex in exemplos if ex.get("autor")}):
        pares = [(e, p) for e, p in zip(exemplos, previsoes) if e.get("autor") == autor]
        saida[autor] = avaliar([e for e, _ in pares], [p for _, p in pares])
    return saida


def tabela(rel: dict) -> str:
    colunas = ["n", "json_valido", "exata", *CAMPOS]
    linhas = ["| grupo | " + " | ".join(colunas) + " |", "|" + "---|" * (len(colunas) + 1)]
    for grupo, m in rel.items():
        celulas = [str(m.get("n", 0))] + [f"{m[c]:.1%}" if c in m else "-" for c in colunas[1:]]
        linhas.append(f"| {grupo} | " + " | ".join(celulas) + " |")
    return "\n".join(linhas)
