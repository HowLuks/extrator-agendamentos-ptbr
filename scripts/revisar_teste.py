"""Revisão manual do conjunto de teste no terminal. Salva a cada exemplo, então dá para parar e voltar.

  python scripts/revisar_teste.py

Para cada mensagem: Enter aceita o gabarito, "e" corrige um campo, "d" descarta o exemplo, "q" sai.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extrator.dados import CAMPOS, ler_jsonl, salvar_jsonl  # noqa: E402

CAMINHO = Path(__file__).resolve().parent.parent / "dados" / "teste.jsonl"


def main():
    linhas = ler_jsonl(CAMINHO)
    pendentes = [ex for ex in linhas if ex["mensagem"] and not ex.get("revisado") and not ex.get("descartado")]
    print(f"{len(pendentes)} mensagens para revisar.\n")
    for i, ex in enumerate(pendentes, 1):
        print(f"[{i}/{len(pendentes)}] {ex['id']} · {ex['negocio']['tipo']} · hoje {ex['hoje']} · autor {ex['autor']}")
        print(f"  mensagem: {ex['mensagem']}")
        for c in CAMPOS:
            print(f"  {c:12} {ex['rotulo'][c]}")
        while True:
            op = input("Enter = ok, e = editar, d = descartar, q = sair: ").strip().lower()
            if op == "q":
                return
            if op == "d":
                ex["descartado"] = True
                break
            if op == "e":
                campo = input(f"  campo ({', '.join(CAMPOS)}): ").strip()
                if campo in CAMPOS:
                    valor = input(f"  novo valor para {campo} (vazio = null): ").strip()
                    ex["rotulo"][campo] = valor or None
                continue
            if op == "":
                ex["revisado"] = True
                break
        salvar_jsonl(CAMINHO, linhas)
        print()


if __name__ == "__main__":
    main()
