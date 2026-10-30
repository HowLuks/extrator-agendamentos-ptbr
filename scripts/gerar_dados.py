"""Gera o dataset sintético em dados/<conjunto>.jsonl.

  python scripts/gerar_dados.py rotulos --conjunto treino --n 600 --semente 1
  python scripts/gerar_dados.py gemini --conjunto treino          # escreve as mensagens que faltam
  python scripts/gerar_dados.py pendentes --conjunto treino --n 50 # lista rótulos sem mensagem
  python scripts/gerar_dados.py importar --conjunto treino arquivo.jsonl --autor claude

O comando gemini retoma de onde parou e para sozinho quando a cota diária acaba.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extrator.dados import hoje_extenso, ler_jsonl, salvar_jsonl, sortear_conjunto  # noqa: E402
from extrator.gemini import cota_esgotada, gerar  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "dados"

SISTEMA_ESCRITOR = """Você escreve mensagens realistas de WhatsApp que clientes brasileiros mandam para pequenos negócios.
Escreva como gente de verdade escreve: informal, às vezes com abreviação (vc, pq, blz), sem acento, com erro de digitação leve,
sem pontuação, com emoji ou com saudação antes. Varie o tamanho e o jeito. Responda só com o texto da mensagem."""


def _instrucao(ex: dict) -> str:
    from datetime import date
    r, d = ex["rotulo"], ex["dica"]
    partes = [f"Negócio: {ex['negocio']['tipo']}. Hoje é {hoje_extenso(date.fromisoformat(ex['hoje']))}."]
    objetivo = {
        "agendar": "O cliente quer marcar um horário.",
        "remarcar": "O cliente já tem um horário marcado e quer mudar para outro. Cite só o NOVO dia/horário, NÃO cite o antigo.",
        "cancelar": "O cliente quer cancelar um horário que já tinha marcado.",
        "consultar": "O cliente só quer saber se tem horário livre, sem confirmar que vai marcar.",
        "outro": f"O cliente não quer marcar nem mexer em horário; ele fala sobre: {d['tema']}.",
    }[r["intencao"]]
    partes.append(objetivo)
    partes.append(f"Cite o serviço \"{r['servico']}\"." if r["servico"] else "NÃO mencione nenhum serviço específico.")
    partes.append(f"Cite o profissional \"{r['profissional']}\"." if r["profissional"] else "NÃO mencione nenhum profissional.")
    partes.append(f"Para a data, use a expressão \"{d['data']}\" (pode variar a escrita, mas mantendo o sentido)."
                  if r["data"] else "NÃO mencione data nem dia da semana.")
    if r["hora"]:
        partes.append(f"Cite o horário {r['hora']} de forma que não fique ambíguo (ex.: '15h', '3 da tarde', '9h30').")
    elif r["periodo"]:
        partes.append(f"Cite só o período do dia ({r['periodo'].replace('manha', 'manhã')}), sem horário exato.")
    else:
        partes.append("NÃO mencione horário nem período do dia.")
    return "\n".join(partes)


def cmd_rotulos(a):
    destino = PASTA / f"{a.conjunto}.jsonl"
    if destino.exists() and not a.forcar:
        sys.exit(f"{destino} já existe; use --forcar para sobrescrever (apaga as mensagens escritas).")
    salvar_jsonl(destino, sortear_conjunto(a.conjunto, a.n, a.semente))
    print(f"{a.n} rótulos em {destino}")


def cmd_gemini(a):
    caminho = PASTA / f"{a.conjunto}.jsonl"
    linhas = ler_jsonl(caminho)
    feitas = 0
    for ex in linhas:
        if ex["mensagem"] or (a.limite and feitas >= a.limite):
            continue
        try:
            texto = gerar(_instrucao(ex), sistema=SISTEMA_ESCRITOR, temperatura=1.0).strip()
        except Exception as e:  # noqa: BLE001
            if cota_esgotada(e):
                print("Cota do Gemini esgotada; rode de novo amanhã para continuar.")
                break
            raise
        ex["mensagem"], ex["autor"] = texto, "gemini"
        salvar_jsonl(caminho, linhas)
        feitas += 1
        print(f"{ex['id']}: {texto}")
    print(f"{feitas} mensagens novas; faltam {sum(not ex['mensagem'] for ex in linhas)}.")


def cmd_pendentes(a):
    for ex in [e for e in ler_jsonl(PASTA / f"{a.conjunto}.jsonl") if not e["mensagem"]][: a.n]:
        print(json.dumps({"id": ex["id"], "negocio": ex["negocio"]["tipo"], **ex["rotulo"], "dica": ex["dica"]},
                         ensure_ascii=False))


def cmd_importar(a):
    caminho = PASTA / f"{a.conjunto}.jsonl"
    linhas = ler_jsonl(caminho)
    por_id = {ex["id"]: ex for ex in linhas}
    novas = 0
    for item in ler_jsonl(a.arquivo):
        ex = por_id.get(item["id"])
        if ex is None or ex["mensagem"]:
            print(f"ignorado: {item['id']} (não existe ou já tem mensagem)")
            continue
        ex["mensagem"], ex["autor"] = item["mensagem"].strip(), a.autor
        novas += 1
    salvar_jsonl(caminho, linhas)
    print(f"{novas} mensagens importadas.")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(required=True)
    r = sub.add_parser("rotulos")
    r.add_argument("--conjunto", required=True)
    r.add_argument("--n", type=int, required=True)
    r.add_argument("--semente", type=int, required=True)
    r.add_argument("--forcar", action="store_true")
    r.set_defaults(f=cmd_rotulos)
    g = sub.add_parser("gemini")
    g.add_argument("--conjunto", required=True)
    g.add_argument("--limite", type=int, default=0)
    g.set_defaults(f=cmd_gemini)
    pe = sub.add_parser("pendentes")
    pe.add_argument("--conjunto", required=True)
    pe.add_argument("--n", type=int, default=50)
    pe.set_defaults(f=cmd_pendentes)
    i = sub.add_parser("importar")
    i.add_argument("--conjunto", required=True)
    i.add_argument("arquivo")
    i.add_argument("--autor", required=True)
    i.set_defaults(f=cmd_importar)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
