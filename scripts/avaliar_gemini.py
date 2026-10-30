"""Roda o Gemini no conjunto de teste revisado e imprime a tabela de métricas.

  python scripts/avaliar_gemini.py          # só exemplos revisados
  python scripts/avaliar_gemini.py --todos  # inclui os ainda não revisados

As respostas ficam em resultados/gemini_teste.jsonl; rodar de novo só chama o que falta.
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from extrator.dados import ler_jsonl, salvar_jsonl  # noqa: E402
from extrator.gemini import cota_esgotada, gerar  # noqa: E402
from extrator.metricas import relatorio, tabela  # noqa: E402
from extrator.prompt import ler_resposta, mensagens_extracao  # noqa: E402

SAIDA = RAIZ / "resultados" / "gemini_teste.jsonl"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--todos", action="store_true")
    a = p.parse_args()
    teste = [ex for ex in ler_jsonl(RAIZ / "dados" / "teste.jsonl")
             if ex["mensagem"] and not ex.get("descartado") and (a.todos or ex.get("revisado"))]
    SAIDA.parent.mkdir(exist_ok=True)
    respostas = {r["id"]: r for r in ler_jsonl(SAIDA)} if SAIDA.exists() else {}
    for ex in teste:
        if ex["id"] in respostas:
            continue
        sistema, usuario = mensagens_extracao(ex)
        try:
            texto = gerar(usuario["content"], sistema=sistema["content"], json=True)
        except Exception as e:  # noqa: BLE001
            if cota_esgotada(e):
                print("Cota do Gemini esgotada; rode de novo amanhã para continuar.")
                break
            raise
        respostas[ex["id"]] = {"id": ex["id"], "resposta": texto}
        salvar_jsonl(SAIDA, list(respostas.values()))
    avaliados = [ex for ex in teste if ex["id"] in respostas]
    print(f"{len(avaliados)} de {len(teste)} exemplos avaliados.\n")
    rel = relatorio(avaliados, [ler_resposta(respostas[ex["id"]]["resposta"]) for ex in avaliados])
    print(tabela(rel))
    (RAIZ / "resultados" / "gemini_metricas.json").write_text(json.dumps(rel, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
